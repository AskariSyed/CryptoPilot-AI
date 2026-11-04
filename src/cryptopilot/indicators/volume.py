"""
CryptoPilot AI - Volume Indicators.
Zero-lookahead implementations of On-Balance Volume (OBV) and
Volume-Weighted Average Price (VWAP).
"""

import numpy as np
import pandas as pd

from cryptopilot.indicators.base import BaseIndicator


def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Computes On-Balance Volume (OBV).
    OBV_t = OBV_{t-1} + (Volume_t if Close_t > Close_{t-1} else -Volume_t if Close_t < Close_{t-1} else 0)
    """
    if close.empty or volume.empty:
        return pd.Series(dtype=np.float64, index=close.index)

    close_diff = close.diff()
    direction = np.zeros(len(close), dtype=np.float64)
    direction[close_diff > 0] = 1.0
    direction[close_diff < 0] = -1.0
    direction[0] = 0.0

    obv = (direction * volume.to_numpy()).cumsum()
    return pd.Series(obv, index=close.index, name="OBV")


def calculate_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    rolling_window: int | None = None,
) -> pd.Series:
    """
    Computes Volume-Weighted Average Price (VWAP).
    Typical Price = (High + Low + Close) / 3
    VWAP = sum(Typical Price * Volume) / sum(Volume)
    """
    if close.empty:
        return pd.Series(dtype=np.float64, index=close.index)

    typical_price = (high + low + close) / 3.0
    tp_vol = typical_price * volume

    if rolling_window is not None:
        if rolling_window < 1:
            raise ValueError(f"rolling_window must be >= 1, got {rolling_window}")
        cum_tp_vol = tp_vol.rolling(window=rolling_window, min_periods=1).sum()
        cum_vol = volume.rolling(window=rolling_window, min_periods=1).sum()
    else:
        cum_tp_vol = tp_vol.cumsum()
        cum_vol = volume.cumsum()

    vwap = np.where(cum_vol > 0.0, cum_tp_vol / cum_vol, typical_price)
    name = f"VWAP_{rolling_window}" if rolling_window else "VWAP"
    return pd.Series(vwap, index=close.index, name=name)


class OBV(BaseIndicator):
    """On-Balance Volume Indicator."""

    def __init__(self) -> None:
        super().__init__(name="OBV", warmup_period=2)

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, ["close", "volume"])
        if df.empty:
            return pd.Series(dtype=np.float64, index=df.index, name=self.name)
        res = calculate_obv(df["close"], df["volume"])
        res.name = self.name
        return res


class VWAP(BaseIndicator):
    """Volume-Weighted Average Price Indicator."""

    def __init__(self, rolling_window: int | None = None) -> None:
        name = f"VWAP_{rolling_window}" if rolling_window else "VWAP"
        super().__init__(name=name, warmup_period=rolling_window or 1)
        self.rolling_window = rolling_window

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, ["high", "low", "close", "volume"])
        if df.empty:
            return pd.Series(dtype=np.float64, index=df.index, name=self.name)
        res = calculate_vwap(df["high"], df["low"], df["close"], df["volume"], self.rolling_window)
        res.name = self.name
        return res
