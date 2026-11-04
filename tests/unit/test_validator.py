"""
Unit tests for cryptopilot.data.validator.CandleValidator.
Covers 8-Point Method testing: Normal valid, Invalid, Boundary, Empty, Missing,
Unexpected, Error conditions, and Floating-point precision.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from cryptopilot.data.exceptions import DataValidationError
from cryptopilot.data.models import Candle
from cryptopilot.data.validator import CandleValidator


class TestCandleValidator:
    def test_ensure_utc(self) -> None:
        # None input
        with pytest.raises(DataValidationError):
            CandleValidator.ensure_utc(None)  # type: ignore[arg-type]

        # Naive datetime
        naive = datetime(2026, 11, 4, 10, 0)
        utc_res = CandleValidator.ensure_utc(naive)
        assert utc_res.tzinfo == UTC

        # Already UTC
        utc_dt = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)
        assert CandleValidator.ensure_utc(utc_dt) == utc_dt

        # Non-UTC timezone (e.g. UTC+5)
        tz_plus5 = timezone(timedelta(hours=5))
        dt_plus5 = datetime(2026, 11, 4, 15, 0, tzinfo=tz_plus5)
        converted = CandleValidator.ensure_utc(dt_plus5)
        assert converted.tzinfo == UTC
        assert converted.hour == 10

    def test_validate_candle_prices_valid(self) -> None:
        candle = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=datetime(2026, 11, 4, 12, 0, tzinfo=UTC),
            open=100.0,
            high=110.0,
            low=95.0,
            close=105.0,
            volume=50.0,
        )
        # Should execute cleanly with no exceptions
        CandleValidator.validate_candle_prices(candle)

    def test_validate_candle_prices_none(self) -> None:
        with pytest.raises(DataValidationError) as exc:
            CandleValidator.validate_candle_prices(None)  # type: ignore[arg-type]
        assert "Candle cannot be None" in str(exc.value)

    @pytest.mark.parametrize(
        "open_val,high_val,low_val,close_val,vol_val,expected_err",
        [
            (0.0, 100.0, 50.0, 80.0, 10.0, "must be strictly positive"),
            (-10.0, 100.0, 50.0, 80.0, 10.0, "must be strictly positive"),
            (100.0, 90.0, 95.0, 100.0, 10.0, "cannot be less than Low"),
            (100.0, 100.0, 105.0, 100.0, 10.0, "cannot be less than Low"),
            (100.0, 100.0, 50.0, 105.0, 10.0, "must be >= max(Open, Close)"),
            (100.0, 110.0, 96.0, 95.0, 10.0, "must be <= min(Open, Close)"),
            (100.0, 110.0, 90.0, 105.0, -1.0, "cannot be negative"),
        ],
    )
    def test_validate_candle_prices_invalid_ranges(
        self,
        open_val: float,
        high_val: float,
        low_val: float,
        close_val: float,
        vol_val: float,
        expected_err: str,
    ) -> None:
        # Bypass Pydantic field validation using object attribute mocking
        class DummyCandle:
            pass

        d = DummyCandle()
        d.open = open_val
        d.high = high_val
        d.low = low_val
        d.close = close_val
        d.volume = vol_val
        with pytest.raises(DataValidationError) as exc:
            CandleValidator.validate_candle_prices(d)  # type: ignore[arg-type]
        assert expected_err in str(exc.value)

    @pytest.mark.parametrize("nan_val", [float("nan"), float("inf"), float("-inf")])
    def test_validate_candle_prices_nan_inf(self, nan_val: float) -> None:
        class DummyCandle:
            open = 100.0
            high = nan_val
            low = 90.0
            close = 95.0
            volume = 10.0

        with pytest.raises(DataValidationError) as exc:
            CandleValidator.validate_candle_prices(DummyCandle())  # type: ignore[arg-type]
        assert "cannot be NaN or Infinite" in str(exc.value)

    def test_detect_duplicates(self) -> None:
        ts1 = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)
        ts2 = datetime(2026, 11, 4, 11, 0, tzinfo=UTC)

        c1 = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=ts1,
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=1.0,
        )
        c2 = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=ts1,
            open=101.0,
            high=106.0,
            low=96.0,
            close=101.0,
            volume=2.0,
        )
        c3 = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=ts2,
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=1.0,
        )

        # Empty
        assert CandleValidator.detect_duplicates([]) == ([], 0)

        # Duplicates present
        unique, dups = CandleValidator.detect_duplicates([c1, c2, c3])
        assert dups == 1
        assert len(unique) == 2
        assert unique[0].open == 100.0  # Preserved the first

    def test_detect_gaps(self) -> None:
        ts1 = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)
        ts2 = datetime(2026, 11, 4, 11, 0, tzinfo=UTC)
        ts3 = datetime(2026, 11, 4, 13, 0, tzinfo=UTC)  # Gap at 12:00

        c1 = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=ts1,
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=1.0,
        )
        c2 = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=ts2,
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=1.0,
        )
        c3 = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=ts3,
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=1.0,
        )

        # Length < 2
        assert CandleValidator.detect_gaps([c1], 3600) == []

        # No gaps
        assert CandleValidator.detect_gaps([c1, c2], 3600) == []

        # Gap present
        gaps = CandleValidator.detect_gaps([c1, c2, c3], 3600)
        assert len(gaps) == 1
        assert gaps[0] == (ts2, ts3)

    def test_filter_unclosed_candles(self) -> None:
        c_closed = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=datetime.now(UTC),
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=1.0,
            is_closed=True,
        )
        c_open = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=datetime.now(UTC),
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=1.0,
            is_closed=False,
        )

        closed, dropped = CandleValidator.filter_unclosed_candles([c_closed, c_open])
        assert len(closed) == 1
        assert len(dropped) == 1
        assert closed[0].is_closed is True
        assert dropped[0].is_closed is False

    def test_validate_series_complete_pipeline(self) -> None:
        # Empty input
        res_empty = CandleValidator.validate_series([], "1h")
        assert res_empty.is_valid is True
        assert len(res_empty.validated_candles) == 0

        # Normal valid series
        base_ts = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)
        candles = [
            Candle(
                symbol="BTC/USDT",
                timeframe="1h",
                timestamp=base_ts + timedelta(hours=i),
                open=100.0 + i,
                high=105.0 + i,
                low=95.0 + i,
                close=102.0 + i,
                volume=10.0,
                is_closed=True,
            )
            for i in range(5)
        ]

        res = CandleValidator.validate_series(candles, "1h")
        assert res.is_valid is True
        assert len(res.validated_candles) == 5
        assert len(res.errors) == 0

        # Series with unclosed candle at end
        candles[-1].is_closed = False
        res_unclosed = CandleValidator.validate_series(candles, "1h", require_closed=True)
        assert len(res_unclosed.validated_candles) == 4
        assert len(res_unclosed.dropped_candles) == 1

        # Series with gap
        gapped = [candles[0], candles[2]]  # Skipped index 1 (11:00)
        res_gapped = CandleValidator.validate_series(gapped, "1h", allow_gaps=False)
        assert res_gapped.is_valid is False
        assert len(res_gapped.missing_intervals) == 1
