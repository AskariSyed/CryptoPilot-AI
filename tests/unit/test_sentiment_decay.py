"""
Tests for CryptoPilot AI - Exponential Time-Decay Calculator.
"""

from datetime import UTC, datetime, timedelta

import pytest

from cryptopilot.sentiment.decay import ExponentialTimeDecay


def test_decay_initialization_valid():
    decay = ExponentialTimeDecay(half_life_hours=2.0, max_age_hours=24.0)
    assert decay.half_life_hours == 2.0
    assert decay.max_age_hours == 24.0


def test_decay_initialization_invalid():
    with pytest.raises(ValueError, match="half_life_hours must be positive"):
        ExponentialTimeDecay(half_life_hours=0.0)

    with pytest.raises(ValueError, match="half_life_hours must be positive"):
        ExponentialTimeDecay(half_life_hours=-1.5)

    with pytest.raises(ValueError, match="max_age_hours must be positive"):
        ExponentialTimeDecay(half_life_hours=2.0, max_age_hours=0.0)


def test_decay_weights_exact_intervals():
    decay = ExponentialTimeDecay(half_life_hours=2.0, max_age_hours=24.0)
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)

    # 0 hours elapsed
    w0 = decay.calculate_weight(now, current_time=now)
    assert w0 == pytest.approx(1.0, abs=1e-5)

    # 1 half-life (2 hours elapsed)
    t_2h = now - timedelta(hours=2)
    w2 = decay.calculate_weight(t_2h, current_time=now)
    assert w2 == pytest.approx(0.5, abs=1e-5)

    # 2 half-lives (4 hours elapsed)
    t_4h = now - timedelta(hours=4)
    w4 = decay.calculate_weight(t_4h, current_time=now)
    assert w4 == pytest.approx(0.25, abs=1e-5)

    # 3 half-lives (6 hours elapsed)
    t_6h = now - timedelta(hours=6)
    w6 = decay.calculate_weight(t_6h, current_time=now)
    assert w6 == pytest.approx(0.125, abs=1e-5)


def test_decay_max_age_expiration():
    decay = ExponentialTimeDecay(half_life_hours=2.0, max_age_hours=24.0)
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)

    # Exactly 24h
    t_24h = now - timedelta(hours=24)
    assert decay.calculate_weight(t_24h, current_time=now) == 0.0
    assert decay.is_expired(t_24h, current_time=now) is True

    # 25h
    t_25h = now - timedelta(hours=25)
    assert decay.calculate_weight(t_25h, current_time=now) == 0.0
    assert decay.is_expired(t_25h, current_time=now) is True

    # 23.9h -> not expired
    t_almost = now - timedelta(hours=23.9)
    assert decay.calculate_weight(t_almost, current_time=now) > 0.0
    assert decay.is_expired(t_almost, current_time=now) is False


def test_decay_future_and_naive_timestamps():
    decay = ExponentialTimeDecay(half_life_hours=2.0, max_age_hours=24.0)
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)

    # Future timestamp (clock drift)
    future = now + timedelta(minutes=5)
    assert decay.calculate_weight(future, current_time=now) == 1.0

    # Naive timestamp compatibility
    naive_pub = datetime(2026, 11, 4, 10, 0, 0)  # 2 hours before now if naive converted to UTC
    w = decay.calculate_weight(naive_pub, current_time=now)
    assert w == pytest.approx(0.5, abs=1e-3)
