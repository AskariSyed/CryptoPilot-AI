"""
CryptoPilot AI - Trend & Volatility Indicators.
Mathematically verified zero-lookahead implementations of MACD, Bollinger Bands,
ATR, ADX, and Historical Volatility.
"""

import math

import numpy as np
import pandas as pd

from cryptopilot.indicators.base import BaseIndicator
from cryptopilot.indicators.moving_averages import calculate_ema, calculate_sma


def calculate_macd(
    series: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Computes Moving Average Convergence Divergence (MACD).
    MACD Line = EMA(fast) - EMA(slow)
    Signal Line = EMA(MACD Line, signal_period)
    Histogram = MACD Line - Signal Line
    """
    if fast_period < 1 or slow_period < 1 or signal_period < 1:
        raise ValueError("All periods must be >= 1")
    if fast_period >= slow_period:
        raise ValueError(f"fast_period ({fast_period}) must be < slow_period ({slow_period})")

    if series.empty:
        empty = pd.Series(dtype=np.float64, index=series.index)
        return empty, empty, empty

    fast_ema = calculate_ema(series, fast_period)
    slow_ema = calculate_ema(series, slow_period)

    macd_line = fast_ema - slow_ema
    macd_line.name = "MACD_LINE"

    signal_line = calculate_ema(macd_line, signal_period)
    signal_line.name = "MACD_SIGNAL"

    histogram = macd_line - signal_line
    histogram.name = "MACD_HIST"

    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    series: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Computes Bollinger Bands:
    Middle Band = SMA(Close, period)
    Upper Band = Middle Band + num_std * std
    Lower Band = Middle Band - num_std * std
    Bandwidth = (Upper - Lower) / Middle
    %B = (Close - Lower) / (Upper - Lower)
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if num_std <= 0:
        raise ValueError(f"num_std must be > 0, got {num_std}")

    if series.empty:
        empty = pd.Series(dtype=np.float64, index=series.index)
        return empty, empty, empty, empty, empty

    middle = calculate_sma(series, period)
    middle.name = f"BB_MID_{period}"

    rolling_std = series.rolling(window=period, min_periods=period).std(ddof=0)

    upper = middle + (rolling_std * num_std)
    upper.name = f"BB_UPPER_{period}"

    lower = middle - (rolling_std * num_std)
    lower.name = f"BB_LOWER_{period}"

    bandwidth = np.where(middle > 0.0, (upper - lower) / middle, 0.0)
    bw_series = pd.Series(bandwidth, index=series.index, name=f"BB_BW_{period}")

    band_range = upper - lower
    pct_b = np.where(band_range > 0.0, (series - lower) / band_range, 0.5)
    pct_b_series = pd.Series(pct_b, index=series.index, name=f"BB_PCT_B_{period}")

    return upper, middle, lower, bw_series, pct_b_series


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Computes Average True Range (ATR) using Wilder's smoothing.
    TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
    ATR_t = (ATR_{t-1} * (period - 1) + TR_t) / period
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if close.empty:
        return pd.Series(dtype=np.float64, index=close.index)
    if len(close) < period:
        return pd.Series(np.nan, index=close.index, dtype=np.float64)

    high_np = high.to_numpy()
    low_np = low.to_numpy()
    close_np = close.to_numpy()
    n = len(close_np)

    tr = np.zeros(n, dtype=np.float64)
    tr[0] = high_np[0] - low_np[0]

    for i in range(1, n):
        hl = high_np[i] - low_np[i]
        hc = abs(high_np[i] - close_np[i - 1])
        lc = abs(low_np[i] - close_np[i - 1])
        tr[i] = max(hl, hc, lc)

    atr_vals = np.full(n, np.nan, dtype=np.float64)
    # First ATR is arithmetic average of first `period` true ranges
    atr_vals[period - 1] = float(np.mean(tr[:period]))

    for i in range(period, n):
        atr_vals[i] = (atr_vals[i - 1] * (period - 1) + tr[i]) / period

    return pd.Series(atr_vals, index=close.index, name=f"ATR_{period}")


def calculate_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Computes Average Directional Index (ADX), +DI, and -DI using Wilder smoothing.
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if close.empty:
        empty = pd.Series(dtype=np.float64, index=close.index)
        return empty, empty, empty

    n = len(close)
    if n < (period * 2):
        empty_nan = pd.Series(np.nan, index=close.index, dtype=np.float64)
        return empty_nan, empty_nan, empty_nan

    high_np = high.to_numpy()
    low_np = low.to_numpy()
    close_np = close.to_numpy()

    plus_dm = np.zeros(n, dtype=np.float64)
    minus_dm = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = high_np[0] - low_np[0]

    for i in range(1, n):
        up_move = high_np[i] - high_np[i - 1]
        down_move = low_np[i - 1] - low_np[i]

        if up_move > down_move and up_move > 0.0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0.0:
            minus_dm[i] = down_move

        hl = high_np[i] - low_np[i]
        hc = abs(high_np[i] - close_np[i - 1])
        lc = abs(low_np[i] - close_np[i - 1])
        tr[i] = max(hl, hc, lc)

    # Wilder smoothing of TR, +DM, -DM
    smooth_tr = np.full(n, np.nan, dtype=np.float64)
    smooth_plus_dm = np.full(n, np.nan, dtype=np.float64)
    smooth_minus_dm = np.full(n, np.nan, dtype=np.float64)

    smooth_tr[period - 1] = float(np.sum(tr[:period]))
    smooth_plus_dm[period - 1] = float(np.sum(plus_dm[:period]))
    smooth_minus_dm[period - 1] = float(np.sum(minus_dm[:period]))

    for i in range(period, n):
        smooth_tr[i] = smooth_tr[i - 1] - (smooth_tr[i - 1] / period) + tr[i]
        smooth_plus_dm[i] = smooth_plus_dm[i - 1] - (smooth_plus_dm[i - 1] / period) + plus_dm[i]
        smooth_minus_dm[i] = (
            smooth_minus_dm[i - 1] - (smooth_minus_dm[i - 1] / period) + minus_dm[i]
        )

    plus_di = np.full(n, np.nan, dtype=np.float64)
    minus_di = np.full(n, np.nan, dtype=np.float64)
    dx = np.full(n, np.nan, dtype=np.float64)

    for i in range(period - 1, n):
        if smooth_tr[i] > 0.0:
            plus_di[i] = (smooth_plus_dm[i] / smooth_tr[i]) * 100.0
            minus_di[i] = (smooth_minus_dm[i] / smooth_tr[i]) * 100.0
        else:
            plus_di[i] = 0.0
            minus_di[i] = 0.0

        di_sum = plus_di[i] + minus_di[i]
        if di_sum > 0.0:
            dx[i] = (abs(plus_di[i] - minus_di[i]) / di_sum) * 100.0
        else:
            dx[i] = 0.0

    # ADX is the Wilder smoothed DX starting at 2 * period - 1
    adx = np.full(n, np.nan, dtype=np.float64)
    adx_start = (2 * period) - 1
    if n >= adx_start:
        adx[adx_start - 1] = float(np.mean(dx[period - 1 : adx_start]))
        for i in range(adx_start, n):
            adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period

    return (
        pd.Series(adx, index=close.index, name=f"ADX_{period}"),
        pd.Series(plus_di, index=close.index, name=f"PLUS_DI_{period}"),
        pd.Series(minus_di, index=close.index, name=f"MINUS_DI_{period}"),
    )


def calculate_historical_volatility(
    close: pd.Series,
    period: int = 20,
    trading_periods: int = 365,
) -> pd.Series:
    """
    Computes Annualized Historical Volatility (standard deviation of log returns).
    Formula: std(ln(Close_t / Close_{t-1}), period) * sqrt(trading_periods)
    """
    if period < 2:
        raise ValueError(f"Period must be >= 2, got {period}")
    if close.empty or len(close) < period:
        return pd.Series(np.nan, index=close.index, dtype=np.float64)

    log_returns = pd.Series(
        np.log(close / close.shift(1)),
        index=close.index,
    )
    rolling_vol = log_returns.rolling(window=period, min_periods=period).std(ddof=1)
    annualized = pd.Series(
        rolling_vol * math.sqrt(trading_periods),
        index=close.index,
        name=f"HV_{period}",
    )
    return annualized


class MACD(BaseIndicator):
    """Moving Average Convergence Divergence Indicator."""

    def __init__(
        self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
    ) -> None:
        super().__init__(
            name=f"MACD_{fast_period}_{slow_period}_{signal_period}",
            warmup_period=slow_period + signal_period,
        )
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        self.validate_input(df, ["close"])
        if df.empty:
            return pd.DataFrame(
                {"MACD_LINE": [], "MACD_SIGNAL": [], "MACD_HIST": []}, index=df.index
            )
        macd_l, signal_l, hist = calculate_macd(
            df["close"], self.fast_period, self.slow_period, self.signal_period
        )
        return pd.DataFrame(
            {"MACD_LINE": macd_l, "MACD_SIGNAL": signal_l, "MACD_HIST": hist}, index=df.index
        )


class BollingerBands(BaseIndicator):
    """Bollinger Bands Indicator."""

    def __init__(self, period: int = 20, num_std: float = 2.0) -> None:
        super().__init__(name=f"BB_{period}_{num_std}", warmup_period=period)
        self.period = period
        self.num_std = num_std

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        self.validate_input(df, ["close"])
        if df.empty:
            return pd.DataFrame(
                {"BB_UPPER": [], "BB_MID": [], "BB_LOWER": [], "BB_BW": [], "BB_PCT_B": []},
                index=df.index,
            )
        up, mid, low, bw, pct_b = calculate_bollinger_bands(df["close"], self.period, self.num_std)
        return pd.DataFrame(
            {"BB_UPPER": up, "BB_MID": mid, "BB_LOWER": low, "BB_BW": bw, "BB_PCT_B": pct_b},
            index=df.index,
        )


class ATR(BaseIndicator):
    """Average True Range Indicator."""

    def __init__(self, period: int = 14) -> None:
        super().__init__(name=f"ATR_{period}", warmup_period=period)
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, ["high", "low", "close"])
        if df.empty:
            return pd.Series(dtype=np.float64, index=df.index, name=self.name)
        res = calculate_atr(df["high"], df["low"], df["close"], self.period)
        res.name = self.name
        return res


class ADX(BaseIndicator):
    """Average Directional Index Indicator."""

    def __init__(self, period: int = 14) -> None:
        super().__init__(name=f"ADX_{period}", warmup_period=period * 2)
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        self.validate_input(df, ["high", "low", "close"])
        if df.empty:
            return pd.DataFrame({"ADX": [], "PLUS_DI": [], "MINUS_DI": []}, index=df.index)
        adx, p_di, m_di = calculate_adx(df["high"], df["low"], df["close"], self.period)
        return pd.DataFrame({"ADX": adx, "PLUS_DI": p_di, "MINUS_DI": m_di}, index=df.index)


class HistoricalVolatility(BaseIndicator):
    """Annualized Historical Volatility Indicator."""

    def __init__(self, period: int = 20, trading_periods: int = 365) -> None:
        super().__init__(name=f"HV_{period}", warmup_period=period + 1)
        self.period = period
        self.trading_periods = trading_periods

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, ["close"])
        if df.empty:
            return pd.Series(dtype=np.float64, index=df.index, name=self.name)
        res = calculate_historical_volatility(df["close"], self.period, self.trading_periods)
        res.name = self.name
        return res
