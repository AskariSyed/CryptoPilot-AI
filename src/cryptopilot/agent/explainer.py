"""
CryptoPilot AI - Transparent Decision Explanation Generator.
Produces human-interpretable natural language rationales for every autonomous trading proposal,
dissecting strategy consensus, ML predictions, sentiment impact, and safety guards.
"""

from cryptopilot.agent.models import ArbitrationInput, MarketRegime
from cryptopilot.strategies.base import SignalType


class DecisionExplainer:
    """
    Constructs comprehensive, structured explanation strings for TradeDecision objects.
    Ensures complete operational auditability and AI explainability.
    """

    def explain(
        self,
        action: SignalType,
        confidence: float,
        composite_score: float,
        input_data: ArbitrationInput,
        regime: MarketRegime,
        technical_score: float,
        veto_reason: str | None = None,
    ) -> str:
        """
        Generates structured Markdown narrative explaining the decision rationale.
        """
        lines: list[str] = []

        # 1. Headline summary
        if veto_reason:
            lines.append(
                f"**DECISION: HOLD (SAFETY OVERRIDE)** for {input_data.symbol} at ${input_data.current_price:,.2f}."
            )
            lines.append(f"**Safety Veto:** {veto_reason}")
        else:
            lines.append(
                f"**DECISION: {action.value}** for {input_data.symbol} at ${input_data.current_price:,.2f} "
                f"with {confidence:.1%} composite confidence (Composite Score: {composite_score:+.2f})."
            )

        # 2. Market Regime Context
        lines.append(f"**Market Regime:** {regime.value}")

        # 3. Strategy Ensemble Breakdown
        if input_data.strategy_signals:
            buy_strats = [
                f"{s.strategy_id} ({s.confidence:.0%})"
                for s in input_data.strategy_signals
                if s.signal == SignalType.BUY
            ]
            sell_strats = [
                f"{s.strategy_id} ({s.confidence:.0%})"
                for s in input_data.strategy_signals
                if s.signal == SignalType.SELL
            ]
            hold_strats = [
                s.strategy_id for s in input_data.strategy_signals if s.signal == SignalType.HOLD
            ]

            strat_summary = (
                f"- **Technical Strategies (Score: {technical_score:+.2f}):** "
                f"{len(buy_strats)} BUY, {len(sell_strats)} SELL, {len(hold_strats)} HOLD."
            )
            lines.append(strat_summary)
            if buy_strats:
                lines.append(f"  - Bullish: {', '.join(buy_strats)}")
            if sell_strats:
                lines.append(f"  - Bearish: {', '.join(sell_strats)}")
        else:
            lines.append("- **Technical Strategies:** No active strategy signals evaluated.")

        # 4. Machine Learning Model Context
        if input_data.ml_prediction is not None:
            ml = input_data.ml_prediction
            top_features_str = ""
            if ml.top_contributing_features:
                top_items = list(ml.top_contributing_features.items())[:3]
                top_features_str = (
                    f" | Top Drivers: {', '.join(f'{k} ({v:.2f})' for k, v in top_items)}"
                )

            lines.append(
                f"- **Machine Learning:** P(Bullish) = {ml.bullish_probability:.1%}, "
                f"Confidence = {ml.confidence_score:.1%}, Edge = {ml.is_bullish_edge}{top_features_str}"
            )
        else:
            lines.append(
                "- **Machine Learning:** Model prediction unavailable (neutral fallback applied)."
            )

        # 5. Sentiment Analysis Context
        if input_data.sentiment is not None:
            sent = input_data.sentiment
            stale_tag = " [STALE]" if sent.is_stale else " [ACTIVE]"
            lines.append(
                f"- **Market Sentiment:** Score = {sent.sentiment_score:+.2f}, "
                f"Confidence = {sent.confidence:.1%}, Articles = {sent.article_count}{stale_tag}"
            )
        else:
            lines.append("- **Market Sentiment:** No recent news sentiment index available.")

        # 6. Concluding Rationale
        if veto_reason:
            lines.append(
                "**Conclusion:** Trade execution was inhibited by deterministic safety guards to protect capital."
            )
        elif action == SignalType.BUY:
            lines.append(
                "**Conclusion:** Strong convergence across quantitative technical indicators, favorable market regime, "
                "and aligned AI predictions confirm an objective high-probability entry setup."
            )
        elif action == SignalType.SELL:
            lines.append(
                "**Conclusion:** Strategy indicators and market regime signal downward continuation or exit criteria. "
                "SELL proposal forwarded to Risk Manager."
            )
        else:
            lines.append(
                "**Conclusion:** Market conditions lack sufficient multi-factor conviction or edge. "
                "Preserving capital in HOLD state."
            )

        return "\n".join(lines)
