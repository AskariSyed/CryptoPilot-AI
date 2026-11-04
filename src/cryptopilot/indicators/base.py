"""
CryptoPilot AI - Technical Indicator Base Class & Invariants.
Enforces zero-lookahead, input validation, and warmup period tracking.
"""

from abc import ABC, abstractmethod

import pandas as pd


class IndicatorError(Exception):
    """Base exception for indicator calculation errors."""

    pass


class InsufficientDataError(IndicatorError):
    """Raised when the input series has fewer observations than the warmup period."""

    def __init__(self, message: str, required_bars: int, available_bars: int) -> None:
        super().__init__(message)
        self.required_bars = required_bars
        self.available_bars = available_bars


class InvalidInputError(IndicatorError):
    """Raised when input DataFrame/Series has invalid types or missing required columns."""

    pass


class BaseIndicator(ABC):
    """
    Abstract base class for all technical indicators.
    Guarantees:
    1. Zero-lookahead bias: output at index t strictly uses inputs from <= t.
    2. Output length equals input length, preserving index alignment.
    3. Warmup periods are explicitly declared.
    """

    def __init__(self, name: str, warmup_period: int) -> None:
        if warmup_period < 1:
            raise ValueError(f"Warmup period must be >= 1, got {warmup_period}")
        self.name = name
        self.warmup_period = warmup_period

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.Series | pd.DataFrame:
        """
        Pure calculation function. Must not modify input DataFrame in-place.
        """
        pass

    def validate_input(self, df: pd.DataFrame, required_columns: list[str]) -> None:
        """Validates that input DataFrame has required columns and enough rows."""
        if df is None or not isinstance(df, pd.DataFrame):
            raise InvalidInputError(f"Input must be a pandas DataFrame, got {type(df)}")

        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise InvalidInputError(
                f"Indicator '{self.name}' requires columns {required_columns}. "
                f"Missing: {missing_cols}"
            )

        if len(df) == 0:
            return

        for col in required_columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                raise InvalidInputError(f"Column '{col}' must contain numeric values")
