"""
CryptoPilot AI - Portfolio & Balance Accounting Domain Models.
Defines typed schemas for ledger transactions, position tracking,
and strict separation of trading performance from external capital contributions.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class AccountType(StrEnum):
    """Account operational mode separating micro-capital from research lab."""

    SMALL_ACCOUNT = "SMALL_ACCOUNT"
    RESEARCH = "RESEARCH"


class LedgerEntryType(StrEnum):
    """Categories of balance movements for clean performance accounting."""

    INITIAL_DEPOSIT = "INITIAL_DEPOSIT"
    MONTHLY_CONTRIBUTION = "MONTHLY_CONTRIBUTION"
    TRADE_REALIZED_PNL = "TRADE_REALIZED_PNL"
    FEE_DEDUCTION = "FEE_DEDUCTION"


class LedgerEntry(BaseModel):
    """Immutable transaction ledger entry representing an individual cash flow."""

    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str
    entry_type: LedgerEntryType
    amount: float = Field(description="Credit (positive) or debit (negative) cash amount")
    balance_after: float = Field(ge=0.0, description="Cash balance following transaction")
    description: str = Field(default="")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class PositionSnapshot(BaseModel):
    """Active open market position representation."""

    position_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    quantity: float = Field(gt=0.0, description="Base asset quantity held")
    entry_price: float = Field(gt=0.0, description="Volume-weighted average entry price")
    current_price: float = Field(gt=0.0, description="Latest mark market price")
    stop_loss_price: float = Field(gt=0.0, description="Active stop-loss exit trigger")
    take_profit_price: float | None = Field(default=None, description="Active take-profit target")
    notional_cost: float = Field(
        gt=0.0, description="Capital deployed at entry: quantity * entry_price"
    )
    current_notional: float = Field(
        gt=0.0, description="Current market value: quantity * current_price"
    )
    unrealized_pnl: float = Field(
        description="Dollar unrealized gain/loss: current_notional - notional_cost"
    )
    unrealized_pnl_pct: float = Field(description="Percentage return on invested cost")
    opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("opened_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class PortfolioSummary(BaseModel):
    """Comprehensive real-time snapshot of portfolio equity and ledger performance."""

    account_id: str
    account_type: AccountType
    cash: float = Field(ge=0.0, description="Liquid cash available for deployment")
    invested_capital: float = Field(
        ge=0.0, description="Capital actively deployed in open positions"
    )
    unrealized_pnl: float = Field(description="Cumulative unrealized floating gain/loss")
    total_equity: float = Field(
        ge=0.0, description="Total portfolio liquidation value: cash + invested + unrealized"
    )
    total_deposits: float = Field(
        ge=0.0, description="Cumulative external capital (initial + contributions)"
    )
    realized_pnl: float = Field(
        description="Cumulative net trading profits/losses after commissions"
    )
    net_profit: float = Field(description="Total profit: total_equity - total_deposits")
    return_on_deposits_pct: float = Field(
        description="Total percentage return relative to cumulative deposits"
    )
    active_positions_count: int = Field(ge=0, description="Number of currently open positions")
    peak_equity: float = Field(ge=0.0, description="Highest historical portfolio equity recorded")
    drawdown_pct: float = Field(
        ge=0.0, le=1.0, description="Current drawdown percentage from peak equity"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v
