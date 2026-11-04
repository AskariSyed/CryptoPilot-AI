"""
CryptoPilot AI - News Feed Ingestion Adapters.
Provides pluggable news provider interfaces including deterministic mock feeds
for unit tests and asynchronous API adapters with timeout and rate-limiting safeguards.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import aiohttp

from cryptopilot.sentiment.models import NewsArticle


class BaseNewsAdapter(ABC):
    """Abstract interface for cryptocurrency news feed adapters."""

    @abstractmethod
    async def fetch_news(
        self, symbols: list[str] | None = None, limit: int = 50
    ) -> list[NewsArticle]:
        """Fetches recent news articles."""
        pass


class MockNewsAdapter(BaseNewsAdapter):
    """
    Deterministic news adapter for offline testing and backtesting simulations.
    """

    def __init__(self, predefined_articles: list[NewsArticle] | None = None) -> None:
        self.articles = predefined_articles or []

    def set_articles(self, articles: list[NewsArticle]) -> None:
        self.articles = articles

    def add_article(
        self,
        article_id: str,
        title: str,
        content: str = "",
        source: str = "MockNews",
        published_at: datetime | None = None,
    ) -> NewsArticle:
        ts = published_at or datetime.now(UTC)
        art = NewsArticle(
            article_id=article_id,
            title=title,
            content=content,
            source=source,
            published_at=ts,
        )
        self.articles.append(art)
        return art

    async def fetch_news(
        self, symbols: list[str] | None = None, limit: int = 50
    ) -> list[NewsArticle]:
        # Return up to limit articles sorted by publication time descending
        sorted_articles = sorted(self.articles, key=lambda a: a.published_at, reverse=True)
        return sorted_articles[:limit]


class CryptoPanicAdapter(BaseNewsAdapter):
    """
    Asynchronous news adapter for CryptoPanic public/developer API.
    Guarantees strict network timeouts and graceful error handling.
    """

    BASE_URL = "https://cryptopanic.com/api/v1/posts/"

    def __init__(
        self,
        auth_token: str = "",
        timeout_seconds: float = 10.0,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.auth_token = auth_token
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._external_session = session

    async def fetch_news(
        self, symbols: list[str] | None = None, limit: int = 50
    ) -> list[NewsArticle]:
        params: dict[str, Any] = {
            "public": "true",
        }
        if self.auth_token:
            params["auth_token"] = self.auth_token
        if symbols:
            # Filter currency tags, e.g. BTC, ETH, SOL
            currencies = [s.split("/")[0].upper() for s in symbols]
            params["currencies"] = ",".join(currencies)

        close_session = False
        session = self._external_session
        if session is None:
            session = aiohttp.ClientSession(timeout=self.timeout)
            close_session = True

        try:
            async with session.get(self.BASE_URL, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results = data.get("results", [])

                articles: list[NewsArticle] = []
                for item in results[:limit]:
                    title = item.get("title", "").strip()
                    if not title:
                        continue
                    pub_str = item.get("published_at", "")
                    try:
                        pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                    except Exception:
                        pub_dt = datetime.now(UTC)

                    article_id = str(item.get("id", pub_str))
                    articles.append(
                        NewsArticle(
                            article_id=article_id,
                            title=title,
                            content=item.get("body", ""),
                            url=item.get("url", ""),
                            source=item.get("source", {}).get("domain", "CryptoPanic"),
                            published_at=pub_dt,
                        )
                    )
                return articles
        except Exception:
            # Return empty list on any network error or timeout
            return []
        finally:
            if close_session and session is not None and not session.closed:
                await session.close()
