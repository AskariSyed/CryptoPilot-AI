"""
CryptoPilot AI - Autonomous Decision Engine Domain Models.
Defines typed schemas for market regimes, strategy arbitration inputs,
dynamic signal weights, and fully explainable trade decisions.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from cryptopilot.models.inference import MLPrediction
from cryptopilot.sentiment.models import AggregatedSentiment
from cryptopilot.strategies.base import SignalType, StrategySignal


class MarketRegime(StrEnum):
    """Classified market regime state."""

    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    UNKNOWN = "UNKNOWN"


class SignalWeights(BaseModel):
    """
    Normalized weighting parameters for technical strategies, ML predictions,
    and market sentiment in the central decision arbiter.
    """

    weight_technical: float = Field(
        default=0.50, ge=0.0, description="Base weight for rule-based strategy ensemble"
    )
    weight_ml: float = Field(
        default=0.35, ge=0.0, description="Weight for calibrated ML continuation model"
    )
    weight_sentiment: float = Field(
        default=0.15,
        ge=0.0,
        description="Weight for news sentiment (strictly supplementary)",
    )

    @model_validator(mode="after")
    def validate_and_normalize(self) -> "SignalWeights":
        total = self.weight_technical + self.weight_ml + self.weight_sentiment
        if total <= 0.0:
            raise ValueError("Total weights must sum to greater than 0.0")
        # Normalize weights so they sum exactly to 1.0
        self.weight_technical = self.weight_technical / total
        self.weight_ml = self.weight_ml / total
        self.weight_sentiment = self.weight_sentiment / total
        return self


class ArbitrationInput(BaseModel):
    """
    Standardized payload delivered to DecisionArbiter combining all upstream streams.
    """

    symbol: str
    current_price: float = Field(gt=0.0, description="Latest reference market price")
    strategy_signals: list[StrategySignal] = Field(
        default_factory=list, description="Signals from 5 independent rule strategies"
    )
    ml_prediction: MLPrediction | None = Field(
        default=None, description="Calibrated XGBoost forward return prediction"
    )
    sentiment: AggregatedSentiment | None = Field(
        default=None, description="Time-decayed per-asset sentiment index"
    )
    market_regime: MarketRegime = Field(
        default=MarketRegime.UNKNOWN, description="Detected market regime"
    )
    bid_ask_spread_pct: float = Field(
        default=0.0, ge=0.0, description="Relative bid/ask spread (ask - bid) / mid"
    )
    is_data_stale: bool = Field(
        default=False, description="Flag set if market data feed has exceeded max latency"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Evaluation timestamp in UTC"
    )

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class TradeDecision(BaseModel):
    """
    Synthesized autonomous trade proposal produced by DecisionArbiter.
    Contains complete transparency metrics and human-interpretable rationale.
    """

    decision_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique trade decision UUID"
    )
    symbol: str
    action: SignalType = Field(description="Synthesized recommendation: BUY, SELL, or HOLD")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Composite confidence score in range [0.0, 1.0]"
    )
    suggested_entry_price: float = Field(gt=0.0, description="Reference entry price")
    suggested_stop_loss: float | None = Field(
        default=None, description="Objective risk stop-loss price"
    )
    suggested_take_profit: float | None = Field(
        default=None, description="Objective take-profit target price"
    )
    market_regime: MarketRegime = Field(description="Market regime active at evaluation")
    strategy_signals: list[StrategySignal] = Field(
        default_factory=list, description="Snapshot of contributing strategy signals"
    )
    technical_consensus_score: float = Field(
        ge=-1.0,
        le=1.0,
        description="Consensus score from rule strategies: [-1.0 = All Sell, +1.0 = All Buy]",
    )
    ml_bullish_prob: float | None = Field(
        default=None, description="Calibrated ML bullish probability"
    )
    sentiment_polarity: float | None = Field(
        default=None, description="Time-decayed news polarity score"
    )
    composite_score: float = Field(
        ge=-1.0,
        le=1.0,
        description="Weighted composite arbitration score: [-1.0 = Strong Sell, +1.0 = Strong Buy]",
    )
    explanation: str = Field(
        description="Detailed natural language rationale explaining the decision"
    )
    risk_approved: bool = Field(
        default=False, description="Approval flag set by downstream Risk Manager"
    )
    rejection_reason: str | None = Field(
        default=None, description="Risk or safety veto explanation if rejected"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Decision timestamp in UTC"
    )

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v
