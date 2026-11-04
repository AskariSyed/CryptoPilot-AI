"""
Unit tests for cryptopilot.sentiment.relevance.AssetRelevanceFilter.
Covers: Keyword token matching, trading pair tagging, macro fallback, and relevance weights.
"""

from datetime import UTC, datetime

from cryptopilot.sentiment.models import NewsArticle
from cryptopilot.sentiment.relevance import AssetRelevanceFilter


class TestAssetRelevanceFilter:
    def test_tag_direct_asset_mentions(self) -> None:
        filter_ = AssetRelevanceFilter()
        now = datetime.now(UTC)

        art_btc = NewsArticle(
            article_id="1", title="Bitcoin Breaks $100K Barrier", published_at=now
        )
        tags_btc = filter_.tag_article(art_btc)
        assert tags_btc == ["BTC/USDT"]

        art_eth = NewsArticle(
            article_id="2", title="Ethereum Developers Propose Gas Limit Increase", published_at=now
        )
        tags_eth = filter_.tag_article(art_eth)
        assert tags_eth == ["ETH/USDT"]

        art_sol = NewsArticle(
            article_id="3", title="Solana DeFi Volume Surpasses Competitors", published_at=now
        )
        tags_sol = filter_.tag_article(art_sol)
        assert tags_sol == ["SOL/USDT"]

    def test_tag_multi_asset_and_macro_mentions(self) -> None:
        filter_ = AssetRelevanceFilter()
        now = datetime.now(UTC)

        # Mentions both BTC and ETH
        art_multi = NewsArticle(
            article_id="4",
            title="Bitcoin and Ethereum See Heavy Institutional Inflows",
            published_at=now,
        )
        tags_multi = filter_.tag_article(art_multi)
        assert set(tags_multi) == {"BTC/USDT", "ETH/USDT"}

        # Macro crypto headline tags all 3 monitored pairs
        art_macro = NewsArticle(
            article_id="5",
            title="SEC Issues New Guidelines on Digital Assets and Crypto Trading",
            published_at=now,
        )
        tags_macro = filter_.tag_article(art_macro)
        assert set(tags_macro) == {"BTC/USDT", "ETH/USDT", "SOL/USDT"}

        # Irrelevant non-crypto headline tags nothing
        art_irrelevant = NewsArticle(
            article_id="6",
            title="Global Crude Oil Inventories Rise Slightly This Quarter",
            published_at=now,
        )
        tags_none = filter_.tag_article(art_irrelevant)
        assert tags_none == []

    def test_calculate_relevance_weights(self) -> None:
        filter_ = AssetRelevanceFilter()
        now = datetime.now(UTC)

        # Title mention = 1.0
        art_title = NewsArticle(
            article_id="1", title="Bitcoin Miners Add Capacity", published_at=now
        )
        assert filter_.calculate_relevance(art_title, "BTC/USDT") == 1.0

        # Body mention = 0.70
        art_body = NewsArticle(
            article_id="2",
            title="Major Financial Firm Expands Crypto Desk",
            content="The firm announced support for Bitcoin spot custody.",
            published_at=now,
        )
        assert filter_.calculate_relevance(art_body, "BTC/USDT") == 0.70

        # Macro fallback = 0.35
        art_macro = NewsArticle(
            article_id="3", title="Binance Records Record Trading Volume", published_at=now
        )
        assert filter_.calculate_relevance(art_macro, "BTC/USDT") == 0.35

        # Irrelevant = 0.0
        art_none = NewsArticle(
            article_id="4", title="Tesla Reports Quarterly Revenue", published_at=now
        )
        assert filter_.calculate_relevance(art_none, "BTC/USDT") == 0.0

        # Threshold check
        assert filter_.is_relevant(art_title, "BTC/USDT", min_relevance=0.50) is True
        assert filter_.is_relevant(art_macro, "BTC/USDT", min_relevance=0.50) is False
