"""
Unit tests for cryptopilot.execution.broker.PaperBroker.
Validates simulated exchange broker mechanics, account isolation ($30 micro-capital vs $10,000 research),
market and limit order execution, bracket lifecycle, order cancellation, and complete audit logging.
"""

from datetime import UTC, datetime

import pytest

from cryptopilot.data.models import Candle, Ticker
from cryptopilot.execution.broker import PaperBroker
from cryptopilot.execution.models import (
    OrderSide,
    OrderStatus,
    OrderType,
    VirtualOrder,
)
from cryptopilot.risk.models import SizedOrderProposal
from cryptopilot.strategies.base import SignalType


@pytest.fixture
def broker() -> PaperBroker:
    return PaperBroker(
        small_account_capital=30.0,
        small_account_contribution=10.0,
        research_capital=10000.0,
    )


def test_broker_account_isolation(broker: PaperBroker) -> None:
    """Verifies complete ledger isolation between small and research accounts."""
    small_pm = broker.get_portfolio("small_account_01")
    research_pm = broker.get_portfolio("research_lab_01")

    assert small_pm.cash == 30.0
    assert research_pm.cash == 10000.0

    # Raising KeyError on unknown account
    with pytest.raises(KeyError, match="Account 'invalid_id' does not exist"):
        broker.get_portfolio("invalid_id")


def test_broker_market_buy_and_sell(broker: PaperBroker) -> None:
    """Tests submitting MARKET BUY followed by MARKET SELL."""
    small_pm = broker.get_portfolio("small_account_01")

    # 1. Market BUY 0.0002 BTC @ ~$50,000 (~$10.00)
    buy_order = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.0002,
        remaining_quantity=0.0002,
    )

    ticker = Ticker(
        symbol="BTC/USDT",
        bid=50000.0,
        ask=50010.0,
        last=50005.0,
        volume_24h=1000.0,
        timestamp=datetime.now(UTC),
    )

    broker.submit_order(buy_order, reference_price=50005.0, ticker=ticker)

    assert buy_order.status == OrderStatus.FILLED
    assert "BTC/USDT" in small_pm.positions
    pos = small_pm.positions["BTC/USDT"]
    assert pos.quantity == 0.0002
    assert small_pm.cash < 30.0  # Deducted notional + fee

    # Research lab should be completely unaffected!
    research_pm = broker.get_portfolio("research_lab_01")
    assert research_pm.cash == 10000.0
    assert len(research_pm.positions) == 0

    # 2. Market SELL to close position
    sell_order = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.0002,
        remaining_quantity=0.0002,
    )
    ticker_higher = Ticker(
        symbol="BTC/USDT",
        bid=52000.0,
        ask=52010.0,
        last=52005.0,
        volume_24h=1200.0,
        timestamp=datetime.now(UTC),
    )
    broker.submit_order(sell_order, reference_price=52005.0, ticker=ticker_higher)

    assert sell_order.status == OrderStatus.FILLED
    assert "BTC/USDT" not in small_pm.positions
    # Profit should have been realized
    assert small_pm.cash > 30.0


def test_broker_submit_bracket_order(broker: PaperBroker) -> None:
    """Tests creating an active bracket order from SizedOrderProposal."""
    proposal = SizedOrderProposal(
        symbol="ETH/USDT",
        action=SignalType.BUY,
        quantity=0.005,
        notional_value=15.0,
        entry_price=3000.0,
        stop_loss_price=2900.0,
        take_profit_price=3200.0,
        risk_budget_dollars=0.50,
        risk_budget_pct=0.016,
        allocation_pct=0.50,
        estimated_fees=0.03,
        rationale="Unit test proposal",
    )

    bracket = broker.submit_bracket(proposal, account_id="small_account_01", reference_price=3000.0)

    assert bracket.is_active is True
    assert bracket.entry_order.status == OrderStatus.FILLED
    assert bracket.stop_loss_order is not None
    assert bracket.stop_loss_order.status == OrderStatus.SUBMITTED
    assert bracket.take_profit_order is not None
    assert bracket.take_profit_order.status == OrderStatus.SUBMITTED

    # Check broker active brackets list with symbol filter
    active_brackets = broker.get_active_brackets(account_id="small_account_01", symbol="ETH/USDT")
    assert len(active_brackets) == 1
    assert active_brackets[0].bracket_id == bracket.bracket_id
    assert len(broker.get_active_brackets(account_id="small_account_01", symbol="BTC/USDT")) == 0


def test_broker_process_candle_bracket_execution(broker: PaperBroker) -> None:
    """Tests bracket stop-loss and take-profit triggering via candle processing."""
    proposal = SizedOrderProposal(
        symbol="SOL/USDT",
        action=SignalType.BUY,
        quantity=0.1,
        notional_value=15.0,
        entry_price=150.0,
        stop_loss_price=140.0,
        take_profit_price=170.0,
        risk_budget_dollars=1.0,
        risk_budget_pct=0.03,
        allocation_pct=0.50,
        estimated_fees=0.03,
        rationale="Unit test bracket execution proposal",
    )

    bracket = broker.submit_bracket(proposal, account_id="small_account_01", reference_price=150.0)
    small_pm = broker.get_portfolio("small_account_01")
    assert "SOL/USDT" in small_pm.positions

    # Candle that triggers Take Profit (high hits 175.0)
    tp_candle = Candle(
        timestamp=datetime.now(UTC),
        symbol="SOL/USDT",
        timeframe="1h",
        open=155.0,
        high=175.0,
        low=152.0,
        close=172.0,
        volume=5000.0,
    )

    fills = broker.process_candle(tp_candle)
    assert len(fills) == 1
    assert fills[0].price == pytest.approx(170.0, rel=0.01)
    # Position closed
    assert "SOL/USDT" not in small_pm.positions
    # Active brackets should now be empty
    assert len(broker.get_active_brackets("small_account_01")) == 0
    assert not bracket.is_active
    assert bracket.exit_reason == "TAKE_PROFIT"


def test_broker_process_candle_limit_orders(broker: PaperBroker) -> None:
    """Tests limit BUY and SELL order matching and portfolio updates via candle updates."""
    limit_buy = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.0001,
        price=49000.0,
        remaining_quantity=0.0001,
    )
    broker.submit_order(limit_buy, reference_price=50000.0)

    # Verify order is submitted and open
    assert limit_buy.status == OrderStatus.SUBMITTED
    open_orders = broker.get_open_orders(account_id="small_account_01", symbol="BTC/USDT")
    assert len(open_orders) == 1

    # Candle that doesn't reach limit price
    candle_no_fill = Candle(
        timestamp=datetime.now(UTC),
        symbol="BTC/USDT",
        timeframe="1h",
        open=50000.0,
        high=51000.0,
        low=49500.0,
        close=50200.0,
        volume=100.0,
    )
    fills = broker.process_candle(candle_no_fill)
    assert len(fills) == 0
    assert limit_buy.status == OrderStatus.SUBMITTED

    # Candle that dips to 48500 (triggers BUY limit at 49000)
    candle_fill = Candle(
        timestamp=datetime.now(UTC),
        symbol="BTC/USDT",
        timeframe="1h",
        open=50000.0,
        high=50100.0,
        low=48500.0,
        close=49200.0,
        volume=100.0,
    )
    fills2 = broker.process_candle(candle_fill)
    assert len(fills2) == 1
    assert limit_buy.status == OrderStatus.FILLED

    small_pm = broker.get_portfolio("small_account_01")
    assert "BTC/USDT" in small_pm.positions

    # Submit SELL limit to exit
    limit_sell = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=0.0001,
        price=52000.0,
        remaining_quantity=0.0001,
    )
    broker.submit_order(limit_sell, reference_price=49200.0)

    # Candle that rallies to 53000 (triggers SELL limit at 52000)
    candle_rally = Candle(
        timestamp=datetime.now(UTC),
        symbol="BTC/USDT",
        timeframe="1h",
        open=50000.0,
        high=53000.0,
        low=49800.0,
        close=52500.0,
        volume=200.0,
    )
    fills3 = broker.process_candle(candle_rally)
    assert len(fills3) == 1
    assert limit_sell.status == OrderStatus.FILLED
    assert "BTC/USDT" not in small_pm.positions


def test_broker_order_cancellation(broker: PaperBroker) -> None:
    """Tests single and batch order cancellation."""
    order1 = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.001,
        price=40000.0,
        remaining_quantity=0.001,
    )
    order2 = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.001,
        price=41000.0,
        remaining_quantity=0.001,
    )
    broker.submit_order(order1, reference_price=50000.0)
    broker.submit_order(order2, reference_price=50000.0)

    # Single cancellation
    canceled = broker.cancel_order(order1.order_id, reason="User cancelled")
    assert canceled.status == OrderStatus.CANCELED
    assert canceled.rejection_reason == "User cancelled"

    # Cannot cancel already cancelled
    with pytest.raises(ValueError, match="Cannot cancel order in status 'CANCELED'"):
        broker.cancel_order(order1.order_id)

    # Cannot cancel unknown order
    with pytest.raises(KeyError, match="Order 'unknown_id' not found"):
        broker.cancel_order("unknown_id")

    # Batch cancel remaining
    canceled_count = broker.cancel_all_orders("small_account_01", symbol="BTC/USDT")
    assert canceled_count == 1
    assert order2.status == OrderStatus.CANCELED


def test_broker_audit_trail_and_retrieval(broker: PaperBroker) -> None:
    """Tests that all broker actions create immutable audit log entries."""
    order = VirtualOrder(
        account_id="small_account_01",
        symbol="SOL/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1,
        remaining_quantity=0.1,
    )
    broker.submit_order(order, reference_price=150.0)

    # Audit events should include ORDER_SUBMITTED and ORDER_FILLED
    logs = broker.get_audit_log(account_id="small_account_01")
    assert len(logs) >= 2
    event_types = [e.event_type for e in logs]
    assert "ORDER_SUBMITTED" in event_types
    assert "ORDER_FILLED" in event_types

    # Order retrieval
    fetched = broker.get_order(order.order_id)
    assert fetched is not None
    assert fetched.order_id == order.order_id

    # Unknown order returns None
    assert broker.get_order("non_existent") is None
