"""
Unit tests for cryptopilot.strategies.base.
Covers: SignalType, StrategySignal schema validation, and BaseStrategy contract.
"""

from datetime import UTC, datetime, timedelta
import pandas as pd
import pytest
from pydantic import ValidationError

from cryptopilot.strategies.base import BaseStrategy, SignalType, StrategySignal


class DummyStrategy(BaseStrategy):
    def __init__(self, min_bars: int = 10) -> None:
        super().__init__(strategy_id="dummy", name="Dummy Strategy", min_bars=min_bars)

    def evaluate(self, df: pd.DataFrame, symbol: str) -> StrategySignal:
        is_valid, err = self.validate_dataframe(df)
        if not is_valid:
            return self.create_hold_signal(symbol, 100.0, err)
        return StrategySignal(
            strategy_id=self.strategy_id,
            symbol=symbol,
            signal=SignalType.BUY,
            confidence=0.85,
            entry_price=100.0,
            suggested_stop_loss=95.0,
            suggested_take_profit=110.0,
            rationale="Test buy signal",
            invalidation_condition="Price < 95",
            timestamp=datetime.now(UTC),
            metrics={"test_metric": 1.0},
        )


class TestStrategyBase:
    def test_strategy_signal_valid(self) -> None:
        signal = StrategySignal(
            strategy_id="test_strat",
            symbol="BTC/USDT",
            signal=SignalType.BUY,
            confidence=0.75,
            entry_price=50000.0,
            suggested_stop_loss=48000.0,
            suggested_take_profit=54000.0,
            rationale="Strong breakout",
            invalidation_condition="Break below 48000",
            timestamp=datetime.now(UTC),
            metrics={"rsi": 55.0},
        )
        assert signal.signal == SignalType.BUY
        assert signal.confidence == 0.75
        assert signal.entry_price == 50000.0

    def test_strategy_signal_utc_coercion(self) -> None:
        naive_dt = datetime(2026, 11, 4, 12, 0)
        signal = StrategySignal(
            strategy_id="test_strat",
            symbol="ETH/USDT",
            signal=SignalType.HOLD,
            confidence=0.0,
            entry_price=2500.0,
            suggested_stop_loss=2400.0,
            rationale="Consolidating",
            invalidation_condition="N/A",
            timestamp=naive_dt,
        )
        assert signal.timestamp.tzinfo == UTC

    @pytest.mark.parametrize(
        "invalid_kwargs",
        [
            {"confidence": 1.5},  # > 1.0
            {"confidence": -0.1},  # < 0.0
            {"entry_price": 0.0},  # <= 0
            {"entry_price": -100.0},
            {"suggested_stop_loss": 0.0},
        ],
    )
    def test_strategy_signal_invalid_ranges(self, invalid_kwargs: dict) -> None:
        base_kwargs = {
            "strategy_id": "test",
            "symbol": "BTC/USDT",
            "signal": SignalType.BUY,
            "confidence": 0.70,
            "entry_price": 100.0,
            "suggested_stop_loss": 90.0,
            "rationale": "ok",
            "invalidation_condition": "none",
            "timestamp": datetime.now(UTC),
        }
        base_kwargs.update(invalid_kwargs)
        with pytest.raises(ValidationError):
            StrategySignal(**base_kwargs)

    def test_base_strategy_initialization_invalid(self) -> None:
        with pytest.raises(ValueError):
            DummyStrategy(min_bars=0)

    def test_validate_dataframe_invalid_types(self) -> None:
        strat = DummyStrategy(min_bars=5)
        ok, err = strat.validate_dataframe(None)  # type: ignore[arg-type]
        assert not ok
        assert "valid pandas DataFrame" in err

        ok, err = strat.validate_dataframe("not a df")  # type: ignore[arg-type]
        assert not ok

    def test_validate_dataframe_insufficient_bars(self) -> None:
        strat = DummyStrategy(min_bars=10)
        short_df = pd.DataFrame(
            {
                "open": [1.0, 2.0],
                "high": [2.0, 3.0],
                "low": [0.5, 1.5],
                "close": [1.5, 2.5],
                "volume": [10.0, 20.0],
            }
        )
        ok, err = strat.validate_dataframe(short_df)
        assert not ok
        assert "Insufficient observations" in err

    def test_validate_dataframe_missing_columns(self) -> None:
        strat = DummyStrategy(min_bars=2)
        df_missing = pd.DataFrame({"close": [1.0, 2.0], "volume": [10.0, 20.0]})
        ok, err = strat.validate_dataframe(df_missing)
        assert not ok
        assert "Missing required price columns" in err

    def test_create_hold_signal(self) -> None:
        strat = DummyStrategy(min_bars=5)
        sig = strat.create_hold_signal("SOL/USDT", 150.0, "Testing hold condition")
        assert sig.signal == SignalType.HOLD
        assert sig.confidence == 0.0
        assert sig.entry_price == 150.0
        assert "Testing hold condition" in sig.rationale
