"""
CryptoPilot AI - Sentiment Analysis Engine Facade.
Orchestrates news feed ingestion, cryptographic deduplication, relevance tagging,
NLP sentiment scoring, exponential time decay, and per-symbol index aggregation.
"""

from datetime import UTC, datetime

from cryptopilot.sentiment.adapter import BaseNewsAdapter, MockNewsAdapter
from cryptopilot.sentiment.aggregator import SentimentAggregator
from cryptopilot.sentiment.classifier import (
    BaseSentimentClassifier,
    RuleBasedFinancialSentimentClassifier,
)
from cryptopilot.sentiment.decay import ExponentialTimeDecay
from cryptopilot.sentiment.deduplicator import NewsDeduplicator
from cryptopilot.sentiment.models import AggregatedSentiment, NewsArticle, SentimentScore
from cryptopilot.sentiment.relevance import AssetRelevanceFilter


class SentimentEngine:
    """
    Top-level Sentiment Engine synthesizing news data into quantitative sentiment indicators.
    """

    def __init__(
        self,
        adapter: BaseNewsAdapter | None = None,
        classifier: BaseSentimentClassifier | None = None,
        deduplicator: NewsDeduplicator | None = None,
        relevance_filter: AssetRelevanceFilter | None = None,
        aggregator: SentimentAggregator | None = None,
        decay: ExponentialTimeDecay | None = None,
    ) -> None:
        self.adapter = adapter or MockNewsAdapter()
        self.classifier = classifier or RuleBasedFinancialSentimentClassifier()
        self.deduplicator = deduplicator or NewsDeduplicator()
        self.relevance = relevance_filter or AssetRelevanceFilter()
        self.decay = decay or ExponentialTimeDecay()
        self.aggregator = aggregator or SentimentAggregator(
            decay_calculator=self.decay,
            relevance_filter=self.relevance,
        )

        # In-memory store of processed articles and their scores
        self._scored_cache: list[tuple[NewsArticle, SentimentScore]] = []

    def ingest_articles(
        self,
        articles: list[NewsArticle],
        current_time: datetime | None = None,
    ) -> int:
        """
        Deduplicates, tags, scores, and caches input articles.
        Returns the count of newly accepted non-duplicate articles.
        """
        now = current_time or datetime.now(UTC)
        unique_articles = self.deduplicator.deduplicate_batch(articles, current_time=now)

        new_count = 0
        for article in unique_articles:
            self.relevance.tag_article(article)
            full_text = f"{article.title} {article.content}"
            score = self.classifier.predict(full_text, article_id=article.article_id)
            self._scored_cache.append((article, score))
            new_count += 1

        # Prune expired items from cache
        self.prune_cache(now)
        return new_count

    async def refresh_from_adapter(
        self,
        symbols: list[str] | None = None,
        current_time: datetime | None = None,
    ) -> int:
        """Fetches fresh articles from configured news adapter and ingests them."""
        articles = await self.adapter.fetch_news(symbols=symbols)
        return self.ingest_articles(articles, current_time=current_time)

    def analyze_symbol(
        self,
        symbol: str,
        current_time: datetime | None = None,
        recent_price_return: float | None = None,
    ) -> AggregatedSentiment:
        """
        Returns the aggregated sentiment index for the specified cryptocurrency symbol.
        """
        now = current_time or datetime.now(UTC)
        return self.aggregator.aggregate(
            symbol=symbol,
            articles_with_scores=self._scored_cache,
            current_time=now,
            recent_price_return=recent_price_return,
        )

    def analyze_all(
        self,
        symbols: list[str],
        current_time: datetime | None = None,
        recent_returns: dict[str, float] | None = None,
    ) -> dict[str, AggregatedSentiment]:
        """
        Returns aggregated sentiment scores across all specified symbols.
        """
        now = current_time or datetime.now(UTC)
        returns = recent_returns or {}
        results: dict[str, AggregatedSentiment] = {}

        for sym in symbols:
            ret = returns.get(sym)
            results[sym] = self.analyze_symbol(sym, current_time=now, recent_price_return=ret)

        return results

    def prune_cache(self, current_time: datetime | None = None) -> int:
        """Removes articles older than decay max_age from the active score cache."""
        now = current_time or datetime.now(UTC)
        initial_len = len(self._scored_cache)
        self._scored_cache = [
            (art, score)
            for art, score in self._scored_cache
            if not self.decay.is_expired(art.published_at, current_time=now)
        ]
        return initial_len - len(self._scored_cache)

    def clear(self) -> None:
        """Clears score cache and deduplication state."""
        self._scored_cache.clear()
        self.deduplicator.clear()
