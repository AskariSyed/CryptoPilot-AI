"""
Unit tests for cryptopilot.strategies.multi_timeframe.MultiTimeframeTrendStrategy.
Covers: Strategy E Macro 1h + Micro 15m evaluation, pullback & resumption, and sell exits.
"""

from unittest.mock import patch

import numpy as np
import pandas as pd

from cryptopilot.strategies.base import SignalType
from cryptopilot.strategies.multi_timeframe import MultiTimeframeTrendStrategy


class TestMultiTimeframeTrendStrategy:
    def test_multi_timeframe_buy_trigger_explicit(self) -> None:
        """Explicitly tests BUY trigger branch."""
        n = 30
        df_macro = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [104.0] * n,
                "volume": [1000.0] * n,
            }
        )
        df_micro = pd.DataFrame(
            {
                "open": [100.0] * (n - 1) + [99.5],  # Bullish resumption: open 99.5, close 101.5
                "high": [105.0] * n,
                "low": [97.0] * n,
                "close": [100.0] * (n - 1) + [101.5],
                "volume": [500.0] * n,
            }
        )
        strategy = MultiTimeframeTrendStrategy(macro_ema_period=10, micro_ema_period=10)

        # Macro indicators: Price 104 > EMA 100, MACD Line 1.5 > 0
        macro_ema = pd.Series([100.0] * n)
        macro_macd = pd.Series([1.5] * n)

        # Micro indicators:
        micro_ema = pd.Series([100.0] * n)
        micro_rsi = pd.Series([48.0] * (n - 1) + [52.0])  # Pullback in [40, 55]
        micro_atr = pd.Series([2.0] * n)
        micro_vol_ma = pd.Series([300.0] * n)  # Vol 500 > Vol MA 300

        with patch(
            "cryptopilot.strategies.multi_timeframe.calculate_ema",
            side_effect=[macro_ema, micro_ema],
        ):
            with patch(
                "cryptopilot.strategies.multi_timeframe.calculate_macd",
                return_value=(macro_macd, macro_macd, macro_macd),
            ):
                with patch(
                    "cryptopilot.strategies.multi_timeframe.calculate_rsi", return_value=micro_rsi
                ):
                    with patch(
                        "cryptopilot.strategies.multi_timeframe.calculate_atr",
                        return_value=micro_atr,
                    ):
                        with patch(
                            "cryptopilot.strategies.multi_timeframe.calculate_volume_ma",
                            return_value=micro_vol_ma,
                        ):
                            signal = strategy.evaluate_multi(df_macro, df_micro, "BTC/USDT")
                            assert signal.signal == SignalType.BUY
                            assert signal.confidence >= 0.70
                            assert signal.suggested_stop_loss < signal.entry_price
                            assert "Multi-timeframe trend alignment" in signal.rationale

    def test_multi_timeframe_bearish_macro_veto(self) -> None:
        n = 30
        df_macro = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [80.0] * n,  # Macro bear < EMA 100
                "volume": [1000.0] * n,
            }
        )
        df_micro = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [98.0] * n,
                "volume": [500.0] * n,
            }
        )
        strategy = MultiTimeframeTrendStrategy(macro_ema_period=10, micro_ema_period=10)

        macro_ema = pd.Series([100.0] * n)
        macro_macd = pd.Series([-1.0] * n)  # Macro MACD < 0
        micro_ema = pd.Series([95.0] * n)
        micro_rsi = pd.Series([50.0] * n)
        micro_atr = pd.Series([2.0] * n)
        micro_vol_ma = pd.Series([300.0] * n)

        with patch(
            "cryptopilot.strategies.multi_timeframe.calculate_ema",
            side_effect=[macro_ema, micro_ema],
        ):
            with patch(
                "cryptopilot.strategies.multi_timeframe.calculate_macd",
                return_value=(macro_macd, macro_macd, macro_macd),
            ):
                with patch(
                    "cryptopilot.strategies.multi_timeframe.calculate_rsi", return_value=micro_rsi
                ):
                    with patch(
                        "cryptopilot.strategies.multi_timeframe.calculate_atr",
                        return_value=micro_atr,
                    ):
                        with patch(
                            "cryptopilot.strategies.multi_timeframe.calculate_volume_ma",
                            return_value=micro_vol_ma,
                        ):
                            signal = strategy.evaluate_multi(df_macro, df_micro, "BTC/USDT")
                            assert signal.signal == SignalType.SELL
                            assert "turned bearish" in signal.rationale

    def test_multi_timeframe_hold_on_nan(self) -> None:
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
        strategy = MultiTimeframeTrendStrategy(macro_ema_period=10, micro_ema_period=10)
        nan_s = pd.Series([np.nan] * n)

        with patch("cryptopilot.strategies.multi_timeframe.calculate_ema", return_value=nan_s):
            with patch(
                "cryptopilot.strategies.multi_timeframe.calculate_macd",
                return_value=(nan_s, nan_s, nan_s),
            ):
                with patch(
                    "cryptopilot.strategies.multi_timeframe.calculate_rsi", return_value=nan_s
                ):
                    with patch(
                        "cryptopilot.strategies.multi_timeframe.calculate_atr", return_value=nan_s
                    ):
                        with patch(
                            "cryptopilot.strategies.multi_timeframe.calculate_volume_ma",
                            return_value=nan_s,
                        ):
                            signal = strategy.evaluate_multi(df, df, "BTC/USDT")
                            assert signal.signal == SignalType.HOLD
                            assert "warmup incomplete" in signal.rationale

    def test_multi_timeframe_single_df_fallback(self) -> None:
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
        strategy = MultiTimeframeTrendStrategy(macro_ema_period=10, micro_ema_period=10)
        signal = strategy.evaluate(df, "ETH/USDT")
        assert signal.strategy_id == "multi_timeframe"
        assert signal.signal in (SignalType.BUY, SignalType.SELL, SignalType.HOLD)

    def test_multi_timeframe_insufficient_bars(self) -> None:
        strategy = MultiTimeframeTrendStrategy()
        short_df = pd.DataFrame(
            {
                "open": [10.0] * 10,
                "high": [11.0] * 10,
                "low": [9.0] * 10,
                "close": [10.0] * 10,
                "volume": [100.0] * 10,
            }
        )
        signal = strategy.evaluate_multi(short_df, short_df, "SOL/USDT")
        assert signal.signal == SignalType.HOLD
        assert "validation failed" in signal.rationale.lower()
