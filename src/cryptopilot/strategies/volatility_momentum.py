"""
CryptoPilot AI - Strategy D: Volatility-Adjusted Momentum.
Captures explosive breakout momentum using a Bollinger Band / Keltner Channel squeeze release,
trend filter (EMA 20), and dynamic ATR-scaled trailing stops.
"""

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from cryptopilot.indicators.moving_averages import calculate_ema
from cryptopilot.indicators.returns import calculate_returns
from cryptopilot.indicators.trend_volatility import (
    calculate_atr,
    calculate_bollinger_bands,
)
from cryptopilot.strategies.base import BaseStrategy, SignalType, StrategySignal


class VolatilityAdjustedMomentumStrategy(BaseStrategy):
    """
    Strategy D: Volatility-Adjusted Momentum.
    Identifies volatility compression (squeeze) followed by expansion and trend momentum.
    """

    def __init__(
        self,
        period: int = 20,
        bb_std: float = 2.0,
        kc_atr_multiplier: float = 1.5,
        momentum_period: int = 12,
        atr_period: int = 14,
    ) -> None:
        super().__init__(
            strategy_id="volatility_momentum",
            name="Volatility-Adjusted Momentum",
            min_bars=max(period, atr_period, momentum_period) + 15,
        )
        self.period = period
        self.bb_std = bb_std
        self.kc_atr_multiplier = kc_atr_multiplier
        self.momentum_period = momentum_period
        self.atr_period = atr_period

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
        timestamp = df["timestamp"].iloc[t] if "timestamp" in df.columns else datetime.now(UTC)
        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        # 1. Compute Bollinger Bands & Keltner Channels
        bb_upper, bb_mid, bb_lower, bb_bw, _pct_b = calculate_bollinger_bands(
            close, self.period, self.bb_std
        )
        ema_mid = calculate_ema(close, self.period)
        atr = calculate_atr(high, low, close, self.atr_period)
        returns_mom = calculate_returns(close, self.momentum_period)

        # Keltner Channels: EMA +/- (kc_atr_multiplier * ATR)
        kc_upper = ema_mid + (atr * self.kc_atr_multiplier)
        kc_lower = ema_mid - (atr * self.kc_atr_multiplier)

        # Determine Squeeze on previous bars: BB inside KC
        # Squeeze True when BB_upper < KC_upper and BB_lower > KC_lower
        is_squeeze_series = (bb_upper < kc_upper) & (bb_lower > kc_lower)
        had_recent_squeeze = bool(is_squeeze_series.iloc[t - 4 : t].any())

        # Squeeze release on current bar: BB expands outside KC
        bb_up_curr = float(bb_upper.iloc[t])
        kc_up_curr = float(kc_upper.iloc[t])
        ema_curr = float(ema_mid.iloc[t])
        atr_curr = float(atr.iloc[t])
        mom_curr = float(returns_mom.iloc[t])
        bw_curr = float(bb_bw.iloc[t])
        bw_min_5 = float(bb_bw.iloc[t - 5 : t].min()) if t >= 5 else bw_curr

        is_breakout_up = bb_up_curr >= kc_up_curr

        metrics: dict[str, Any] = {
            "price": curr_price,
            "bb_upper": bb_up_curr,
            "kc_upper": kc_up_curr,
            "ema_20": ema_curr,
            "atr": atr_curr,
            "momentum_12": mom_curr,
            "bandwidth": bw_curr,
            "had_recent_squeeze": had_recent_squeeze,
        }

        if any(np.isnan(v) for v in metrics.values() if isinstance(v, (int, float))):
            return self.create_hold_signal(
                symbol,
                curr_price,
                "Indicator calculation produced NaNs (warmup incomplete)",
                metrics,
                timestamp,
            )

        # 2. Evaluate BUY Entry Conditions
        # Condition 1: Squeeze release fired (breakout up after recent squeeze)
        # Condition 2: Momentum is positive
        # Condition 3: Close > EMA 20
        trend_above_ema = curr_price > ema_curr
        positive_mom = mom_curr > 0.0

        if had_recent_squeeze and is_breakout_up and positive_mom and trend_above_ema:
            stop_loss = curr_price - (2.5 * atr_curr)
            if stop_loss >= curr_price or stop_loss <= 0.0:
                stop_loss = curr_price * 0.97

            take_profit = curr_price + (3.0 * (curr_price - stop_loss))

            # Confidence formula based on bandwidth expansion ratio
            bw_expansion = max(0.0, min(1.0, (bw_curr - bw_min_5) / max(0.001, bw_min_5)))
            confidence = float(np.clip(0.60 + (0.35 * bw_expansion), 0.60, 0.95))

            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.BUY,
                confidence=confidence,
                entry_price=curr_price,
                suggested_stop_loss=stop_loss,
                suggested_take_profit=take_profit,
                rationale=(
                    f"Volatility squeeze release breakout: Bollinger Upper ({bb_up_curr:.2f}) "
                    f"expanded outside Keltner Channel ({kc_up_curr:.2f}). "
                    f"12-bar momentum is positive (+{mom_curr * 100:.2f}%) and price > EMA 20."
                ),
                invalidation_condition=f"Close below EMA 20 midpoint ({ema_curr:.2f})",
                timestamp=timestamp,
                metrics=metrics,
            )

        # 3. Evaluate SELL Exit Conditions
        # Momentum turned negative or price closed below EMA 20
        if mom_curr < -0.01 or curr_price < ema_curr:
            confidence = 0.70 if curr_price < ema_curr else 0.60
            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.SELL,
                confidence=confidence,
                entry_price=curr_price,
                suggested_stop_loss=curr_price * 1.02,
                suggested_take_profit=None,
                rationale=(
                    f"Volatility momentum exhaustion: Price dropped below EMA 20 ({ema_curr:.2f}) "
                    f"or 12-bar momentum turned negative ({mom_curr * 100:.2f}%)."
                ),
                invalidation_condition="Price breaks back above upper Bollinger Band",
                timestamp=timestamp,
                metrics=metrics,
            )

        # 4. Default to HOLD
        reasons: list[str] = []
        if not had_recent_squeeze:
            reasons.append("No recent volatility squeeze")
        if not is_breakout_up:
            reasons.append("Bollinger Band not expanding outside Keltner Channel")
        if not positive_mom:
            reasons.append(f"Momentum negative ({mom_curr * 100:.2f}%)")
        if not trend_above_ema:
            reasons.append(f"Price ({curr_price:.2f}) <= EMA 20 ({ema_curr:.2f})")

        reason_str = "No setup: " + (", ".join(reasons) if reasons else "Consolidating/no breakout")
        return self.create_hold_signal(symbol, curr_price, reason_str, metrics, timestamp)
