"""
CryptoPilot AI - Strategy C: Bollinger Band Mean Reversion.
Exploits statistical price dislocations strictly in consolidating, ranging markets (ADX < 20).
Enforces regime filters to prevent catching falling knives in trending breakdowns.
"""

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from cryptopilot.indicators.momentum import calculate_rsi
from cryptopilot.indicators.trend_volatility import (
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
)
from cryptopilot.strategies.base import BaseStrategy, SignalType, StrategySignal


class BollingerMeanReversionStrategy(BaseStrategy):
    """
    Strategy C: Bollinger Band Mean Reversion.
    Operates strictly within low-trend regimes (ADX < 20) with confirmed reversal candle closes.
    """

    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        adx_period: int = 14,
        atr_period: int = 14,
        max_adx_regime: float = 20.0,
    ) -> None:
        super().__init__(
            strategy_id="bollinger_reversion",
            name="Bollinger Mean Reversion",
            min_bars=max(bb_period, adx_period * 2) + 10,
        )
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.atr_period = atr_period
        self.max_adx_regime = max_adx_regime

    def evaluate(self, df: pd.DataFrame, symbol: str) -> StrategySignal:
        is_valid, err_msg = self.validate_dataframe(df)
        if not is_valid:
            price = float(df["close"].iloc[-1]) if df is not None and not df.empty else 0.0
            return self.create_hold_signal(symbol, price, f"Data validation failed: {err_msg}")

        close = df["close"]
        high = df["high"]
        low = df["low"]
        open_p = df["open"]
        t = len(df) - 1

        curr_price = float(close.iloc[t])
        timestamp = df["timestamp"].iloc[t] if "timestamp" in df.columns else datetime.now(UTC)
        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        # 1. Calculate Indicators
        upper, middle, lower, bw, pct_b = calculate_bollinger_bands(
            close, self.bb_period, self.bb_std
        )
        rsi = calculate_rsi(close, self.rsi_period)
        adx, p_di, m_di = calculate_adx(high, low, close, self.adx_period)
        atr = calculate_atr(high, low, close, self.atr_period)

        bb_up = float(upper.iloc[t])
        bb_mid = float(middle.iloc[t])
        bb_low = float(lower.iloc[t])
        bb_low_prev = float(lower.iloc[t - 1])
        rsi_curr = float(rsi.iloc[t])
        rsi_prev = float(rsi.iloc[t - 1])
        adx_curr = float(adx.iloc[t])
        atr_curr = float(atr.iloc[t])

        metrics: dict[str, Any] = {
            "price": curr_price,
            "bb_upper": bb_up,
            "bb_middle": bb_mid,
            "bb_lower": bb_low,
            "rsi": rsi_curr,
            "adx": adx_curr,
            "atr": atr_curr,
        }

        if any(np.isnan(v) for v in metrics.values()):
            return self.create_hold_signal(
                symbol,
                curr_price,
                "Indicator calculation produced NaNs (warmup incomplete)",
                metrics,
                timestamp,
            )

        # 2. Strict Regime Filter: ADX < max_adx_regime (only ranging markets allowed)
        if adx_curr >= self.max_adx_regime:
            return self.create_hold_signal(
                symbol,
                curr_price,
                f"Regime filter: Market is trending (ADX {adx_curr:.1f} >= {self.max_adx_regime}). Mean-reversion deactivated.",
                metrics,
                timestamp,
            )

        # 3. Evaluate BUY Entry Conditions
        # Condition 1: Low touched or pierced lower band on current or previous bar
        touched_lower = (float(low.iloc[t]) <= bb_low) or (float(low.iloc[t - 1]) <= bb_low_prev)
        # Condition 2: Bullish candle close (Close > Open)
        bullish_close = curr_price > float(open_p.iloc[t])
        # Condition 3: RSI oversold recovery (RSI > 35 and RSI_prev <= 35 or RSI < 40)
        rsi_rebound = (rsi_curr > 35.0 and rsi_prev <= 35.0) or (
            30.0 <= rsi_curr <= 42.0 and rsi_curr > rsi_prev
        )

        if touched_lower and bullish_close and rsi_rebound:
            stop_loss = bb_low - (0.5 * atr_curr)
            if stop_loss >= curr_price or stop_loss <= 0.0:
                stop_loss = curr_price * 0.98

            take_profit = bb_mid  # Target middle band for mean reversion

            # Confidence formula
            adx_cushion = max(0.0, min(1.0, (self.max_adx_regime - adx_curr) / self.max_adx_regime))
            band_pos = max(0.0, min(1.0, (curr_price - bb_low) / max(0.001, bb_mid - bb_low)))
            confidence = float(np.clip(0.50 + (0.30 * adx_cushion) + (0.20 * band_pos), 0.50, 0.90))

            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.BUY,
                confidence=confidence,
                entry_price=curr_price,
                suggested_stop_loss=stop_loss,
                suggested_take_profit=take_profit,
                rationale=(
                    f"Mean reversion setup: Price touched lower Bollinger Band ({bb_low:.2f}) "
                    f"in ranging regime (ADX {adx_curr:.1f} < {self.max_adx_regime}). "
                    f"Bullish candle formed with RSI rebounding ({rsi_curr:.1f})."
                ),
                invalidation_condition=f"Lower band breakdown with close below {stop_loss:.2f}",
                timestamp=timestamp,
                metrics=metrics,
            )

        # 4. Evaluate SELL Exit Conditions
        # Reached or exceeded middle band or upper band, or RSI overbought (> 65)
        reached_target = curr_price >= bb_mid or curr_price >= bb_up
        overbought = rsi_curr >= 65.0

        if reached_target or overbought:
            confidence = 0.75 if curr_price >= bb_up else 0.65
            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.SELL,
                confidence=confidence,
                entry_price=curr_price,
                suggested_stop_loss=curr_price * 1.02,
                suggested_take_profit=None,
                rationale=(
                    f"Mean reversion exit: Price reached target band ({bb_mid:.2f}) or "
                    f"RSI reached overbought territory ({rsi_curr:.1f} >= 65)."
                ),
                invalidation_condition="Price drops back below lower band",
                timestamp=timestamp,
                metrics=metrics,
            )

        # 5. Default to HOLD
        reasons: list[str] = []
        if not touched_lower:
            reasons.append(f"Price ({curr_price:.2f}) not at lower band ({bb_low:.2f})")
        if not bullish_close:
            reasons.append("Current candle is not bullish (Close <= Open)")
        if not rsi_rebound:
            reasons.append(f"RSI ({rsi_curr:.1f}) not rebounding from oversold")

        reason_str = "No setup: " + (
            ", ".join(reasons) if reasons else "Consolidating within bands"
        )
        return self.create_hold_signal(symbol, curr_price, reason_str, metrics, timestamp)
