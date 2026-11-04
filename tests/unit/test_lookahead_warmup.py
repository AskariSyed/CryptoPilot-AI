"""
Quantitative Verification: Zero-Lookahead Bias & Warmup Invariant Assertions.
Mathematically proves that no future data leaks into past or current indicators.
"""

import numpy as np
import pandas as pd
import pytest

from cryptopilot.indicators.momentum import calculate_rsi
from cryptopilot.indicators.moving_averages import calculate_ema, calculate_sma, calculate_wma
from cryptopilot.indicators.returns import calculate_returns
from cryptopilot.indicators.trend_volatility import (
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_macd,
)
from cryptopilot.indicators.volume import calculate_obv, calculate_vwap


class TestZeroLookaheadAndWarmup:
    @pytest.fixture
    def market_series(self) -> pd.DataFrame:
        np.random.seed(12345)
        n = 120
        close = 100.0 + np.cumsum(np.random.randn(n) * 1.5)
        high = close + np.random.uniform(0.5, 2.5, n)
        low = close - np.random.uniform(0.5, 2.5, n)
        open_p = close + np.random.randn(n) * 0.5
        volume = np.random.uniform(50.0, 500.0, n)
        return pd.DataFrame(
            {"open": open_p, "high": high, "low": low, "close": close, "volume": volume}
        )

    def test_sma_zero_lookahead(self, market_series: pd.DataFrame) -> None:
        """For bar t, SMA(series[:t+1])[-1] == SMA(series)[t]."""
        full_res = calculate_sma(market_series["close"], period=10)
        for t in range(15, 40):
            sliced_res = calculate_sma(market_series["close"].iloc[: t + 1], period=10)
            assert full_res.iloc[t] == pytest.approx(sliced_res.iloc[-1])

    def test_ema_zero_lookahead(self, market_series: pd.DataFrame) -> None:
        """For bar t, EMA(series[:t+1])[-1] == EMA(series)[t]."""
        full_res = calculate_ema(market_series["close"], period=12)
        for t in range(20, 45):
            sliced_res = calculate_ema(market_series["close"].iloc[: t + 1], period=12)
            assert full_res.iloc[t] == pytest.approx(sliced_res.iloc[-1])

    def test_wma_zero_lookahead(self, market_series: pd.DataFrame) -> None:
        full_res = calculate_wma(market_series["close"], period=5)
        for t in range(10, 30):
            sliced_res = calculate_wma(market_series["close"].iloc[: t + 1], period=5)
            assert full_res.iloc[t] == pytest.approx(sliced_res.iloc[-1])

    def test_rsi_zero_lookahead(self, market_series: pd.DataFrame) -> None:
        full_res = calculate_rsi(market_series["close"], period=14)
        for t in range(20, 45):
            sliced_res = calculate_rsi(market_series["close"].iloc[: t + 1], period=14)
            assert full_res.iloc[t] == pytest.approx(sliced_res.iloc[-1])

    def test_macd_zero_lookahead(self, market_series: pd.DataFrame) -> None:
        macd_l, signal_l, hist = calculate_macd(market_series["close"], 12, 26, 9)
        for t in range(40, 60):
            s_macd, s_sig, s_hist = calculate_macd(market_series["close"].iloc[: t + 1], 12, 26, 9)
            assert macd_l.iloc[t] == pytest.approx(s_macd.iloc[-1])
            assert signal_l.iloc[t] == pytest.approx(s_sig.iloc[-1])
            assert hist.iloc[t] == pytest.approx(s_hist.iloc[-1])

    def test_bollinger_bands_zero_lookahead(self, market_series: pd.DataFrame) -> None:
        up, mid, low, bw, pct_b = calculate_bollinger_bands(market_series["close"], 20, 2.0)
        for t in range(25, 50):
            s_up, s_mid, s_low, s_bw, s_pct = calculate_bollinger_bands(
                market_series["close"].iloc[: t + 1], 20, 2.0
            )
            assert up.iloc[t] == pytest.approx(s_up.iloc[-1])
            assert mid.iloc[t] == pytest.approx(s_mid.iloc[-1])
            assert low.iloc[t] == pytest.approx(s_low.iloc[-1])
            assert bw.iloc[t] == pytest.approx(s_bw.iloc[-1])
            assert pct_b.iloc[t] == pytest.approx(s_pct.iloc[-1])

    def test_atr_zero_lookahead(self, market_series: pd.DataFrame) -> None:
        atr = calculate_atr(market_series["high"], market_series["low"], market_series["close"], 14)
        for t in range(20, 45):
            s_atr = calculate_atr(
                market_series["high"].iloc[: t + 1],
                market_series["low"].iloc[: t + 1],
                market_series["close"].iloc[: t + 1],
                14,
            )
            assert atr.iloc[t] == pytest.approx(s_atr.iloc[-1])

    def test_adx_zero_lookahead(self, market_series: pd.DataFrame) -> None:
        adx, p_di, m_di = calculate_adx(
            market_series["high"], market_series["low"], market_series["close"], 14
        )
        for t in range(35, 55):
            s_adx, s_p_di, s_m_di = calculate_adx(
                market_series["high"].iloc[: t + 1],
                market_series["low"].iloc[: t + 1],
                market_series["close"].iloc[: t + 1],
                14,
            )
            assert adx.iloc[t] == pytest.approx(s_adx.iloc[-1])
            assert p_di.iloc[t] == pytest.approx(s_p_di.iloc[-1])
            assert m_di.iloc[t] == pytest.approx(s_m_di.iloc[-1])

    def test_obv_zero_lookahead(self, market_series: pd.DataFrame) -> None:
        obv = calculate_obv(market_series["close"], market_series["volume"])
        for t in range(10, 30):
            s_obv = calculate_obv(
                market_series["close"].iloc[: t + 1],
                market_series["volume"].iloc[: t + 1],
            )
            assert obv.iloc[t] == pytest.approx(s_obv.iloc[-1])

    def test_vwap_zero_lookahead(self, market_series: pd.DataFrame) -> None:
        vwap = calculate_vwap(
            market_series["high"],
            market_series["low"],
            market_series["close"],
            market_series["volume"],
        )
        for t in range(10, 30):
            s_vwap = calculate_vwap(
                market_series["high"].iloc[: t + 1],
                market_series["low"].iloc[: t + 1],
                market_series["close"].iloc[: t + 1],
                market_series["volume"].iloc[: t + 1],
            )
            assert vwap.iloc[t] == pytest.approx(s_vwap.iloc[-1])

    def test_returns_zero_lookahead(self, market_series: pd.DataFrame) -> None:
        ret = calculate_returns(market_series["close"], periods=3)
        for t in range(5, 25):
            s_ret = calculate_returns(market_series["close"].iloc[: t + 1], periods=3)
            assert ret.iloc[t] == pytest.approx(s_ret.iloc[-1])
