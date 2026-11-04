"""
Unit tests for cryptopilot.strategies.volatility_momentum.VolatilityAdjustedMomentumStrategy.
Covers: Strategy D BUY, SELL, HOLD, squeeze release detection, and trailing stops.
"""

from unittest.mock import patch

import numpy as np
import pandas as pd

from cryptopilot.strategies.base import SignalType
from cryptopilot.strategies.volatility_momentum import VolatilityAdjustedMomentumStrategy


class TestVolatilityAdjustedMomentumStrategy:
    def test_volatility_momentum_buy_trigger_explicit(self) -> None:
        """Explicitly tests BUY trigger branch."""
        n = 30
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [108.0] * n,
                "low": [98.0] * n,
                "close": [105.0] * n,
                "volume": [500.0] * n,
            }
        )
        strategy = VolatilityAdjustedMomentumStrategy(period=10, momentum_period=5, atr_period=5)

        # Squeeze on bars t-4..t-1 (BB < KC), and breakout on bar t (BB >= KC)
        bb_up = pd.Series([101.0] * 28 + [101.0, 107.0])  # Expands to 107
        bb_mid = pd.Series([100.0] * n)
        bb_low = pd.Series([98.0] * n)
        bb_bw = pd.Series([0.04] * 28 + [0.05, 0.09])  # Expanding bandwidth

        ema_mid = pd.Series([99.0] * n)  # Price 105 > EMA 99
        atr_s = pd.Series([2.0] * n)  # KC Upper = 99 + 1.5 * 2 = 102.0
        # BB Upper was 101 < 102 (squeeze), now 107 >= 102 (breakout)
        returns_s = pd.Series([0.05] * n)  # Positive momentum

        with patch(
            "cryptopilot.strategies.volatility_momentum.calculate_bollinger_bands",
            return_value=(bb_up, bb_mid, bb_low, bb_bw, bb_bw),
        ):
            with patch(
                "cryptopilot.strategies.volatility_momentum.calculate_ema", return_value=ema_mid
            ):
                with patch(
                    "cryptopilot.strategies.volatility_momentum.calculate_atr", return_value=atr_s
                ):
                    with patch(
                        "cryptopilot.strategies.volatility_momentum.calculate_returns",
                        return_value=returns_s,
                    ):
                        signal = strategy.evaluate(df, "BTC/USDT")
                        assert signal.signal == SignalType.BUY
                        assert signal.confidence >= 0.60
                        assert signal.suggested_stop_loss < signal.entry_price
                        assert "squeeze release breakout" in signal.rationale

    def test_volatility_momentum_sell_on_exhaustion(self) -> None:
        n = 30
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [102.0] * n,
                "low": [92.0] * n,
                "close": [94.0] * n,  # Price 94 < EMA 98
                "volume": [200.0] * n,
            }
        )
        strategy = VolatilityAdjustedMomentumStrategy(period=10, momentum_period=5, atr_period=5)

        bb_s = pd.Series([100.0] * n)
        ema_mid = pd.Series([98.0] * n)
        atr_s = pd.Series([2.0] * n)
        returns_s = pd.Series([-0.05] * n)  # Negative momentum

        with patch(
            "cryptopilot.strategies.volatility_momentum.calculate_bollinger_bands",
            return_value=(bb_s, bb_s, bb_s, bb_s, bb_s),
        ):
            with patch(
                "cryptopilot.strategies.volatility_momentum.calculate_ema", return_value=ema_mid
            ):
                with patch(
                    "cryptopilot.strategies.volatility_momentum.calculate_atr", return_value=atr_s
                ):
                    with patch(
                        "cryptopilot.strategies.volatility_momentum.calculate_returns",
                        return_value=returns_s,
                    ):
                        signal = strategy.evaluate(df, "ETH/USDT")
                        assert signal.signal == SignalType.SELL
                        assert "exhaustion" in signal.rationale.lower()

    def test_volatility_momentum_hold_on_nan(self) -> None:
        n = 30
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [102.0] * n,
                "low": [98.0] * n,
                "close": [100.0] * n,
                "volume": [100.0] * n,
            }
        )
        strategy = VolatilityAdjustedMomentumStrategy(period=10, momentum_period=5, atr_period=5)
        nan_s = pd.Series([np.nan] * n)

        with patch(
            "cryptopilot.strategies.volatility_momentum.calculate_bollinger_bands",
            return_value=(nan_s, nan_s, nan_s, nan_s, nan_s),
        ):
            with patch(
                "cryptopilot.strategies.volatility_momentum.calculate_ema", return_value=nan_s
            ):
                with patch(
                    "cryptopilot.strategies.volatility_momentum.calculate_atr", return_value=nan_s
                ):
                    with patch(
                        "cryptopilot.strategies.volatility_momentum.calculate_returns",
                        return_value=nan_s,
                    ):
                        signal = strategy.evaluate(df, "BTC/USDT")
                        assert signal.signal == SignalType.HOLD
                        assert "warmup incomplete" in signal.rationale

    def test_volatility_momentum_insufficient_bars(self) -> None:
        strategy = VolatilityAdjustedMomentumStrategy()
        short_df = pd.DataFrame(
            {
                "open": [10.0] * 10,
                "high": [11.0] * 10,
                "low": [9.0] * 10,
                "close": [10.0] * 10,
                "volume": [100.0] * 10,
            }
        )
        signal = strategy.evaluate(short_df, "SOL/USDT")
        assert signal.signal == SignalType.HOLD
        assert "Insufficient observations" in signal.rationale

    def test_volatility_momentum_hold_no_setup(self) -> None:
        """When no squeeze or breakout exists, return detailed HOLD."""
        n = 30
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [102.0] * n,
                "low": [98.0] * n,
                "close": [100.0] * n,  # Price 100 >= EMA 99 (no sell)
                "volume": [100.0] * n,
                "timestamp": [pd.Timestamp("2026-01-01 00:00:00")] * n,
            }
        )
        strategy = VolatilityAdjustedMomentumStrategy(period=10, momentum_period=5, atr_period=5)
        # No squeeze: BB lower < KC lower
        bb_up = pd.Series([101.0] * n)
        bb_mid = pd.Series([99.0] * n)
        bb_low = pd.Series([95.0] * n)  # Lower than KC lower (96.0), so not in squeeze
        bb_bw = pd.Series([0.06] * n)

        ema_mid = pd.Series([99.0] * n)
        atr_s = pd.Series(
            [2.0] * n
        )  # KC Upper = 99 + 3 = 102, KC Lower = 96. BB Upper 101 < 102 (no breakout)
        returns_s = pd.Series([0.005] * n)  # Positive momentum > 0, but no squeeze release

        with patch(
            "cryptopilot.strategies.volatility_momentum.calculate_bollinger_bands",
            return_value=(bb_up, bb_mid, bb_low, bb_bw, bb_bw),
        ):
            with patch(
                "cryptopilot.strategies.volatility_momentum.calculate_ema", return_value=ema_mid
            ):
                with patch(
                    "cryptopilot.strategies.volatility_momentum.calculate_atr", return_value=atr_s
                ):
                    with patch(
                        "cryptopilot.strategies.volatility_momentum.calculate_returns",
                        return_value=returns_s,
                    ):
                        signal = strategy.evaluate(df, "BTC/USDT")
                        assert signal.signal == SignalType.HOLD
                        assert "No setup" in signal.rationale
