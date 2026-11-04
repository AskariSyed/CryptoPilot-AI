"""
CryptoPilot AI - Strategy B: RSI & MACD Momentum Confirmation.
Demands synchronous momentum convergence between MACD histogram crossover,
RSI bullish non-overbought zone (50-70), and volume confirmation.
"""

from datetime import UTC, datetime
from typing import Any
import numpy as np
import pandas as pd

from cryptopilot.indicators.momentum import calculate_rsi
from cryptopilot.indicators.moving_averages import calculate_ema, calculate_volume_ma
from cryptopilot.indicators.trend_volatility import calculate_atr, calculate_macd
from cryptopilot.strategies.base import BaseStrategy, SignalType, StrategySignal


class RSIMACDConfirmationStrategy(BaseStrategy):
    """
    Strategy B: RSI & MACD Confirmation.
    Captures high-probability momentum continuation with strict volume validation.
    """

    def __init__(
        self,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        ema_filter_period: int = 50,
        volume_ma_period: int = 20,
        atr_period: int = 14,
    ) -> None:
        super().__init__(
            strategy_id="rsi_macd",
            name="RSI & MACD Confirmation",
            min_bars=max(macd_slow + macd_signal, ema_filter_period) + 15,
        )
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.ema_filter_period = ema_filter_period
        self.volume_ma_period = volume_ma_period
        self.atr_period = atr_period

    def evaluate(self, df: pd.DataFrame, symbol: str) -> StrategySignal:
        is_valid, err_msg = self.validate_dataframe(df)
        if not is_valid:
            price = float(df["close"].iloc[-1]) if df is not None and not df.empty else 0.0
            return self.create_hold_signal(symbol, price, f"Data validation failed: {err_msg}")

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]
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

        # 1. Compute Indicators
        ema_filter = calculate_ema(close, self.ema_filter_period)
        macd_line, signal_line, hist = calculate_macd(
            close, self.macd_fast, self.macd_slow, self.macd_signal
        )
        rsi = calculate_rsi(close, self.rsi_period)
        vol_ma = calculate_volume_ma(volume, self.volume_ma_period)
        atr = calculate_atr(high, low, close, self.atr_period)

        ema_val = float(ema_filter.iloc[t])
        macd_curr = float(macd_line.iloc[t])
        hist_curr = float(hist.iloc[t])
        hist_prev = float(hist.iloc[t - 1])
        hist_prev2 = float(hist.iloc[t - 2])
        rsi_curr = float(rsi.iloc[t])
        vol_curr = float(volume.iloc[t])
        vol_ma_curr = float(vol_ma.iloc[t])
        atr_curr = float(atr.iloc[t])

        metrics: dict[str, Any] = {
            "price": curr_price,
            "ema_filter": ema_val,
            "macd": macd_curr,
            "macd_hist": hist_curr,
            "rsi": rsi_curr,
            "volume": vol_curr,
            "volume_ma": vol_ma_curr,
            "atr": atr_curr,
        }

        if any(np.isnan(v) for v in metrics.values()):
            return self.create_hold_signal(
                symbol, curr_price, "Indicator calculation produced NaNs (warmup incomplete)", metrics, timestamp
            )

        # 2. Evaluate BUY Conditions
        # Price > EMA filter
        trend_ok = curr_price > ema_val
        # Histogram crossed above 0
        hist_cross_up = (hist_curr > 0.0) and (hist_prev <= 0.0)
        # RSI in active momentum zone (50 < RSI < 70)
        rsi_bullish = 50.0 < rsi_curr < 70.0
        # Volume above average
        volume_ok = vol_curr > vol_ma_curr

        if trend_ok and hist_cross_up and rsi_bullish and volume_ok:
            stop_loss = curr_price - (1.5 * atr_curr)
            if stop_loss >= curr_price or stop_loss <= 0.0:
                stop_loss = curr_price * 0.98

            take_profit = curr_price + (2.5 * (curr_price - stop_loss))

            # Confidence formula
            rsi_sweet_spot = max(0.0, min(1.0, (70.0 - rsi_curr) / 20.0))
            hist_strength = min(1.0, max(0.0, hist_curr / (atr_curr if atr_curr > 0 else 1.0)))
            confidence = float(np.clip(0.55 + (0.20 * rsi_sweet_spot) + (0.20 * hist_strength), 0.55, 0.95))

            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.BUY,
                confidence=confidence,
                entry_price=curr_price,
                suggested_stop_loss=stop_loss,
                suggested_take_profit=take_profit,
                rationale=(
                    f"MACD histogram crossed positive ({hist_curr:.4f}) with RSI in bullish zone "
                    f"({rsi_curr:.1f}) above EMA {self.ema_filter_period}. "
                    f"Volume ({vol_curr:.0f}) confirmed above 20-bar average ({vol_ma_curr:.0f})."
                ),
                invalidation_condition="MACD Line drops below zero or RSI breaks below 45",
                timestamp=timestamp,
                metrics=metrics,
            )

        # 3. Evaluate SELL Conditions
        # MACD histogram negative for 2 consecutive bars OR RSI > 75 overbought exhaustion
        hist_negative_2 = (hist_curr < 0.0) and (hist_prev < 0.0) and (hist_prev2 >= 0.0 or curr_price < ema_val)
        overbought_exhaustion = rsi_curr > 75.0

        if hist_negative_2 or overbought_exhaustion:
            confidence = 0.80 if overbought_exhaustion else 0.70
            rationale_text = (
                f"RSI overbought exhaustion ({rsi_curr:.1f} > 75)"
                if overbought_exhaustion
                else f"MACD histogram consecutive negative bars ({hist_curr:.4f})"
            )
            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.SELL,
                confidence=confidence,
                entry_price=curr_price,
                suggested_stop_loss=curr_price * 1.02,
                suggested_take_profit=None,
                rationale=rationale_text,
                invalidation_condition=f"RSI rebounds above 60 with positive MACD histogram",
                timestamp=timestamp,
                metrics=metrics,
            )

        # 4. Default to HOLD
        reasons: list[str] = []
        if not trend_ok:
            reasons.append(f"Price ({curr_price:.2f}) <= EMA 50 ({ema_val:.2f})")
        if not hist_cross_up:
            reasons.append(f"No fresh MACD histogram cross (hist={hist_curr:.4f})")
        if not rsi_bullish:
            reasons.append(f"RSI ({rsi_curr:.1f}) not in range (50, 70)")
        if not volume_ok:
            reasons.append("Volume below average")

        reason_str = "No setup: " + (", ".join(reasons) if reasons else "Momentum neutral")
        return self.create_hold_signal(symbol, curr_price, reason_str, metrics, timestamp)
