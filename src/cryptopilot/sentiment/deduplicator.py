"""
CryptoPilot AI - News Content Deduplication Engine.
Eliminates syndicated and duplicate wire news stories using SHA-256 cryptographic
content hashing and fuzzy token-similarity matching.
"""

import hashlib
import re
from datetime import UTC, datetime, timedelta

from cryptopilot.sentiment.models import NewsArticle


class NewsDeduplicator:
    """
    Deduplicates news feeds using SHA-256 cryptographic hashes of normalized titles
    and Jaccard token similarity for syndicated rewrites.
    """

    def __init__(
        self,
        fuzzy_threshold: float = 0.80,
        cache_ttl_hours: float = 24.0,
        max_cache_size: int = 10000,
    ) -> None:
        self.fuzzy_threshold = min(1.0, max(0.1, fuzzy_threshold))
        self.cache_ttl = timedelta(hours=max(1.0, cache_ttl_hours))
        self.max_cache_size = max(1, max_cache_size)

        # Cache: hash -> (normalized_tokens_set, insertion_timestamp)
        self._seen_hashes: dict[str, tuple[set[str], datetime]] = {}

    @classmethod
    def normalize_title(cls, title: str) -> str:
        """Lowercases, removes punctuation, and condenses whitespace."""
        cleaned = re.sub(r"[^\w\s]", " ", title.lower())
        return " ".join(cleaned.split())

    @classmethod
    def compute_content_hash(cls, title: str) -> str:
        """Computes SHA-256 hash of normalized title."""
        normalized = cls.normalize_title(title)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _tokenize(self, text: str) -> set[str]:
        """Extracts token set for fuzzy matching."""
        normalized = self.normalize_title(text)
        return set(normalized.split())

    def _jaccard_similarity(self, set_a: set[str], set_b: set[str]) -> float:
        """Computes Jaccard similarity coefficient between two token sets."""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return float(intersection / union) if union > 0 else 0.0

    def is_duplicate(self, article: NewsArticle, current_time: datetime | None = None) -> bool:
        """
        Determines whether an article is an exact or fuzzy duplicate of a recently seen headline.
        If not duplicate, registers the article in the deduplication cache.
        """
        now = current_time or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        self.prune(now)

        content_hash = self.compute_content_hash(article.title)
        article.content_hash = content_hash

        # 1. Exact SHA-256 Hash Match
        if content_hash in self._seen_hashes:
            return True

        # 2. Fuzzy Token Similarity Match
        article_tokens = self._tokenize(article.title)
        if len(article_tokens) >= 3:
            for cached_tokens, _entry_time in self._seen_hashes.values():
                sim = self._jaccard_similarity(article_tokens, cached_tokens)
                if sim >= self.fuzzy_threshold:
                    return True

        # Not duplicate: register in cache
        if len(self._seen_hashes) >= self.max_cache_size:
            # Evict oldest entry
            oldest_key = min(self._seen_hashes.keys(), key=lambda k: self._seen_hashes[k][1])
            self._seen_hashes.pop(oldest_key, None)

        self._seen_hashes[content_hash] = (article_tokens, now)
        return False

    def deduplicate_batch(
        self,
        articles: list[NewsArticle],
        current_time: datetime | None = None,
    ) -> list[NewsArticle]:
        """Filters a list of articles, returning only unique, non-duplicate items."""
        now = current_time or datetime.now(UTC)
        unique_articles: list[NewsArticle] = []
        for article in articles:
            if not self.is_duplicate(article, current_time=now):
                unique_articles.append(article)
        return unique_articles

    def prune(self, current_time: datetime | None = None) -> int:
        """Purges cache entries older than cache_ttl. Returns number of purged items."""
        now = current_time or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        cutoff = now - self.cache_ttl
        expired_keys = [k for k, (_tokens, t) in self._seen_hashes.items() if t < cutoff]
        for k in expired_keys:
            self._seen_hashes.pop(k, None)
        return len(expired_keys)

    def clear(self) -> None:
        """Clears cache."""
        self._seen_hashes.clear()
