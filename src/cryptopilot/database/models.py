"""
CryptoPilot AI - SQLAlchemy 2.0 Relational Database Models.
Defines normalized, indexed persistence models for market data, trading pairs,
portfolios, deposits, positions, orders, trades, risk events, and autonomous decisions.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.0 ORM models."""

    # Generic JSON type with SQLite compatibility
    type_annotation_map = {
        dict[str, Any]: JSON().with_variant(SQLiteJSON, "sqlite"),
        list[Any]: JSON().with_variant(SQLiteJSON, "sqlite"),
    }


def utc_now() -> datetime:
    """Helper returning timezone-aware current UTC datetime."""
    return datetime.now(UTC)


def generate_uuid() -> str:
    """Helper returning a new string UUIDv4."""
    return str(uuid.uuid4())


class ExchangeModel(Base):
    """Supported exchange connection profiles."""

    __tablename__ = "exchanges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rate_limit_ms: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    trading_pairs: Mapped[list["TradingPairModel"]] = relationship(
        "TradingPairModel", back_populates="exchange", cascade="all, delete-orphan"
    )


class TradingPairModel(Base):
    """Trading pair specifications and exchange constraints."""

    __tablename__ = "trading_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("exchanges.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    base_asset: Mapped[str] = mapped_column(String(10), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(10), nullable=False)
    price_precision: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    quantity_precision: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    min_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0001)
    min_notional: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (UniqueConstraint("exchange_id", "symbol", name="uq_exchange_trading_pair"),)

    # Relationships
    exchange: Mapped["ExchangeModel"] = relationship(
        "ExchangeModel", back_populates="trading_pairs"
    )
    candles: Mapped[list["MarketCandleModel"]] = relationship(
        "MarketCandleModel", back_populates="trading_pair", cascade="all, delete-orphan"
    )


class MarketCandleModel(Base):
    """Historical and live normalized OHLCV market observations."""

    __tablename__ = "market_candles"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    pair_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("trading_pairs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "open_time", name="uq_candle_symbol_tf_open"),
        Index("ix_candle_open_time_desc", open_time.desc()),
        Index("ix_candle_sym_tf_open_desc", symbol, timeframe, open_time.desc()),
    )

    trading_pair: Mapped[TradingPairModel | None] = relationship(
        "TradingPairModel", back_populates="candles"
    )


class MarketSnapshotModel(Base):
    """Order book and ticker snapshots for spread and liquidity tracking."""

    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    bid_price: Mapped[float] = mapped_column(Float, nullable=False)
    ask_price: Mapped[float] = mapped_column(Float, nullable=False)
    spread: Mapped[float] = mapped_column(Float, nullable=False)
    mid_price: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (Index("ix_snapshot_sym_ts_desc", symbol, timestamp.desc()),)


class PortfolioModel(Base):
    """Portfolio ledger accounting with micro-capital and research isolation."""

    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # 'small_account_01'
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'small_account'
    currency: Mapped[str] = mapped_column(String(10), default="USDT", nullable=False)
    initial_balance: Mapped[float] = mapped_column(Float, nullable=False)
    current_cash: Mapped[float] = mapped_column(Float, nullable=False)
    invested_capital: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_deposits: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_fees_paid: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_trading_halted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    deposits: Mapped[list["DepositModel"]] = relationship(
        "DepositModel", back_populates="portfolio", cascade="all, delete-orphan"
    )
    positions: Mapped[list["PositionModel"]] = relationship(
        "PositionModel", back_populates="portfolio", cascade="all, delete-orphan"
    )
    orders: Mapped[list["OrderModel"]] = relationship(
        "OrderModel", back_populates="portfolio", cascade="all, delete-orphan"
    )
    risk_events: Mapped[list["RiskEventModel"]] = relationship(
        "RiskEventModel", back_populates="portfolio", cascade="all, delete-orphan"
    )


class DepositModel(Base):
    """External capital contributions tracked distinctly from trading profits."""

    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    portfolio_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USDT", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)

    portfolio: Mapped["PortfolioModel"] = relationship("PortfolioModel", back_populates="deposits")


class PositionModel(Base):
    """Active and closed trading positions."""

    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    portfolio_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), default="LONG", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss_price: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_pos_port_status", portfolio_id, status),
        Index("ix_pos_sym_status", symbol, status),
    )

    portfolio: Mapped["PortfolioModel"] = relationship("PortfolioModel", back_populates="positions")
    trades: Mapped[list["TradeModel"]] = relationship(
        "TradeModel", back_populates="position", cascade="all, delete-orphan"
    )


class OrderModel(Base):
    """Simulated virtual orders in paper trading."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    portfolio_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    client_order_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=generate_uuid
    )
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)  # MARKET, LIMIT, STOP_LOSS
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY, SELL
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", nullable=False, index=True
    )  # PENDING, SUBMITTED, FILLED, CANCELED, REJECTED
    filled_quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    average_fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    slippage_paid: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_orders_port_status", portfolio_id, status),
        Index("ix_orders_sym_created", symbol, created_at.desc()),
    )

    portfolio: Mapped["PortfolioModel"] = relationship("PortfolioModel", back_populates="orders")
    trades: Mapped[list["TradeModel"]] = relationship(
        "TradeModel", back_populates="order", cascade="all, delete-orphan"
    )


class TradeModel(Base):
    """Executed trade fills corresponding to orders."""

    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    order_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("positions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    notional: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fee_currency: Mapped[str] = mapped_column(String(10), default="USDT", nullable=False)
    slippage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    __table_args__ = (
        Index("ix_trades_port_ts_desc", portfolio_id, timestamp.desc()),
        Index("ix_trades_sym_ts_desc", symbol, timestamp.desc()),
    )

    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="trades")
    position: Mapped[PositionModel | None] = relationship("PositionModel", back_populates="trades")


class RiskEventModel(Base):
    """Audit log of risk management checks, circuit breaker events, and trade vetoes."""

    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    portfolio_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="INFO")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    __table_args__ = (Index("ix_risk_events_port_ts_desc", portfolio_id, timestamp.desc()),)

    portfolio: Mapped["PortfolioModel"] = relationship(
        "PortfolioModel", back_populates="risk_events"
    )


class AgentDecisionModel(Base):
    """Unified audit log of Central Autonomous Decision Arbiter evaluations."""

    __tablename__ = "agent_decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY, SELL, HOLD
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    market_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_signals_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    ml_prediction_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    sentiment_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    risk_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    explanation_text: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_agent_decisions_sym_ts_desc", symbol, timestamp.desc()),)
