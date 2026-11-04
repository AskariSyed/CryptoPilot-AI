"""
CryptoPilot AI - Momentum Indicators.
Mathematically verified zero-lookahead implementations of RSI and Stochastic Oscillator.
"""

import numpy as np
import pandas as pd

from cryptopilot.indicators.base import BaseIndicator
from cryptopilot.indicators.moving_averages import calculate_sma


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Computes Relative Strength Index (RSI) using Wilder's Smoothing Technique.
    Guarantees standard financial accuracy and zero lookahead.
    Values before warmup period (period) are NaN.
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if series.empty:
        return pd.Series(dtype=np.float64, index=series.index)
    if len(series) <= period:
        return pd.Series(np.nan, index=series.index, dtype=np.float64)

    delta = series.diff()
    gains = delta.clip(lower=0.0).to_numpy()
    losses = (-delta.clip(upper=0.0)).to_numpy()

    rsi_values = np.full(len(series), np.nan, dtype=np.float64)

    # First average calculation at index = period (using indices 1 through period)
    avg_gain = float(np.mean(gains[1 : period + 1]))
    avg_loss = float(np.mean(losses[1 : period + 1]))

    if avg_loss == 0.0:
        rsi_values[period] = 100.0 if avg_gain > 0.0 else 50.0
    else:
        rs = avg_gain / avg_loss
        rsi_values[period] = 100.0 - (100.0 / (1.0 + rs))

    # Wilder's Smoothing for subsequent periods
    for i in range(period + 1, len(series)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0.0:
            rsi_values[i] = 100.0 if avg_gain > 0.0 else 50.0
        else:
            rs = avg_gain / avg_loss
            rsi_values[i] = 100.0 - (100.0 / (1.0 + rs))

    return pd.Series(rsi_values, index=series.index, name=f"RSI_{period}")


def calculate_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[pd.Series, pd.Series]:
    """
    Computes Stochastic Oscillator (%K and %D).
    %K = ((Close - Lowest Low) / (Highest High - Lowest Low)) * 100
    %D = SMA(%K, d_period)
    """
    if k_period < 1 or d_period < 1:
        raise ValueError(f"Periods must be >= 1, got k={k_period}, d={d_period}")
    if close.empty:
        empty = pd.Series(dtype=np.float64, index=close.index)
        return empty, empty

    lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
    highest_high = high.rolling(window=k_period, min_periods=k_period).max()

    hl_range = highest_high - lowest_low

    # Handle zero range division edge case (constant price across window)
    fast_k = np.where(hl_range == 0.0, 50.0, ((close - lowest_low) / hl_range) * 100.0)
    fast_k_series = pd.Series(fast_k, index=close.index, name=f"STOCH_K_{k_period}")

    # Set NaN for warmup period
    if len(close) >= k_period:
        fast_k_series.iloc[: k_period - 1] = np.nan
    else:
        fast_k_series.iloc[:] = np.nan

    slow_d_series = calculate_sma(fast_k_series, d_period)
    slow_d_series.name = f"STOCH_D_{d_period}"

    return fast_k_series, slow_d_series


class RSI(BaseIndicator):
    """Relative Strength Index Indicator."""

    def __init__(self, period: int = 14, column: str = "close") -> None:
        super().__init__(name=f"RSI_{period}", warmup_period=period + 1)
        self.period = period
        self.column = column

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, [self.column])
        if df.empty:
            return pd.Series(dtype=np.float64, index=df.index, name=self.name)
        res = calculate_rsi(df[self.column], self.period)
        res.name = self.name
        return res


class StochasticOscillator(BaseIndicator):
    """Stochastic Oscillator (%K, %D)."""

    def __init__(self, k_period: int = 14, d_period: int = 3) -> None:
        super().__init__(name=f"STOCH_{k_period}_{d_period}", warmup_period=k_period + d_period)
        self.k_period = k_period
        self.d_period = d_period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        self.validate_input(df, ["high", "low", "close"])
        if df.empty:
            return pd.DataFrame(
                {f"STOCH_K_{self.k_period}": [], f"STOCH_D_{self.d_period}": []}, index=df.index
            )
        k_series, d_series = calculate_stochastic(
            df["high"], df["low"], df["close"], self.k_period, self.d_period
        )
        return pd.DataFrame({k_series.name: k_series, d_series.name: d_series}, index=df.index)
