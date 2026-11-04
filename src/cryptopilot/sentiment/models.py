"""
CryptoPilot AI - Sentiment Analysis Domain Models.
Defines typed schemas for raw news articles, classification scores,
time-decayed weights, and aggregated asset sentiment indices.
"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class SentimentLabel(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class NewsArticle(BaseModel):
    """Normalized cryptocurrency news headline and article representation."""

    article_id: str
    title: str = Field(min_length=1)
    content: str = ""
    url: str = ""
    source: str = "Unknown"
    published_at: datetime
    symbols_mentioned: list[str] = Field(default_factory=list)
    content_hash: str = ""

    @field_validator("published_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class SentimentScore(BaseModel):
    """FinBERT / NLP sentiment inference output for a single article."""

    article_id: str
    label: SentimentLabel
    polarity: float = Field(ge=-1.0, le=1.0, description="Score S = P(Bullish) - P(Bearish)")
    confidence: float = Field(ge=0.0, le=1.0)
    p_bullish: float = Field(default=0.0, ge=0.0, le=1.0)
    p_bearish: float = Field(default=0.0, ge=0.0, le=1.0)
    p_neutral: float = Field(default=0.0, ge=0.0, le=1.0)


class AggregatedSentiment(BaseModel):
    """Time-decay weighted sentiment index for a specific cryptocurrency symbol."""

    symbol: str
    sentiment_score: float = Field(ge=-1.0, le=1.0, description="Weighted composite polarity score")
    confidence: float = Field(ge=0.0, le=1.0)
    article_count: int = Field(ge=0)
    bullish_count: int = Field(ge=0)
    bearish_count: int = Field(ge=0)
    neutral_count: int = Field(ge=0)
    is_stale: bool = False
    timestamp: datetime

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v
