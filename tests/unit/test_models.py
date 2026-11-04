"""
Unit tests for cryptopilot.data.models.
Covers: Valid, Invalid, Boundary, Empty, and Precision conditions for domain entities.
"""

from datetime import UTC, datetime

import pytest

from cryptopilot.data.models import (
    Candle,
    MarketMetadata,
    OrderBook,
    OrderBookLevel,
    Symbol,
    Ticker,
    Timeframe,
)


class TestTimeframe:
    def test_duration_seconds_and_ms(self) -> None:
        assert Timeframe.M1.duration_seconds == 60
        assert Timeframe.M1.duration_ms == 60000

        assert Timeframe.M15.duration_seconds == 900
        assert Timeframe.M15.duration_ms == 900000

        assert Timeframe.H1.duration_seconds == 3600
        assert Timeframe.H1.duration_ms == 3600000

        assert Timeframe.H4.duration_seconds == 14400
        assert Timeframe.H4.duration_ms == 14400000

    def test_round_down_timestamp(self) -> None:
        # 14:23:45 -> 1m rounds to 14:23:00
        dt = datetime(2026, 11, 4, 14, 23, 45, tzinfo=UTC)
        rounded_1m = Timeframe.M1.round_down_timestamp(dt)
        assert rounded_1m == datetime(2026, 11, 4, 14, 23, 0, tzinfo=UTC)

        # 14:23:45 -> 15m rounds to 14:15:00
        rounded_15m = Timeframe.M15.round_down_timestamp(dt)
        assert rounded_15m == datetime(2026, 11, 4, 14, 15, 0, tzinfo=UTC)

        # 14:23:45 -> 1h rounds to 14:00:00
        rounded_1h = Timeframe.H1.round_down_timestamp(dt)
        assert rounded_1h == datetime(2026, 11, 4, 14, 0, 0, tzinfo=UTC)

        # 14:23:45 -> 4h rounds to 12:00:00
        rounded_4h = Timeframe.H4.round_down_timestamp(dt)
        assert rounded_4h == datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)

    def test_round_down_naive_datetime(self) -> None:
        naive_dt = datetime(2026, 11, 4, 14, 23, 45)
        rounded = Timeframe.H1.round_down_timestamp(naive_dt)
        assert rounded.tzinfo == UTC
        assert rounded == datetime(2026, 11, 4, 14, 0, 0, tzinfo=UTC)


class TestSymbol:
    def test_valid_symbol(self) -> None:
        sym = Symbol.from_string("btc/usdt")
        assert sym.raw == "BTC/USDT"
        assert sym.base == "BTC"
        assert sym.quote == "USDT"
        assert str(sym) == "BTC/USDT"

    @pytest.mark.parametrize(
        "invalid_sym",
        [
            "BTCUSDT",
            "BTC/",
            "/USDT",
            "/",
            "   ",
            "BTC/USDT/EXTRA",
        ],
    )
    def test_invalid_symbol_strings(self, invalid_sym: str) -> None:
        with pytest.raises(ValueError):
            Symbol.from_string(invalid_sym)


class TestCandle:
    def test_valid_candle(self) -> None:
        c = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=datetime(2026, 11, 4, 12, 0, tzinfo=UTC),
            open=40000.0,
            high=41000.0,
            low=39500.0,
            close=40500.0,
            volume=100.0,
            is_closed=True,
        )
        assert c.return_pct == 1.25
        assert c.hl_spread == 1500.0
        assert c.body_size == 500.0

    def test_candle_utc_coercion(self) -> None:
        naive_dt = datetime(2026, 11, 4, 12, 0)
        c = Candle(
            symbol="ETH/USDT",
            timeframe="15m",
            timestamp=naive_dt,
            open=2500.0,
            high=2600.0,
            low=2450.0,
            close=2480.0,
            volume=50.0,
        )
        assert c.timestamp.tzinfo == UTC

    def test_candle_negative_return(self) -> None:
        c = Candle(
            symbol="SOL/USDT",
            timeframe="1h",
            timestamp=datetime(2026, 11, 4, 12, 0, tzinfo=UTC),
            open=100.0,
            high=105.0,
            low=90.0,
            close=90.0,
            volume=100.0,
        )
        assert c.return_pct == -10.0
        assert c.body_size == 10.0

    def test_from_ccxt_tuple(self) -> None:
        raw = [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 150.5]
        candle = Candle.from_ccxt_tuple(raw, "BTC/USDT", "1h", is_closed=True)
        assert candle.open == 42000.0
        assert candle.close == 42300.0
        assert candle.volume == 150.5
        assert candle.is_closed is True
        assert candle.timestamp == datetime.fromtimestamp(1704067200, tz=UTC)

    def test_from_ccxt_tuple_invalid_length(self) -> None:
        with pytest.raises(ValueError) as exc:
            Candle.from_ccxt_tuple([1704067200000, 42000.0], "BTC/USDT", "1h")
        assert "at least 6 elements" in str(exc.value)


class TestTicker:
    def test_ticker_metrics(self) -> None:
        t = Ticker(
            symbol="BTC/USDT",
            bid=50000.0,
            ask=50010.0,
            last=50005.0,
            volume_24h=12000.0,
            timestamp=datetime.now(UTC),
        )
        assert t.spread == 10.0
        assert round(t.mid_price, 2) == 50005.0
        assert abs(t.spread_pct - 0.02) < 1e-4

    def test_ticker_zero_mid_price_edge_case(self) -> None:
        t = Ticker(
            symbol="ETH/USDT",
            bid=1.0,
            ask=1.0,
            last=1.0,
            volume_24h=0.0,
            timestamp=datetime.now(UTC),
        )
        assert t.spread == 0.0
        assert t.spread_pct == 0.0


class TestOrderBook:
    def test_order_book_spread_and_depth(self) -> None:
        bids = [
            OrderBookLevel(price=49990.0, amount=1.5),
            OrderBookLevel(price=49980.0, amount=3.0),
        ]
        asks = [
            OrderBookLevel(price=50010.0, amount=2.0),
            OrderBookLevel(price=50020.0, amount=4.0),
        ]
        ob = OrderBook(symbol="BTC/USDT", bids=bids, asks=asks, timestamp=datetime.now(UTC))

        assert ob.best_bid == 49990.0
        assert ob.best_ask == 50010.0
        assert ob.spread == 20.0
        assert round(ob.spread_bps, 2) == 4.0

    def test_empty_order_book(self) -> None:
        ob = OrderBook(symbol="BTC/USDT", bids=[], asks=[], timestamp=datetime.now(UTC))
        assert ob.best_bid is None
        assert ob.best_ask is None
        assert ob.spread is None
        assert ob.spread_bps is None


class TestMarketMetadata:
    def test_round_price_precision(self) -> None:
        meta = MarketMetadata(
            symbol="BTC/USDT",
            base="BTC",
            quote="USDT",
            price_precision=2,
            quantity_precision=6,
            min_quantity=0.0001,
            min_notional=5.0,
        )
        assert meta.round_price(67432.5678) == 67432.57
        assert meta.round_price(67432.5612) == 67432.56
        assert meta.round_price(0.0) == 0.0
        assert meta.round_price(-10.0) == 0.0

    def test_round_quantity_floor_behavior(self) -> None:
        meta = MarketMetadata(
            symbol="BTC/USDT",
            base="BTC",
            quote="USDT",
            price_precision=2,
            quantity_precision=4,
            min_quantity=0.0001,
            min_notional=5.0,
        )
        # 0.123499 should floor to 0.1234 to prevent ordering more than available cash
        assert meta.round_quantity(0.123499) == 0.1234
        assert meta.round_quantity(0.0) == 0.0
        assert meta.round_quantity(-5.0) == 0.0

    def test_satisfies_min_notional(self) -> None:
        meta = MarketMetadata(
            symbol="BTC/USDT",
            base="BTC",
            quote="USDT",
            min_quantity=0.001,
            min_notional=5.0,
        )
        # Price 10,000 * 0.001 = $10 (satisfies notional $5 and min_qty 0.001)
        assert meta.satisfies_min_notional(10000.0, 0.001) is True

        # Price 10,000 * 0.0004 = $4 (fails notional $5 and min_qty 0.001)
        assert meta.satisfies_min_notional(10000.0, 0.0004) is False

        # Price 2,000 * 0.002 = $4 (fails notional $5 even though qty >= min_qty)
        assert meta.satisfies_min_notional(2000.0, 0.002) is False
