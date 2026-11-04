"""
CryptoPilot AI - Asset Relevance Tagging & Filtering.
Maps headline and article content to target cryptocurrency trading pairs
(BTC/USDT, ETH/USDT, SOL/USDT) using boundary-aware regex patterns and keyword weighting.
"""

import re

from cryptopilot.sentiment.models import NewsArticle


class AssetRelevanceFilter:
    """
    Identifies asset mentions and assigns relevance scores for BTC, ETH, and SOL.
    """

    ASSET_PATTERNS: dict[str, list[re.Pattern]] = {
        "BTC/USDT": [
            re.compile(r"\b(btc|bitcoin|satoshi|xbt)\b", re.IGNORECASE),
        ],
        "ETH/USDT": [
            re.compile(r"\b(eth|ethereum|ether|vitalik)\b", re.IGNORECASE),
        ],
        "SOL/USDT": [
            re.compile(r"\b(sol|solana)\b", re.IGNORECASE),
        ],
    }

    # Macro crypto patterns relevant across all top assets
    MACRO_PATTERNS: list[re.Pattern] = [
        re.compile(
            r"\b(crypto|cryptocurrency|digital assets|altcoins|sec|etf|binance|coinbase)\b",
            re.IGNORECASE,
        ),
    ]

    def tag_article(self, article: NewsArticle) -> list[str]:
        """
        Scans title and content, populates article.symbols_mentioned with matching trading pairs.
        """
        text = f"{article.title} {article.content}"
        matches: list[str] = []

        for symbol, patterns in self.ASSET_PATTERNS.items():
            if any(p.search(text) for p in patterns):
                matches.append(symbol)

        # If no specific coin is mentioned, check for macro crypto relevance
        if not matches and any(p.search(text) for p in self.MACRO_PATTERNS):
            # General market news tags all monitored assets
            matches = list(self.ASSET_PATTERNS.keys())

        article.symbols_mentioned = matches
        return matches

    def calculate_relevance(self, article: NewsArticle, target_symbol: str) -> float:
        """
        Calculates a relevance weight in [0.0, 1.0] for the target symbol:
        - 1.0: Target symbol explicitly mentioned in headline title.
        - 0.7: Target symbol mentioned in content body.
        - 0.35: General macro crypto news (no specific asset named).
        - 0.0: Irrelevant to target symbol.
        """
        patterns = self.ASSET_PATTERNS.get(target_symbol, [])
        if not patterns:
            return 0.0

        # Title mention (highest relevance)
        if any(p.search(article.title) for p in patterns):
            return 1.0

        # Body mention
        if any(p.search(article.content) for p in patterns):
            return 0.70

        # Macro fallback
        full_text = f"{article.title} {article.content}"
        if any(p.search(full_text) for p in self.MACRO_PATTERNS):
            return 0.35

        return 0.0

    def is_relevant(
        self, article: NewsArticle, target_symbol: str, min_relevance: float = 0.30
    ) -> bool:
        """Returns True if article meets minimum relevance threshold for target symbol."""
        return self.calculate_relevance(article, target_symbol) >= min_relevance
