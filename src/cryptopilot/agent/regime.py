"""
CryptoPilot AI - Market Regime Classifier.
Identifies macro market states (Trending Bull, Trending Bear, Ranging, High Volatility)
from technical indicator vectors to modulate strategy weights and filter conflicting setups.
"""

import pandas as pd

from cryptopilot.agent.models import MarketRegime


class MarketRegimeClassifier:
    """
    Classifies the current market regime based on trend strength (ADX),
    moving average geometry (EMA20/EMA50), momentum (MACD), and volatility (ATR/BB Width).
    """

    def __init__(
        self,
        adx_trend_threshold: float = 25.0,
        adx_ranging_threshold: float = 20.0,
        high_volatility_atr_ratio: float = 0.035,
    ) -> None:
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_ranging_threshold = adx_ranging_threshold
        self.high_volatility_atr_ratio = high_volatility_atr_ratio

    def classify(self, df: pd.DataFrame) -> MarketRegime:
        """
        Determines the active MarketRegime from the most recent closed bar in df.
        Returns MarketRegime.UNKNOWN if data is missing or insufficient.
        """
        if df is None or df.empty or len(df) < 10:
            return MarketRegime.UNKNOWN

        last_row = df.iloc[-1]

        # Extract indicator values with fallbacks
        close = float(last_row.get("close", 0.0))
        if close <= 0.0:
            return MarketRegime.UNKNOWN

        # Volatility check (ATR ratio)
        atr = float(last_row.get("atr_14", 0.0))
        if atr > 0.0 and (atr / close) >= self.high_volatility_atr_ratio:
            return MarketRegime.HIGH_VOLATILITY

        # Trend strength
        adx = float(last_row.get("adx_14", 0.0))
        ema_20 = float(last_row.get("ema_20", 0.0))
        ema_50 = float(last_row.get("ema_50", 0.0))
        macd_hist = float(last_row.get("macd_12_26_9_hist", 0.0))

        # If key indicators are absent, default to RANGING or UNKNOWN
        if ema_20 <= 0.0 or ema_50 <= 0.0 or adx <= 0.0:
            return MarketRegime.UNKNOWN

        # 1. Trending Bull Condition
        if (
            adx >= self.adx_trend_threshold
            and close > ema_50
            and ema_20 > ema_50
            and macd_hist >= 0.0
        ):
            return MarketRegime.TRENDING_BULL

        # 2. Trending Bear Condition
        if (
            adx >= self.adx_trend_threshold
            and close < ema_50
            and ema_20 < ema_50
            and macd_hist <= 0.0
        ):
            return MarketRegime.TRENDING_BEAR

        # 3. Ranging Market Condition
        if adx <= self.adx_ranging_threshold or (ema_20 <= close <= ema_50):
            return MarketRegime.RANGING

        # Moderate trend or transition state
        return MarketRegime.RANGING

    def get_strategy_multipliers(self, regime: MarketRegime) -> dict[str, float]:
        """
        Returns dynamic weighting multipliers for each strategy ID based on market regime.
        Prevents counter-trend strategies in strong trends, and trend-following in ranging chops.
        """
        if regime == MarketRegime.TRENDING_BULL:
            return {
                "ema_trend": 1.30,
                "multi_timeframe": 1.30,
                "volatility_momentum": 1.20,
                "rsi_macd": 1.00,
                "bollinger_reversion": 0.30,
            }
        elif regime == MarketRegime.TRENDING_BEAR:
            return {
                "ema_trend": 1.30,
                "multi_timeframe": 1.30,
                "volatility_momentum": 1.20,
                "rsi_macd": 1.00,
                "bollinger_reversion": 0.30,
            }
        elif regime == MarketRegime.RANGING:
            return {
                "bollinger_reversion": 1.60,
                "rsi_macd": 1.10,
                "volatility_momentum": 0.80,
                "ema_trend": 0.50,
                "multi_timeframe": 0.50,
            }
        elif regime == MarketRegime.HIGH_VOLATILITY:
            return {
                "volatility_momentum": 1.40,
                "rsi_macd": 0.80,
                "ema_trend": 0.70,
                "multi_timeframe": 0.70,
                "bollinger_reversion": 0.40,
            }
        else:
            # UNKNOWN regime: uniform default multipliers
            return {
                "ema_trend": 1.00,
                "rsi_macd": 1.00,
                "bollinger_reversion": 1.00,
                "volatility_momentum": 1.00,
                "multi_timeframe": 1.00,
            }
