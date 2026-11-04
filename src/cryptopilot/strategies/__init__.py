"""
CryptoPilot AI - Quantitative Strategy Ensemble.
Five battle-tested, independent rule strategies with explicit rationales,
confidence scoring, and objective risk parameters.
"""

from cryptopilot.strategies.base import BaseStrategy, SignalType, StrategySignal
from cryptopilot.strategies.bollinger_reversion import BollingerMeanReversionStrategy
from cryptopilot.strategies.ema_trend import EMATrendFollowingStrategy
from cryptopilot.strategies.multi_timeframe import MultiTimeframeTrendStrategy
from cryptopilot.strategies.rsi_macd import RSIMACDConfirmationStrategy
from cryptopilot.strategies.volatility_momentum import VolatilityAdjustedMomentumStrategy

__all__ = [
    "SignalType",
    "StrategySignal",
    "BaseStrategy",
    "EMATrendFollowingStrategy",
    "RSIMACDConfirmationStrategy",
    "BollingerMeanReversionStrategy",
    "VolatilityAdjustedMomentumStrategy",
    "MultiTimeframeTrendStrategy",
]
