"""
Unit tests for cryptopilot.execution.matcher.OrderMatcher.
Validates realistic execution mechanics: quadratic slippage, bid/ask spreads,
limit order candle matching, maker/taker fees, and strict intrabar stop-loss priority.
"""

from datetime import UTC, datetime

import pytest

from cryptopilot.data.models import Candle, Ticker
from cryptopilot.execution.matcher import OrderMatcher
from cryptopilot.execution.models import (
    BracketOrder,
    OrderSide,
    OrderStatus,
    OrderType,
    VirtualOrder,
)


@pytest.fixture
def matcher() -> OrderMatcher:
    return OrderMatcher(
        taker_fee_rate=0.0010,  # 0.10%
        maker_fee_rate=0.0005,  # 0.05%
        base_slippage=0.0002,  # 0.02%
        impact_factor=0.05,
        reference_volume=100000.0,
        max_slippage=0.02,  # 2.0%
        default_half_spread_pct=0.00025,  # 0.025%
    )


def test_matcher_slippage_calculation(matcher: OrderMatcher) -> None:
    """Verifies quadratic slippage model and cap."""
    # Near zero notional
    rate_low = matcher.calculate_slippage_rate(notional=10.0)
    assert pytest.approx(rate_low, abs=1e-5) == 0.0002

    # Medium notional ($50k on $100k reference volume -> (0.5)^2 * 0.05 = 0.0125 + 0.0002 = 0.0127)
    rate_med = matcher.calculate_slippage_rate(notional=50000.0)
    assert pytest.approx(rate_med, abs=1e-4) == 0.0127

    # Huge notional capped at max_slippage (2%)
    rate_high = matcher.calculate_slippage_rate(notional=1000000.0)
    assert rate_high == 0.02

    # Zero reference volume fallback
    matcher_zero_ref = OrderMatcher(reference_volume=0.0, base_slippage=0.0005)
    assert matcher_zero_ref.calculate_slippage_rate(100.0) == 0.0005


def test_match_market_order_with_ticker(matcher: OrderMatcher) -> None:
    """Tests market BUY and SELL fills using explicit Ticker bid/ask."""
    ticker = Ticker(
        symbol="BTC/USDT",
        bid=50000.0,
        ask=50010.0,
        last=50005.0,
        volume_24h=1500.0,
        timestamp=datetime.now(UTC),
    )

    # BUY Order
    buy_order = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.001,
        remaining_quantity=0.001,
        status=OrderStatus.SUBMITTED,
    )
    buy_fill = matcher.match_market_order(buy_order, reference_price=50005.0, ticker=ticker)

    assert buy_order.status == OrderStatus.FILLED
    assert buy_order.filled_quantity == 0.001
    assert buy_order.remaining_quantity == 0.0
    # Fill price should be >= ask
    assert buy_fill.price >= ticker.ask
    assert buy_fill.fee > 0.0
    assert buy_fill.fee_rate == 0.0010

    # SELL Order
    sell_order = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.001,
        remaining_quantity=0.001,
        status=OrderStatus.SUBMITTED,
    )
    sell_fill = matcher.match_market_order(sell_order, reference_price=50005.0, ticker=ticker)

    assert sell_order.status == OrderStatus.FILLED
    # Fill price should be <= bid
    assert sell_fill.price <= ticker.bid
    assert sell_fill.fee > 0.0


def test_match_market_order_without_ticker(matcher: OrderMatcher) -> None:
    """Tests market order fallback to default half-spread when ticker is None."""
    order = VirtualOrder(
        account_id="small_account_01",
        symbol="ETH/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1,
        remaining_quantity=0.1,
        status=OrderStatus.PENDING,
    )
    ref_price = 3000.0
    fill = matcher.match_market_order(order, reference_price=ref_price, ticker=None)

    assert order.status == OrderStatus.FILLED
    # Half spread + slippage should make fill price > ref_price
    assert fill.price > ref_price
    assert fill.notional == pytest.approx(fill.price * 0.1, abs=1e-4)


def test_match_market_order_invalid_inputs(matcher: OrderMatcher) -> None:
    """Verifies that invalid order states or prices raise ValueError."""
    order = VirtualOrder(
        account_id="small_account_01",
        symbol="SOL/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=1.0,
        remaining_quantity=1.0,
        status=OrderStatus.FILLED,  # Invalid status
    )
    with pytest.raises(ValueError, match="Cannot match order in status FILLED"):
        matcher.match_market_order(order, reference_price=150.0)

    order.status = OrderStatus.SUBMITTED
    with pytest.raises(ValueError, match="Invalid reference price"):
        matcher.match_market_order(order, reference_price=-10.0)


def test_match_limit_order_buy(matcher: OrderMatcher) -> None:
    """Tests BUY Limit order execution against candle extremes."""
    candle = Candle(
        timestamp=datetime.now(UTC),
        symbol="BTC/USDT",
        timeframe="1h",
        open=50200.0,
        high=50500.0,
        low=49800.0,
        close=50100.0,
        volume=120.0,
    )

    # 1. Unfilled: limit price below candle low
    unfilled = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.01,
        price=49500.0,  # Below low of 49800
        remaining_quantity=0.01,
        status=OrderStatus.SUBMITTED,
    )
    res_none = matcher.match_limit_order(unfilled, candle)
    assert res_none is None
    assert unfilled.status == OrderStatus.SUBMITTED

    # 2. Normal fill: limit price within candle range
    filled = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.01,
        price=50000.0,  # Above low of 49800, below open of 50200
        remaining_quantity=0.01,
        status=OrderStatus.SUBMITTED,
    )
    fill = matcher.match_limit_order(filled, candle)
    assert fill is not None
    assert filled.status == OrderStatus.FILLED
    assert fill.price == 50000.0
    assert fill.fee_rate == 0.0005  # Maker fee
    assert fill.slippage_cost == 0.0

    # 3. Gap down favorable fill: candle open is below limit price
    gap_order = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.01,
        price=50300.0,  # Higher than candle open (50200)
        remaining_quantity=0.01,
        status=OrderStatus.SUBMITTED,
    )
    gap_fill = matcher.match_limit_order(gap_order, candle)
    assert gap_fill is not None
    assert gap_fill.price == 50200.0  # Filled favorably at open


def test_match_limit_order_sell(matcher: OrderMatcher) -> None:
    """Tests SELL Limit order execution against candle extremes."""
    candle = Candle(
        timestamp=datetime.now(UTC),
        symbol="ETH/USDT",
        timeframe="1h",
        open=3000.0,
        high=3200.0,
        low=2950.0,
        close=3150.0,
        volume=500.0,
    )

    # 1. Unfilled: limit price above candle high
    unfilled = VirtualOrder(
        account_id="small_account_01",
        symbol="ETH/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=0.5,
        price=3300.0,
        remaining_quantity=0.5,
        status=OrderStatus.SUBMITTED,
    )
    assert matcher.match_limit_order(unfilled, candle) is None

    # 2. Normal fill: limit price within candle range
    filled = VirtualOrder(
        account_id="small_account_01",
        symbol="ETH/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=0.5,
        price=3100.0,
        remaining_quantity=0.5,
        status=OrderStatus.SUBMITTED,
    )
    fill = matcher.match_limit_order(filled, candle)
    assert fill is not None
    assert fill.price == 3100.0
    assert filled.status == OrderStatus.FILLED

    # 3. Gap up favorable fill: candle open is above limit price
    gap_order = VirtualOrder(
        account_id="small_account_01",
        symbol="ETH/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=0.5,
        price=2980.0,  # Lower than candle open (3000)
        remaining_quantity=0.5,
        status=OrderStatus.SUBMITTED,
    )
    gap_fill = matcher.match_limit_order(gap_order, candle)
    assert gap_fill is not None
    assert gap_fill.price == 3000.0  # Filled favorably at open


def test_match_limit_order_invalid_states(matcher: OrderMatcher) -> None:
    """Verifies that invalid order states or prices return None."""
    candle = Candle(
        timestamp=datetime.now(UTC),
        symbol="BTC/USDT",
        timeframe="1h",
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
        volume=100.0,
    )

    order_no_price = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.01,
        remaining_quantity=0.01,
        price=None,
        status=OrderStatus.SUBMITTED,
    )
    assert matcher.match_limit_order(order_no_price, candle) is None

    order_filled = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.01,
        remaining_quantity=0.01,
        price=50000.0,
        status=OrderStatus.FILLED,
    )
    assert matcher.match_limit_order(order_filled, candle) is None


def test_bracket_triggers_inactive_or_no_hit(matcher: OrderMatcher) -> None:
    """Verifies no triggers fired when bracket is inactive or prices are within bounds."""
    entry = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        remaining_quantity=0.0,
        status=OrderStatus.FILLED,
    )
    sl = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.STOP_LOSS,
        quantity=0.01,
        stop_price=49000.0,
        remaining_quantity=0.01,
        status=OrderStatus.SUBMITTED,
    )
    tp = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.TAKE_PROFIT,
        quantity=0.01,
        stop_price=53000.0,
        remaining_quantity=0.01,
        status=OrderStatus.SUBMITTED,
    )

    bracket = BracketOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        entry_order=entry,
        stop_loss_order=sl,
        take_profit_order=tp,
        is_active=False,
    )

    candle = Candle(
        timestamp=datetime.now(UTC),
        symbol="BTC/USDT",
        timeframe="1h",
        open=50000.0,
        high=51000.0,
        low=49500.0,
        close=50500.0,
        volume=100.0,
    )

    # Inactive bracket
    reason, fill = matcher.evaluate_bracket_triggers(bracket, candle)
    assert reason is None and fill is None

    # Active bracket, prices safely inside (low 49500 > SL 49000, high 51000 < TP 53000)
    bracket.is_active = True
    reason, fill = matcher.evaluate_bracket_triggers(bracket, candle)
    assert reason is None and fill is None


def test_bracket_triggers_stop_loss(matcher: OrderMatcher) -> None:
    """Tests Stop-Loss execution when candle low penetrates stop price."""
    entry = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        remaining_quantity=0.0,
        status=OrderStatus.FILLED,
    )
    sl = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.STOP_LOSS,
        quantity=0.01,
        stop_price=49000.0,
        remaining_quantity=0.01,
        status=OrderStatus.SUBMITTED,
    )
    tp = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.TAKE_PROFIT,
        quantity=0.01,
        stop_price=53000.0,
        remaining_quantity=0.01,
        status=OrderStatus.SUBMITTED,
    )

    bracket = BracketOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        entry_order=entry,
        stop_loss_order=sl,
        take_profit_order=tp,
        is_active=True,
    )

    # Candle dips to 48500 (below SL 49000)
    candle = Candle(
        timestamp=datetime.now(UTC),
        symbol="BTC/USDT",
        timeframe="1h",
        open=50000.0,
        high=50200.0,
        low=48500.0,
        close=48800.0,
        volume=100.0,
    )

    reason, fill = matcher.evaluate_bracket_triggers(bracket, candle)
    assert reason == "STOP_LOSS"
    assert fill is not None
    assert not bracket.is_active
    assert bracket.exit_reason == "STOP_LOSS"
    assert sl.status == OrderStatus.FILLED
    assert tp.status == OrderStatus.CANCELED


def test_bracket_triggers_take_profit(matcher: OrderMatcher) -> None:
    """Tests Take-Profit execution when candle high touches target price."""
    entry = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        remaining_quantity=0.0,
        status=OrderStatus.FILLED,
    )
    sl = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.STOP_LOSS,
        quantity=0.01,
        stop_price=49000.0,
        remaining_quantity=0.01,
        status=OrderStatus.SUBMITTED,
    )
    tp = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.TAKE_PROFIT,
        quantity=0.01,
        stop_price=53000.0,
        remaining_quantity=0.01,
        status=OrderStatus.SUBMITTED,
    )

    bracket = BracketOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        entry_order=entry,
        stop_loss_order=sl,
        take_profit_order=tp,
        is_active=True,
    )

    # Candle rallies to 53500 (above TP 53000) without breaching SL (low 49500)
    candle = Candle(
        timestamp=datetime.now(UTC),
        symbol="BTC/USDT",
        timeframe="1h",
        open=51000.0,
        high=53500.0,
        low=50500.0,
        close=53200.0,
        volume=100.0,
    )

    reason, fill = matcher.evaluate_bracket_triggers(bracket, candle)
    assert reason == "TAKE_PROFIT"
    assert fill is not None
    assert not bracket.is_active
    assert bracket.exit_reason == "TAKE_PROFIT"
    assert tp.status == OrderStatus.FILLED
    assert sl.status == OrderStatus.CANCELED


def test_bracket_triggers_strict_stop_loss_priority_on_dual_touch(
    matcher: OrderMatcher,
) -> None:
    """
    CRITICAL RISK INVARIANT TEST:
    On extreme volatility candles where BOTH Stop-Loss and Take-Profit are breached,
    Stop-Loss MUST execute first to strictly guard against optimistic backtest bias!
    """
    entry = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        remaining_quantity=0.0,
        status=OrderStatus.FILLED,
    )
    sl = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.STOP_LOSS,
        quantity=0.01,
        stop_price=49000.0,
        remaining_quantity=0.01,
        status=OrderStatus.SUBMITTED,
    )
    tp = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.TAKE_PROFIT,
        quantity=0.01,
        stop_price=53000.0,
        remaining_quantity=0.01,
        status=OrderStatus.SUBMITTED,
    )

    bracket = BracketOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        entry_order=entry,
        stop_loss_order=sl,
        take_profit_order=tp,
        is_active=True,
    )

    # Dual-touch candle: low 48000 (breaches SL 49000) AND high 54000 (breaches TP 53000)
    dual_touch_candle = Candle(
        timestamp=datetime.now(UTC),
        symbol="BTC/USDT",
        timeframe="1h",
        open=50000.0,
        high=54000.0,
        low=48000.0,
        close=51000.0,
        volume=500.0,
    )

    reason, fill = matcher.evaluate_bracket_triggers(bracket, dual_touch_candle)
    assert reason == "STOP_LOSS", "Stop-loss MUST have priority over take-profit on dual-touch!"
    assert fill is not None
    assert bracket.exit_reason == "STOP_LOSS"
    assert sl.status == OrderStatus.FILLED
    assert tp.status == OrderStatus.CANCELED
