"""
Tests for CryptoPilot AI - Autonomous Decision Engine Domain Models.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cryptopilot.agent.models import (
    ArbitrationInput,
    MarketRegime,
    SignalWeights,
    TradeDecision,
)
from cryptopilot.strategies.base import SignalType


def test_market_regime_enum_values():
    assert MarketRegime.TRENDING_BULL == "TRENDING_BULL"
    assert MarketRegime.TRENDING_BEAR == "TRENDING_BEAR"
    assert MarketRegime.RANGING == "RANGING"
    assert MarketRegime.HIGH_VOLATILITY == "HIGH_VOLATILITY"
    assert MarketRegime.UNKNOWN == "UNKNOWN"


def test_signal_weights_default_and_normalization():
    # Default weights: 0.50, 0.35, 0.15 sum to 1.0
    sw = SignalWeights()
    assert sw.weight_technical == pytest.approx(0.50, abs=1e-5)
    assert sw.weight_ml == pytest.approx(0.35, abs=1e-5)
    assert sw.weight_sentiment == pytest.approx(0.15, abs=1e-5)

    # Custom unnormalized weights should be automatically normalized
    sw_custom = SignalWeights(weight_technical=2.0, weight_ml=1.0, weight_sentiment=1.0)
    assert sw_custom.weight_technical == pytest.approx(0.50, abs=1e-5)
    assert sw_custom.weight_ml == pytest.approx(0.25, abs=1e-5)
    assert sw_custom.weight_sentiment == pytest.approx(0.25, abs=1e-5)


def test_signal_weights_invalid_total():
    with pytest.raises(ValidationError, match="Total weights must sum to greater than 0.0"):
        SignalWeights(weight_technical=0.0, weight_ml=0.0, weight_sentiment=0.0)


def test_arbitration_input_defaults_and_utc():
    now_naive = datetime(2026, 11, 5, 12, 0, 0)
    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        timestamp=now_naive,
    )
    assert input_data.symbol == "BTC/USDT"
    assert input_data.current_price == 50000.0
    assert input_data.timestamp.tzinfo == UTC
    assert input_data.strategy_signals == []
    assert input_data.ml_prediction is None
    assert input_data.sentiment is None
    assert input_data.market_regime == MarketRegime.UNKNOWN
    assert input_data.bid_ask_spread_pct == 0.0
    assert input_data.is_data_stale is False


def test_trade_decision_model_fields_and_validation():
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)
    decision = TradeDecision(
        symbol="ETH/USDT",
        action=SignalType.BUY,
        confidence=0.82,
        suggested_entry_price=3000.0,
        suggested_stop_loss=2850.0,
        suggested_take_profit=3300.0,
        market_regime=MarketRegime.TRENDING_BULL,
        technical_consensus_score=0.75,
        composite_score=0.70,
        explanation="Test explanation",
        timestamp=now,
    )
    assert decision.symbol == "ETH/USDT"
    assert decision.action == SignalType.BUY
    assert decision.confidence == 0.82
    assert decision.suggested_stop_loss == 2850.0
    assert decision.suggested_take_profit == 3300.0
    assert len(decision.decision_id) > 10
    assert decision.risk_approved is False
    assert decision.rejection_reason is None
