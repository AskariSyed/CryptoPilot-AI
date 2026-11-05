"""
Tests for CryptoPilot AI - Decision Safety Guard.
"""

from datetime import UTC, datetime

from cryptopilot.agent.models import ArbitrationInput, MarketRegime
from cryptopilot.agent.safety import SafetyGuard
from cryptopilot.models.inference import MLPrediction
from cryptopilot.strategies.base import SignalType, StrategySignal


def _create_signal(
    strategy_id: str,
    signal: SignalType,
    confidence: float,
    current_price: float = 50000.0,
) -> StrategySignal:
    return StrategySignal(
        strategy_id=strategy_id,
        symbol="BTC/USDT",
        signal=signal,
        confidence=confidence,
        entry_price=current_price,
        suggested_stop_loss=current_price * 0.95
        if signal == SignalType.BUY
        else current_price * 1.05,
        suggested_take_profit=current_price * 1.10
        if signal == SignalType.BUY
        else current_price * 0.90,
        rationale=f"Rationale for {strategy_id}",
        invalidation_condition="None",
        timestamp=datetime.now(UTC),
    )


def test_safety_guard_hold_always_approved():
    guard = SafetyGuard()
    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        is_data_stale=True,  # Even with stale data, HOLD is safe
    )
    is_safe, reason = guard.evaluate(input_data, SignalType.HOLD, confidence=0.0)
    assert is_safe is True
    assert reason is None


def test_safety_guard_stale_data_veto():
    guard = SafetyGuard()
    sig = _create_signal("ema_trend", SignalType.BUY, confidence=0.80)
    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=[sig],
        is_data_stale=True,
    )
    is_safe, reason = guard.evaluate(input_data, SignalType.BUY, confidence=0.80)
    assert is_safe is False
    assert reason is not None
    assert "stale" in reason.lower()


def test_safety_guard_excessive_spread_veto():
    guard = SafetyGuard(max_spread_pct=0.0050)
    sig = _create_signal("ema_trend", SignalType.BUY, confidence=0.80)
    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=[sig],
        bid_ask_spread_pct=0.0080,  # 0.8% > 0.5%
    )
    is_safe, reason = guard.evaluate(input_data, SignalType.BUY, confidence=0.80)
    assert is_safe is False
    assert reason is not None
    assert "spread" in reason.lower()


def test_safety_guard_missing_signals_veto():
    guard = SafetyGuard()
    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=[],
    )
    is_safe, reason = guard.evaluate(input_data, SignalType.BUY, confidence=0.80)
    assert is_safe is False
    assert reason is not None
    assert "no technical strategy signals" in reason.lower()


def test_safety_guard_severe_contradiction_veto():
    guard = SafetyGuard(strong_conflict_threshold=0.65)
    sig_buy = _create_signal("ema_trend", SignalType.BUY, confidence=0.75)
    sig_sell = _create_signal("bollinger_reversion", SignalType.SELL, confidence=0.72)

    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=[sig_buy, sig_sell],
    )
    is_safe, reason = guard.evaluate(input_data, SignalType.BUY, confidence=0.70)
    assert is_safe is False
    assert reason is not None
    assert "conflict" in reason.lower()


def test_safety_guard_ml_contrarian_veto():
    guard = SafetyGuard(ml_bearish_veto_prob=0.35, ml_bullish_veto_prob=0.65)
    sig_buy = _create_signal("ema_trend", SignalType.BUY, confidence=0.75)

    # ML is strongly bearish (P=0.20 < 0.35)
    ml_bearish = MLPrediction(
        symbol="BTC/USDT",
        horizon_bars=4,
        bullish_probability=0.20,
        confidence_score=0.60,
        cost_threshold=0.0045,
        is_bullish_edge=False,
        timestamp=datetime.now(UTC),
    )
    input_data = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=[sig_buy],
        ml_prediction=ml_bearish,
    )
    is_safe, reason = guard.evaluate(input_data, SignalType.BUY, confidence=0.70)
    assert is_safe is False
    assert reason is not None
    assert "machine learning model is strongly bearish" in reason.lower()

    # ML is strongly bullish (P=0.80 > 0.65) but proposed action is SELL
    sig_sell = _create_signal("ema_trend", SignalType.SELL, confidence=0.75)
    ml_bullish = MLPrediction(
        symbol="BTC/USDT",
        horizon_bars=4,
        bullish_probability=0.80,
        confidence_score=0.60,
        cost_threshold=0.0045,
        is_bullish_edge=True,
        timestamp=datetime.now(UTC),
    )
    input_data_sell = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=[sig_sell],
        ml_prediction=ml_bullish,
    )
    is_safe_sell, reason_sell = guard.evaluate(input_data_sell, SignalType.SELL, confidence=0.70)
    assert is_safe_sell is False
    assert reason_sell is not None
    assert "machine learning model is strongly bullish" in reason_sell.lower()


def test_safety_guard_low_confidence_and_high_volatility():
    guard = SafetyGuard(min_confidence_threshold=0.55, high_volatility_min_confidence=0.70)
    sig = _create_signal("ema_trend", SignalType.BUY, confidence=0.60)

    # Low confidence (< 0.55)
    input_normal = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=[sig],
        market_regime=MarketRegime.TRENDING_BULL,
    )
    is_safe_low, reason_low = guard.evaluate(input_normal, SignalType.BUY, confidence=0.50)
    assert is_safe_low is False
    assert "below minimum required threshold" in reason_low.lower()

    # Normal confidence in HIGH_VOLATILITY (< 0.70)
    input_vol = ArbitrationInput(
        symbol="BTC/USDT",
        current_price=50000.0,
        strategy_signals=[sig],
        market_regime=MarketRegime.HIGH_VOLATILITY,
    )
    is_safe_vol, reason_vol = guard.evaluate(input_vol, SignalType.BUY, confidence=0.62)
    assert is_safe_vol is False
    assert "high_volatility" in reason_vol.lower()

    # Sufficient confidence in HIGH_VOLATILITY (>= 0.70)
    is_safe_vol_ok, reason_vol_ok = guard.evaluate(input_vol, SignalType.BUY, confidence=0.75)
    assert is_safe_vol_ok is True
    assert reason_vol_ok is None
