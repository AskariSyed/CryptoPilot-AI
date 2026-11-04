"""
Unit tests for cryptopilot.indicators.momentum.
Covers: Valid, Invalid, Boundary, Edge cases (constant price, mono-trends),
and Wilder's smoothing verification for RSI and Stochastic Oscillator.
"""

import numpy as np
import pandas as pd
import pytest

from cryptopilot.indicators.base import InvalidInputError
from cryptopilot.indicators.momentum import (
    RSI,
    StochasticOscillator,
    calculate_rsi,
    calculate_stochastic,
)


class TestMomentum:
    def test_calculate_rsi_monotonically_rising(self) -> None:
        """When prices only rise, losses are 0 -> RSI should be 100.0."""
        prices = pd.Series([10.0 + i for i in range(25)])
        rsi = calculate_rsi(prices, period=14)
        assert np.isnan(rsi.iloc[13])
        assert rsi.iloc[14] == pytest.approx(100.0)
        assert rsi.iloc[20] == pytest.approx(100.0)

    def test_calculate_rsi_monotonically_falling(self) -> None:
        """When prices only fall, gains are 0 -> RSI should be 0.0."""
        prices = pd.Series([100.0 - i for i in range(25)])
        rsi = calculate_rsi(prices, period=14)
        assert np.isnan(rsi.iloc[13])
        assert rsi.iloc[14] == pytest.approx(0.0)
        assert rsi.iloc[20] == pytest.approx(0.0)

    def test_calculate_rsi_constant_price(self) -> None:
        """When prices never change, gains=0 and losses=0 -> RSI should be 50.0."""
        prices = pd.Series([50.0] * 25)
        rsi = calculate_rsi(prices, period=14)
        assert np.isnan(rsi.iloc[13])
        assert rsi.iloc[14] == pytest.approx(50.0)

    def test_calculate_rsi_empty_and_short(self) -> None:
        empty = pd.Series([], dtype=np.float64)
        assert calculate_rsi(empty, period=14).empty

        short = pd.Series([10.0, 11.0, 12.0])
        assert calculate_rsi(short, period=14).isna().all()

        with pytest.raises(ValueError):
            calculate_rsi(short, period=0)

    def test_calculate_stochastic_standard(self) -> None:
        high = pd.Series([12.0, 14.0, 15.0, 13.0, 16.0, 14.0, 15.0])
        low = pd.Series([10.0, 11.0, 12.0, 10.0, 13.0, 11.0, 12.0])
        close = pd.Series([11.0, 13.0, 14.0, 12.0, 15.0, 12.0, 14.0])

        k, d = calculate_stochastic(high, low, close, k_period=4, d_period=2)
        assert np.isnan(k.iloc[0])
        assert np.isnan(k.iloc[2])
        # At index 3: window 0..3: high max=15, low min=10. close=12.
        # %K = (12 - 10) / (15 - 10) * 100 = 2/5 * 100 = 40.0
        assert k.iloc[3] == pytest.approx(40.0)

    def test_calculate_stochastic_constant_price(self) -> None:
        """When high == low, %K should return 50.0 rather than ZeroDivisionError."""
        high = pd.Series([10.0] * 10)
        low = pd.Series([10.0] * 10)
        close = pd.Series([10.0] * 10)

        k, d = calculate_stochastic(high, low, close, k_period=3, d_period=2)
        assert k.iloc[3] == pytest.approx(50.0)
        assert d.iloc[4] == pytest.approx(50.0)

    def test_calculate_stochastic_invalid_and_empty(self) -> None:
        empty = pd.Series([], dtype=np.float64)
        k, d = calculate_stochastic(empty, empty, empty, 5, 3)
        assert k.empty and d.empty

        with pytest.raises(ValueError):
            calculate_stochastic(empty, empty, empty, 0, 3)
        with pytest.raises(ValueError):
            calculate_stochastic(empty, empty, empty, 5, 0)

    def test_momentum_classes(self) -> None:
        df = pd.DataFrame(
            {
                "open": [10.0 + i for i in range(30)],
                "high": [12.0 + i for i in range(30)],
                "low": [9.0 + i for i in range(30)],
                "close": [11.0 + i for i in range(30)],
            }
        )

        rsi_ind = RSI(period=14)
        rsi_res = rsi_ind.calculate(df)
        assert rsi_res.name == "RSI_14"
        assert not np.isnan(rsi_res.iloc[15])

        stoch_ind = StochasticOscillator(k_period=14, d_period=3)
        stoch_res = stoch_ind.calculate(df)
        assert "STOCH_K_14" in stoch_res.columns
        assert "STOCH_D_3" in stoch_res.columns

    def test_momentum_classes_errors(self) -> None:
        df_bad = pd.DataFrame({"open": [1.0, 2.0]})
        rsi_ind = RSI(period=14)
        with pytest.raises(InvalidInputError):
            rsi_ind.calculate(df_bad)

        stoch_ind = StochasticOscillator(k_period=14, d_period=3)
        with pytest.raises(InvalidInputError):
            stoch_ind.calculate(df_bad)
