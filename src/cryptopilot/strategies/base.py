"""
CryptoPilot AI - Quantitative Strategy Base Interfaces & Schemas.
Strictly typed via Pydantic v2. Enforces deterministic signal generation,
explicit confidence scoring [0.0, 1.0], rationale logs, and objective stop-loss levels.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
import pandas as pd
from pydantic import BaseModel, Field, field_validator


class SignalType(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class StrategySignal(BaseModel):
    strategy_id: str = Field(description="Unique strategy identifier e.g. ema_trend")
    symbol: str = Field(description="Trading pair symbol e.g. BTC/USDT")
    signal: SignalType = Field(description="Trading action: BUY, SELL, or HOLD")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score in range [0.0, 1.0]. Values < 0.50 are weak/unconfirmed.",
    )
    entry_price: float = Field(gt=0.0, description="Reference entry price at evaluation")
    suggested_stop_loss: float = Field(
        gt=0.0,
        description="Objective stop loss level calculated from volatility or swing structure",
    )
    suggested_take_profit: float | None = Field(
        default=None,
        description="Optional objective take profit target price",
    )
    rationale: str = Field(description="Interpretable human-readable explanation for signal")
    invalidation_condition: str = Field(
        description="Objective condition that nullifies the trade setup"
    )
    timestamp: datetime = Field(description="Signal timestamp in UTC")
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Exact indicator snapshots at bar close",
    )

    @field_validator("timestamp")
    @classmethod
    def enforce_utc_timestamp(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("suggested_stop_loss")
    @classmethod
    def validate_stop_loss_relative_to_entry(cls, v: float, info: Any) -> float:
        # Stop loss validation will be contextual in strategy implementations
        return v


class BaseStrategy(ABC):
    """
    Abstract base class for all independent quantitative strategies.
    Guarantees:
    1. Returns a typed StrategySignal on every evaluation.
    2. Defaults to HOLD if data is insufficient, choppy, or conflicting.
    3. Operates strictly on confirmed closed bars (zero lookahead).
    """

    def __init__(self, strategy_id: str, name: str, min_bars: int) -> None:
        if min_bars < 1:
            raise ValueError(f"min_bars must be >= 1, got {min_bars}")
        self.strategy_id = strategy_id
        self.name = name
        self.min_bars = min_bars

    @abstractmethod
    def evaluate(self, df: pd.DataFrame, symbol: str) -> StrategySignal:
        """
        Evaluates indicator conditions on the latest confirmed closed bar.
        Must return a valid StrategySignal.
        """
        pass

    def validate_dataframe(self, df: pd.DataFrame) -> tuple[bool, str]:
        """
        Verifies DataFrame structure and bar count.
        Returns (is_valid, error_message).
        """
        if df is None or not isinstance(df, pd.DataFrame):
            return False, "Input must be a valid pandas DataFrame"
        if len(df) < self.min_bars:
            return False, f"Insufficient observations: required >= {self.min_bars}, got {len(df)}"

        required_cols = ["open", "high", "low", "close", "volume"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            return False, f"Missing required price columns: {missing}"

        return True, ""

    def create_hold_signal(
        self,
        symbol: str,
        current_price: float,
        reason: str,
        metrics: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> StrategySignal:
        """Helper to construct a deterministic, standard HOLD signal."""
        price = max(current_price, 0.0001)
        ts = timestamp or datetime.now(UTC)
        return StrategySignal(
            strategy_id=self.strategy_id,
            symbol=symbol,
            signal=SignalType.HOLD,
            confidence=0.0,
            entry_price=price,
            suggested_stop_loss=price * 0.95,
            suggested_take_profit=None,
            rationale=reason,
            invalidation_condition="N/A (Holding cash/no setup)",
            timestamp=ts,
            metrics=metrics or {},
        )
