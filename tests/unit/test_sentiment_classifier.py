"""
Unit tests for cryptopilot.sentiment.classifier.
Covers: Rule-based lexicon classifier, negation flipping, polarity scoring, and FinBERT fallback.
"""

from cryptopilot.sentiment.classifier import (
    FinBERTClassifier,
    RuleBasedFinancialSentimentClassifier,
)
from cryptopilot.sentiment.models import SentimentLabel


class TestSentimentClassifier:
    def test_rule_based_strong_bullish_text(self) -> None:
        classifier = RuleBasedFinancialSentimentClassifier()
        text = "Bitcoin surges past previous all-time high with massive institutional approval and adoption"
        score = classifier.predict(text, article_id="bull_1")

        assert score.label == SentimentLabel.BULLISH
        assert score.polarity > 0.30
        assert score.p_bullish > score.p_bearish
        assert score.confidence > 0.0

    def test_rule_based_strong_bearish_text(self) -> None:
        classifier = RuleBasedFinancialSentimentClassifier()
        text = "Major crypto exchange suffers catastrophic exploit and liquidation crash, filing bankruptcy"
        score = classifier.predict(text, article_id="bear_1")

        assert score.label == SentimentLabel.BEARISH
        assert score.polarity < -0.30
        assert score.p_bearish > score.p_bullish

    def test_rule_based_negation_handling(self) -> None:
        classifier = RuleBasedFinancialSentimentClassifier()

        # "not bullish" must invert positive weight
        score_negated = classifier.predict("Bitcoin is not bullish today", article_id="neg_1")
        assert score_negated.polarity < 0.0

        # "failed breakout" must register bearish
        score_failed = classifier.predict(
            "Ethereum failed breakout after resistance rejection", article_id="neg_2"
        )
        assert score_failed.polarity < 0.0

    def test_rule_based_neutral_and_empty_text(self) -> None:
        classifier = RuleBasedFinancialSentimentClassifier()

        # Neutral informational headline
        score_neu = classifier.predict(
            "Bitcoin network mining difficulty adjusts every two weeks", article_id="neu_1"
        )
        assert score_neu.label == SentimentLabel.NEUTRAL
        assert abs(score_neu.polarity) <= 0.15

        # Empty text fallback
        score_empty = classifier.predict("", article_id="empty_1")
        assert score_empty.label == SentimentLabel.NEUTRAL
        assert score_empty.polarity == 0.0
        assert score_empty.confidence == 0.0

    def test_finbert_classifier_graceful_fallback(self) -> None:
        """When transformers library is absent, FinBERTClassifier uses rule-based fallback without crashing."""
        classifier = FinBERTClassifier()
        # Even if pipeline is not installed, predict must execute cleanly
        score = classifier.predict(
            "Solana rally continues with heavy buying pressure", article_id="fb_1"
        )
        assert score.label == SentimentLabel.BULLISH
        assert score.polarity > 0.0
