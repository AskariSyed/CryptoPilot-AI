"""
Unit tests for cryptopilot.strategies.bollinger_reversion.BollingerMeanReversionStrategy.
Covers: Strategy C BUY, SELL, HOLD, strict ADX regime filtering, and stop-loss logic.
"""

from unittest.mock import patch

import numpy as np
import pandas as pd

from cryptopilot.strategies.base import SignalType
from cryptopilot.strategies.bollinger_reversion import BollingerMeanReversionStrategy


class TestBollingerMeanReversionStrategy:
    def test_bollinger_reversion_buy_trigger_explicit(self) -> None:
        """Explicitly tests BUY trigger branch."""
        n = 30
        df = pd.DataFrame(
            {
                "open": [92.0] * (n - 1) + [91.0],  # Last candle open 91, close 95 (bullish)
                "high": [96.0] * n,
                "low": [89.0] * (n - 1) + [90.0],  # Pierced lower band
                "close": [92.0] * (n - 1) + [95.0],
                "volume": [200.0] * n,
            }
        )
        strategy = BollingerMeanReversionStrategy(bb_period=10, adx_period=10)

        upper_s = pd.Series([110.0] * n)
        middle_s = pd.Series([100.0] * n)
        lower_s = pd.Series([90.0] * n)
        bw_s = pd.Series([0.2] * n)
        pct_b_s = pd.Series([0.3] * n)

        rsi_s = pd.Series([32.0] * (n - 1) + [38.0])  # Rebounding from oversold > 35
        adx_s = pd.Series([15.0] * n)  # Ranging regime < 20
        atr_s = pd.Series([2.0] * n)

        with patch(
            "cryptopilot.strategies.bollinger_reversion.calculate_bollinger_bands",
            return_value=(upper_s, middle_s, lower_s, bw_s, pct_b_s),
        ):
            with patch(
                "cryptopilot.strategies.bollinger_reversion.calculate_rsi", return_value=rsi_s
            ):
                with patch(
                    "cryptopilot.strategies.bollinger_reversion.calculate_adx",
                    return_value=(adx_s, adx_s, adx_s),
                ):
                    with patch(
                        "cryptopilot.strategies.bollinger_reversion.calculate_atr",
                        return_value=atr_s,
                    ):
                        signal = strategy.evaluate(df, "BTC/USDT")
                        assert signal.signal == SignalType.BUY
                        assert signal.confidence >= 0.50
                        assert signal.suggested_stop_loss < signal.entry_price
                        assert signal.suggested_take_profit == 100.0  # Middle band target
                        assert "Mean reversion setup" in signal.rationale

    def test_bollinger_regime_filter_rejects_trending_market(self) -> None:
        """Strong trend (ADX >= 20) MUST deactivate mean reversion."""
        n = 30
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [102.0] * n,
                "volume": [200.0] * n,
            }
        )
        strategy = BollingerMeanReversionStrategy(bb_period=10, adx_period=10, max_adx_regime=20.0)

        upper_s = pd.Series([110.0] * n)
        middle_s = pd.Series([100.0] * n)
        lower_s = pd.Series([90.0] * n)
        bw_s = pd.Series([0.2] * n)
        pct_b_s = pd.Series([0.5] * n)

        rsi_s = pd.Series([45.0] * n)
        adx_s = pd.Series([28.0] * n)  # ADX 28 >= 20 (trending)
        atr_s = pd.Series([2.0] * n)

        with patch(
            "cryptopilot.strategies.bollinger_reversion.calculate_bollinger_bands",
            return_value=(upper_s, middle_s, lower_s, bw_s, pct_b_s),
        ):
            with patch(
                "cryptopilot.strategies.bollinger_reversion.calculate_rsi", return_value=rsi_s
            ):
                with patch(
                    "cryptopilot.strategies.bollinger_reversion.calculate_adx",
                    return_value=(adx_s, adx_s, adx_s),
                ):
                    with patch(
                        "cryptopilot.strategies.bollinger_reversion.calculate_atr",
                        return_value=atr_s,
                    ):
                        signal = strategy.evaluate(df, "ETH/USDT")
                        assert signal.signal == SignalType.HOLD
                        assert "Regime filter: Market is trending" in signal.rationale

    def test_bollinger_reversion_sell_at_middle_or_upper_band(self) -> None:
        n = 30
        df = pd.DataFrame(
            {
                "open": [99.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [102.0] * n,  # Price 102 >= middle 100
                "volume": [100.0] * n,
            }
        )
        strategy = BollingerMeanReversionStrategy(bb_period=10, adx_period=10)

        upper_s = pd.Series([110.0] * n)
        middle_s = pd.Series([100.0] * n)
        lower_s = pd.Series([90.0] * n)
        bw_s = pd.Series([0.2] * n)
        pct_b_s = pd.Series([0.6] * n)

        rsi_s = pd.Series([55.0] * n)
        adx_s = pd.Series([15.0] * n)
        atr_s = pd.Series([2.0] * n)

        with patch(
            "cryptopilot.strategies.bollinger_reversion.calculate_bollinger_bands",
            return_value=(upper_s, middle_s, lower_s, bw_s, pct_b_s),
        ):
            with patch(
                "cryptopilot.strategies.bollinger_reversion.calculate_rsi", return_value=rsi_s
            ):
                with patch(
                    "cryptopilot.strategies.bollinger_reversion.calculate_adx",
                    return_value=(adx_s, adx_s, adx_s),
                ):
                    with patch(
                        "cryptopilot.strategies.bollinger_reversion.calculate_atr",
                        return_value=atr_s,
                    ):
                        signal = strategy.evaluate(df, "SOL/USDT")
                        assert signal.signal == SignalType.SELL
                        assert "Mean reversion exit" in signal.rationale

    def test_bollinger_reversion_hold_on_nan(self) -> None:
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
        strategy = BollingerMeanReversionStrategy(bb_period=10, adx_period=10)
        nan_s = pd.Series([np.nan] * n)

        with patch(
            "cryptopilot.strategies.bollinger_reversion.calculate_bollinger_bands",
            return_value=(nan_s, nan_s, nan_s, nan_s, nan_s),
        ):
            with patch(
                "cryptopilot.strategies.bollinger_reversion.calculate_rsi", return_value=nan_s
            ):
                with patch(
                    "cryptopilot.strategies.bollinger_reversion.calculate_adx",
                    return_value=(nan_s, nan_s, nan_s),
                ):
                    with patch(
                        "cryptopilot.strategies.bollinger_reversion.calculate_atr",
                        return_value=nan_s,
                    ):
                        signal = strategy.evaluate(df, "BTC/USDT")
                        assert signal.signal == SignalType.HOLD
                        assert "warmup incomplete" in signal.rationale

    def test_bollinger_reversion_insufficient_bars(self) -> None:
        strategy = BollingerMeanReversionStrategy()
        short_df = pd.DataFrame(
            {
                "open": [10.0] * 15,
                "high": [11.0] * 15,
                "low": [9.0] * 15,
                "close": [10.0] * 15,
                "volume": [100.0] * 15,
            }
        )
        signal = strategy.evaluate(short_df, "BTC/USDT")
        assert signal.signal == SignalType.HOLD
        assert "Insufficient observations" in signal.rationale

    def test_bollinger_reversion_hold_no_setup_ranging(self) -> None:
        """When market is ranging (ADX < 20) but price consolidates mid-band, return HOLD with detailed reasons."""
        n = 30
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [102.0] * n,
                "low": [98.0] * n,
                "close": [99.0] * n,  # Middle between 90 and 110, close <= open
                "volume": [100.0] * n,
                "timestamp": [pd.Timestamp("2026-01-01 00:00:00")] * n,
            }
        )
        strategy = BollingerMeanReversionStrategy(bb_period=10, adx_period=10)
        upper_s = pd.Series([110.0] * n)
        middle_s = pd.Series([100.0] * n)
        lower_s = pd.Series([90.0] * n)
        bw_s = pd.Series([0.2] * n)
        pct_b_s = pd.Series([0.45] * n)
        rsi_s = pd.Series([50.0] * n)
        adx_s = pd.Series([15.0] * n)  # Ranging
        atr_s = pd.Series([2.0] * n)

        with patch(
            "cryptopilot.strategies.bollinger_reversion.calculate_bollinger_bands",
            return_value=(upper_s, middle_s, lower_s, bw_s, pct_b_s),
        ):
            with patch(
                "cryptopilot.strategies.bollinger_reversion.calculate_rsi", return_value=rsi_s
            ):
                with patch(
                    "cryptopilot.strategies.bollinger_reversion.calculate_adx",
                    return_value=(adx_s, adx_s, adx_s),
                ):
                    with patch(
                        "cryptopilot.strategies.bollinger_reversion.calculate_atr",
                        return_value=atr_s,
                    ):
                        signal = strategy.evaluate(df, "BTC/USDT")
                        assert signal.signal == SignalType.HOLD
                        assert "No setup" in signal.rationale
