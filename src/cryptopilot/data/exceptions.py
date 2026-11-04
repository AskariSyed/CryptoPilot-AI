"""
CryptoPilot AI - Market Data Domain Exceptions.
"""


class MarketDataError(Exception):
    """Base exception for all market data errors."""

    def __init__(self, message: str, details: object = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ExchangeConnectionError(MarketDataError):
    """Raised when connection to an exchange fails after retries."""

    pass


class RateLimitExceededError(MarketDataError):
    """Raised when exchange rate limit is breached (HTTP 429)."""

    def __init__(
        self, message: str, retry_after_seconds: float = 5.0, details: object = None
    ) -> None:
        super().__init__(message, details)
        self.retry_after_seconds = retry_after_seconds


class DataValidationError(MarketDataError):
    """Raised when market data violates financial consistency or integrity rules."""

    pass


class DuplicateCandleError(DataValidationError):
    """Raised when duplicate timestamps are found in a candle series."""

    pass


class CandleGapDetectedError(DataValidationError):
    """Raised when missing candle intervals are detected in an expected continuous series."""

    def __init__(self, message: str, missing_count: int = 1, details: object = None) -> None:
        super().__init__(message, details)
        self.missing_count = missing_count


class StaleDataError(DataValidationError):
    """Raised when received candle or ticker data is older than allowed staleness threshold."""

    pass


class SymbolNotFoundError(MarketDataError):
    """Raised when an asset pair symbol is not found on the exchange."""

    pass


class InvalidTimeframeError(MarketDataError):
    """Raised when an unsupported timeframe is requested."""

    pass
