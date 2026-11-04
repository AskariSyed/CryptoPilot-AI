"""
CryptoPilot AI - Backtesting Domain Models and Schemas.
Enforces typed schemas for orders, positions, trades, equity curve points,
performance metrics, and benchmark comparisons.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


class ExitReason(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    SIGNAL = "SIGNAL"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    FORCE_CLOSE = "FORCE_CLOSE"


class SimulatedOrder(BaseModel):
    """Represents an order submitted during backtesting."""

    model_config = ConfigDict(validate_assignment=True)

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float = Field(gt=0.0)
    target_price: float = Field(gt=0.0)
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime
    filled_at: datetime | None = None
    fill_price: float | None = None
    fee_paid: float = 0.0
    slippage_paid: float = 0.0
    rationale: str = ""

    @field_validator("created_at", "filled_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class SimulatedPosition(BaseModel):
    """Represents an active or closed position in the backtester."""

    model_config = ConfigDict(validate_assignment=True)

    position_id: str
    symbol: str
    side: OrderSide = OrderSide.BUY
    entry_price: float = Field(gt=0.0)
    current_price: float = Field(gt=0.0)
    quantity: float = Field(gt=0.0)
    stop_loss: float = Field(gt=0.0)
    take_profit: float | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    fees_paid: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    @field_validator("opened_at", "closed_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class Trade(BaseModel):
    """Completed trade record for performance accounting."""

    trade_id: str
    symbol: str
    side: OrderSide = OrderSide.BUY
    entry_time: datetime
    exit_time: datetime
    entry_price: float = Field(gt=0.0)
    exit_price: float = Field(gt=0.0)
    quantity: float = Field(gt=0.0)
    gross_pnl: float
    net_pnl: float
    fees_paid: float = Field(ge=0.0)
    exit_reason: ExitReason
    return_pct: float
    bars_held: int = Field(ge=0, default=0)

    @field_validator("entry_time", "exit_time", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class EquityPoint(BaseModel):
    """Snapshot of portfolio equity at a specific timestamp."""

    timestamp: datetime
    cash: float
    invested_value: float
    total_equity: float
    cumulative_deposits: float
    net_profit: float
    drawdown_pct: float = Field(ge=0.0)

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class PerformanceMetrics(BaseModel):
    """Comprehensive quantitative performance metrics."""

    initial_capital: float
    final_equity: float
    total_deposits: float
    net_profit: float
    net_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    max_drawdown_duration_bars: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate_pct: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    expectancy: float
    avg_trade_pnl: float
    avg_win: float
    avg_loss: float
    profit_loss_ratio: float
    total_fees_paid: float


class BenchmarkComparison(BaseModel):
    """Comparative performance vs Buy & Hold benchmark or Cash."""

    name: str
    initial_equity: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float


class BacktestResult(BaseModel):
    """Master result container returned by the backtest engine."""

    strategy_id: str
    symbol: str
    timeframe: str
    start_time: datetime
    end_time: datetime
    initial_capital: float
    final_equity: float
    total_deposits: float
    metrics: PerformanceMetrics
    benchmarks: list[BenchmarkComparison] = Field(default_factory=list)
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    trades: list[Trade] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
