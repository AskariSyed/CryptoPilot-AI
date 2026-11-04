"""
Tests for CryptoPilot AI - News Feed Adapters & Sentiment Engine Facade.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptopilot.sentiment.adapter import CryptoPanicAdapter, MockNewsAdapter
from cryptopilot.sentiment.engine import SentimentEngine
from cryptopilot.sentiment.models import NewsArticle


@pytest.mark.asyncio
async def test_mock_news_adapter():
    adapter = MockNewsAdapter()
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)

    adapter.add_article(
        article_id="art-1",
        title="Bitcoin breaks all time high",
        published_at=now - timedelta(hours=1),
    )
    adapter.add_article(
        article_id="art-2",
        title="Ethereum upgrade scheduled",
        published_at=now,
    )

    articles = await adapter.fetch_news(limit=1)
    assert len(articles) == 1
    # Sorted descending by published_at
    assert articles[0].article_id == "art-2"

    all_articles = await adapter.fetch_news(limit=10)
    assert len(all_articles) == 2


@pytest.mark.asyncio
async def test_cryptopanic_adapter_success():
    mock_payload = {
        "results": [
            {
                "id": 12345,
                "title": "Solana sets new active address record",
                "body": "Daily active addresses surpassed previous records.",
                "url": "https://cryptopanic.com/news/12345",
                "source": {"domain": "coindesk.com"},
                "published_at": "2026-11-04T10:00:00Z",
            },
            {
                "id": 12346,
                "title": "",  # Empty title should be skipped
                "body": "Empty",
                "published_at": "2026-11-04T10:05:00Z",
            },
        ]
    }

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_payload)
    mock_resp.__aenter__.return_value = mock_resp
    mock_resp.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp
    mock_session.closed = False
    mock_session.close = AsyncMock()

    adapter = CryptoPanicAdapter(auth_token="dummy_token", session=mock_session)
    articles = await adapter.fetch_news(symbols=["SOL/USDT"])

    assert len(articles) == 1
    assert articles[0].article_id == "12345"
    assert articles[0].title == "Solana sets new active address record"
    assert articles[0].source == "coindesk.com"


@pytest.mark.asyncio
async def test_cryptopanic_adapter_failure_fallback():
    mock_resp = AsyncMock()
    mock_resp.status = 500
    mock_resp.__aenter__.return_value = mock_resp
    mock_resp.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    adapter = CryptoPanicAdapter(session=mock_session)
    articles = await adapter.fetch_news()
    assert articles == []

    # Test exception fallback
    mock_session.get.side_effect = Exception("Network timeout")
    articles_err = await adapter.fetch_news()
    assert articles_err == []


@pytest.mark.asyncio
async def test_sentiment_engine_workflow():
    adapter = MockNewsAdapter()
    engine = SentimentEngine(adapter=adapter)

    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)

    # 1. Ingest batch of articles
    articles = [
        NewsArticle(
            article_id="btc-1",
            title="Bitcoin adoption accelerates across institutional treasuries",
            content="Massive accumulation observed in on-chain metrics.",
            published_at=now,
        ),
        NewsArticle(
            article_id="btc-2",
            title="Bitcoin adoption accelerates across institutional treasuries",  # Exact duplicate
            content="Duplicate content.",
            published_at=now,
        ),
        NewsArticle(
            article_id="sol-1",
            title="Solana outage causes network halt and investor panic",
            content="Validator downtime triggers sudden liquidation cascade.",
            published_at=now,
        ),
    ]

    new_count = engine.ingest_articles(articles, current_time=now)
    # 2 unique articles should be ingested (duplicate dropped)
    assert new_count == 2
    assert len(engine._scored_cache) == 2

    # 2. Analyze BTC
    btc_sentiment = engine.analyze_symbol("BTC/USDT", current_time=now)
    assert btc_sentiment.symbol == "BTC/USDT"
    assert btc_sentiment.sentiment_score > 0.0
    assert btc_sentiment.bullish_count == 1
    assert btc_sentiment.article_count == 1
    assert btc_sentiment.is_stale is False

    # 3. Analyze SOL
    sol_sentiment = engine.analyze_symbol("SOL/USDT", current_time=now)
    assert sol_sentiment.symbol == "SOL/USDT"
    assert sol_sentiment.sentiment_score < 0.0
    assert sol_sentiment.bearish_count == 1
    assert sol_sentiment.article_count == 1

    # 4. Analyze All
    all_sentiments = engine.analyze_all(
        symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        current_time=now,
    )
    assert "BTC/USDT" in all_sentiments
    assert "SOL/USDT" in all_sentiments
    assert "ETH/USDT" in all_sentiments
    assert all_sentiments["ETH/USDT"].article_count == 0  # No ETH news ingested

    # 5. Refresh from adapter
    adapter.add_article(
        article_id="eth-1",
        title="Ethereum network upgrade surges with record inflows",
        published_at=now,
    )
    refreshed = await engine.refresh_from_adapter(current_time=now)
    assert refreshed == 1
    eth_sentiment = engine.analyze_symbol("ETH/USDT", current_time=now)
    assert eth_sentiment.article_count == 1
    assert eth_sentiment.sentiment_score > 0.0

    # 6. Cache pruning of expired articles
    future_25h = now + timedelta(hours=25)
    pruned = engine.prune_cache(current_time=future_25h)
    assert pruned > 0
    assert len(engine._scored_cache) == 0

    # 7. Clear
    engine.clear()
    assert len(engine._scored_cache) == 0
