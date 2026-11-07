"""
Unit tests for cryptopilot.database.models.
Validates model definitions, primary keys, defaults, UTC helpers, and JSON mappings.
"""

from datetime import UTC, datetime

from cryptopilot.database.models import (
    AgentDecisionModel,
    DepositModel,
    ExchangeModel,
    MarketCandleModel,
    MarketSnapshotModel,
    OrderModel,
    PortfolioModel,
    PositionModel,
    RiskEventModel,
    TradeModel,
    TradingPairModel,
    generate_uuid,
    utc_now,
)


def test_helpers() -> None:
    """Verifies uuid and utc helper functions."""
    u1 = generate_uuid()
    u2 = generate_uuid()
    assert len(u1) == 36
    assert u1 != u2

    now = utc_now()
    assert now.tzinfo == UTC


def test_exchange_and_trading_pair_models() -> None:
    """Tests ExchangeModel and TradingPairModel instantiation and defaults."""
    ex = ExchangeModel(
        id="binance",
        name="Binance Exchange",
        is_active=True,
        rate_limit_ms=50,
    )
    assert ex.id == "binance"
    assert ex.name == "Binance Exchange"
    assert ex.is_active is True
    assert ex.rate_limit_ms == 50

    pair = TradingPairModel(
        exchange_id="binance",
        symbol="BTC/USDT",
        base_asset="BTC",
        quote_asset="USDT",
        price_precision=2,
        quantity_precision=4,
        min_quantity=0.0001,
        min_notional=5.0,
        is_active=True,
    )
    assert pair.symbol == "BTC/USDT"
    assert pair.min_notional == 5.0


def test_market_candle_model() -> None:
    """Tests MarketCandleModel fields and types."""
    now = datetime.now(UTC)
    candle = MarketCandleModel(
        symbol="ETH/USDT",
        timeframe="1h",
        open_time=now,
        close_time=now,
        open=3000.0,
        high=3050.0,
        low=2980.0,
        close=3020.0,
        volume=150.0,
        is_closed=True,
    )
    assert candle.symbol == "ETH/USDT"
    assert candle.timeframe == "1h"
    assert candle.close == 3020.0
    assert candle.is_closed is True


def test_market_snapshot_model() -> None:
    """Tests MarketSnapshotModel creation."""
    now = datetime.now(UTC)
    snap = MarketSnapshotModel(
        symbol="SOL/USDT",
        timestamp=now,
        bid_price=150.0,
        ask_price=150.05,
        spread=0.05,
        mid_price=150.025,
    )
    assert snap.symbol == "SOL/USDT"
    assert snap.spread == 0.05


def test_portfolio_and_deposit_models() -> None:
    """Tests PortfolioModel and DepositModel."""
    port = PortfolioModel(
        id="small_account_01",
        account_type="small_account",
        currency="USDT",
        initial_balance=30.0,
        current_cash=30.0,
        invested_capital=0.0,
        realized_pnl=0.0,
        total_deposits=0.0,
        total_fees_paid=0.0,
        is_trading_halted=False,
    )
    assert port.id == "small_account_01"
    assert port.current_cash == 30.0
    assert port.is_trading_halted is False

    dep = DepositModel(
        portfolio_id="small_account_01",
        amount=10.0,
        currency="USDT",
        note="Monthly contribution",
    )
    assert dep.portfolio_id == "small_account_01"
    assert dep.amount == 10.0


def test_position_and_order_models() -> None:
    """Tests PositionModel and OrderModel."""
    pos = PositionModel(
        id="pos-001",
        portfolio_id="small_account_01",
        symbol="BTC/USDT",
        side="LONG",
        status="OPEN",
        quantity=0.0002,
        entry_price=50000.0,
        current_price=50500.0,
        stop_loss_price=49000.0,
        take_profit_price=52000.0,
        unrealized_pnl=0.10,
    )
    assert pos.status == "OPEN"
    assert pos.quantity == 0.0002

    ord_model = OrderModel(
        id="ord-001",
        portfolio_id="small_account_01",
        symbol="BTC/USDT",
        client_order_id="cli-001",
        order_type="MARKET",
        side="BUY",
        quantity=0.0002,
        status="SUBMITTED",
        filled_quantity=0.0,
        fee=0.0,
        slippage_paid=0.0,
    )
    assert ord_model.client_order_id == "cli-001"
    assert ord_model.side == "BUY"


def test_trade_model() -> None:
    """Tests TradeModel record."""
    trade = TradeModel(
        id="trd-001",
        order_id="ord-001",
        portfolio_id="small_account_01",
        symbol="BTC/USDT",
        side="BUY",
        price=50000.0,
        quantity=0.0002,
        notional=10.0,
        fee=0.01,
        fee_currency="USDT",
        slippage=0.002,
    )
    assert trade.notional == 10.0
    assert trade.fee == 0.01


def test_risk_and_agent_decision_models() -> None:
    """Tests RiskEventModel and AgentDecisionModel."""
    risk = RiskEventModel(
        portfolio_id="small_account_01",
        event_type="DAILY_LOSS_LIMIT",
        severity="CRITICAL",
        details={"loss_pct": 0.021},
    )
    assert risk.severity == "CRITICAL"
    assert risk.details["loss_pct"] == 0.021

    dec = AgentDecisionModel(
        id="dec-001",
        symbol="BTC/USDT",
        decision="BUY",
        confidence=0.85,
        market_regime="TRENDING_BULL",
        strategy_signals_json={"ema_trend": "BUY"},
        ml_prediction_json={"prob": 0.72},
        sentiment_summary_json={"score": 0.45},
        risk_approved=True,
        explanation_text="Strong alignment across EMA trend and ML.",
    )
    assert dec.decision == "BUY"
    assert dec.confidence == 0.85
    assert dec.risk_approved is True
