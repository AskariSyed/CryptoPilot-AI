"""
CryptoPilot AI - Central Autonomous Decision Arbiter.
Combines rule-based strategy signals, ML continuation probabilities, market sentiment,
and regime classifications into deterministic, explainable trade proposals.
"""

import statistics
from datetime import UTC, datetime

from cryptopilot.agent.explainer import DecisionExplainer
from cryptopilot.agent.models import (
    ArbitrationInput,
    SignalWeights,
    TradeDecision,
)
from cryptopilot.agent.regime import MarketRegimeClassifier
from cryptopilot.agent.safety import SafetyGuard
from cryptopilot.strategies.base import SignalType, StrategySignal


class DecisionArbiter:
    """
    Central Decision Arbiter synthesizing technical indicators, machine learning,
    and market sentiment with regime adaptation and deterministic default-to-HOLD safety.
    """

    def __init__(
        self,
        weights: SignalWeights | None = None,
        regime_classifier: MarketRegimeClassifier | None = None,
        safety_guard: SafetyGuard | None = None,
        explainer: DecisionExplainer | None = None,
        buy_threshold: float = 0.25,
        sell_threshold: float = -0.25,
    ) -> None:
        self.weights = weights or SignalWeights()
        self.regime_classifier = regime_classifier or MarketRegimeClassifier()
        self.safety_guard = safety_guard or SafetyGuard()
        self.explainer = explainer or DecisionExplainer()
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def synthesize_decision(self, input_data: ArbitrationInput) -> TradeDecision:
        """
        Executes multi-factor arbitration across technical, ML, and sentiment inputs.
        Guarantees strict safety invariants and returns a fully explained TradeDecision.
        """
        regime = input_data.market_regime
        regime_multipliers = self.regime_classifier.get_strategy_multipliers(regime)

        # 1. Technical Strategy Ensemble Scoring
        tech_score, tech_conf = self._calculate_technical_score(
            input_data.strategy_signals, regime_multipliers
        )

        # 2. Machine Learning Model Scoring
        ml_score, ml_conf = self._calculate_ml_score(input_data)

        # 3. Market Sentiment Scoring
        sent_score, sent_conf = self._calculate_sentiment_score(input_data)

        # 4. Effective Weight Allocation (dynamic reweighting for missing/stale streams)
        w_tech, w_ml, w_sent = self._resolve_weights(input_data)

        # 5. Composite Polarity Score Calculation
        composite_score = (w_tech * tech_score) + (w_ml * ml_score) + (w_sent * sent_score)
        composite_score = max(-1.0, min(1.0, composite_score))

        # 6. Composite Confidence Calculation
        composite_conf = (w_tech * tech_conf) + (w_ml * ml_conf) + (w_sent * sent_conf)

        # Multi-factor alignment boost or conflict penalty
        if (tech_score > 0 and ml_score > 0) or (tech_score < 0 and ml_score < 0):
            # Concordance between technicals and ML boosts conviction
            composite_conf = min(1.0, composite_conf * 1.15)
        elif (tech_score > 0 and ml_score < 0) or (tech_score < 0 and ml_score > 0):
            # Discordance penalizes conviction
            composite_conf = composite_conf * 0.70

        composite_conf = max(0.0, min(1.0, composite_conf))

        # 7. Preliminary Action Determination
        # Requirement: BUY requires positive composite score and non-negative technicals
        # SELL requires negative composite score and non-positive technicals
        if composite_score >= self.buy_threshold and tech_score > 0.0:
            preliminary_action = SignalType.BUY
        elif composite_score <= self.sell_threshold and tech_score < 0.0:
            preliminary_action = SignalType.SELL
        else:
            preliminary_action = SignalType.HOLD

        # 8. Deterministic Safety Guard Verification
        is_safe, veto_reason = self.safety_guard.evaluate(
            input_data=input_data,
            proposed_action=preliminary_action,
            confidence=composite_conf,
        )

        final_action = preliminary_action if is_safe else SignalType.HOLD
        final_confidence = composite_conf if is_safe else 0.0

        # 9. Derive Consensus Stop-Loss & Take-Profit Targets
        suggested_sl, suggested_tp = self._derive_price_targets(
            action=final_action,
            current_price=input_data.current_price,
            signals=input_data.strategy_signals,
        )

        # 10. Generate Transparent Explanation
        explanation = self.explainer.explain(
            action=final_action,
            confidence=final_confidence,
            composite_score=composite_score,
            input_data=input_data,
            regime=regime,
            technical_score=tech_score,
            veto_reason=veto_reason,
        )

        return TradeDecision(
            symbol=input_data.symbol,
            action=final_action,
            confidence=final_confidence,
            suggested_entry_price=input_data.current_price,
            suggested_stop_loss=suggested_sl,
            suggested_take_profit=suggested_tp,
            market_regime=regime,
            strategy_signals=input_data.strategy_signals,
            technical_consensus_score=tech_score,
            ml_bullish_prob=(
                input_data.ml_prediction.bullish_probability
                if input_data.ml_prediction is not None
                else None
            ),
            sentiment_polarity=(
                input_data.sentiment.sentiment_score if input_data.sentiment is not None else None
            ),
            composite_score=composite_score,
            explanation=explanation,
            risk_approved=False,
            rejection_reason=veto_reason,
            timestamp=input_data.timestamp or datetime.now(UTC),
        )

    def _calculate_technical_score(
        self,
        signals: list[StrategySignal],
        regime_multipliers: dict[str, float],
    ) -> tuple[float, float]:
        """Calculates regime-weighted technical consensus polarity [-1, 1] and confidence."""
        if not signals:
            return 0.0, 0.0

        total_weight = 0.0
        weighted_polarity_sum = 0.0
        weighted_conf_sum = 0.0

        for sig in signals:
            w = regime_multipliers.get(sig.strategy_id, 1.0)
            if sig.signal == SignalType.BUY:
                pol = 1.0
            elif sig.signal == SignalType.SELL:
                pol = -1.0
            else:
                pol = 0.0

            weighted_polarity_sum += pol * sig.confidence * w
            weighted_conf_sum += sig.confidence * w
            total_weight += w

        if total_weight <= 0.0:
            return 0.0, 0.0

        score = max(-1.0, min(1.0, weighted_polarity_sum / total_weight))
        conf = max(0.0, min(1.0, weighted_conf_sum / total_weight))
        return score, conf

    def _calculate_ml_score(self, input_data: ArbitrationInput) -> tuple[float, float]:
        """Translates ML bullish probability to polarity score [-1, 1] and confidence."""
        if input_data.ml_prediction is None:
            return 0.0, 0.0

        ml = input_data.ml_prediction
        # P in [0, 1] -> Polarity in [-1, 1]
        score = float(max(-1.0, min(1.0, 2.0 * (ml.bullish_probability - 0.50))))
        conf = float(ml.confidence_score)
        return score, conf

    def _calculate_sentiment_score(self, input_data: ArbitrationInput) -> tuple[float, float]:
        """Translates sentiment index into polarity score [-1, 1] and confidence."""
        if input_data.sentiment is None or input_data.sentiment.is_stale:
            return 0.0, 0.0

        sent = input_data.sentiment
        score = float(max(-1.0, min(1.0, sent.sentiment_score)))
        conf = float(sent.confidence)
        return score, conf

    def _resolve_weights(self, input_data: ArbitrationInput) -> tuple[float, float, float]:
        """
        Dynamically adjusts signal weights when ML or Sentiment data is absent,
        preserving a normalized total weight of 1.0.
        """
        has_ml = input_data.ml_prediction is not None
        has_sent = input_data.sentiment is not None and not input_data.sentiment.is_stale

        w_tech = self.weights.weight_technical
        w_ml = self.weights.weight_ml if has_ml else 0.0
        w_sent = self.weights.weight_sentiment if has_sent else 0.0

        total = w_tech + w_ml + w_sent
        if total <= 0.0:
            return 1.0, 0.0, 0.0

        return w_tech / total, w_ml / total, w_sent / total

    def _derive_price_targets(
        self,
        action: SignalType,
        current_price: float,
        signals: list[StrategySignal],
    ) -> tuple[float | None, float | None]:
        """
        Extracts consensus Stop-Loss and Take-Profit targets from agreeing strategy signals.
        """
        if action == SignalType.HOLD:
            return None, None

        if action == SignalType.BUY:
            agreeing = [
                s
                for s in signals
                if s.signal == SignalType.BUY and s.suggested_stop_loss < current_price
            ]
            if agreeing:
                # Use conservative median stop-loss level
                sl_candidates = [s.suggested_stop_loss for s in agreeing]
                stop_loss = float(statistics.median(sl_candidates))
            else:
                # Fallback to standard 3% risk distance
                stop_loss = current_price * 0.97

            # Derive take profit (median of valid targets or 2:1 risk-reward)
            tp_candidates = [
                s.suggested_take_profit
                for s in agreeing
                if s.suggested_take_profit is not None and s.suggested_take_profit > current_price
            ]
            if tp_candidates:
                take_profit = float(statistics.median(tp_candidates))
            else:
                risk_dist = current_price - stop_loss
                take_profit = current_price + (2.0 * risk_dist)

            return round(stop_loss, 4), round(take_profit, 4)

        elif action == SignalType.SELL:
            agreeing = [
                s
                for s in signals
                if s.signal == SignalType.SELL and s.suggested_stop_loss > current_price
            ]
            if agreeing:
                sl_candidates = [s.suggested_stop_loss for s in agreeing]
                stop_loss = float(statistics.median(sl_candidates))
            else:
                stop_loss = current_price * 1.03

            tp_candidates = [
                s.suggested_take_profit
                for s in agreeing
                if s.suggested_take_profit is not None and s.suggested_take_profit < current_price
            ]
            if tp_candidates:
                take_profit = float(statistics.median(tp_candidates))
            else:
                risk_dist = stop_loss - current_price
                take_profit = current_price - (2.0 * risk_dist)

            return round(stop_loss, 4), round(take_profit, 4)

        return None, None
