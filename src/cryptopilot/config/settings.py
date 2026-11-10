"""
CryptoPilot AI - Application Configuration & Settings.
Validated via Pydantic v2 and pydantic-settings.
"""

from enum import StrEnum

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentType(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class TradingMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class AccountType(StrEnum):
    SMALL_ACCOUNT = "small_account"
    RESEARCH = "research"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Operational Environment
    cryptopilot_env: EnvironmentType = Field(
        default=EnvironmentType.DEVELOPMENT,
        description="Current runtime environment (development, testing, production)",
    )
    log_level: str = Field(default="INFO", description="Logging level")
    debug: bool = Field(default=False, description="Enable debug logging and features")

    # Trading Execution Controls
    # Live trading is strictly prohibited in initial releases
    trading_mode: TradingMode = Field(
        default=TradingMode.PAPER,
        description="Trading operational mode. Initial release permits only PAPER trading.",
    )
    enable_live_trading: bool = Field(
        default=False,
        description="Hard barrier: Must remain false in this release.",
    )

    # Account Parameters
    account_type: AccountType = Field(
        default=AccountType.SMALL_ACCOUNT,
        description="Active account profile: small_account ($30) or research ($10,000)",
    )
    initial_capital: float = Field(
        default=30.0,
        gt=0.0,
        description="Initial virtual capital in quote currency (USDT)",
    )
    monthly_contribution: float = Field(
        default=10.0,
        ge=0.0,
        description="Monthly recurring deposit ledgered separately from trading profits",
    )
    currency: str = Field(default="USDT", description="Quote currency denomination")

    # Quantitative Risk Constraints
    max_position_allocation_pct: float = Field(
        default=0.30,
        gt=0.0,
        le=1.0,
        description="Maximum capital allocation to a single position (30% of total equity)",
    )
    max_risk_per_trade_pct: float = Field(
        default=0.01,
        gt=0.0,
        le=0.10,
        description="Maximum risk budget per trade (1% of total equity)",
    )
    daily_loss_limit_pct: float = Field(
        default=0.02,
        gt=0.0,
        le=0.20,
        description="Daily loss circuit breaker threshold (2% of starting daily equity)",
    )
    max_concurrent_positions: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Maximum simultaneous open positions (1 for small account)",
    )

    # Market Data & CCXT Configuration
    exchange_id: str = Field(
        default="binance",
        description="Exchange identifier for CCXT public market data ingestion",
    )
    default_symbols: list[str] = Field(
        default=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        description="Monitored cryptocurrency trading pairs",
    )
    default_timeframes: list[str] = Field(
        default=["1m", "15m", "1h", "4h"],
        description="Supported market candle timeframes",
    )
    enable_rate_limit: bool = Field(
        default=True,
        description="Enable CCXT built-in rate limiting",
    )
    request_timeout_ms: int = Field(
        default=10000,
        ge=1000,
        le=60000,
        description="Exchange request timeout in milliseconds",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts on transient network errors",
    )
    retry_backoff_factor: float = Field(
        default=1.5,
        ge=1.0,
        le=5.0,
        description="Exponential backoff factor for retries",
    )
    daemon_cycle_interval_seconds: float = Field(
        default=60.0,
        gt=0.0,
        description="Delay between continuous market-data cycles",
    )
    log_file_path: str = Field(
        default="logs/cryptopilot.log",
        description="Rotating application log path",
    )

    # Database Configuration
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/cryptopilot_dev.db",
        description="Asynchronous database connection URL",
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="FastAPI host binding")
    api_port: int = Field(default=8000, ge=1024, le=65535, description="FastAPI port")
    api_secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for administrative endpoint protection",
    )

    @field_validator("enable_live_trading")
    @classmethod
    def validate_live_trading_prohibition(cls, v: bool) -> bool:
        if v:
            raise ValueError(
                "Live trading execution is strictly disabled in this release. "
                "enable_live_trading must be False."
            )
        return v

    @field_validator("default_symbols", mode="before")
    @classmethod
    def parse_symbols_list(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        if isinstance(v, list):
            return [str(s).strip() for s in v if str(s).strip()]
        raise ValueError(f"Invalid format for symbols: {v}")

    @field_validator("default_timeframes", mode="before")
    @classmethod
    def parse_timeframes_list(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [tf.strip() for tf in v.split(",") if tf.strip()]
        if isinstance(v, list):
            return [str(tf).strip() for tf in v if str(tf).strip()]
        raise ValueError(f"Invalid format for timeframes: {v}")


_cached_settings: Settings | None = None


def get_settings() -> Settings:
    """Retrieve singleton application settings instance."""
    global _cached_settings
    if _cached_settings is None:
        _cached_settings = Settings()
    return _cached_settings


def reset_settings() -> None:
    """Reset cached settings (primarily for test fixture isolation)."""
    global _cached_settings
    _cached_settings = None
