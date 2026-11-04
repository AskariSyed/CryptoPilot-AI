"""
Unit tests for cryptopilot.sentiment.models.
Covers: Schema validation, UTC timezone enforcement, and field constraints.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cryptopilot.sentiment.models import (
    AggregatedSentiment,
    NewsArticle,
    SentimentLabel,
    SentimentScore,
)


class TestSentimentModels:
    def test_news_article_valid_and_utc(self) -> None:
        naive_dt = datetime(2026, 1, 1, 12, 0, 0)
        art = NewsArticle(
            article_id="art_1",
            title="Bitcoin Surges to New High",
            published_at=naive_dt,
        )
        assert art.published_at.tzinfo == UTC
        assert art.source == "Unknown"
        assert art.symbols_mentioned == []

    def test_news_article_empty_title_raises_error(self) -> None:
        with pytest.raises(ValidationError):
            NewsArticle(
                article_id="bad",
                title="",
                published_at=datetime.now(UTC),
            )

    def test_sentiment_score_validation(self) -> None:
        score = SentimentScore(
            article_id="art_1",
            label=SentimentLabel.BULLISH,
            polarity=0.75,
            confidence=0.85,
            p_bullish=0.85,
            p_bearish=0.10,
            p_neutral=0.05,
        )
        assert score.label == SentimentLabel.BULLISH
        assert score.polarity == 0.75

        # Out-of-bounds polarity
        with pytest.raises(ValidationError):
            SentimentScore(
                article_id="bad",
                label=SentimentLabel.BULLISH,
                polarity=1.5,  # > 1.0
                confidence=0.5,
                p_bullish=0.5,
                p_bearish=0.3,
                p_neutral=0.2,
            )

    def test_aggregated_sentiment_model(self) -> None:
        agg = AggregatedSentiment(
            symbol="BTC/USDT",
            sentiment_score=0.45,
            confidence=0.60,
            article_count=5,
            bullish_count=4,
            bearish_count=1,
            neutral_count=0,
            is_stale=False,
            timestamp=datetime(2026, 1, 1, 12, 0, 0),
        )
        assert agg.timestamp.tzinfo == UTC
        assert agg.symbol == "BTC/USDT"
        assert agg.article_count == 5
        assert agg.is_stale is False
