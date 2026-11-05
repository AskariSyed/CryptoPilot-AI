"""
CryptoPilot AI - Deterministic Safety Guard & Default-to-HOLD Invariant.
Enforces non-negotiable safety rules: stale market data veto, excessive spread veto,
strategy contradiction veto, low confidence veto, and ML contrarian veto.
"""

from cryptopilot.agent.models import ArbitrationInput, MarketRegime
from cryptopilot.strategies.base import SignalType


class SafetyGuard:
    """
    Evaluates proposed trades against deterministic safety constraints.
    Returns (is_approved: bool, veto_reason: str | None).
    """

    def __init__(
        self,
        max_spread_pct: float = 0.0050,  # 0.50% max spread
        min_confidence_threshold: float = 0.55,  # 55% minimum composite confidence
        high_volatility_min_confidence: float = 0.70,  # 70% confidence required in high vol
        ml_bearish_veto_prob: float = 0.35,  # Veto BUY if ML P(bullish) < 35%
        ml_bullish_veto_prob: float = 0.65,  # Veto SELL if ML P(bullish) > 65%
        strong_conflict_threshold: float = 0.65,  # Disagreement threshold
    ) -> None:
        self.max_spread_pct = max_spread_pct
        self.min_confidence_threshold = min_confidence_threshold
        self.high_volatility_min_confidence = high_volatility_min_confidence
        self.ml_bearish_veto_prob = ml_bearish_veto_prob
        self.ml_bullish_veto_prob = ml_bullish_veto_prob
        self.strong_conflict_threshold = strong_conflict_threshold

    def evaluate(
        self,
        input_data: ArbitrationInput,
        proposed_action: SignalType,
        confidence: float,
    ) -> tuple[bool, str | None]:
        """
        Validates safety invariants. If any invariant fails, returns (False, veto_reason).
        If proposed action is HOLD, safety passes immediately.
        """
        # HOLD is always safe
        if proposed_action == SignalType.HOLD:
            return True, None

        # 1. Stale Data Invariant
        if input_data.is_data_stale:
            return (
                False,
                "Market data feed is stale or exceeded maximum latency tolerance. Defaulting to HOLD.",
            )

        # 2. Excessive Bid/Ask Spread Invariant
        if input_data.bid_ask_spread_pct > self.max_spread_pct:
            return (
                False,
                f"Bid/ask spread ({input_data.bid_ask_spread_pct * 100:.2f}%) exceeds maximum limit "
                f"({self.max_spread_pct * 100:.2f}%). Defaulting to HOLD to avoid adverse execution.",
            )

        # 3. Missing Strategies Invariant
        if not input_data.strategy_signals:
            return (
                False,
                "No technical strategy signals provided. Defaulting to HOLD.",
            )

        # 4. Severe Contradiction Invariant
        has_strong_buy = any(
            s.signal == SignalType.BUY and s.confidence >= self.strong_conflict_threshold
            for s in input_data.strategy_signals
        )
        has_strong_sell = any(
            s.signal == SignalType.SELL and s.confidence >= self.strong_conflict_threshold
            for s in input_data.strategy_signals
        )
        if has_strong_buy and has_strong_sell:
            return (
                False,
                "Severe technical strategy conflict: simultaneous high-confidence BUY and SELL signals detected. Defaulting to HOLD.",
            )

        # 5. ML Contrarian Veto
        if input_data.ml_prediction is not None:
            p_bull = input_data.ml_prediction.bullish_probability
            if proposed_action == SignalType.BUY and p_bull < self.ml_bearish_veto_prob:
                return (
                    False,
                    f"Machine Learning model is strongly bearish (P(bullish)={p_bull:.1%} < {self.ml_bearish_veto_prob:.1%}). "
                    f"BUY recommendation vetoed by AI safety filter.",
                )
            if proposed_action == SignalType.SELL and p_bull > self.ml_bullish_veto_prob:
                return (
                    False,
                    f"Machine Learning model is strongly bullish (P(bullish)={p_bull:.1%} > {self.ml_bullish_veto_prob:.1%}). "
                    f"SELL recommendation vetoed by AI safety filter.",
                )

        # 6. Minimum Confidence Invariant
        if confidence < self.min_confidence_threshold:
            return (
                False,
                f"Composite confidence ({confidence:.1%}) is below minimum required threshold ({self.min_confidence_threshold:.1%}). "
                f"Defaulting to HOLD.",
            )

        # 7. High Volatility Regime Invariant
        if (
            input_data.market_regime == MarketRegime.HIGH_VOLATILITY
            and confidence < self.high_volatility_min_confidence
        ):
            return (
                False,
                f"Market regime is HIGH_VOLATILITY and composite confidence ({confidence:.1%}) "
                f"does not meet elevated hurdle ({self.high_volatility_min_confidence:.1%}). Defaulting to HOLD.",
            )

        return True, None
