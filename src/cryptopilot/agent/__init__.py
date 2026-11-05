"""
CryptoPilot AI - Autonomous Decision Engine Package.
Synthesizes multi-strategy consensus, machine learning predictions, and market sentiment
with dynamic regime adaptation and deterministic default-to-HOLD safety invariants.
"""

from cryptopilot.agent.arbiter import DecisionArbiter
from cryptopilot.agent.explainer import DecisionExplainer
from cryptopilot.agent.models import (
    ArbitrationInput,
    MarketRegime,
    SignalWeights,
    TradeDecision,
)
from cryptopilot.agent.regime import MarketRegimeClassifier
from cryptopilot.agent.safety import SafetyGuard

__all__ = [
    "ArbitrationInput",
    "DecisionArbiter",
    "DecisionExplainer",
    "MarketRegime",
    "MarketRegimeClassifier",
    "SafetyGuard",
    "SignalWeights",
    "TradeDecision",
]
