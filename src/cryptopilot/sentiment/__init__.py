"""
CryptoPilot AI - Sentiment Analysis Module.
Provides financial news ingestion, cryptographic deduplication, relevance tagging,
NLP/FinBERT sentiment scoring, exponential time decay, and asset sentiment aggregation.
"""

from cryptopilot.sentiment.adapter import BaseNewsAdapter, CryptoPanicAdapter, MockNewsAdapter
from cryptopilot.sentiment.aggregator import SentimentAggregator
from cryptopilot.sentiment.classifier import (
    BaseSentimentClassifier,
    FinBERTClassifier,
    RuleBasedFinancialSentimentClassifier,
)
from cryptopilot.sentiment.decay import ExponentialTimeDecay
from cryptopilot.sentiment.deduplicator import NewsDeduplicator
from cryptopilot.sentiment.engine import SentimentEngine
from cryptopilot.sentiment.models import (
    AggregatedSentiment,
    NewsArticle,
    SentimentLabel,
    SentimentScore,
)
from cryptopilot.sentiment.relevance import AssetRelevanceFilter

__all__ = [
    "AggregatedSentiment",
    "AssetRelevanceFilter",
    "BaseNewsAdapter",
    "BaseSentimentClassifier",
    "CryptoPanicAdapter",
    "ExponentialTimeDecay",
    "FinBERTClassifier",
    "MockNewsAdapter",
    "NewsArticle",
    "NewsDeduplicator",
    "RuleBasedFinancialSentimentClassifier",
    "SentimentAggregator",
    "SentimentEngine",
    "SentimentLabel",
    "SentimentScore",
]
