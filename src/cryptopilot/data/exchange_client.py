"""
CryptoPilot AI - Asynchronous Exchange Client.
Provides a resilient, rate-limited, retry-protected wrapper around CCXT public endpoints.
Requires zero private API keys.
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any, TypeVar

import ccxt.async_support as ccxt_async

from cryptopilot.data.exceptions import (
    ExchangeConnectionError,
    InvalidTimeframeError,
    MarketDataError,
    RateLimitExceededError,
    SymbolNotFoundError,
)
from cryptopilot.data.models import (
    Candle,
    MarketMetadata,
    OrderBook,
    OrderBookLevel,
    Symbol,
    Ticker,
    Timeframe,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ExchangeClient:
    """
    Asynchronous CCXT wrapper for public cryptocurrency market data.
    Implements rate-limiting, exponential backoff, and robust error translation.
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        timeout_ms: int = 10000,
        enable_rate_limit: bool = True,
        max_retries: int = 3,
        retry_backoff: float = 1.5,
        custom_exchange: Any | None = None,
    ) -> None:
        self.exchange_id = exchange_id.lower()
        self.timeout_ms = timeout_ms
        self.enable_rate_limit = enable_rate_limit
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

        if custom_exchange is not None:
            self._exchange = custom_exchange
        else:
            exchange_class = getattr(ccxt_async, self.exchange_id, None)
            if exchange_class is None:
                raise ExchangeConnectionError(f"Unsupported exchange '{self.exchange_id}' in CCXT")
            self._exchange = exchange_class(
                {
                    "enableRateLimit": self.enable_rate_limit,
                    "timeout": self.timeout_ms,
                    "options": {
                        "defaultType": "spot",
                    },
                }
            )

        self._markets_loaded = False
        self._markets_lock = asyncio.Lock()

    async def __aenter__(self) -> "ExchangeClient":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def initialize(self) -> None:
        """Loads exchange markets and trading rules asynchronously."""
        async with self._markets_lock:
            if not self._markets_loaded:
                await self._execute_with_retry("load_markets", self._exchange.load_markets)
                self._markets_loaded = True

    async def close(self) -> None:
        """Closes underlying aiohttp session and cleanup exchange resources."""
        if self._exchange is not None:
            await self._exchange.close()

    async def _execute_with_retry(
        self,
        op_name: str,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Executes a CCXT coroutine with exponential backoff on transient network faults.
        Translates CCXT exceptions to CryptoPilot domain exceptions.
        """
        attempt = 0
        current_delay = 0.5

        while True:
            attempt += 1
            try:
                return await func(*args, **kwargs)
            except ccxt_async.RateLimitExceeded as e:
                logger.warning(
                    "Exchange rate limit exceeded in %s on attempt %d: %s", op_name, attempt, e
                )
                if attempt > self.max_retries:
                    raise RateLimitExceededError(
                        f"Rate limit exceeded after {attempt} attempts in {op_name}",
                        details={"exchange": self.exchange_id, "error": str(e)},
                    ) from e
                await asyncio.sleep(current_delay * 2.0)
                current_delay *= self.retry_backoff

            except ccxt_async.BadSymbol as e:
                logger.error("Symbol not found on exchange %s: %s", self.exchange_id, e)
                raise SymbolNotFoundError(
                    f"Symbol not supported or invalid on {self.exchange_id}",
                    details={"error": str(e)},
                ) from e

            except (TimeoutError, ccxt_async.NetworkError, ccxt_async.RequestTimeout) as e:
                logger.warning(
                    "Network error in %s (attempt %d/%d): %s",
                    op_name,
                    attempt,
                    self.max_retries,
                    e,
                )
                if attempt > self.max_retries:
                    raise ExchangeConnectionError(
                        f"Network failure after {self.max_retries} retries in {op_name}: {e}",
                        details={"exchange": self.exchange_id, "error": str(e)},
                    ) from e
                await asyncio.sleep(current_delay)
                current_delay *= self.retry_backoff

            except ccxt_async.BaseError as e:
                logger.error("CCXT error during %s: %s", op_name, e)
                raise ExchangeConnectionError(
                    f"Exchange error in {op_name}: {e}",
                    details={"exchange": self.exchange_id, "error": str(e)},
                ) from e

            except Exception as e:
                logger.error("Unexpected error in %s: %s", op_name, e)
                raise MarketDataError(
                    f"Unexpected failure in {op_name}: {e}",
                    details={"exchange": self.exchange_id, "error": str(e)},
                ) from e

    async def fetch_ticker(self, symbol: str) -> Ticker:
        """Fetches current ticker (bid, ask, last, 24h volume) for a symbol."""
        await self.initialize()
        sym = Symbol.from_string(symbol).raw
        data = await self._execute_with_retry("fetch_ticker", self._exchange.fetch_ticker, sym)

        ts_raw = data.get("timestamp")
        dt = datetime.fromtimestamp(ts_raw / 1000.0, tz=UTC) if ts_raw else datetime.now(UTC)

        last_val = data.get("last")
        last = float(last_val) if last_val is not None else 0.0

        bid_val = data.get("bid")
        ask_val = data.get("ask")
        bid = (
            float(bid_val)
            if (bid_val is not None and float(bid_val) > 0.0)
            else (last * 0.9995 if last > 0.0 else 0.0)
        )
        ask = (
            float(ask_val)
            if (ask_val is not None and float(ask_val) > 0.0)
            else (last * 1.0005 if last > 0.0 else 0.0)
        )
        vol = float(data.get("baseVolume") or data.get("quoteVolume") or 0.0)

        return Ticker(
            symbol=sym,
            bid=bid,
            ask=ask,
            last=last,
            volume_24h=vol,
            timestamp=dt,
        )

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> OrderBook:
        """Fetches order book depth for a symbol."""
        await self.initialize()
        sym = Symbol.from_string(symbol).raw
        data = await self._execute_with_retry(
            "fetch_order_book", self._exchange.fetch_order_book, sym, limit
        )

        ts_raw = data.get("timestamp")
        dt = datetime.fromtimestamp(ts_raw / 1000.0, tz=UTC) if ts_raw else datetime.now(UTC)

        bids = [
            OrderBookLevel(price=float(item[0]), amount=float(item[1]))
            for item in data.get("bids", [])
            if len(item) >= 2
        ]
        asks = [
            OrderBookLevel(price=float(item[0]), amount=float(item[1]))
            for item in data.get("asks", [])
            if len(item) >= 2
        ]

        return OrderBook(
            symbol=sym,
            bids=bids,
            asks=asks,
            timestamp=dt,
        )

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str | Timeframe,
        since: datetime | None = None,
        limit: int = 500,
    ) -> list[Candle]:
        """
        Fetches OHLCV historical candles.
        Marks the last candle as is_closed=False if its window is currently active.
        """
        await self.initialize()
        sym = Symbol.from_string(symbol).raw
        tf_str = timeframe.value if isinstance(timeframe, Timeframe) else timeframe

        if tf_str not in [tf.value for tf in Timeframe]:
            raise InvalidTimeframeError(f"Unsupported timeframe '{tf_str}'")

        since_ms = int(since.astimezone(UTC).timestamp() * 1000) if since else None

        raw_ohlcv = await self._execute_with_retry(
            "fetch_ohlcv",
            self._exchange.fetch_ohlcv,
            sym,
            tf_str,
            since_ms,
            limit,
        )

        if not raw_ohlcv:
            return []

        now_utc = datetime.now(UTC)
        tf_enum = Timeframe(tf_str)
        interval_sec = tf_enum.duration_seconds

        candles: list[Candle] = []
        for i, item in enumerate(raw_ohlcv):
            # Check if this is the final candle in the returned set
            is_last = i == len(raw_ohlcv) - 1
            candle_ts = datetime.fromtimestamp(item[0] / 1000.0, tz=UTC)
            bar_age_seconds = (now_utc - candle_ts).total_seconds()

            # A candle is considered closed if current time has progressed past its end
            is_closed = bar_age_seconds >= interval_sec if is_last else True

            candle = Candle.from_ccxt_tuple(
                raw_tuple=item,
                symbol=sym,
                timeframe=tf_str,
                is_closed=is_closed,
            )
            candles.append(candle)

        return candles

    async def fetch_market_metadata(self, symbol: str) -> MarketMetadata:
        """Retrieves trading precision, minimum notional, and fees for a symbol."""
        await self.initialize()
        sym_obj = Symbol.from_string(symbol)
        sym = sym_obj.raw

        market = self._exchange.markets.get(sym)
        if not market:
            # Try reloading markets once
            await self._execute_with_retry("load_markets", self._exchange.load_markets, True)
            market = self._exchange.markets.get(sym)

        if not market:
            raise SymbolNotFoundError(f"Symbol '{sym}' not found in exchange markets registry")

        precision = market.get("precision", {}) or {}
        price_prec = int(precision.get("price") or 2)
        qty_prec = int(precision.get("amount") or 6)

        limits = market.get("limits", {}) or {}
        amount_limits = limits.get("amount", {}) or {}
        cost_limits = limits.get("cost", {}) or {}

        min_qty = float(amount_limits.get("min") or 0.0001)
        min_notional = float(cost_limits.get("min") or 5.0)

        maker = float(market.get("maker") or 0.001)
        taker = float(market.get("taker") or 0.001)

        return MarketMetadata(
            symbol=sym,
            base=sym_obj.base,
            quote=sym_obj.quote,
            price_precision=price_prec,
            quantity_precision=qty_prec,
            min_quantity=min_qty,
            min_notional=min_notional,
            maker_fee=maker,
            taker_fee=taker,
        )

    async def fetch_historical_range(
        self,
        symbol: str,
        timeframe: str | Timeframe,
        start_time: datetime,
        end_time: datetime,
        max_batch_size: int = 500,
    ) -> list[Candle]:
        """
        Fetches continuous historical OHLCV data across an extended date range
        by automatically paginating forward in time.
        """
        await self.initialize()
        tf_enum = Timeframe(timeframe) if isinstance(timeframe, str) else timeframe
        interval_ms = tf_enum.duration_ms

        start_utc = start_time.astimezone(UTC)
        end_utc = end_time.astimezone(UTC)

        if start_utc >= end_utc:
            raise MarketDataError("start_time must be strictly earlier than end_time")

        current_since = start_utc
        all_candles: list[Candle] = []
        seen_timestamps = set()

        while current_since < end_utc:
            batch = await self.fetch_ohlcv(
                symbol=symbol,
                timeframe=tf_enum,
                since=current_since,
                limit=max_batch_size,
            )

            if not batch:
                break

            new_candles = 0
            for candle in batch:
                ts = candle.timestamp
                if ts >= end_utc:
                    break
                if ts not in seen_timestamps:
                    seen_timestamps.add(ts)
                    all_candles.append(candle)
                    new_candles += 1

            # If no new candles were added, avoid infinite loop
            if new_candles == 0:
                break

            last_ts = batch[-1].timestamp
            next_ms = int(last_ts.timestamp() * 1000) + interval_ms
            current_since = datetime.fromtimestamp(next_ms / 1000.0, tz=UTC)

            # Small sleep to respect public exchange rate limits
            await asyncio.sleep(0.05)

        return all_candles
