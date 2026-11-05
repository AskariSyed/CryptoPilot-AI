"""
Tests for CryptoPilot AI - Risk Circuit Breakers & Emergency Protocols.
"""

from datetime import UTC, datetime, timedelta

import pytest

from cryptopilot.risk.circuit_breaker import CircuitBreaker


def test_circuit_breaker_invalid_init():
    with pytest.raises(ValueError, match="daily_loss_limit_pct"):
        CircuitBreaker(daily_loss_limit_pct=0.0)

    with pytest.raises(ValueError, match="daily_loss_limit_pct"):
        CircuitBreaker(daily_loss_limit_pct=0.25)

    with pytest.raises(ValueError, match="max_consecutive_losses"):
        CircuitBreaker(max_consecutive_losses=0)


def test_circuit_breaker_daily_loss_trip_and_rollover():
    # 2% daily loss limit
    cb = CircuitBreaker(daily_loss_limit_pct=0.02)
    t0 = datetime(2026, 11, 5, 0, 1, 0, tzinfo=UTC)

    # Initial equity snapshot: $100.00
    cb.update_daily_equity(current_equity=100.0, current_time=t0)
    assert cb.is_active(t0) is False

    # Equity drops to $98.05 (lost $1.95 < $2.00 = 2%)
    t1 = t0 + timedelta(hours=2)
    cb.update_daily_equity(current_equity=98.05, current_time=t1)
    assert cb.is_active(t1) is False

    # Equity drops to $97.90 (lost $2.10 > $2.00 = 2% limit) -> Breaker TRIPS!
    t2 = t0 + timedelta(hours=4)
    cb.update_daily_equity(current_equity=97.90, current_time=t2)
    assert cb.is_active(t2) is True

    state = cb.get_state(current_equity=97.90, current_time=t2)
    assert state.is_tripped is True
    assert "Daily loss limit (2.0%) reached" in state.trip_reason
    assert state.starting_daily_equity == 100.0

    # Next UTC Day Rollover: Nov 6 00:01:00 UTC -> Daily breaker automatically resets!
    t_next_day = datetime(2026, 11, 6, 0, 1, 0, tzinfo=UTC)
    cb.update_daily_equity(current_equity=97.90, current_time=t_next_day)
    assert cb.is_active(t_next_day) is False
    assert cb._starting_daily_equity == 97.90


def test_circuit_breaker_consecutive_loss_cooldown():
    cb = CircuitBreaker(max_consecutive_losses=3, cooldown_hours=12.0)
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    # Loss 1
    cb.record_trade_result(realized_pnl=-0.20, current_time=now)
    assert cb.is_active(now) is False

    # Loss 2
    cb.record_trade_result(realized_pnl=-0.30, current_time=now)
    assert cb.is_active(now) is False

    # A winning trade resets the streak
    cb.record_trade_result(realized_pnl=0.50, current_time=now)
    assert cb._consecutive_losses == 0

    # Now 3 consecutive losses
    cb.record_trade_result(realized_pnl=-0.10, current_time=now)
    cb.record_trade_result(realized_pnl=-0.15, current_time=now)
    cb.record_trade_result(realized_pnl=-0.25, current_time=now)

    # Breaker must be TRIPPED for 12 hours
    assert cb.is_active(now) is True
    state = cb.get_state(current_equity=30.0, current_time=now)
    assert "Consecutive loss limit (3) reached" in state.trip_reason

    # 11 hours later: still active
    t_11h = now + timedelta(hours=11)
    assert cb.is_active(t_11h) is True

    # 12.1 hours later: cooldown expired -> automatically restored!
    t_12h = now + timedelta(hours=12, minutes=6)
    assert cb.is_active(t_12h) is False


def test_circuit_breaker_emergency_stop():
    cb = CircuitBreaker()
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    cb.trigger_emergency_stop(reason="Flash crash anomaly detected")
    assert cb.is_active(now) is True

    state = cb.get_state(current_equity=30.0, current_time=now)
    assert state.emergency_stop is True
    assert "EMERGENCY HALT" in state.trip_reason

    # Date rollover should NOT clear emergency stop
    next_day = now + timedelta(days=2)
    cb.update_daily_equity(30.0, current_time=next_day)
    assert cb.is_active(next_day) is True

    # Manual reset
    cb.reset_emergency_stop()
    assert cb.is_active(next_day) is False
