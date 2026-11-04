"""
CryptoPilot AI - Market Data Validator & Pipeline.
4-Stage verification guaranteeing zero-lookahead, timestamp monotonicity,
price consistency, gap detection, and incomplete candle filtering.
"""

import math
from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from cryptopilot.data.exceptions import (
    DataValidationError,
)
from cryptopilot.data.models import Candle, Timeframe


class CandleValidationResult(BaseModel):
    is_valid: bool = Field(description="True if candle series passed all validation checks")
    validated_candles: list[Candle] = Field(default_factory=list)
    dropped_candles: list[Candle] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    missing_intervals: list[tuple[datetime, datetime]] = Field(default_factory=list)
    duplicate_count: int = Field(default=0)


class CandleValidator:
    """
    Validates market candle sequences across 4 sequential stages:
    Stage 1: Monotonicity and UTC timestamp checking.
    Stage 2: Financial price consistency (High >= Low, High >= max(Open, Close), Low <= min(Open, Close)).
    Stage 3: Duplicate and missing candle (gap) detection.
    Stage 4: Incomplete candle filtering (drops unclosed candles).
    """

    @staticmethod
    def ensure_utc(dt: datetime) -> datetime:
        """Converts any datetime to UTC or ensures tzinfo is UTC."""
        if dt is None:
            raise DataValidationError("Timestamp cannot be None")
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    @staticmethod
    def validate_candle_prices(candle: Candle) -> None:
        """
        Stage 2 Check: Asserts price sanity.
        Raises DataValidationError if prices are invalid, non-finite, or inconsistent.
        """
        if candle is None:
            raise DataValidationError("Candle cannot be None")

        for attr in ("open", "high", "low", "close", "volume"):
            val = getattr(candle, attr, None)
            if val is None or not isinstance(val, (int, float)):
                raise DataValidationError(f"Candle {attr} must be a number, got {val}")
            if math.isnan(val) or math.isinf(val):
                raise DataValidationError(f"Candle {attr} cannot be NaN or Infinite: {val}")

        if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
            raise DataValidationError(
                f"Candle OHLC prices must be strictly positive (> 0). "
                f"Got O={candle.open}, H={candle.high}, L={candle.low}, C={candle.close}"
            )

        if candle.volume < 0:
            raise DataValidationError(f"Candle volume cannot be negative, got {candle.volume}")

        if candle.high < candle.low:
            raise DataValidationError(
                f"Candle High ({candle.high}) cannot be less than Low ({candle.low})"
            )

        max_oc = max(candle.open, candle.close)
        min_oc = min(candle.open, candle.close)

        # Allow epsilon floating-point tolerance of 1e-8
        if candle.high < (max_oc - 1e-8):
            raise DataValidationError(
                f"Candle High ({candle.high}) must be >= max(Open, Close) ({max_oc})"
            )

        if candle.low > (min_oc + 1e-8):
            raise DataValidationError(
                f"Candle Low ({candle.low}) must be <= min(Open, Close) ({min_oc})"
            )

    @staticmethod
    def detect_duplicates(candles: Sequence[Candle]) -> tuple[list[Candle], int]:
        """
        Stage 3A Check: Identifies and removes duplicate timestamps, preserving the first seen.
        Returns unique candles list and duplicate count.
        """
        if not candles:
            return [], 0

        seen_timestamps = set()
        unique_candles: list[Candle] = []
        duplicates = 0

        for candle in candles:
            ts = CandleValidator.ensure_utc(candle.timestamp)
            if ts in seen_timestamps:
                duplicates += 1
            else:
                seen_timestamps.add(ts)
                unique_candles.append(candle)

        return unique_candles, duplicates

    @staticmethod
    def detect_gaps(
        candles: Sequence[Candle],
        expected_interval_seconds: int,
    ) -> list[tuple[datetime, datetime]]:
        """
        Stage 3B Check: Detects missing intervals in an ordered sequence of candles.
        Returns a list of (expected_timestamp, actual_next_timestamp) gap intervals.
        """
        if len(candles) < 2:
            return []

        gaps: list[tuple[datetime, datetime]] = []
        for i in range(len(candles) - 1):
            curr_ts = CandleValidator.ensure_utc(candles[i].timestamp)
            next_ts = CandleValidator.ensure_utc(candles[i + 1].timestamp)

            delta = int((next_ts - curr_ts).total_seconds())
            if delta < expected_interval_seconds:
                # Monotonicity violation (should have been sorted or deduplicated)
                continue
            if delta > expected_interval_seconds:
                # Gap detected
                gaps.append((curr_ts, next_ts))

        return gaps

    @staticmethod
    def filter_unclosed_candles(candles: Sequence[Candle]) -> tuple[list[Candle], list[Candle]]:
        """
        Stage 4: Filters out unclosed candles (`is_closed == False`).
        Returns (closed_candles, dropped_unclosed_candles).
        """
        closed: list[Candle] = []
        dropped: list[Candle] = []
        for c in candles:
            if c.is_closed:
                closed.append(c)
            else:
                dropped.append(c)
        return closed, dropped

    @classmethod
    def validate_series(
        cls,
        candles: Sequence[Candle],
        timeframe: str | Timeframe,
        require_closed: bool = True,
        allow_gaps: bool = False,
    ) -> CandleValidationResult:
        """
        Executes the full 4-stage validation pipeline on a candle collection.
        """
        errors: list[str] = []

        if not candles:
            return CandleValidationResult(
                is_valid=True,
                validated_candles=[],
                dropped_candles=[],
                errors=[],
                missing_intervals=[],
                duplicate_count=0,
            )

        tf_enum = Timeframe(timeframe) if isinstance(timeframe, str) else timeframe
        expected_interval = tf_enum.duration_seconds

        # Stage 2: Individual Price Sanity
        valid_price_candles: list[Candle] = []
        dropped_candles: list[Candle] = []
        for c in candles:
            try:
                cls.validate_candle_prices(c)
                valid_price_candles.append(c)
            except DataValidationError as e:
                errors.append(f"Invalid candle at {getattr(c, 'timestamp', 'unknown')}: {e}")
                dropped_candles.append(c)

        if not valid_price_candles:
            return CandleValidationResult(
                is_valid=False,
                validated_candles=[],
                dropped_candles=dropped_candles,
                errors=errors,
            )

        # Stage 1: Sort chronologically by UTC timestamp
        sorted_candles = sorted(
            valid_price_candles,
            key=lambda c: cls.ensure_utc(c.timestamp),
        )

        # Stage 3A: Detect Duplicates
        deduped_candles, dup_count = cls.detect_duplicates(sorted_candles)
        if dup_count > 0:
            errors.append(f"Found and deduplicated {dup_count} duplicate candle timestamps")

        # Stage 3B: Detect Gaps
        gaps = cls.detect_gaps(deduped_candles, expected_interval)
        if gaps and not allow_gaps:
            errors.append(f"Detected {len(gaps)} missing candle intervals (gaps)")

        # Stage 4: Incomplete / Unclosed Filter
        if require_closed:
            final_candles, unclosed_dropped = cls.filter_unclosed_candles(deduped_candles)
            dropped_candles.extend(unclosed_dropped)
        else:
            final_candles = deduped_candles

        is_valid = len(errors) == 0 or (dup_count > 0 and len(errors) == 1 and allow_gaps)
        if gaps and not allow_gaps:
            is_valid = False

        return CandleValidationResult(
            is_valid=is_valid,
            validated_candles=final_candles,
            dropped_candles=dropped_candles,
            errors=errors,
            missing_intervals=gaps,
            duplicate_count=dup_count,
        )
