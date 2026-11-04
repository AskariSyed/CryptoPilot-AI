"""
CryptoPilot AI - Sentiment Aggregator & Asset Index Calculator.
Aggregates time-decayed, relevance-weighted sentiment scores per cryptocurrency asset,
incorporates already-priced-in discounts, and flags stale windows.
"""

from datetime import UTC, datetime

from cryptopilot.sentiment.decay import ExponentialTimeDecay
from cryptopilot.sentiment.models import (
    AggregatedSentiment,
    NewsArticle,
    SentimentLabel,
    SentimentScore,
)
from cryptopilot.sentiment.relevance import AssetRelevanceFilter


class SentimentAggregator:
    """
    Computes weighted composite sentiment index for individual cryptocurrency trading pairs.
    """

    def __init__(
        self,
        decay_calculator: ExponentialTimeDecay | None = None,
        relevance_filter: AssetRelevanceFilter | None = None,
        min_relevance_threshold: float = 0.30,
        priced_in_return_threshold: float = 0.05,  # 5.0% price move threshold
        priced_in_discount_factor: float = 0.50,  # 50% discount if already pumped/dumped
    ) -> None:
        self.decay = decay_calculator or ExponentialTimeDecay()
        self.relevance = relevance_filter or AssetRelevanceFilter()
        self.min_relevance_threshold = min_relevance_threshold
        self.priced_in_return_threshold = priced_in_return_threshold
        self.priced_in_discount_factor = priced_in_discount_factor

    def aggregate(
        self,
        symbol: str,
        articles_with_scores: list[tuple[NewsArticle, SentimentScore]],
        current_time: datetime | None = None,
        recent_price_return: float | None = None,
    ) -> AggregatedSentiment:
        """
        Calculates time-decayed and relevance-weighted sentiment index for symbol.
        """
        now = current_time or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        weighted_polarity_sum = 0.0
        weighted_confidence_sum = 0.0
        total_weight = 0.0

        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        valid_article_count = 0

        for article, score in articles_with_scores:
            # 1. Relevance check
            rel_weight = self.relevance.calculate_relevance(article, symbol)
            if rel_weight < self.min_relevance_threshold:
                continue

            # 2. Time decay weight
            time_weight = self.decay.calculate_weight(article.published_at, current_time=now)
            if time_weight <= 0.0:
                continue

            combined_weight = rel_weight * time_weight
            weighted_polarity_sum += score.polarity * combined_weight
            weighted_confidence_sum += score.confidence * combined_weight
            total_weight += combined_weight

            valid_article_count += 1
            if score.label == SentimentLabel.BULLISH:
                bullish_count += 1
            elif score.label == SentimentLabel.BEARISH:
                bearish_count += 1
            else:
                neutral_count += 1

        if total_weight <= 0.0 or valid_article_count == 0:
            # Neutral fallback when no active news
            return AggregatedSentiment(
                symbol=symbol,
                sentiment_score=0.0,
                confidence=0.0,
                article_count=0,
                bullish_count=0,
                bearish_count=0,
                neutral_count=0,
                is_stale=True,
                timestamp=now,
            )

        raw_sentiment = weighted_polarity_sum / total_weight
        confidence = weighted_confidence_sum / total_weight

        # 3. Already-Priced-In Discounting:
        # If asset already pumped >= 5% and news is bullish, discount sentiment impact
        # If asset already dumped <= -5% and news is bearish, discount sentiment impact
        discounted_sentiment = raw_sentiment
        if recent_price_return is not None:
            if raw_sentiment > 0.0 and recent_price_return >= self.priced_in_return_threshold:
                discounted_sentiment *= self.priced_in_discount_factor
            elif raw_sentiment < 0.0 and recent_price_return <= -self.priced_in_return_threshold:
                discounted_sentiment *= self.priced_in_discount_factor

        # Bounded between -1.0 and 1.0
        final_sentiment = max(-1.0, min(1.0, discounted_sentiment))

        return AggregatedSentiment(
            symbol=symbol,
            sentiment_score=final_sentiment,
            confidence=confidence,
            article_count=valid_article_count,
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            neutral_count=neutral_count,
            is_stale=False,
            timestamp=now,
        )
