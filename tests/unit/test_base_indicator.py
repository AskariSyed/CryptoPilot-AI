"""
Unit tests for cryptopilot.indicators.base.
Covers: BaseIndicator validation, error models, and warmup invariants.
"""

import pandas as pd
import pytest

from cryptopilot.indicators.base import (
    BaseIndicator,
    InsufficientDataError,
    InvalidInputError,
)


class DummyIndicator(BaseIndicator):
    def __init__(self, warmup: int = 5) -> None:
        super().__init__(name="Dummy", warmup_period=warmup)

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        self.validate_input(df, ["close"])
        return df["close"]


class TestBaseIndicator:
    def test_warmup_period_invalid(self) -> None:
        with pytest.raises(ValueError) as exc:
            DummyIndicator(warmup=0)
        assert "Warmup period must be >= 1" in str(exc.value)

    def test_insufficient_data_error_properties(self) -> None:
        err = InsufficientDataError("Not enough bars", required_bars=20, available_bars=10)
        assert err.required_bars == 20
        assert err.available_bars == 10
        assert "Not enough bars" in str(err)

    def test_validate_input_non_dataframe(self) -> None:
        ind = DummyIndicator()
        with pytest.raises(InvalidInputError) as exc:
            ind.validate_input("not a dataframe", ["close"])  # type: ignore[arg-type]
        assert "must be a pandas DataFrame" in str(exc.value)

        with pytest.raises(InvalidInputError):
            ind.validate_input(None, ["close"])  # type: ignore[arg-type]

    def test_validate_input_non_numeric_column(self) -> None:
        ind = DummyIndicator()
        df = pd.DataFrame({"close": ["abc", "def"]})
        with pytest.raises(InvalidInputError) as exc:
            ind.validate_input(df, ["close"])
        assert "must contain numeric values" in str(exc.value)

    def test_validate_input_empty_dataframe(self) -> None:
        ind = DummyIndicator()
        df = pd.DataFrame(columns=["close"])
        # Should not raise for empty DataFrame
        ind.validate_input(df, ["close"])
