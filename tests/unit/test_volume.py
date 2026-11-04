"""
Unit tests for cryptopilot.indicators.volume.
Covers: On-Balance Volume (OBV) and Volume-Weighted Average Price (VWAP).
"""

import numpy as np
import pandas as pd
import pytest

from cryptopilot.indicators.base import InvalidInputError
from cryptopilot.indicators.volume import OBV, VWAP, calculate_obv, calculate_vwap


class TestVolumeIndicators:
    def test_calculate_obv_directional_accumulation(self) -> None:
        close = pd.Series([10.0, 12.0, 11.0, 11.0, 14.0])
        volume = pd.Series([100.0, 200.0, 150.0, 50.0, 300.0])

        obv = calculate_obv(close, volume)
        # Day 0: flat (direction=0) -> 0
        assert obv.iloc[0] == 0.0
        # Day 1: up (12 > 10) -> +200 -> 200
        assert obv.iloc[1] == 200.0
        # Day 2: down (11 < 12) -> -150 -> 50
        assert obv.iloc[2] == 50.0
        # Day 3: flat (11 == 11) -> 0 -> 50
        assert obv.iloc[3] == 50.0
        # Day 4: up (14 > 11) -> +300 -> 350
        assert obv.iloc[4] == 350.0

    def test_calculate_obv_empty(self) -> None:
        empty = pd.Series([], dtype=np.float64)
        assert calculate_obv(empty, empty).empty

    def test_calculate_vwap_typical_price(self) -> None:
        high = pd.Series([11.0, 21.0])
        low = pd.Series([9.0, 19.0])
        close = pd.Series([10.0, 20.0])
        volume = pd.Series([100.0, 200.0])

        # Typical prices: Day 0 = (11+9+10)/3 = 10.0. Day 1 = (21+19+20)/3 = 20.0.
        # Day 0 VWAP = 10.0 * 100 / 100 = 10.0
        # Day 1 Cumulative VWAP = (1000 + 4000) / 300 = 5000 / 300 = 16.666667
        vwap = calculate_vwap(high, low, close, volume)
        assert vwap.iloc[0] == pytest.approx(10.0)
        assert vwap.iloc[1] == pytest.approx(50.0 / 3.0)

    def test_calculate_vwap_rolling_window(self) -> None:
        high = pd.Series([11.0, 21.0, 31.0])
        low = pd.Series([9.0, 19.0, 29.0])
        close = pd.Series([10.0, 20.0, 30.0])
        volume = pd.Series([100.0, 100.0, 100.0])

        # Rolling window 2:
        # At index 2: typical prices are 20 and 30, vol is 100 and 100 -> VWAP = 25.0
        vwap_roll2 = calculate_vwap(high, low, close, volume, rolling_window=2)
        assert vwap_roll2.iloc[2] == pytest.approx(25.0)

    def test_calculate_vwap_zero_volume_fallback(self) -> None:
        high = pd.Series([11.0])
        low = pd.Series([9.0])
        close = pd.Series([10.0])
        volume = pd.Series([0.0])

        vwap = calculate_vwap(high, low, close, volume)
        # Should fallback to typical price (10.0) without crashing with zero division
        assert vwap.iloc[0] == pytest.approx(10.0)

    def test_calculate_vwap_invalid_window_and_empty(self) -> None:
        empty = pd.Series([], dtype=np.float64)
        assert calculate_vwap(empty, empty, empty, empty).empty

        series = pd.Series([10.0])
        with pytest.raises(ValueError):
            calculate_vwap(series, series, series, series, rolling_window=0)

    def test_classes_dataframe_integration(self) -> None:
        df = pd.DataFrame(
            {
                "high": [12.0, 14.0, 13.0],
                "low": [8.0, 10.0, 9.0],
                "close": [10.0, 12.0, 11.0],
                "volume": [100.0, 200.0, 150.0],
            }
        )

        obv = OBV()
        res_obv = obv.calculate(df)
        assert res_obv.name == "OBV"

        vwap = VWAP(rolling_window=2)
        res_vwap = vwap.calculate(df)
        assert res_vwap.name == "VWAP_2"

    def test_classes_invalid_input(self) -> None:
        df_bad = pd.DataFrame({"dummy": [1.0]})
        with pytest.raises(InvalidInputError):
            OBV().calculate(df_bad)
        with pytest.raises(InvalidInputError):
            VWAP().calculate(df_bad)

