"""
Tests for CryptoPilot AI - Decision Explanation Generator.
"""

from datetime import UTC, datetime

from cryptopilot.agent.explainer import DecisionExplainer
from cryptopilot.agent.models import ArbitrationInput, MarketRegime
from cryptopilot.models.inference import MLPrediction
from cryptopilot.sentiment.models import AggregatedSentiment
from cryptopilot.strategies.base import SignalType, StrategySignal


def test_decision_explainer_buy_narrative():
    explainer = DecisionExplainer()
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    signals = [
        StrategySignal(
            strategy_id="ema_trend",
            symbol="BTC/USDT",
            signal=SignalType.BUY,
            confidence=0.80,
            entry_price=50000.0,
            suggested_stop_loss=48500.0,
            suggested_take_profit=53000.0,
            rationale="Fast EMA crossed slow EMA",
            invalidation_condition="Close < slow EMA",
            timestamp=now,
        ),
        StrategySignal(
            strategy_id="rsi_macd",
            symbol="BTC/USDT",
            signal=SignalType.BUY,
            confidence=0.75,
            entry_price=50000.0,
            suggested_stop_loss=48800.0,
            suggested_take_profit=52500.0,
            rationale="MACD bullish crossover",
            invalidation_condition="RSI > 75",
            timestamp=now,
        ),
    ]

    ml = MLPrediction(
        symbol="BTC/USDT",
        horizon_bars=4,
        bullish_probability=0.68,
        confidence_score=0.72,
        cost_threshold=0.0045,
        is_bullish_edge=True,
        top_contributing_features={"rsi_14": 0.45, "log_return_1h": 0.35},
        timestamp=now,
    )

    sent = AggregatedSentiment(
        symbol="BTC/USDT",
        sentiment_score=0.45,
        confidence=0.80,
        article_count=12,
        bullish_count=9,
        bearish_count=1,
        neutral_count=2,
        is_stale=False,
        timestamp=now,
    )

    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=signals,
        ml_prediction=ml,
        sentiment=sent,
        market_regime=MarketRegime.TRENDING_BULL,
        timestamp=now,
    )

    narrative = explainer.explain(
        action=SignalType.BUY,
        confidence=0.78,
        composite_score=0.65,
        input_data=input_data,
        regime=MarketRegime.TRENDING_BULL,
        technical_score=0.77,
    )

    assert "DECISION: BUY" in narrative
    assert "TRENDING_BULL" in narrative
    assert "2 BUY" in narrative
    assert "P(Bullish) = 68.0%" in narrative
    assert "Top Drivers: rsi_14" in narrative
    assert "Score = +0.45" in narrative


def test_decision_explainer_veto_narrative():
    explainer = DecisionExplainer()
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    input_data = ArbitrationInput(
        symbol="ETH/USDT",
        current_price=3000.0,
        strategy_signals=[],
        market_regime=MarketRegime.HIGH_VOLATILITY,
        timestamp=now,
    )

    narrative = explainer.explain(
        action=SignalType.HOLD,
        confidence=0.0,
        composite_score=0.0,
        input_data=input_data,
        regime=MarketRegime.HIGH_VOLATILITY,
        technical_score=0.0,
        veto_reason="Excessive spread (1.20% > max 0.50%).",
    )

    assert "DECISION: HOLD (SAFETY OVERRIDE)" in narrative
    assert "Safety Veto:" in narrative
    assert "Excessive spread" in narrative
    assert "HIGH_VOLATILITY" in narrative
    assert "No active strategy signals evaluated" in narrative
