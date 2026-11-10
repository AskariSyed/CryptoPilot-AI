"""
CryptoPilot AI - FastAPI REST API Pydantic Domain Schemas.
Defines typed request and response payloads, standardized API envelopes,
and telemetry DTOs.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Helper returning current timezone-aware UTC datetime."""
    return datetime.now(UTC)


class ApiResponse[T](BaseModel):
    """Standardized API response envelope."""

    success: bool = True
    data: T | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)


# 1. System & Telemetry Schemas
class HealthData(BaseModel):
    """System health check and daemon heartbeat payload."""

    status: str = "HEALTHY"
    version: str = "0.1.0"
    uptime_seconds: float = Field(ge=0.0)
    trading_mode: str = "paper"
    database: str = "CONNECTED"
    exchange_connectivity: str = "CONNECTED"
    circuit_breaker_active: bool = False


class SystemStatusData(BaseModel):
    """System configuration and operational overview."""

    environment: str
    trading_mode: str
    live_trading_enabled: bool = False
    active_portfolios: list[str]
    monitored_symbols: list[str]
    supported_timeframes: list[str]
    initial_capital: float
    monthly_contribution: float


# 2. Market Data Schemas
class MarketCandleItem(BaseModel):
    """OHLCV market bar data transfer object."""

    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = True


class MarketCandlesResponse(BaseModel):
    """List of OHLCV bars for a pair and timeframe."""

    symbol: str
    timeframe: str
    count: int
    candles: list[MarketCandleItem]


class MarketTickerData(BaseModel):
    """Real-time market snapshot for a symbol."""

    symbol: str
    bid: float
    ask: float
    last: float
    spread: float
    mid_price: float
    timestamp: datetime


# 3. Portfolio & Accounting Schemas
class PortfolioSummaryData(BaseModel):
    """Current portfolio valuation, cash balances, and separated deposit metrics."""

    portfolio_id: str
    account_type: str
    currency: str = "USDT"
    initial_capital: float
    total_deposits: float
    total_cash: float
    invested_capital: float
    current_equity: float
    realized_pnl: float
    unrealized_pnl: float
    total_fees_paid: float
    net_trading_return_pct: float
    max_drawdown_pct: float
    is_trading_halted: bool


class PositionItem(BaseModel):
    """Active or closed position detail."""

    id: str
    portfolio_id: str
    symbol: str
    side: str
    status: str
    quantity: float
    entry_price: float
    current_price: float
    exit_price: float | None = None
    stop_loss_price: float
    take_profit_price: float | None = None
    unrealized_pnl: float = 0.0
    realized_pnl: float | None = None
    opened_at: datetime
    closed_at: datetime | None = None


class OrderItem(BaseModel):
    """Virtual paper trading order status."""

    id: str
    portfolio_id: str
    symbol: str
    client_order_id: str
    order_type: str
    side: str
    quantity: float
    price: float | None = None
    stop_price: float | None = None
    status: str
    filled_quantity: float
    average_fill_price: float | None = None
    fee: float
    slippage_paid: float
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class TradeItem(BaseModel):
    """Individual trade execution fill receipt."""

    id: str
    order_id: str
    position_id: str | None = None
    portfolio_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    notional: float
    fee: float
    fee_currency: str = "USDT"
    slippage: float
    timestamp: datetime


# 4. Decision & Risk Schemas
class DecisionItem(BaseModel):
    """Central Autonomous Decision Arbiter audit entry."""

    id: str
    symbol: str
    timestamp: datetime
    decision: str
    confidence: float
    market_regime: str
    strategy_signals: dict[str, Any]
    ml_prediction: dict[str, Any] | None = None
    sentiment_summary: dict[str, Any] | None = None
    risk_approved: bool
    rejection_reason: str | None = None
    explanation: str


class RiskStatusData(BaseModel):
    """Real-time circuit breaker and exposure risk limits."""

    portfolio_id: str
    is_tripped: bool
    trip_reason: str | None = None
    starting_daily_equity: float
    current_daily_loss: float
    daily_loss_pct: float
    daily_loss_limit_pct: float
    consecutive_losses: int
    emergency_stop: bool
    is_trading_halted: bool


class RiskEventItem(BaseModel):
    """Risk telemetry audit log event."""

    id: int
    portfolio_id: str
    event_type: str
    severity: str
    details: dict[str, Any]
    timestamp: datetime


# 5. Admin & Control Request Schemas
class DepositRequest(BaseModel):
    """Simulated capital injection request."""

    portfolio_id: str = "small_account_01"
    amount: float = Field(gt=0.0, description="Deposit amount in quote currency (e.g. 10.0)")
    currency: str = "USDT"
    note: str | None = Field(default="Simulated monthly contribution", max_length=256)


class EmergencyHaltRequest(BaseModel):
    """Emergency halt trigger request."""

    portfolio_id: str = "small_account_01"
    reason: str = Field(default="Manual kill-switch activated", max_length=256)


class OrderCancelRequest(BaseModel):
    """Order cancellation request."""

    portfolio_id: str = "small_account_01"
    order_id: str
    reason: str = Field(default="Manual order cancellation", max_length=256)
