"""
CryptoPilot AI - Price Return Calculations.
Zero-lookahead implementations of multi-period simple and logarithmic returns.
"""

import numpy as np
import pandas as pd

from cryptopilot.indicators.base import BaseIndicator


def calculate_returns(series: pd.Series, periods: int = 1) -> pd.Series:
    """
    Computes percentage price return over k periods.
    Formula: (Close_t - Close_{t-k}) / Close_{t-k}
    """
    if periods < 1:
        raise ValueError(f"Periods must be >= 1, got {periods}")
    if series.empty:
        return pd.Series(dtype=np.float64, index=series.index)
    return series.pct_change(periods=periods)


def calculate_log_returns(series: pd.Series, periods: int = 1) -> pd.Series:
    """
    Computes continuous logarithmic return over k periods.
    Formula: ln(Close_t / Close_{t-k})
    """
    if periods < 1:
        raise ValueError(f"Periods must be >= 1, got {periods}")
    if series.empty:
        return pd.Series(dtype=np.float64, index=series.index)
    return pd.Series(
        np.log(series / series.shift(periods)),
        index=series.index,
        name=f"LOG_RET_{periods}",
    )


class PriceReturns(BaseIndicator):
    """Simple Price Return Indicator."""

    def __init__(self, periods: int = 1, column: str = "close") -> None:
        super().__init__(name=f"RET_{periods}", warmup_period=periods + 1)
        self.periods = periods
        self.column = column

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, [self.column])
        if df.empty:
            return pd.Series(dtype=np.float64, index=df.index, name=self.name)
        res = calculate_returns(df[self.column], self.periods)
        res.name = self.name
        return res


class LogReturns(BaseIndicator):
    """Logarithmic Price Return Indicator."""

    def __init__(self, periods: int = 1, column: str = "close") -> None:
        super().__init__(name=f"LOG_RET_{periods}", warmup_period=periods + 1)
        self.periods = periods
        self.column = column

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, [self.column])
        if df.empty:
            return pd.Series(dtype=np.float64, index=df.index, name=self.name)
        res = calculate_log_returns(df[self.column], self.periods)
        res.name = self.name
        return res
