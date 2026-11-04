"""
Unit tests for cryptopilot.strategies.ema_trend.EMATrendFollowingStrategy.
Covers: Strategy A BUY, SELL, HOLD branches, and risk stop calculations.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest

from cryptopilot.strategies.base import SignalType
from cryptopilot.strategies.ema_trend import EMATrendFollowingStrategy


class TestEMATrendFollowingStrategy:
    @pytest.fixture
    def base_bullish_df(self) -> pd.DataFrame:
        """Generates 230 bars of synthetic data configured for a clean EMA cross."""
        n = 230
        timestamps = [datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=i) for i in range(n)]

        close = np.linspace(100.0, 130.0, 200).tolist()
        close.extend(np.linspace(131.0, 200.0, 30).tolist())

        close_arr = np.array(close[:n])
        high_arr = close_arr + 2.0
        low_arr = close_arr - 2.0
        open_arr = close_arr - 0.5
        vol_arr = np.full(n, 500.0)

        return pd.DataFrame(
            {
                "timestamp": timestamps[:n],
                "open": open_arr,
                "high": high_arr,
                "low": low_arr,
                "close": close_arr,
                "volume": vol_arr,
            }
        )

    def test_ema_trend_buy_signal_explicit(self) -> None:
        """Mocks indicators to strictly trigger BUY branch lines 108-140."""
        n = 30
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [102.0] * n,
                "volume": [100.0] * n,
            }
        )
        strategy = EMATrendFollowingStrategy(fast_period=5, slow_period=10, baseline_period=20)

        # Mock calculate_ema and calculate_adx and calculate_atr
        fast_s = pd.Series([10.0] * 28 + [15.0, 20.0])  # Crossed above
        slow_s = pd.Series([12.0] * 28 + [16.0, 18.0])  # Slow was higher, now lower
        base_s = pd.Series([10.0] * 30)  # Price 102 > base 10
        adx_s = pd.Series([20.0] * 27 + [26.0, 28.0, 30.0])  # Rising > 25
        atr_s = pd.Series([2.0] * 30)

        with patch("cryptopilot.strategies.ema_trend.calculate_ema", side_effect=[fast_s, slow_s, base_s]):
            with patch("cryptopilot.strategies.ema_trend.calculate_adx", return_value=(adx_s, adx_s, adx_s)):
                with patch("cryptopilot.strategies.ema_trend.calculate_atr", return_value=atr_s):
                    signal = strategy.evaluate(df, "BTC/USDT")
                    assert signal.signal == SignalType.BUY
                    assert signal.confidence >= 0.50
                    assert signal.suggested_stop_loss < signal.entry_price
                    assert signal.suggested_take_profit is not None
                    assert "crossed above" in signal.rationale

    def test_ema_trend_sell_on_bearish_cross(self) -> None:
        n = 30
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [100.0] * n,
                "volume": [100.0] * n,
            }
        )
        strategy = EMATrendFollowingStrategy(fast_period=5, slow_period=10, baseline_period=20)

        fast_s = pd.Series([20.0] * 28 + [18.0, 15.0])  # Crossed below
        slow_s = pd.Series([18.0] * 28 + [18.0, 18.0])
        base_s = pd.Series([50.0] * 30)
        adx_s = pd.Series([30.0] * 30)
        atr_s = pd.Series([2.0] * 30)

        with patch("cryptopilot.strategies.ema_trend.calculate_ema", side_effect=[fast_s, slow_s, base_s]):
            with patch("cryptopilot.strategies.ema_trend.calculate_adx", return_value=(adx_s, adx_s, adx_s)):
                with patch("cryptopilot.strategies.ema_trend.calculate_atr", return_value=atr_s):
                    signal = strategy.evaluate(df, "ETH/USDT")
                    assert signal.signal == SignalType.SELL
                    assert "Trend breakdown detected" in signal.rationale

    def test_ema_trend_hold_on_macro_bear(self) -> None:
        n = 30
        df = pd.DataFrame(
            {
                "open": [40.0] * n,
                "high": [45.0] * n,
                "low": [35.0] * n,
                "close": [40.0] * n,
                "volume": [100.0] * n,
            }
        )
        strategy = EMATrendFollowingStrategy(fast_period=5, slow_period=10, baseline_period=20)

        fast_s = pd.Series([40.0] * 30)
        slow_s = pd.Series([40.0] * 30)
        base_s = pd.Series([100.0] * 30)  # Price 40 < Base 100
        adx_s = pd.Series([15.0] * 30)  # Low ADX
        atr_s = pd.Series([2.0] * 30)

        with patch("cryptopilot.strategies.ema_trend.calculate_ema", side_effect=[fast_s, slow_s, base_s]):
            with patch("cryptopilot.strategies.ema_trend.calculate_adx", return_value=(adx_s, adx_s, adx_s)):
                with patch("cryptopilot.strategies.ema_trend.calculate_atr", return_value=atr_s):
                    signal = strategy.evaluate(df, "BTC/USDT")
                    assert signal.signal == SignalType.HOLD
                    assert "No setup" in signal.rationale

    def test_ema_trend_hold_on_nan_metrics(self) -> None:
        n = 30
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [100.0] * n,
                "volume": [100.0] * n,
            }
        )
        strategy = EMATrendFollowingStrategy(fast_period=5, slow_period=10, baseline_period=20)

        nan_s = pd.Series([np.nan] * 30)
        with patch("cryptopilot.strategies.ema_trend.calculate_ema", return_value=nan_s):
            with patch("cryptopilot.strategies.ema_trend.calculate_adx", return_value=(nan_s, nan_s, nan_s)):
                with patch("cryptopilot.strategies.ema_trend.calculate_atr", return_value=nan_s):
                    signal = strategy.evaluate(df, "BTC/USDT")
                    assert signal.signal == SignalType.HOLD
                    assert "warmup incomplete" in signal.rationale

    def test_ema_trend_insufficient_bars(self) -> None:
        strategy = EMATrendFollowingStrategy(baseline_period=200)
        short_df = pd.DataFrame(
            {
                "open": [10.0] * 50,
                "high": [11.0] * 50,
                "low": [9.0] * 50,
                "close": [10.0] * 50,
                "volume": [100.0] * 50,
            }
        )
        signal = strategy.evaluate(short_df, "SOL/USDT")
        assert signal.signal == SignalType.HOLD
        assert "Insufficient observations" in signal.rationale
