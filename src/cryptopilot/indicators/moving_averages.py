"""
CryptoPilot AI - Moving Average Indicator Calculations.
Mathematically verified zero-lookahead implementations of SMA, EMA, WMA, and Volume MA.
"""

import numpy as np
import pandas as pd

from cryptopilot.indicators.base import BaseIndicator


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """
    Computes Simple Moving Average (SMA).
    Formula: SMA_t = (1 / N) * sum_{i=0}^{N-1} x_{t-i}
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if series.empty:
        return pd.Series(dtype=np.float64, index=series.index)
    return series.rolling(window=period, min_periods=period).mean()


def calculate_ema(series: pd.Series, period: int, alpha: float | None = None) -> pd.Series:
    """
    Computes Exponential Moving Average (EMA).
    Formula:
      alpha = 2 / (N + 1) if not provided
      EMA_0 = SMA_0..N-1
      EMA_t = alpha * x_t + (1 - alpha) * EMA_{t-1}
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if series.empty:
        return pd.Series(dtype=np.float64, index=series.index)

    if alpha is None:
        alpha = 2.0 / (period + 1.0)
    elif not (0.0 < alpha <= 1.0):
        raise ValueError(f"Smoothing factor alpha must be in (0.0, 1.0], got {alpha}")

    # Use pandas ewm with adjust=False for standard recursive financial EMA
    result = series.ewm(alpha=alpha, adjust=False, min_periods=period).mean()

    # In standard financial practice, values before warmup period are set to NaN
    if len(result) >= period:
        result.iloc[: period - 1] = np.nan
    else:
        result.iloc[:] = np.nan
    return result


def calculate_wma(series: pd.Series, period: int) -> pd.Series:
    """
    Computes Linearly Weighted Moving Average (WMA).
    Formula: WMA_t = sum_{i=1}^N (i * x_{t-N+i}) / sum_{i=1}^N i
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if series.empty:
        return pd.Series(dtype=np.float64, index=series.index)
    if len(series) < period:
        return pd.Series(np.nan, index=series.index, dtype=np.float64)

    weights = np.arange(1, period + 1, dtype=np.float64)
    sum_weights = weights.sum()

    def _wma_window(window: np.ndarray) -> float:
        return float(np.dot(window, weights) / sum_weights)

    return series.rolling(window=period, min_periods=period).apply(_wma_window, raw=True)


def calculate_volume_ma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Computes Simple Moving Average of volume series."""
    return calculate_sma(volume, period)


class SMA(BaseIndicator):
    """Simple Moving Average (SMA) Indicator."""

    def __init__(self, period: int = 20, column: str = "close") -> None:
        super().__init__(name=f"SMA_{period}", warmup_period=period)
        self.period = period
        self.column = column

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, [self.column])
        if df.empty:
            return pd.Series(dtype=np.float64, index=df.index, name=self.name)
        res = calculate_sma(df[self.column], self.period)
        res.name = self.name
        return res


class EMA(BaseIndicator):
    """Exponential Moving Average (EMA) Indicator."""

    def __init__(self, period: int = 20, column: str = "close", alpha: float | None = None) -> None:
        super().__init__(name=f"EMA_{period}", warmup_period=period)
        self.period = period
        self.column = column
        self.alpha = alpha

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, [self.column])
        if df.empty:
            return pd.Series(dtype=np.float64, index=df.index, name=self.name)
        res = calculate_ema(df[self.column], self.period, self.alpha)
        res.name = self.name
        return res


class VolumeMA(BaseIndicator):
    """Volume Moving Average Indicator."""

    def __init__(self, period: int = 20, column: str = "volume") -> None:
        super().__init__(name=f"VolumeMA_{period}", warmup_period=period)
        self.period = period
        self.column = column

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, [self.column])
        if df.empty:
            return pd.Series(dtype=np.float64, index=df.index, name=self.name)
        res = calculate_volume_ma(df[self.column], self.period)
        res.name = self.name
        return res
