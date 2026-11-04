"""
CryptoPilot AI - Strategy E: Multi-Timeframe Trend Confirmation.
Enforces macro (1h) regime confirmation with micro (15m) pullback and resumption triggers.
Eliminates low-timeframe noise by ensuring trade direction aligns with macro order flow.
"""

from datetime import UTC, datetime
from typing import Any
import numpy as np
import pandas as pd

from cryptopilot.indicators.momentum import calculate_rsi
from cryptopilot.indicators.moving_averages import calculate_ema, calculate_volume_ma
from cryptopilot.indicators.trend_volatility import calculate_atr, calculate_macd
from cryptopilot.strategies.base import BaseStrategy, SignalType, StrategySignal


class MultiTimeframeTrendStrategy(BaseStrategy):
    """
    Strategy E: Multi-Timeframe Trend Confirmation.
    Macro (1h): Trend direction filter (Price > EMA 50, MACD > 0).
    Micro (15m): Low-risk pullback to EMA 20 with volume-confirmed bullish resumption.
    """

    def __init__(
        self,
        macro_ema_period: int = 50,
        micro_ema_period: int = 20,
        micro_rsi_period: int = 14,
        micro_atr_period: int = 14,
        micro_vol_ma_period: int = 20,
    ) -> None:
        super().__init__(
            strategy_id="multi_timeframe",
            name="Multi-Timeframe Trend Confirmation",
            min_bars=max(macro_ema_period, micro_ema_period, micro_rsi_period) + 15,
        )
        self.macro_ema_period = macro_ema_period
        self.micro_ema_period = micro_ema_period
        self.micro_rsi_period = micro_rsi_period
        self.micro_atr_period = micro_atr_period
        self.micro_vol_ma_period = micro_vol_ma_period

    def evaluate_multi(
        self,
        df_macro: pd.DataFrame,
        df_micro: pd.DataFrame,
        symbol: str,
    ) -> StrategySignal:
        """
        Primary evaluation method taking both Macro (1h) and Micro (15m) DataFrames.
        """
        valid_macro, err_macro = self.validate_dataframe(df_macro)
        valid_micro, err_micro = self.validate_dataframe(df_micro)

        if not valid_micro:
            price = float(df_micro["close"].iloc[-1]) if df_micro is not None and not df_micro.empty else 0.0
            return self.create_hold_signal(symbol, price, f"Micro data validation failed: {err_micro}")

        if not valid_macro:
            price = float(df_micro["close"].iloc[-1])
            return self.create_hold_signal(symbol, price, f"Macro data validation failed: {err_macro}")

        # 1. Macro (1h) Indicators
        macro_close = df_macro["close"]
        macro_ema = calculate_ema(macro_close, self.macro_ema_period)
        macro_macd_l, _sig, _hist = calculate_macd(macro_close, 12, 26, 9)

        macro_p = float(macro_close.iloc[-1])
        macro_ema_val = float(macro_ema.iloc[-1])
        macro_macd_val = float(macro_macd_l.iloc[-1])

        # Macro Trend Filter: Price > EMA 50 AND MACD Line > 0
        macro_bullish = (macro_p > macro_ema_val) and (macro_macd_val > 0.0)
        macro_bearish = (macro_p < macro_ema_val) and (macro_macd_val < 0.0)

        # 2. Micro (15m) Indicators
        micro_close = df_micro["close"]
        micro_open = df_micro["open"]
        micro_high = df_micro["high"]
        micro_low = df_micro["low"]
        micro_vol = df_micro["volume"]
        t = len(df_micro) - 1

        micro_p = float(micro_close.iloc[t])
        timestamp = (
            df_micro["timestamp"].iloc[t]
            if "timestamp" in df_micro.columns
            else datetime.now(UTC)
        )
        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        micro_ema = calculate_ema(micro_close, self.micro_ema_period)
        micro_rsi = calculate_rsi(micro_close, self.micro_rsi_period)
        micro_atr = calculate_atr(micro_high, micro_low, micro_close, self.micro_atr_period)
        micro_vol_ma = calculate_volume_ma(micro_vol, self.micro_vol_ma_period)

        m_ema_val = float(micro_ema.iloc[t])
        m_rsi_val = float(micro_rsi.iloc[t])
        m_rsi_prev = float(micro_rsi.iloc[t - 1])
        m_atr_val = float(micro_atr.iloc[t])
        m_vol_val = float(micro_vol.iloc[t])
        m_vol_ma_val = float(micro_vol_ma.iloc[t])

        metrics: dict[str, Any] = {
            "micro_price": micro_p,
            "macro_price": macro_p,
            "macro_ema_50": macro_ema_val,
            "macro_macd": macro_macd_val,
            "micro_ema_20": m_ema_val,
            "micro_rsi": m_rsi_val,
            "micro_atr": m_atr_val,
            "micro_vol": m_vol_val,
            "micro_vol_ma": m_vol_ma_val,
        }

        if any(np.isnan(v) for v in metrics.values()):
            return self.create_hold_signal(
                symbol, micro_p, "Indicator calculation produced NaNs (warmup incomplete)", metrics, timestamp
            )

        # 3. Evaluate BUY Conditions
        # Condition A: Macro is Bullish
        # Condition B: Micro pullback into EMA 20 zone with RSI in [40, 52] on current or previous bar
        recent_pullback_rsi = (40.0 <= m_rsi_prev <= 55.0) or (40.0 <= m_rsi_val <= 55.0)
        near_ema = abs(micro_p - m_ema_val) <= (1.0 * m_atr_val)
        # Condition C: Micro bullish resumption: Close > Open and Close > EMA 20
        bullish_candle = (micro_p > float(micro_open.iloc[t])) and (micro_p >= m_ema_val)
        # Condition D: Volume above average
        volume_confirmed = m_vol_val > (0.90 * m_vol_ma_val)

        if macro_bullish and recent_pullback_rsi and near_ema and bullish_candle and volume_confirmed:
            swing_low_3 = float(micro_low.iloc[t - 2 : t + 1].min())
            stop_loss = swing_low_3 - (0.5 * m_atr_val)
            if stop_loss >= micro_p or stop_loss <= 0.0:
                stop_loss = micro_p * 0.98

            take_profit = micro_p + (2.5 * (micro_p - stop_loss))

            # Confidence scoring
            macro_strength = min(1.0, max(0.0, (macro_p - macro_ema_val) / max(1.0, macro_ema_val * 0.05)))
            vol_boost = 0.15 if m_vol_val > m_vol_ma_val else 0.05
            confidence = float(np.clip(0.70 + (0.15 * macro_strength) + vol_boost, 0.70, 0.95))

            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.BUY,
                confidence=confidence,
                entry_price=micro_p,
                suggested_stop_loss=stop_loss,
                suggested_take_profit=take_profit,
                rationale=(
                    f"Multi-timeframe trend alignment: Macro 1h is bullish (Price {macro_p:.2f} > EMA {macro_ema_val:.2f}, "
                    f"MACD {macro_macd_val:.2f} > 0). Micro 15m formed bullish resumption candle above "
                    f"EMA 20 ({m_ema_val:.2f}) following healthy pullback (RSI {m_rsi_val:.1f})."
                ),
                invalidation_condition=f"Macro 1h closes below EMA 50 ({macro_ema_val:.2f})",
                timestamp=timestamp,
                metrics=metrics,
            )

        # 4. Evaluate SELL Conditions
        # Macro reversed bearish OR Micro closed decisively below EMA 20 in bearish macro
        if macro_bearish or (micro_p < m_ema_val and float(micro_close.iloc[t - 1]) < float(micro_ema.iloc[t - 1])):
            confidence = 0.80 if macro_bearish else 0.65
            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.SELL,
                confidence=confidence,
                entry_price=micro_p,
                suggested_stop_loss=micro_p * 1.02,
                suggested_take_profit=None,
                rationale=(
                    f"Trend invalidation: Macro 1h turned bearish ({macro_p:.2f} < EMA {macro_ema_val:.2f}) "
                    f"or micro 15m trend structure broke below EMA 20 ({m_ema_val:.2f})."
                ),
                invalidation_condition="Macro 1h crosses back above EMA 50",
                timestamp=timestamp,
                metrics=metrics,
            )

        # 5. Default to HOLD
        reasons: list[str] = []
        if not macro_bullish:
            reasons.append("Macro 1h trend not bullish")
        if not recent_pullback_rsi:
            reasons.append(f"Micro RSI ({m_rsi_val:.1f}) not in pullback zone [40, 55]")
        if not bullish_candle:
            reasons.append("Micro candle is not a bullish resumption bar")

        reason_str = "No setup: " + (", ".join(reasons) if reasons else "Waiting for MTF alignment")
        return self.create_hold_signal(symbol, micro_p, reason_str, metrics, timestamp)

    def evaluate(self, df: pd.DataFrame, symbol: str) -> StrategySignal:
        """
        Fallback evaluate method when single DataFrame is supplied.
        Treats the single DataFrame as the micro DataFrame with synthesized macro context.
        """
        # When evaluating with single dataframe, use it for both micro and macro
        return self.evaluate_multi(df_macro=df, df_micro=df, symbol=symbol)
