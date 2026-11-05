"""
CryptoPilot AI - Virtual Paper Trading Domain Models.
Defines typed schemas for simulated orders, order states, fills,
bracket order lifecycle tracking, and execution audit logging.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class OrderStatus(StrEnum):
    """Simulated order lifecycle states."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


class OrderType(StrEnum):
    """Supported virtual order types."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderSide(StrEnum):
    """Trading direction side."""

    BUY = "BUY"
    SELL = "SELL"


class VirtualOrder(BaseModel):
    """
    Representation of an individual simulated order in the virtual broker.
    """

    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = Field(description="Account identifier (small_account_01 or research_lab_01)")
    symbol: str = Field(description="Trading pair symbol e.g. BTC/USDT")
    side: OrderSide = Field(description="BUY or SELL")
    order_type: OrderType = Field(description="Order execution style")
    quantity: float = Field(gt=0.0, description="Base asset quantity")
    price: float | None = Field(default=None, description="Limit price if LIMIT order")
    stop_price: float | None = Field(
        default=None, description="Trigger price if STOP_LOSS or TAKE_PROFIT"
    )
    filled_quantity: float = Field(default=0.0, ge=0.0, description="Quantity successfully filled")
    remaining_quantity: float = Field(ge=0.0, description="Quantity remaining to be filled")
    average_fill_price: float | None = Field(
        default=None, description="Volume-weighted average fill price"
    )
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Current lifecycle state")
    fee_paid: float = Field(default=0.0, ge=0.0, description="Cumulative commissions paid")
    slippage_paid: float = Field(default=0.0, ge=0.0, description="Cumulative price slippage drag")
    rejection_reason: str | None = Field(default=None, description="Explanation if rejected")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class VirtualFill(BaseModel):
    """
    Record of an individual fill event against market liquidity.
    """

    fill_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    account_id: str
    symbol: str
    side: OrderSide
    price: float = Field(gt=0.0, description="Execution fill price")
    quantity: float = Field(gt=0.0, description="Filled quantity")
    notional: float = Field(gt=0.0, description="Dollar value: price * quantity")
    fee: float = Field(ge=0.0, description="Commission deducted")
    fee_rate: float = Field(ge=0.0, description="Commission percentage applied")
    slippage_rate: float = Field(ge=0.0, description="Price slippage percentage experienced")
    slippage_cost: float = Field(ge=0.0, description="Dollar slippage drag experienced")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class BracketOrder(BaseModel):
    """
    Virtual bracket structure linking an entry order with simultaneous
    Stop-Loss and Take-Profit exit triggers.
    """

    bracket_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str
    symbol: str
    entry_order: VirtualOrder
    stop_loss_order: VirtualOrder | None = None
    take_profit_order: VirtualOrder | None = None
    is_active: bool = True
    exit_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None

    @field_validator("created_at", "closed_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class ExecutionAuditEvent(BaseModel):
    """
    Immutable audit event log capturing every virtual broker action for transparency.
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str
    event_type: str = Field(
        description="Event category: ORDER_SUBMITTED, ORDER_FILLED, BRACKET_OPENED, etc."
    )
    order_id: str | None = None
    symbol: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v
