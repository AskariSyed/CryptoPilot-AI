"""
CryptoPilot AI - Quantitative Feature Engineering Pipeline.
Transforms raw OHLCV candles into a synchronized, zero-lookahead feature matrix
for rule strategies and machine learning inference.
"""

import numpy as np
import pandas as pd

from cryptopilot.indicators.base import InvalidInputError
from cryptopilot.indicators.momentum import calculate_rsi, calculate_stochastic
from cryptopilot.indicators.moving_averages import calculate_sma, calculate_volume_ma
from cryptopilot.indicators.returns import calculate_log_returns, calculate_returns
from cryptopilot.indicators.trend_volatility import (
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_historical_volatility,
    calculate_macd,
)
from cryptopilot.indicators.volume import calculate_obv, calculate_vwap


class FeaturePipeline:
    """
    Zero-lookahead feature generation pipeline.
    Combines trend, momentum, volatility, volume, and return features.
    """

    DEFAULT_RETURN_PERIODS: list[int] = [1, 3, 6, 12, 24]
    MAX_WARMUP_BARS: int = 60  # Covers slow MACD (26+9) and ADX (14*2)

    def __init__(
        self,
        return_periods: list[int] | None = None,
        max_warmup: int = MAX_WARMUP_BARS,
    ) -> None:
        self.return_periods = return_periods or self.DEFAULT_RETURN_PERIODS
        self.max_warmup = max_warmup

    def transform(self, df: pd.DataFrame, drop_warmup: bool = True) -> pd.DataFrame:
        """
        Transforms validated OHLCV DataFrame into a standardized feature matrix.
        Guarantees:
        1. No future data leakage.
        2. Finite, numeric feature values.
        3. Index alignment with input DataFrame.
        """
        if df is None or not isinstance(df, pd.DataFrame):
            raise InvalidInputError(f"Input must be a pandas DataFrame, got {type(df)}")

        required = ["open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise InvalidInputError(f"DataFrame is missing required columns: {missing}")

        if df.empty:
            return pd.DataFrame(index=df.index)

        features = pd.DataFrame(index=df.index)
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # 1. Multi-period Simple Returns
        for p in self.return_periods:
            features[f"return_{p}"] = calculate_returns(close, periods=p)

        # 2. Multi-period Log Returns
        for p in [1, 3, 6]:
            features[f"log_return_{p}"] = calculate_log_returns(close, periods=p)

        # 3. Moving Average Ratios
        sma_20 = calculate_sma(close, 20)
        sma_50 = calculate_sma(close, 50)
        features["close_to_sma_20"] = np.where(sma_20 > 0.0, (close / sma_20) - 1.0, 0.0)
        features["close_to_sma_50"] = np.where(sma_50 > 0.0, (close / sma_50) - 1.0, 0.0)
        features["sma_20_50_ratio"] = np.where(sma_50 > 0.0, (sma_20 / sma_50) - 1.0, 0.0)

        # 4. Momentum Indicators
        features["rsi_14"] = calculate_rsi(close, 14)
        stoch_k, stoch_d = calculate_stochastic(high, low, close, 14, 3)
        features["stoch_k_14"] = stoch_k
        features["stoch_d_3"] = stoch_d

        # 5. Trend & Volatility
        macd_l, signal_l, hist = calculate_macd(close, 12, 26, 9)
        features["macd_line"] = macd_l
        features["macd_signal"] = signal_l
        features["macd_hist"] = hist

        _up, _mid, _low, bw, pct_b = calculate_bollinger_bands(close, 20, 2.0)
        features["bb_bandwidth_20"] = bw
        features["bb_percent_b_20"] = pct_b

        atr_14 = calculate_atr(high, low, close, 14)
        features["atr_14"] = atr_14
        features["atr_ratio"] = np.where(close > 0.0, atr_14 / close, 0.0)

        adx_14, p_di, m_di = calculate_adx(high, low, close, 14)
        features["adx_14"] = adx_14
        features["plus_di_14"] = p_di
        features["minus_di_14"] = m_di
        features["di_diff"] = p_di - m_di

        features["hist_vol_20"] = calculate_historical_volatility(close, 20)

        # 6. Volume Dynamics
        vol_ma_20 = calculate_volume_ma(volume, 20)
        features["vol_to_ma_20"] = np.where(vol_ma_20 > 0.0, volume / vol_ma_20, 1.0)

        obv = calculate_obv(close, volume)
        features["obv"] = obv
        features["obv_diff_5"] = calculate_returns(obv, periods=5)

        vwap = calculate_vwap(high, low, close, volume)
        features["vwap_ratio"] = np.where(vwap > 0.0, (close / vwap) - 1.0, 0.0)

        # Handle infinite values that could arise from zero divisions
        features = features.replace([np.inf, -np.inf], np.nan)

        if drop_warmup:
            features = features.iloc[self.max_warmup :]

        return features
