"""
CryptoPilot AI - Financial Sentiment Classification Pipeline.
Implements FinBERT transformer classification and high-throughput rule-based financial
lexicon classification with probabilistic softmax calibration.
"""

import math
import re
from abc import ABC, abstractmethod
from typing import Any

from cryptopilot.sentiment.models import SentimentLabel, SentimentScore


class BaseSentimentClassifier(ABC):
    """Abstract interface for sentiment classification models."""

    @abstractmethod
    def predict(self, text: str, article_id: str = "") -> SentimentScore:
        """Classifies text into bullish, bearish, or neutral probabilities."""
        pass


class RuleBasedFinancialSentimentClassifier(BaseSentimentClassifier):
    """
    High-throughput, deterministic financial lexicon sentiment classifier.
    Designed for zero-dependency execution and offline integration tests.
    """

    BULLISH_KEYWORDS: dict[str, float] = {
        "surge": 1.5,
        "breakout": 1.8,
        "rally": 1.5,
        "bullish": 1.8,
        "all-time high": 2.0,
        "ath": 1.8,
        "inflow": 1.2,
        "adoption": 1.3,
        "approval": 1.7,
        "approved": 1.7,
        "upgrade": 1.2,
        "gain": 1.0,
        "soar": 1.5,
        "jump": 1.2,
        "accumulate": 1.3,
        "accumulation": 1.3,
        "partnership": 1.2,
        "rebound": 1.1,
        "recovery": 1.1,
        "buy": 1.0,
    }

    BEARISH_KEYWORDS: dict[str, float] = {
        "crash": 2.0,
        "plunge": 1.8,
        "dump": 1.7,
        "bearish": 1.8,
        "drop": 1.0,
        "hack": 2.0,
        "exploit": 1.8,
        "scam": 1.8,
        "outflow": 1.3,
        "liquidation": 1.5,
        "ban": 1.8,
        "lawsuit": 1.6,
        "subpoena": 1.5,
        "fraud": 2.0,
        "slump": 1.3,
        "decline": 1.0,
        "bankruptcy": 2.0,
        "insolvent": 2.0,
        "sell": 1.0,
        "loss": 1.1,
    }

    NEGATIONS: set[str] = {"not", "never", "no", "fails", "failed", "unlikely", "neither"}

    def predict(self, text: str, article_id: str = "") -> SentimentScore:
        if not text or not text.strip():
            return SentimentScore(
                article_id=article_id,
                label=SentimentLabel.NEUTRAL,
                polarity=0.0,
                confidence=0.0,
                p_bullish=0.333,
                p_bearish=0.333,
                p_neutral=0.334,
            )

        words = re.findall(r"\b\w+\b", text.lower())
        pos_score = 0.0
        neg_score = 0.0

        for i, word in enumerate(words):
            is_negated = (i > 0 and words[i - 1] in self.NEGATIONS) or (
                i > 1 and words[i - 2] in self.NEGATIONS
            )

            if word in self.BULLISH_KEYWORDS:
                weight = self.BULLISH_KEYWORDS[word]
                if is_negated:
                    neg_score += weight
                else:
                    pos_score += weight

            elif word in self.BEARISH_KEYWORDS:
                weight = self.BEARISH_KEYWORDS[word]
                if is_negated:
                    pos_score += weight
                else:
                    neg_score += weight

        # Softmax normalization
        exp_pos = math.exp(min(5.0, pos_score))
        exp_neg = math.exp(min(5.0, neg_score))
        exp_neu = math.exp(1.0)  # Neutral baseline prior
        total_exp = exp_pos + exp_neg + exp_neu

        p_bullish = float(exp_pos / total_exp)
        p_bearish = float(exp_neg / total_exp)
        p_neutral = float(exp_neu / total_exp)

        # Polarity S = P(Bullish) - P(Bearish) in [-1.0, 1.0]
        polarity = float(np_clip(p_bullish - p_bearish, -1.0, 1.0))
        confidence = float(
            max(p_bullish, p_bearish, p_neutral) - min(p_bullish, p_bearish, p_neutral)
        )

        if polarity > 0.15:
            label = SentimentLabel.BULLISH
        elif polarity < -0.15:
            label = SentimentLabel.BEARISH
        else:
            label = SentimentLabel.NEUTRAL

        return SentimentScore(
            article_id=article_id,
            label=label,
            polarity=polarity,
            confidence=confidence,
            p_bullish=p_bullish,
            p_bearish=p_bearish,
            p_neutral=p_neutral,
        )


def np_clip(val: float, low: float, high: float) -> float:
    return max(low, min(high, val))


class FinBERTClassifier(BaseSentimentClassifier):
    """
    Adapter for FinBERT (ProsusAI/finbert).
    Gracefully falls back to RuleBasedFinancialSentimentClassifier if transformers is unavailable.
    """

    def __init__(
        self, model_name: str = "ProsusAI/finbert", fallback_if_missing: bool = True
    ) -> None:
        self.model_name = model_name
        self.fallback_if_missing = fallback_if_missing
        self._fallback = RuleBasedFinancialSentimentClassifier()
        self._pipeline: Any = None
        self._is_transformer_available: bool = False

        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                "text-classification", model=model_name, return_all_scores=True
            )
            self._is_transformer_available = True
        except (ImportError, Exception):
            self._is_transformer_available = False

    @property
    def is_transformer_active(self) -> bool:
        return self._is_transformer_available

    def predict(self, text: str, article_id: str = "") -> SentimentScore:
        if not self._is_transformer_available:
            return self._fallback.predict(text, article_id=article_id)

        try:
            # FinBERT labels: positive, negative, neutral
            results = self._pipeline(text[:512])[0]
            scores_map = {r["label"].lower(): float(r["score"]) for r in results}

            p_pos = scores_map.get("positive", 0.33)
            p_neg = scores_map.get("negative", 0.33)
            p_neu = scores_map.get("neutral", 0.34)

            polarity = float(np_clip(p_pos - p_neg, -1.0, 1.0))
            confidence = float(max(p_pos, p_neg, p_neu) - min(p_pos, p_neg, p_neu))

            if polarity > 0.15:
                label = SentimentLabel.BULLISH
            elif polarity < -0.15:
                label = SentimentLabel.BEARISH
            else:
                label = SentimentLabel.NEUTRAL

            return SentimentScore(
                article_id=article_id,
                label=label,
                polarity=polarity,
                confidence=confidence,
                p_bullish=p_pos,
                p_bearish=p_neg,
                p_neutral=p_neu,
            )
        except Exception:
            return self._fallback.predict(text, article_id=article_id)
