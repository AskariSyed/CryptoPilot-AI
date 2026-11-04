"""
Unit tests for cryptopilot.strategies.rsi_macd.RSIMACDConfirmationStrategy.
Covers: Strategy B BUY, SELL, HOLD, overbought filtering, and stop-loss logic.
"""

from unittest.mock import patch

import numpy as np
import pandas as pd

from cryptopilot.strategies.base import SignalType
from cryptopilot.strategies.rsi_macd import RSIMACDConfirmationStrategy


class TestRSIMACDConfirmationStrategy:
    def test_rsi_macd_buy_trigger_explicit(self) -> None:
        """Explicitly tests BUY trigger branch."""
        n = 50
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [102.0] * n,
                "volume": [500.0] * n,
            }
        )
        strategy = RSIMACDConfirmationStrategy(ema_filter_period=10, macd_slow=15, macd_signal=5)

        ema_s = pd.Series([90.0] * n)  # Price 102 > EMA 90
        macd_l = pd.Series([1.0] * n)
        macd_sig = pd.Series([0.5] * n)
        hist_s = pd.Series([-0.2] * (n - 2) + [-0.1, 0.5])  # Crossed above 0 on last bar
        rsi_s = pd.Series([58.0] * n)  # 50 < 58 < 70
        vol_ma_s = pd.Series([300.0] * n)  # Vol 500 > Vol MA 300
        atr_s = pd.Series([2.0] * n)

        with patch("cryptopilot.strategies.rsi_macd.calculate_ema", return_value=ema_s):
            with patch(
                "cryptopilot.strategies.rsi_macd.calculate_macd",
                return_value=(macd_l, macd_sig, hist_s),
            ):
                with patch("cryptopilot.strategies.rsi_macd.calculate_rsi", return_value=rsi_s):
                    with patch(
                        "cryptopilot.strategies.rsi_macd.calculate_volume_ma", return_value=vol_ma_s
                    ):
                        with patch(
                            "cryptopilot.strategies.rsi_macd.calculate_atr", return_value=atr_s
                        ):
                            signal = strategy.evaluate(df, "BTC/USDT")
                            assert signal.signal == SignalType.BUY
                            assert signal.confidence >= 0.55
                            assert signal.suggested_stop_loss < signal.entry_price
                            assert signal.suggested_take_profit is not None
                            assert "crossed positive" in signal.rationale

    def test_rsi_macd_sell_on_negative_histogram(self) -> None:
        n = 50
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [85.0] * n,
                "volume": [200.0] * n,
            }
        )
        strategy = RSIMACDConfirmationStrategy(ema_filter_period=10, macd_slow=15, macd_signal=5)

        ema_s = pd.Series([90.0] * n)  # Price 85 < EMA 90
        macd_l = pd.Series([-1.0] * n)
        macd_sig = pd.Series([-0.5] * n)
        hist_s = pd.Series([0.5] * (n - 3) + [-0.2, -0.4, -0.6])  # Consecutive negative
        rsi_s = pd.Series([45.0] * n)
        vol_ma_s = pd.Series([300.0] * n)
        atr_s = pd.Series([2.0] * n)

        with patch("cryptopilot.strategies.rsi_macd.calculate_ema", return_value=ema_s):
            with patch(
                "cryptopilot.strategies.rsi_macd.calculate_macd",
                return_value=(macd_l, macd_sig, hist_s),
            ):
                with patch("cryptopilot.strategies.rsi_macd.calculate_rsi", return_value=rsi_s):
                    with patch(
                        "cryptopilot.strategies.rsi_macd.calculate_volume_ma", return_value=vol_ma_s
                    ):
                        with patch(
                            "cryptopilot.strategies.rsi_macd.calculate_atr", return_value=atr_s
                        ):
                            signal = strategy.evaluate(df, "ETH/USDT")
                            assert signal.signal == SignalType.SELL
                            assert "negative" in signal.rationale.lower()

    def test_rsi_macd_sell_on_overbought(self) -> None:
        n = 50
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [102.0] * n,
                "volume": [200.0] * n,
            }
        )
        strategy = RSIMACDConfirmationStrategy(ema_filter_period=10, macd_slow=15, macd_signal=5)

        ema_s = pd.Series([90.0] * n)
        macd_l = pd.Series([1.0] * n)
        macd_sig = pd.Series([0.5] * n)
        hist_s = pd.Series([0.5] * n)
        rsi_s = pd.Series([80.0] * n)  # Extreme overbought > 75
        vol_ma_s = pd.Series([100.0] * n)
        atr_s = pd.Series([2.0] * n)

        with patch("cryptopilot.strategies.rsi_macd.calculate_ema", return_value=ema_s):
            with patch(
                "cryptopilot.strategies.rsi_macd.calculate_macd",
                return_value=(macd_l, macd_sig, hist_s),
            ):
                with patch("cryptopilot.strategies.rsi_macd.calculate_rsi", return_value=rsi_s):
                    with patch(
                        "cryptopilot.strategies.rsi_macd.calculate_volume_ma", return_value=vol_ma_s
                    ):
                        with patch(
                            "cryptopilot.strategies.rsi_macd.calculate_atr", return_value=atr_s
                        ):
                            signal = strategy.evaluate(df, "SOL/USDT")
                            assert signal.signal == SignalType.SELL
                            assert "overbought" in signal.rationale.lower()

    def test_rsi_macd_hold_on_nan(self) -> None:
        n = 50
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [100.0] * n,
                "volume": [100.0] * n,
            }
        )
        strategy = RSIMACDConfirmationStrategy(ema_filter_period=10, macd_slow=15, macd_signal=5)
        nan_s = pd.Series([np.nan] * n)

        with patch("cryptopilot.strategies.rsi_macd.calculate_ema", return_value=nan_s):
            with patch(
                "cryptopilot.strategies.rsi_macd.calculate_macd", return_value=(nan_s, nan_s, nan_s)
            ):
                with patch("cryptopilot.strategies.rsi_macd.calculate_rsi", return_value=nan_s):
                    with patch(
                        "cryptopilot.strategies.rsi_macd.calculate_volume_ma", return_value=nan_s
                    ):
                        with patch(
                            "cryptopilot.strategies.rsi_macd.calculate_atr", return_value=nan_s
                        ):
                            signal = strategy.evaluate(df, "BTC/USDT")
                            assert signal.signal == SignalType.HOLD
                            assert "warmup incomplete" in signal.rationale

    def test_rsi_macd_insufficient_bars(self) -> None:
        strategy = RSIMACDConfirmationStrategy()
        short_df = pd.DataFrame(
            {
                "open": [10.0] * 20,
                "high": [11.0] * 20,
                "low": [9.0] * 20,
                "close": [10.0] * 20,
                "volume": [100.0] * 20,
            }
        )
        signal = strategy.evaluate(short_df, "SOL/USDT")
        assert signal.signal == SignalType.HOLD
        assert "Insufficient observations" in signal.rationale

    def test_rsi_macd_hold_no_setup(self) -> None:
        """When neither buy nor sell conditions are met, return detailed HOLD."""
        n = 50
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [88.0] * n,  # Price 88 <= EMA 90
                "volume": [100.0] * n,
                "timestamp": [pd.Timestamp("2026-01-01 00:00:00")] * n,
            }
        )
        strategy = RSIMACDConfirmationStrategy(ema_filter_period=10, macd_slow=15, macd_signal=5)
        ema_s = pd.Series([90.0] * n)
        macd_l = pd.Series([0.1] * n)
        macd_sig = pd.Series([0.1] * n)
        hist_s = pd.Series([0.05] * n)  # Positive, so not sell
        rsi_s = pd.Series([45.0] * n)  # Not in (50, 70), not extreme overbought
        vol_ma_s = pd.Series([200.0] * n)  # Vol 100 < Vol MA 200
        atr_s = pd.Series([2.0] * n)

        with patch("cryptopilot.strategies.rsi_macd.calculate_ema", return_value=ema_s):
            with patch(
                "cryptopilot.strategies.rsi_macd.calculate_macd",
                return_value=(macd_l, macd_sig, hist_s),
            ):
                with patch("cryptopilot.strategies.rsi_macd.calculate_rsi", return_value=rsi_s):
                    with patch(
                        "cryptopilot.strategies.rsi_macd.calculate_volume_ma", return_value=vol_ma_s
                    ):
                        with patch(
                            "cryptopilot.strategies.rsi_macd.calculate_atr", return_value=atr_s
                        ):
                            signal = strategy.evaluate(df, "BTC/USDT")
                            assert signal.signal == SignalType.HOLD
                            assert "No setup" in signal.rationale
