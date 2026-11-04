"""
Unit tests for cryptopilot.data.exchange_client.ExchangeClient.
Mocks all CCXT network calls for 100% deterministic, offline execution.
Covers 8-Point Method testing across all retry, timeout, rate-limiting, and error branches.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import ccxt.async_support as ccxt_async
import pytest

from cryptopilot.data.exceptions import (
    ExchangeConnectionError,
    InvalidTimeframeError,
    MarketDataError,
    RateLimitExceededError,
    SymbolNotFoundError,
)
from cryptopilot.data.exchange_client import ExchangeClient
from cryptopilot.data.models import Timeframe


class MockCCXTExchange:
    """Mock CCXT async exchange."""

    def __init__(self) -> None:
        self.load_markets = AsyncMock(return_value={})
        self.close = AsyncMock()
        self.fetch_ticker = AsyncMock()
        self.fetch_order_book = AsyncMock()
        self.fetch_ohlcv = AsyncMock()
        self.markets: dict[str, Any] = {
            "BTC/USDT": {
                "precision": {"price": 2, "amount": 6},
                "limits": {"amount": {"min": 0.0001}, "cost": {"min": 5.0}},
                "maker": 0.001,
                "taker": 0.001,
            }
        }


class TestExchangeClient:
    def test_init_unsupported_exchange(self) -> None:
        with pytest.raises(ExchangeConnectionError) as exc:
            ExchangeClient(exchange_id="non_existent_crypto_exchange_xyz")
        assert "Unsupported exchange" in str(exc.value)

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self) -> None:
        mock_ex = MockCCXTExchange()
        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)

        async with client as c:
            assert c is client
            mock_ex.load_markets.assert_called_once()

        mock_ex.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_ticker_success(self) -> None:
        mock_ex = MockCCXTExchange()
        mock_ex.fetch_ticker.return_value = {
            "symbol": "BTC/USDT",
            "bid": 65000.0,
            "ask": 65010.0,
            "last": 65005.0,
            "baseVolume": 1500.0,
            "timestamp": 1704067200000,
        }

        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)
        ticker = await client.fetch_ticker("BTC/USDT")

        assert ticker.symbol == "BTC/USDT"
        assert ticker.bid == 65000.0
        assert ticker.ask == 65010.0
        assert ticker.last == 65005.0
        assert ticker.volume_24h == 1500.0
        assert ticker.timestamp == datetime.fromtimestamp(1704067200, tz=UTC)

    @pytest.mark.asyncio
    async def test_fetch_ticker_fallback_when_bid_ask_zero(self) -> None:
        mock_ex = MockCCXTExchange()
        mock_ex.fetch_ticker.return_value = {
            "symbol": "BTC/USDT",
            "bid": 0.0,
            "ask": 0.0,
            "last": 50000.0,
            "baseVolume": 100.0,
            "timestamp": None,
        }

        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)
        ticker = await client.fetch_ticker("BTC/USDT")

        assert ticker.bid == 50000.0 * 0.9995
        assert ticker.ask == 50000.0 * 1.0005
        assert ticker.timestamp.tzinfo == UTC

    @pytest.mark.asyncio
    async def test_fetch_order_book_success(self) -> None:
        mock_ex = MockCCXTExchange()
        mock_ex.fetch_order_book.return_value = {
            "bids": [[65000.0, 1.2], [64990.0, 3.4]],
            "asks": [[65010.0, 2.1], [65020.0, 4.5]],
            "timestamp": 1704067200000,
        }

        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)
        ob = await client.fetch_order_book("BTC/USDT", limit=10)

        assert len(ob.bids) == 2
        assert len(ob.asks) == 2
        assert ob.best_bid == 65000.0
        assert ob.best_ask == 65010.0

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_success_and_unclosed_check(self) -> None:
        mock_ex = MockCCXTExchange()
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        older_ms = now_ms - (3600 * 1000 * 2)

        mock_ex.fetch_ohlcv.return_value = [
            [older_ms, 60000.0, 60500.0, 59500.0, 60200.0, 100.0],
            [now_ms, 60200.0, 60800.0, 60100.0, 60600.0, 50.0],
        ]

        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)
        candles = await client.fetch_ohlcv("BTC/USDT", "1h")

        assert len(candles) == 2
        # Older candle is closed
        assert candles[0].is_closed is True
        # Current candle age is < 1h, so is_closed must be False
        assert candles[1].is_closed is False

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_empty(self) -> None:
        mock_ex = MockCCXTExchange()
        mock_ex.fetch_ohlcv.return_value = []

        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)
        candles = await client.fetch_ohlcv("ETH/USDT", "15m")
        assert candles == []

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_invalid_timeframe(self) -> None:
        mock_ex = MockCCXTExchange()
        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)

        with pytest.raises(InvalidTimeframeError) as exc:
            await client.fetch_ohlcv("BTC/USDT", "2d")
        assert "Unsupported timeframe" in str(exc.value)

    @pytest.mark.asyncio
    async def test_fetch_market_metadata_success(self) -> None:
        mock_ex = MockCCXTExchange()
        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)

        meta = await client.fetch_market_metadata("BTC/USDT")
        assert meta.symbol == "BTC/USDT"
        assert meta.base == "BTC"
        assert meta.quote == "USDT"
        assert meta.price_precision == 2
        assert meta.quantity_precision == 6
        assert meta.min_notional == 5.0

    @pytest.mark.asyncio
    async def test_fetch_market_metadata_symbol_not_found(self) -> None:
        mock_ex = MockCCXTExchange()
        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)

        with pytest.raises(SymbolNotFoundError):
            await client.fetch_market_metadata("UNKNOWN/USDT")

    @pytest.mark.asyncio
    async def test_retry_on_transient_network_error(self) -> None:
        mock_ex = MockCCXTExchange()
        call_count = 0

        async def flaky_fetch(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ccxt_async.RequestTimeout("Simulated timeout")
            return {
                "symbol": "BTC/USDT",
                "bid": 65000.0,
                "ask": 65010.0,
                "last": 65005.0,
                "baseVolume": 100.0,
                "timestamp": 1704067200000,
            }

        mock_ex.fetch_ticker.side_effect = flaky_fetch
        client = ExchangeClient(
            exchange_id="binance", custom_exchange=mock_ex, max_retries=2, retry_backoff=1.0
        )
        ticker = await client.fetch_ticker("BTC/USDT")

        assert call_count == 2
        assert ticker.last == 65005.0

    @pytest.mark.asyncio
    async def test_retry_exhaustion_raises_exchange_connection_error(self) -> None:
        mock_ex = MockCCXTExchange()
        mock_ex.fetch_ticker.side_effect = ccxt_async.NetworkError("Persistent connection drop")

        client = ExchangeClient(
            exchange_id="binance", custom_exchange=mock_ex, max_retries=2, retry_backoff=1.0
        )
        with pytest.raises(ExchangeConnectionError) as exc:
            await client.fetch_ticker("BTC/USDT")
        assert "Network failure after 2 retries" in str(exc.value)

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_error(self) -> None:
        mock_ex = MockCCXTExchange()
        mock_ex.fetch_ticker.side_effect = ccxt_async.RateLimitExceeded(
            "HTTP 429 Too Many Requests"
        )

        client = ExchangeClient(
            exchange_id="binance", custom_exchange=mock_ex, max_retries=1, retry_backoff=1.0
        )
        with pytest.raises(RateLimitExceededError) as exc:
            await client.fetch_ticker("BTC/USDT")
        assert "Rate limit exceeded" in str(exc.value)

    @pytest.mark.asyncio
    async def test_bad_symbol_error(self) -> None:
        mock_ex = MockCCXTExchange()
        mock_ex.fetch_ticker.side_effect = ccxt_async.BadSymbol("No such symbol on exchange")

        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)
        with pytest.raises(SymbolNotFoundError):
            await client.fetch_ticker("INVALID/USDT")

    @pytest.mark.asyncio
    async def test_unexpected_exception_raises_market_data_error(self) -> None:
        mock_ex = MockCCXTExchange()
        mock_ex.fetch_ticker.side_effect = RuntimeError("Random runtime crash")

        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)
        with pytest.raises(MarketDataError) as exc:
            await client.fetch_ticker("BTC/USDT")
        assert "Unexpected failure" in str(exc.value)

    @pytest.mark.asyncio
    async def test_fetch_historical_range_pagination(self) -> None:
        mock_ex = MockCCXTExchange()

        # Generate 2 batches of 2 candles
        base_ms = 1704067200000  # 2024-01-01 00:00:00 UTC
        batch1 = [
            [base_ms, 40000.0, 40500.0, 39500.0, 40200.0, 10.0],
            [base_ms + 3600000, 40200.0, 40800.0, 40100.0, 40500.0, 15.0],
        ]
        batch2 = [
            [base_ms + 7200000, 40500.0, 41000.0, 40400.0, 40900.0, 20.0],
            [base_ms + 10800000, 40900.0, 41200.0, 40700.0, 41100.0, 25.0],
        ]

        call_idx = 0

        async def paged_ohlcv(*args: Any, **kwargs: Any) -> list[list[float]]:
            nonlocal call_idx
            call_idx += 1
            if call_idx == 1:
                return batch1
            elif call_idx == 2:
                return batch2
            return []

        mock_ex.fetch_ohlcv.side_effect = paged_ohlcv
        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)

        t_start = datetime.fromtimestamp(base_ms / 1000.0, tz=UTC)
        t_end = datetime.fromtimestamp((base_ms + 14400000) / 1000.0, tz=UTC)

        candles = await client.fetch_historical_range("BTC/USDT", Timeframe.H1, t_start, t_end)
        assert len(candles) == 4
        assert candles[0].open == 40000.0
        assert candles[3].close == 41100.0

    @pytest.mark.asyncio
    async def test_fetch_historical_range_invalid_dates(self) -> None:
        mock_ex = MockCCXTExchange()
        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)

        t1 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
        t2 = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)

        with pytest.raises(MarketDataError) as exc:
            await client.fetch_historical_range("BTC/USDT", "1h", t1, t2)
        assert "start_time must be strictly earlier" in str(exc.value)
