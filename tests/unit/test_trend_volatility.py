"""
Unit tests for cryptopilot.indicators.trend_volatility.
Covers: MACD, Bollinger Bands, ATR, ADX, and Historical Volatility.
"""

import numpy as np
import pandas as pd
import pytest

from cryptopilot.indicators.base import InvalidInputError
from cryptopilot.indicators.trend_volatility import (
    ADX,
    ATR,
    MACD,
    BollingerBands,
    HistoricalVolatility,
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_historical_volatility,
    calculate_macd,
)


class TestTrendVolatility:
    def test_calculate_macd_identity_and_components(self) -> None:
        """Verify Histogram = MACD_Line - Signal_Line."""
        prices = pd.Series([100.0 + (i * 0.5) for i in range(50)])
        macd_l, signal_l, hist = calculate_macd(
            prices, fast_period=12, slow_period=26, signal_period=9
        )

        # Check column names
        assert macd_l.name == "MACD_LINE"
        assert signal_l.name == "MACD_SIGNAL"
        assert hist.name == "MACD_HIST"

        # Check identity wherever both are not NaN
        valid_idx = (~macd_l.isna()) & (~signal_l.isna())
        diff = macd_l[valid_idx] - signal_l[valid_idx]
        np.testing.assert_allclose(hist[valid_idx].to_numpy(), diff.to_numpy(), rtol=1e-5)

    def test_calculate_macd_invalid_periods(self) -> None:
        prices = pd.Series([1.0, 2.0, 3.0])
        with pytest.raises(ValueError):
            calculate_macd(prices, fast_period=26, slow_period=12)  # fast >= slow
        with pytest.raises(ValueError):
            calculate_macd(prices, fast_period=0, slow_period=10)

    def test_calculate_bollinger_bands(self) -> None:
        prices = pd.Series([10.0, 12.0, 11.0, 13.0, 12.0, 14.0, 13.0, 15.0, 14.0, 16.0] * 3)
        up, mid, low, bw, pct_b = calculate_bollinger_bands(prices, period=20, num_std=2.0)

        assert up.iloc[25] > mid.iloc[25]
        assert mid.iloc[25] > low.iloc[25]
        assert bw.iloc[25] > 0.0

        # When Close == Middle, %B should be approx 0.5
        # Verify bandwidth = (upper - lower) / mid
        expected_bw = (up.iloc[25] - low.iloc[25]) / mid.iloc[25]
        assert bw.iloc[25] == pytest.approx(expected_bw)

    def test_calculate_bollinger_bands_errors(self) -> None:
        prices = pd.Series([1.0, 2.0])
        with pytest.raises(ValueError):
            calculate_bollinger_bands(prices, period=0)
        with pytest.raises(ValueError):
            calculate_bollinger_bands(prices, period=5, num_std=-1.0)

    def test_calculate_atr_true_range(self) -> None:
        high = pd.Series([12.0, 15.0, 14.0, 16.0])
        low = pd.Series([10.0, 11.0, 12.0, 13.0])
        close = pd.Series([11.0, 14.0, 13.0, 15.0])

        # Period 2
        atr = calculate_atr(high, low, close, period=2)
        assert np.isnan(atr.iloc[0])
        assert not np.isnan(atr.iloc[1])
        assert atr.iloc[1] > 0.0

    def test_calculate_atr_empty_and_short(self) -> None:
        empty = pd.Series([], dtype=np.float64)
        assert calculate_atr(empty, empty, empty, 5).empty

        short = pd.Series([1.0, 2.0])
        assert calculate_atr(short, short, short, 5).isna().all()

        with pytest.raises(ValueError):
            calculate_atr(short, short, short, 0)

    def test_calculate_adx_trending(self) -> None:
        # Generate 40 bars of strong uptrend
        high = pd.Series([10.0 + (i * 2.0) for i in range(40)])
        low = pd.Series([8.0 + (i * 2.0) for i in range(40)])
        close = pd.Series([9.5 + (i * 2.0) for i in range(40)])

        adx, p_di, m_di = calculate_adx(high, low, close, period=14)
        # In a strong uptrend, +DI should be significantly greater than -DI
        assert p_di.iloc[35] > m_di.iloc[35]
        assert not np.isnan(adx.iloc[35])

    def test_calculate_adx_empty_and_short(self) -> None:
        empty = pd.Series([], dtype=np.float64)
        adx, p_di, m_di = calculate_adx(empty, empty, empty, 14)
        assert adx.empty and p_di.empty and m_di.empty

        short = pd.Series([1.0] * 10)
        adx_s, p_di_s, m_di_s = calculate_adx(short, short, short, 14)
        assert adx_s.isna().all()

        with pytest.raises(ValueError):
            calculate_adx(short, short, short, 0)

    def test_calculate_historical_volatility(self) -> None:
        prices = pd.Series([100.0 * (1.02**i) for i in range(30)])  # Steady growth
        hv = calculate_historical_volatility(prices, period=10, trading_periods=365)
        assert np.isnan(hv.iloc[8])
        assert not np.isnan(hv.iloc[15])
        assert hv.iloc[15] >= 0.0

    def test_trend_volatility_classes(self) -> None:
        df = pd.DataFrame(
            {
                "open": [100.0 + i for i in range(60)],
                "high": [102.0 + i for i in range(60)],
                "low": [98.0 + i for i in range(60)],
                "close": [101.0 + i for i in range(60)],
            }
        )

        macd = MACD()
        res_macd = macd.calculate(df)
        assert "MACD_LINE" in res_macd.columns

        bb = BollingerBands()
        res_bb = bb.calculate(df)
        assert "BB_UPPER" in res_bb.columns

        atr = ATR()
        res_atr = atr.calculate(df)
        assert res_atr.name == "ATR_14"

        adx = ADX()
        res_adx = adx.calculate(df)
        assert "ADX" in res_adx.columns

        hv = HistoricalVolatility()
        res_hv = hv.calculate(df)
        assert res_hv.name == "HV_20"

    def test_trend_volatility_classes_invalid_input(self) -> None:
        df_bad = pd.DataFrame({"dummy": [1.0, 2.0]})
        with pytest.raises(InvalidInputError):
            MACD().calculate(df_bad)
        with pytest.raises(InvalidInputError):
            ATR().calculate(df_bad)
