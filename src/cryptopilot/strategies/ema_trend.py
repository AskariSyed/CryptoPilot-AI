"""
CryptoPilot AI - Strategy A: EMA Trend Following.
Combines triple EMA alignment (20/50/200) with ADX trend-strength confirmation
and ATR-based dynamic stop-loss positioning.
"""

from datetime import UTC, datetime
from typing import Any
import numpy as np
import pandas as pd

from cryptopilot.indicators.moving_averages import calculate_ema
from cryptopilot.indicators.trend_volatility import calculate_adx, calculate_atr
from cryptopilot.strategies.base import BaseStrategy, SignalType, StrategySignal


class EMATrendFollowingStrategy(BaseStrategy):
    """
    Strategy A: EMA Trend Following.
    Captures sustained directional trends filtered by macro regime and ADX strength.
    """

    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        baseline_period: int = 200,
        adx_period: int = 14,
        atr_period: int = 14,
        min_adx: float = 25.0,
    ) -> None:
        super().__init__(
            strategy_id="ema_trend",
            name="EMA Trend Following",
            min_bars=baseline_period + 10,
        )
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.baseline_period = baseline_period
        self.adx_period = adx_period
        self.atr_period = atr_period
        self.min_adx = min_adx

    def evaluate(self, df: pd.DataFrame, symbol: str) -> StrategySignal:
        is_valid, err_msg = self.validate_dataframe(df)
        if not is_valid:
            price = float(df["close"].iloc[-1]) if df is not None and not df.empty else 0.0
            return self.create_hold_signal(symbol, price, f"Data validation failed: {err_msg}")

        close = df["close"]
        high = df["high"]
        low = df["low"]
        t = len(df) - 1

        curr_price = float(close.iloc[t])
        timestamp = (
            df["timestamp"].iloc[t]
            if "timestamp" in df.columns
            else datetime.now(UTC)
        )
        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        # 1. Calculate Indicators
        ema_fast = calculate_ema(close, self.fast_period)
        ema_slow = calculate_ema(close, self.slow_period)
        ema_baseline = calculate_ema(close, self.baseline_period)
        adx, p_di, m_di = calculate_adx(high, low, close, self.adx_period)
        atr = calculate_atr(high, low, close, self.atr_period)

        # Inspect current and previous values
        f_curr, f_prev = float(ema_fast.iloc[t]), float(ema_fast.iloc[t - 1])
        s_curr, s_prev = float(ema_slow.iloc[t]), float(ema_slow.iloc[t - 1])
        base_curr = float(ema_baseline.iloc[t])
        adx_curr = float(adx.iloc[t])
        adx_prev1 = float(adx.iloc[t - 1])
        adx_prev2 = float(adx.iloc[t - 2])
        atr_curr = float(atr.iloc[t])

        metrics: dict[str, Any] = {
            "price": curr_price,
            "ema_fast": f_curr,
            "ema_slow": s_curr,
            "ema_baseline": base_curr,
            "adx": adx_curr,
            "atr": atr_curr,
        }

        # Check for invalid/NaN values in indicators
        if any(np.isnan(v) for v in metrics.values()):
            return self.create_hold_signal(
                symbol, curr_price, "Indicator calculation produced NaNs (warmup incomplete)", metrics, timestamp
            )

        # 2. Evaluate BUY Entry Conditions
        # Condition 1: Macro bull regime (Price > EMA 200)
        macro_bull = curr_price > base_curr
        # Condition 2: Fast crosses above slow (or recent crossover within 2 bars with fast > slow)
        bullish_cross = (f_curr > s_curr) and ((f_prev <= s_prev) or (float(ema_fast.iloc[t - 2]) <= float(ema_slow.iloc[t - 2])))
        # Condition 3: ADX >= min_adx
        strong_trend = adx_curr >= self.min_adx
        # Condition 4: ADX rising
        adx_rising = adx_curr > adx_prev1 >= adx_prev2

        if macro_bull and bullish_cross and strong_trend and adx_rising:
            # Stop-loss: min(swing low last 5 bars, Close - 2.0 * ATR)
            swing_low_5 = float(low.iloc[t - 4 : t + 1].min())
            atr_stop = curr_price - (2.0 * atr_curr)
            stop_loss = min(swing_low_5, atr_stop)

            # Ensure stop loss is strictly positive and below entry
            if stop_loss >= curr_price:
                stop_loss = curr_price * 0.98

            take_profit = curr_price + (2.0 * (curr_price - stop_loss))

            # Confidence Formula
            adx_factor = min(1.0, max(0.0, (adx_curr - self.min_adx) / self.min_adx))
            dist_factor = min(1.0, max(0.0, (f_curr - s_curr) / (atr_curr if atr_curr > 0 else 1.0)))
            confidence = float(np.clip(0.50 + (0.25 * adx_factor) + (0.25 * dist_factor), 0.50, 0.95))

            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.BUY,
                confidence=confidence,
                entry_price=curr_price,
                suggested_stop_loss=stop_loss,
                suggested_take_profit=take_profit,
                rationale=(
                    f"EMA {self.fast_period} crossed above EMA {self.slow_period} "
                    f"in macro bull regime (Price > EMA {self.baseline_period}). "
                    f"ADX at {adx_curr:.1f} confirms accelerating trend strength."
                ),
                invalidation_condition=f"Close below EMA {self.baseline_period} ({base_curr:.2f})",
                timestamp=timestamp,
                metrics=metrics,
            )

        # 3. Evaluate SELL Exit Conditions
        # Condition: Fast crosses below slow OR price closes below slow EMA
        bearish_cross = (f_curr < s_curr) and (f_prev >= s_prev)
        break_below_slow = curr_price < s_curr and float(close.iloc[t - 1]) >= s_prev

        if bearish_cross or break_below_slow:
            confidence = 0.75 if bearish_cross else 0.65
            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.SELL,
                confidence=confidence,
                entry_price=curr_price,
                suggested_stop_loss=curr_price * 1.02,
                suggested_take_profit=None,
                rationale=(
                    f"Trend breakdown detected: EMA {self.fast_period} crossed below "
                    f"EMA {self.slow_period} or price closed below EMA {self.slow_period}."
                ),
                invalidation_condition=f"Rebound back above EMA {self.slow_period} ({s_curr:.2f})",
                timestamp=timestamp,
                metrics=metrics,
            )

        # 4. Default to HOLD
        reasons: list[str] = []
        if not macro_bull:
            reasons.append(f"Price ({curr_price:.2f}) <= EMA 200 ({base_curr:.2f})")
        if not strong_trend:
            reasons.append(f"ADX ({adx_curr:.1f}) < {self.min_adx}")
        if not adx_rising:
            reasons.append("ADX not rising")
        if f_curr <= s_curr:
            reasons.append(f"EMA {self.fast_period} <= EMA {self.slow_period}")

        reason_str = "No setup: " + (", ".join(reasons) if reasons else "Choppy trend conditions")
        return self.create_hold_signal(symbol, curr_price, reason_str, metrics, timestamp)
