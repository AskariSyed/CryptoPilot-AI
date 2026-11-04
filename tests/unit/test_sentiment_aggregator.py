"""
Tests for CryptoPilot AI - Sentiment Aggregator & Asset Index Calculator.
"""

from datetime import UTC, datetime, timedelta

import pytest

from cryptopilot.sentiment.aggregator import SentimentAggregator
from cryptopilot.sentiment.decay import ExponentialTimeDecay
from cryptopilot.sentiment.models import (
    NewsArticle,
    SentimentLabel,
    SentimentScore,
)
from cryptopilot.sentiment.relevance import AssetRelevanceFilter


def test_aggregator_empty_articles_fallback():
    aggregator = SentimentAggregator()
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)

    result = aggregator.aggregate(symbol="BTC/USDT", articles_with_scores=[], current_time=now)
    assert result.symbol == "BTC/USDT"
    assert result.sentiment_score == 0.0
    assert result.confidence == 0.0
    assert result.article_count == 0
    assert result.bullish_count == 0
    assert result.bearish_count == 0
    assert result.neutral_count == 0
    assert result.is_stale is True


def test_aggregator_filters_irrelevant_and_expired():
    aggregator = SentimentAggregator(min_relevance_threshold=0.30)
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)

    # Irrelevant article (mentions only Solana, symbol queried is BTC/USDT)
    art_irrelevant = NewsArticle(
        article_id="irr-1",
        title="Solana ecosystem booming with new DEX volume",
        published_at=now,
    )
    score_irrelevant = SentimentScore(
        article_id="irr-1",
        label=SentimentLabel.BULLISH,
        polarity=0.8,
        confidence=0.9,
    )

    # Expired article (26 hours old)
    art_expired = NewsArticle(
        article_id="exp-1",
        title="Bitcoin breaks above resistance level",
        published_at=now - timedelta(hours=26),
    )
    score_expired = SentimentScore(
        article_id="exp-1",
        label=SentimentLabel.BULLISH,
        polarity=0.9,
        confidence=0.9,
    )

    result = aggregator.aggregate(
        symbol="BTC/USDT",
        articles_with_scores=[
            (art_irrelevant, score_irrelevant),
            (art_expired, score_expired),
        ],
        current_time=now,
    )

    assert result.article_count == 0
    assert result.sentiment_score == 0.0
    assert result.is_stale is True


def test_aggregator_multi_article_time_weighted():
    decay = ExponentialTimeDecay(half_life_hours=2.0, max_age_hours=24.0)
    relevance = AssetRelevanceFilter()
    aggregator = SentimentAggregator(decay_calculator=decay, relevance_filter=relevance)

    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)

    # Recent article (published now, elapsed = 0, weight = 1.0)
    art_recent = NewsArticle(
        article_id="rec-1",
        title="Bitcoin institutional ETF inflows hit new all-time record",
        published_at=now,
    )
    score_recent = SentimentScore(
        article_id="rec-1",
        label=SentimentLabel.BULLISH,
        polarity=0.8,
        confidence=0.9,
    )

    # Older article (published 2 hours ago -> half-life -> time weight = 0.5)
    art_older = NewsArticle(
        article_id="old-1",
        title="Bitcoin miners sell reserves amidst difficulty increase",
        published_at=now - timedelta(hours=2),
    )
    score_older = SentimentScore(
        article_id="old-1",
        label=SentimentLabel.BEARISH,
        polarity=-0.6,
        confidence=0.8,
    )

    result = aggregator.aggregate(
        symbol="BTC/USDT",
        articles_with_scores=[(art_recent, score_recent), (art_older, score_older)],
        current_time=now,
    )

    assert result.article_count == 2
    assert result.bullish_count == 1
    assert result.bearish_count == 1
    assert result.neutral_count == 0
    assert result.is_stale is False
    # Polarity should be positive because the recent bullish article has 2x time weight of the 2h old bearish article
    assert result.sentiment_score > 0.2
    assert 0.0 < result.confidence <= 1.0


def test_aggregator_priced_in_discount():
    aggregator = SentimentAggregator(
        priced_in_return_threshold=0.05,
        priced_in_discount_factor=0.50,
    )
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)

    art_bullish = NewsArticle(
        article_id="pump-1",
        title="Ethereum layer 2 transactions surge to historic highs",
        published_at=now,
    )
    score_bullish = SentimentScore(
        article_id="pump-1",
        label=SentimentLabel.BULLISH,
        polarity=0.8,
        confidence=0.9,
    )

    # Case 1: Bullish news with normal return (+1%) -> no discount
    res_normal = aggregator.aggregate(
        symbol="ETH/USDT",
        articles_with_scores=[(art_bullish, score_bullish)],
        current_time=now,
        recent_price_return=0.01,
    )
    assert res_normal.sentiment_score == pytest.approx(0.8, abs=1e-3)

    # Case 2: Bullish news after +7% pump -> discounted by 50%
    res_discounted = aggregator.aggregate(
        symbol="ETH/USDT",
        articles_with_scores=[(art_bullish, score_bullish)],
        current_time=now,
        recent_price_return=0.07,
    )
    assert res_discounted.sentiment_score == pytest.approx(0.4, abs=1e-3)

    # Case 3: Bearish news after -6% dump -> discounted by 50%
    art_bearish = NewsArticle(
        article_id="dump-1",
        title="Ethereum smart contract vulnerability triggers panic selloff",
        published_at=now,
    )
    score_bearish = SentimentScore(
        article_id="dump-1",
        label=SentimentLabel.BEARISH,
        polarity=-0.8,
        confidence=0.9,
    )
    res_bear_discounted = aggregator.aggregate(
        symbol="ETH/USDT",
        articles_with_scores=[(art_bearish, score_bearish)],
        current_time=now,
        recent_price_return=-0.06,
    )
    assert res_bear_discounted.sentiment_score == pytest.approx(-0.4, abs=1e-3)
