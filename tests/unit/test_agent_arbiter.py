"""
Tests for CryptoPilot AI - Central Autonomous Decision Arbiter.
"""

from datetime import UTC, datetime

import pytest

from cryptopilot.agent.arbiter import DecisionArbiter
from cryptopilot.agent.models import ArbitrationInput, MarketRegime
from cryptopilot.models.inference import MLPrediction
from cryptopilot.sentiment.models import AggregatedSentiment
from cryptopilot.strategies.base import SignalType, StrategySignal


def _make_signal(
    strategy_id: str,
    signal: SignalType,
    confidence: float,
    current_price: float = 50000.0,
    sl_ratio: float = 0.95,
    tp_ratio: float = 1.10,
) -> StrategySignal:
    sl = current_price * sl_ratio if signal == SignalType.BUY else current_price * (2 - sl_ratio)
    tp = current_price * tp_ratio if signal == SignalType.BUY else current_price * (2 - tp_ratio)
    return StrategySignal(
        strategy_id=strategy_id,
        symbol="BTC/USDT",
        signal=signal,
        confidence=confidence,
        entry_price=current_price,
        suggested_stop_loss=sl,
        suggested_take_profit=tp,
        rationale=f"Strategy {strategy_id} triggered {signal.value}",
        invalidation_condition="Opposing cross",
        timestamp=datetime.now(UTC),
    )


def test_arbiter_unanimous_buy():
    arbiter = DecisionArbiter()
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    signals = [
        _make_signal("ema_trend", SignalType.BUY, confidence=0.85, sl_ratio=0.96, tp_ratio=1.08),
        _make_signal("rsi_macd", SignalType.BUY, confidence=0.80, sl_ratio=0.95, tp_ratio=1.10),
        _make_signal(
            "multi_timeframe", SignalType.BUY, confidence=0.85, sl_ratio=0.97, tp_ratio=1.07
        ),
    ]

    ml = MLPrediction(
        symbol="BTC/USDT",
        horizon_bars=4,
        bullish_probability=0.75,
        confidence_score=0.80,
        cost_threshold=0.0045,
        is_bullish_edge=True,
        timestamp=now,
    )

    sent = AggregatedSentiment(
        symbol="BTC/USDT",
        sentiment_score=0.60,
        confidence=0.75,
        article_count=10,
        bullish_count=8,
        bearish_count=1,
        neutral_count=1,
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

    decision = arbiter.synthesize_decision(input_data)

    assert decision.symbol == "BTC/USDT"
    assert decision.action == SignalType.BUY
    assert decision.confidence > 0.70
    assert decision.composite_score > 0.50
    assert decision.suggested_stop_loss is not None
    assert decision.suggested_take_profit is not None
    assert decision.suggested_stop_loss < 50000.0
    assert decision.suggested_take_profit > 50000.0
    assert decision.risk_approved is False
    assert decision.rejection_reason is None
    assert "DECISION: BUY" in decision.explanation


def test_arbiter_unanimous_sell():
    arbiter = DecisionArbiter()
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    signals = [
        _make_signal("ema_trend", SignalType.SELL, confidence=0.80, sl_ratio=0.96, tp_ratio=1.08),
        _make_signal("rsi_macd", SignalType.SELL, confidence=0.75, sl_ratio=0.95, tp_ratio=1.10),
    ]

    ml = MLPrediction(
        symbol="BTC/USDT",
        horizon_bars=4,
        bullish_probability=0.20,  # Strongly bearish
        confidence_score=0.75,
        cost_threshold=0.0045,
        is_bullish_edge=False,
        timestamp=now,
    )

    sent = AggregatedSentiment(
        symbol="BTC/USDT",
        sentiment_score=-0.50,
        confidence=0.70,
        article_count=5,
        bullish_count=0,
        bearish_count=5,
        neutral_count=0,
        is_stale=False,
        timestamp=now,
    )

    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=signals,
        ml_prediction=ml,
        sentiment=sent,
        market_regime=MarketRegime.TRENDING_BEAR,
        timestamp=now,
    )

    decision = arbiter.synthesize_decision(input_data)

    assert decision.action == SignalType.SELL
    assert decision.confidence > 0.65
    assert decision.composite_score < -0.40
    assert decision.suggested_stop_loss is not None
    assert decision.suggested_take_profit is not None
    assert decision.suggested_stop_loss > 50000.0
    assert decision.suggested_take_profit < 50000.0
    assert "DECISION: SELL" in decision.explanation


def test_arbiter_contradiction_safety_veto():
    arbiter = DecisionArbiter()
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    # 1 strong BUY and 1 strong SELL
    signals = [
        _make_signal("ema_trend", SignalType.BUY, confidence=0.80),
        _make_signal("bollinger_reversion", SignalType.SELL, confidence=0.82),
    ]

    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=signals,
        market_regime=MarketRegime.RANGING,
        timestamp=now,
    )

    decision = arbiter.synthesize_decision(input_data)

    # Must be vetoed to HOLD
    assert decision.action == SignalType.HOLD
    assert decision.confidence == 0.0
    assert decision.suggested_stop_loss is None
    assert decision.suggested_take_profit is None
    assert decision.rejection_reason is not None
    assert "conflict" in decision.rejection_reason.lower()
    assert "SAFETY OVERRIDE" in decision.explanation


def test_arbiter_dynamic_reweighting_no_ml_no_sentiment():
    arbiter = DecisionArbiter()
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    # Only technical signals (no ML, no sentiment)
    signals = [
        _make_signal("ema_trend", SignalType.BUY, confidence=0.75, sl_ratio=0.96),
        _make_signal("volatility_momentum", SignalType.BUY, confidence=0.70, sl_ratio=0.95),
    ]

    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=signals,
        ml_prediction=None,
        sentiment=None,
        market_regime=MarketRegime.TRENDING_BULL,
        timestamp=now,
    )

    decision = arbiter.synthesize_decision(input_data)

    assert decision.action == SignalType.BUY
    assert decision.ml_bullish_prob is None
    assert decision.sentiment_polarity is None
    assert decision.technical_consensus_score > 0.0
    assert decision.composite_score == pytest.approx(decision.technical_consensus_score, abs=1e-3)


def test_arbiter_stale_data_veto():
    arbiter = DecisionArbiter()
    signals = [_make_signal("ema_trend", SignalType.BUY, confidence=0.90)]

    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=signals,
        is_data_stale=True,
    )

    decision = arbiter.synthesize_decision(input_data)
    assert decision.action == SignalType.HOLD
    assert decision.confidence == 0.0
    assert decision.rejection_reason is not None
    assert "stale" in decision.rejection_reason.lower()


def test_arbiter_neutral_hold_preliminary():
    arbiter = DecisionArbiter()
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    # Strategies vote HOLD
    signals = [
        StrategySignal(
            strategy_id="ema_trend",
            symbol="BTC/USDT",
            signal=SignalType.HOLD,
            confidence=0.50,
            entry_price=50000.0,
            suggested_stop_loss=48000.0,
            suggested_take_profit=54000.0,
            rationale="No clear trend",
            invalidation_condition="None",
            timestamp=now,
        )
    ]

    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=signals,
        timestamp=now,
    )

    decision = arbiter.synthesize_decision(input_data)
    assert decision.action == SignalType.HOLD
    assert decision.suggested_stop_loss is None
    assert decision.suggested_take_profit is None


def test_arbiter_discordance_penalty():
    arbiter = DecisionArbiter()
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    # Technicals bullish (+0.60), ML bearish (P=0.38)
    signals = [_make_signal("ema_trend", SignalType.BUY, confidence=0.70)]
    ml_discordant = MLPrediction(
        symbol="BTC/USDT",
        horizon_bars=4,
        bullish_probability=0.38,  # Negative ML polarity
        confidence_score=0.60,
        cost_threshold=0.0045,
        is_bullish_edge=False,
        timestamp=now,
    )

    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=signals,
        ml_prediction=ml_discordant,
        timestamp=now,
    )

    decision = arbiter.synthesize_decision(input_data)
    # Discordance penalizes confidence
    assert decision.action == SignalType.HOLD or decision.confidence < 0.60


def test_arbiter_fallback_price_targets():
    arbiter = DecisionArbiter()
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    # Signals with no take profit and invalid stop loss (sl >= current_price)
    signals = [
        StrategySignal(
            strategy_id="ema_trend",
            symbol="BTC/USDT",
            signal=SignalType.BUY,
            confidence=0.85,
            entry_price=50000.0,
            suggested_stop_loss=55000.0,  # Invalid: above entry price
            suggested_take_profit=None,  # No explicit TP
            rationale="Test fallback",
            invalidation_condition="None",
            timestamp=now,
        )
    ]

    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=signals,
        market_regime=MarketRegime.TRENDING_BULL,
        timestamp=now,
    )

    decision = arbiter.synthesize_decision(input_data)
    assert decision.action == SignalType.BUY
    # Fallback SL = 50000 * 0.97 = 48500.0
    assert decision.suggested_stop_loss == pytest.approx(48500.0, abs=1.0)
    # Fallback TP = 50000 + 2 * (50000 - 48500) = 53000.0
    assert decision.suggested_take_profit == pytest.approx(53000.0, abs=1.0)
