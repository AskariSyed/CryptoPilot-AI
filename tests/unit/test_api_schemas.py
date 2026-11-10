"""
Unit tests for cryptopilot.api.schemas.
Validates Pydantic response envelopes, request models, and UTC datetime defaults.
"""

from datetime import UTC, datetime

from cryptopilot.api.schemas import (
    ApiResponse,
    DepositRequest,
    EmergencyHaltRequest,
    HealthData,
    MarketCandleItem,
    MarketCandlesResponse,
    MarketTickerData,
    OrderCancelRequest,
    OrderItem,
    PortfolioSummaryData,
    PositionItem,
    RiskStatusData,
    SystemStatusData,
    TradeItem,
    utc_now,
)


def test_api_response_envelope() -> None:
    """Tests standard generic API envelope serialization."""
    envelope = ApiResponse[dict[str, str]](
        success=True,
        data={"message": "hello"},
        error=None,
    )
    dumped = envelope.model_dump(mode="json")
    assert dumped["success"] is True
    assert dumped["data"]["message"] == "hello"
    assert dumped["error"] is None
    assert "timestamp" in dumped

    # Error envelope
    err_envelope = ApiResponse[None](
        success=False,
        data=None,
        error="Invalid token",
    )
    assert err_envelope.success is False
    assert err_envelope.error == "Invalid token"


def test_utc_now_helper() -> None:
    """Verifies utc_now helper returns UTC datetime."""
    now = utc_now()
    assert now.tzinfo == UTC


def test_system_schemas() -> None:
    """Tests HealthData and SystemStatusData models."""
    health = HealthData(uptime_seconds=120.5)
    assert health.status == "HEALTHY"
    assert health.trading_mode == "paper"
    assert health.uptime_seconds == 120.5

    status = SystemStatusData(
        environment="development",
        trading_mode="paper",
        live_trading_enabled=False,
        active_portfolios=["small_account_01"],
        monitored_symbols=["BTC/USDT"],
        supported_timeframes=["1h"],
        initial_capital=30.0,
        monthly_contribution=10.0,
    )
    assert status.initial_capital == 30.0
    assert status.live_trading_enabled is False


def test_market_schemas() -> None:
    """Tests MarketCandleItem, MarketCandlesResponse, and MarketTickerData."""
    candle = MarketCandleItem(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime.now(UTC),
        open=50000.0,
        high=51000.0,
        low=49500.0,
        close=50500.0,
        volume=100.0,
        is_closed=True,
    )
    resp = MarketCandlesResponse(
        symbol="BTC/USDT",
        timeframe="1h",
        count=1,
        candles=[candle],
    )
    assert resp.count == 1

    ticker = MarketTickerData(
        symbol="BTC/USDT",
        bid=50000.0,
        ask=50010.0,
        last=50005.0,
        spread=10.0,
        mid_price=50005.0,
        timestamp=datetime.now(UTC),
    )
    assert ticker.spread == 10.0


def test_trading_and_portfolio_schemas() -> None:
    """Tests PortfolioSummaryData, PositionItem, OrderItem, TradeItem."""
    port = PortfolioSummaryData(
        portfolio_id="small_account_01",
        account_type="small_account",
        currency="USDT",
        initial_capital=30.0,
        total_deposits=10.0,
        total_cash=25.0,
        invested_capital=15.0,
        current_equity=40.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        total_fees_paid=0.02,
        net_trading_return_pct=0.0,
        max_drawdown_pct=0.0,
        is_trading_halted=False,
    )
    assert port.current_equity == 40.0

    pos = PositionItem(
        id="pos-1",
        portfolio_id="small_account_01",
        symbol="BTC/USDT",
        side="LONG",
        status="OPEN",
        quantity=0.0002,
        entry_price=50000.0,
        current_price=50500.0,
        stop_loss_price=49000.0,
        opened_at=datetime.now(UTC),
    )
    assert pos.quantity == 0.0002

    ord_item = OrderItem(
        id="ord-1",
        portfolio_id="small_account_01",
        symbol="BTC/USDT",
        client_order_id="cli-1",
        order_type="MARKET",
        side="BUY",
        quantity=0.0002,
        status="FILLED",
        filled_quantity=0.0002,
        average_fill_price=50000.0,
        fee=0.01,
        slippage_paid=0.002,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert ord_item.status == "FILLED"

    trade = TradeItem(
        id="trd-1",
        order_id="ord-1",
        portfolio_id="small_account_01",
        symbol="BTC/USDT",
        side="BUY",
        price=50000.0,
        quantity=0.0002,
        notional=10.0,
        fee=0.01,
        slippage=0.002,
        timestamp=datetime.now(UTC),
    )
    assert trade.notional == 10.0


def test_control_requests() -> None:
    """Tests request DTO models and defaults."""
    dep = DepositRequest(amount=10.0)
    assert dep.portfolio_id == "small_account_01"
    assert dep.amount == 10.0

    halt = EmergencyHaltRequest(reason="Test shutdown")
    assert halt.reason == "Test shutdown"

    cancel = OrderCancelRequest(order_id="ord-999")
    assert cancel.order_id == "ord-999"

    risk = RiskStatusData(
        portfolio_id="small_account_01",
        is_tripped=False,
        starting_daily_equity=30.0,
        current_daily_loss=0.0,
        daily_loss_pct=0.0,
        daily_loss_limit_pct=0.02,
        consecutive_losses=0,
        emergency_stop=False,
        is_trading_halted=False,
    )
    assert risk.is_tripped is False
