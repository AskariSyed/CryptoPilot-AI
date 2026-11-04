"""
Unit tests for cryptopilot.indicators.moving_averages.
Covers: Valid, Invalid, Boundary, Empty, Missing, and Floating-point precision conditions.
"""

import numpy as np
import pandas as pd
import pytest

from cryptopilot.indicators.base import InvalidInputError
from cryptopilot.indicators.moving_averages import (
    EMA,
    SMA,
    VolumeMA,
    calculate_ema,
    calculate_sma,
    calculate_volume_ma,
    calculate_wma,
)


class TestMovingAverages:
    def test_calculate_sma_reference_values(self) -> None:
        """Verify SMA calculation against exact manual reference values."""
        data = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        sma3 = calculate_sma(data, period=3)

        assert np.isnan(sma3.iloc[0])
        assert np.isnan(sma3.iloc[1])
        assert sma3.iloc[2] == pytest.approx(20.0)  # (10+20+30)/3
        assert sma3.iloc[3] == pytest.approx(30.0)  # (20+30+40)/3
        assert sma3.iloc[4] == pytest.approx(40.0)  # (30+40+50)/3

    def test_calculate_sma_period_one(self) -> None:
        """Boundary: period=1 must equal the input series exactly."""
        data = pd.Series([12.5, 15.0, 18.2])
        sma1 = calculate_sma(data, period=1)
        pd.testing.assert_series_equal(sma1, data)

    def test_calculate_sma_empty_and_insufficient(self) -> None:
        """Empty input and len < period."""
        empty = pd.Series([], dtype=np.float64)
        assert calculate_sma(empty, 5).empty

        short = pd.Series([10.0, 20.0])
        res = calculate_sma(short, 5)
        assert len(res) == 2
        assert res.isna().all()

    def test_calculate_sma_invalid_period(self) -> None:
        with pytest.raises(ValueError) as exc:
            calculate_sma(pd.Series([1.0, 2.0]), period=0)
        assert "Period must be >= 1" in str(exc.value)

    def test_calculate_ema_reference_values(self) -> None:
        """Verify EMA with alpha=2/(N+1)."""
        data = pd.Series([10.0, 20.0, 30.0, 40.0])
        # Period 3: alpha = 2 / (3 + 1) = 0.5
        # EMA starts after warmup (index 2):
        ema3 = calculate_ema(data, period=3)
        assert np.isnan(ema3.iloc[0])
        assert np.isnan(ema3.iloc[1])
        assert not np.isnan(ema3.iloc[2])

    def test_calculate_ema_custom_alpha(self) -> None:
        data = pd.Series([10.0, 20.0, 30.0, 40.0])
        ema_custom = calculate_ema(data, period=2, alpha=0.5)
        assert np.isnan(ema_custom.iloc[0])
        assert ema_custom.iloc[1] == pytest.approx(15.0)  # 0.5*20 + 0.5*10

    def test_calculate_ema_invalid_alpha_and_period(self) -> None:
        data = pd.Series([1.0, 2.0])
        with pytest.raises(ValueError):
            calculate_ema(data, period=0)
        with pytest.raises(ValueError):
            calculate_ema(data, period=2, alpha=0.0)
        with pytest.raises(ValueError):
            calculate_ema(data, period=2, alpha=1.5)

    def test_calculate_wma_reference_values(self) -> None:
        """Verify WMA with weights [1, 2, 3] sum=6."""
        data = pd.Series([10.0, 20.0, 30.0, 40.0])
        wma3 = calculate_wma(data, period=3)

        assert np.isnan(wma3.iloc[0])
        assert np.isnan(wma3.iloc[1])
        # At index 2: (10*1 + 20*2 + 30*3) / 6 = (10 + 40 + 90)/6 = 140/6 = 23.333333
        assert wma3.iloc[2] == pytest.approx(140.0 / 6.0)
        # At index 3: (20*1 + 30*2 + 40*3) / 6 = (20 + 60 + 120)/6 = 200/6 = 33.333333
        assert wma3.iloc[3] == pytest.approx(200.0 / 6.0)

    def test_calculate_wma_empty_and_short(self) -> None:
        empty = pd.Series([], dtype=np.float64)
        assert calculate_wma(empty, 3).empty

        short = pd.Series([10.0, 20.0])
        assert calculate_wma(short, 5).isna().all()

        with pytest.raises(ValueError):
            calculate_wma(short, 0)

    def test_calculate_volume_ma(self) -> None:
        vols = pd.Series([100.0, 200.0, 300.0, 400.0])
        vma = calculate_volume_ma(vols, period=2)
        assert np.isnan(vma.iloc[0])
        assert vma.iloc[1] == pytest.approx(150.0)

    def test_classes_dataframe_integration(self) -> None:
        df = pd.DataFrame(
            {
                "close": [10.0, 20.0, 30.0, 40.0, 50.0],
                "volume": [100.0, 150.0, 200.0, 250.0, 300.0],
            }
        )

        sma = SMA(period=3)
        res_sma = sma.calculate(df)
        assert res_sma.name == "SMA_3"
        assert res_sma.iloc[2] == pytest.approx(20.0)

        ema = EMA(period=3)
        res_ema = ema.calculate(df)
        assert res_ema.name == "EMA_3"

        vma = VolumeMA(period=2)
        res_vma = vma.calculate(df)
        assert res_vma.name == "VolumeMA_2"

    def test_class_missing_columns(self) -> None:
        df = pd.DataFrame({"open": [1.0, 2.0]})
        sma = SMA(period=2, column="close")
        with pytest.raises(InvalidInputError) as exc:
            sma.calculate(df)
        assert "Missing" in str(exc.value)

    def test_class_empty_dataframe(self) -> None:
        df = pd.DataFrame({"close": []})
        sma = SMA(period=5)
        res = sma.calculate(df)
        assert res.empty
