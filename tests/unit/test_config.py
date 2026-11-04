"""
Unit tests for cryptopilot.config.settings.
Covers: Valid, Invalid, Boundary, Empty, and Error conditions.
"""

import pytest
from pydantic import ValidationError

from cryptopilot.config.settings import (
    AccountType,
    EnvironmentType,
    Settings,
    TradingMode,
    get_settings,
    reset_settings,
)


class TestSettings:
    def test_default_settings(self) -> None:
        """Verify default settings instantiation."""
        settings = Settings()
        assert settings.cryptopilot_env == EnvironmentType.DEVELOPMENT
        assert settings.trading_mode == TradingMode.PAPER
        assert settings.enable_live_trading is False
        assert settings.account_type == AccountType.SMALL_ACCOUNT
        assert settings.initial_capital == 30.0
        assert settings.monthly_contribution == 10.0
        assert settings.max_position_allocation_pct == 0.30
        assert settings.max_risk_per_trade_pct == 0.01
        assert settings.daily_loss_limit_pct == 0.02
        assert settings.max_concurrent_positions == 1
        assert "BTC/USDT" in settings.default_symbols
        assert "1h" in settings.default_timeframes

    def test_live_trading_prohibition(self) -> None:
        """Verify hardcoded rejection when enable_live_trading is set to True."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(enable_live_trading=True)
        assert "Live trading execution is strictly disabled" in str(exc_info.value)

    def test_symbols_parsing_variations(self) -> None:
        """Verify parsing comma-separated strings and lists."""
        s1 = Settings(default_symbols="BTC/USDT, ETH/USDT, SOL/USDT")  # type: ignore[arg-type]
        assert s1.default_symbols == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

        s2 = Settings(default_symbols=["BTC/USDT", "SOL/USDT"])
        assert s2.default_symbols == ["BTC/USDT", "SOL/USDT"]

        with pytest.raises(ValidationError):
            Settings(default_symbols=12345)  # type: ignore[arg-type]

    def test_timeframes_parsing_variations(self) -> None:
        """Verify parsing timeframes from comma-separated string and list."""
        s1 = Settings(default_timeframes="1m, 15m, 1h")  # type: ignore[arg-type]
        assert s1.default_timeframes == ["1m", "15m", "1h"]

        with pytest.raises(ValidationError):
            Settings(default_timeframes=None)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "invalid_field,invalid_val",
        [
            ("initial_capital", 0.0),
            ("initial_capital", -10.0),
            ("monthly_contribution", -1.0),
            ("max_position_allocation_pct", 0.0),
            ("max_position_allocation_pct", 1.5),
            ("max_risk_per_trade_pct", 0.0),
            ("max_risk_per_trade_pct", 0.25),
            ("daily_loss_limit_pct", 0.0),
            ("daily_loss_limit_pct", 0.50),
            ("max_concurrent_positions", 0),
            ("max_concurrent_positions", 15),
            ("request_timeout_ms", 500),
            ("request_timeout_ms", 100000),
            ("max_retries", -1),
            ("retry_backoff_factor", 0.5),
            ("api_port", 80),
        ],
    )
    def test_boundary_and_invalid_numeric_ranges(
        self, invalid_field: str, invalid_val: object
    ) -> None:
        """Verify numeric bounds are strictly enforced by Pydantic."""
        with pytest.raises(ValidationError):
            Settings(**{invalid_field: invalid_val})

    def test_singleton_get_and_reset_settings(self) -> None:
        """Verify get_settings returns singleton and reset_settings clears cache."""
        reset_settings()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

        reset_settings()
        s3 = get_settings()
        assert s3 is not s1
