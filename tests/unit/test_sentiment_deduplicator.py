"""
Unit tests for cryptopilot.sentiment.deduplicator.NewsDeduplicator.
Covers: Content normalization, SHA-256 hash deduplication, fuzzy token similarity, and cache TTL.
"""

from datetime import UTC, datetime, timedelta

from cryptopilot.sentiment.deduplicator import NewsDeduplicator
from cryptopilot.sentiment.models import NewsArticle


class TestNewsDeduplicator:
    def test_normalize_title_and_hash(self) -> None:
        raw_title = "  Bitcoin  Surges   Past  $90,000!!  "
        normalized = NewsDeduplicator.normalize_title(raw_title)
        assert normalized == "bitcoin surges past 90 000"

        hash1 = NewsDeduplicator.compute_content_hash(raw_title)
        hash2 = NewsDeduplicator.compute_content_hash("bitcoin surges past $90,000")
        assert hash1 == hash2

    def test_exact_duplicate_detection(self) -> None:
        deduper = NewsDeduplicator()
        art1 = NewsArticle(
            article_id="1",
            title="SEC Approves Bitcoin ETF",
            published_at=datetime.now(UTC),
        )
        art2 = NewsArticle(
            article_id="2",
            title="sec approves bitcoin etf",  # Same title, different case
            published_at=datetime.now(UTC),
        )

        assert deduper.is_duplicate(art1) is False  # First seen -> unique
        assert deduper.is_duplicate(art2) is True  # Duplicate!

    def test_fuzzy_duplicate_detection_for_syndicated_wires(self) -> None:
        """Slight title rewrites from syndicates must be identified as duplicates."""
        deduper = NewsDeduplicator(fuzzy_threshold=0.75)
        art1 = NewsArticle(
            article_id="1",
            title="Ethereum Layer 2 TVL Hits New Record High This Week",
            published_at=datetime.now(UTC),
        )
        art2 = NewsArticle(
            article_id="2",
            title="Ethereum Layer 2 TVL Hits Record High This Week",  # Missing word 'New'
            published_at=datetime.now(UTC),
        )

        assert deduper.is_duplicate(art1) is False
        assert deduper.is_duplicate(art2) is True  # Fuzzy duplicate

    def test_deduplicate_batch(self) -> None:
        deduper = NewsDeduplicator()
        now = datetime.now(UTC)
        articles = [
            NewsArticle(article_id="1", title="Bitcoin Rally Continues", published_at=now),
            NewsArticle(article_id="2", title="Bitcoin Rally Continues", published_at=now),  # Dup
            NewsArticle(article_id="3", title="Solana Outperforms Ethereum", published_at=now),
            NewsArticle(article_id="4", title="Bitcoin Rally Continues!!", published_at=now),  # Dup
        ]
        unique = deduper.deduplicate_batch(articles)
        assert len(unique) == 2
        assert unique[0].article_id == "1"
        assert unique[1].article_id == "3"

    def test_cache_ttl_pruning(self) -> None:
        deduper = NewsDeduplicator(cache_ttl_hours=2.0)
        t0 = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)

        art1 = NewsArticle(article_id="1", title="First Story", published_at=t0)
        assert deduper.is_duplicate(art1, current_time=t0) is False

        # 3 hours later (past 2.0h TTL)
        t1 = t0 + timedelta(hours=3)
        purged = deduper.prune(current_time=t1)
        assert purged == 1

        # Now the same title should be treated as fresh again
        assert deduper.is_duplicate(art1, current_time=t1) is False

    def test_cache_max_size_eviction(self) -> None:
        deduper = NewsDeduplicator(max_cache_size=2)
        now = datetime.now(UTC)

        art1 = NewsArticle(article_id="1", title="Title One", published_at=now)
        art2 = NewsArticle(article_id="2", title="Title Two", published_at=now)
        art3 = NewsArticle(article_id="3", title="Title Three", published_at=now)

        deduper.is_duplicate(art1)
        deduper.is_duplicate(art2)
        # Adding third must evict oldest
        deduper.is_duplicate(art3)
        assert len(deduper._seen_hashes) == 2
