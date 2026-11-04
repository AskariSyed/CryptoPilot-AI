"""
CryptoPilot AI - Market Data Engine.
"""

from cryptopilot.data.exceptions import (
    CandleGapDetectedError,
    DataValidationError,
    DuplicateCandleError,
    ExchangeConnectionError,
    InvalidTimeframeError,
    MarketDataError,
    RateLimitExceededError,
    StaleDataError,
    SymbolNotFoundError,
)
from cryptopilot.data.exchange_client import ExchangeClient
from cryptopilot.data.models import (
    Candle,
    MarketMetadata,
    OrderBook,
    OrderBookLevel,
    Symbol,
    Ticker,
    Timeframe,
)
from cryptopilot.data.storage import MarketDataStorage
from cryptopilot.data.validator import CandleValidationResult, CandleValidator

__all__ = [
    "Candle",
    "Ticker",
    "OrderBook",
    "OrderBookLevel",
    "MarketMetadata",
    "Symbol",
    "Timeframe",
    "CandleValidator",
    "CandleValidationResult",
    "ExchangeClient",
    "MarketDataStorage",
    "MarketDataError",
    "ExchangeConnectionError",
    "RateLimitExceededError",
    "DataValidationError",
    "DuplicateCandleError",
    "CandleGapDetectedError",
    "StaleDataError",
    "SymbolNotFoundError",
    "InvalidTimeframeError",
]

