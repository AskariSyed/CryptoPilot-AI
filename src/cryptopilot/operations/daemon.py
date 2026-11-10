"""Continuous paper-trading operation loop."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from cryptopilot.config.settings import get_settings
from cryptopilot.data.exchange_client import ExchangeClient
from cryptopilot.database.connection import get_db_manager
from cryptopilot.database.repository import CandleRepository
from cryptopilot.operations.notifications import NotificationService

logger = logging.getLogger(__name__)
CycleHook = Callable[[str, str], Awaitable[None]]


@dataclass(slots=True)
class DaemonStatus:
    """Observable runtime state for health probes and operators."""

    started_at: datetime | None = None
    last_heartbeat: datetime | None = None
    last_success: datetime | None = None
    last_error: str | None = None
    cycles_completed: int = 0
    errors_seen: int = 0
    exchange_connected: bool = False


_runtime_status = DaemonStatus()


def get_daemon_status() -> DaemonStatus:
    """Return the process-wide daemon status used by health probes."""
    return _runtime_status


@dataclass(slots=True)
class TradingDaemon:
    """Fetches public market data and persists it on a bounded async schedule."""

    exchange: ExchangeClient | None = None
    notifications: NotificationService = field(default_factory=NotificationService)
    cycle_interval_seconds: float = 60.0
    candle_limit: int = 500
    on_candles: CycleHook | None = None
    status: DaemonStatus = field(default_factory=get_daemon_status)
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)

    async def run(self) -> None:
        """Run cycles until stop is requested."""
        self.status.started_at = datetime.now(UTC)
        self._stop_event.clear()
        settings = get_settings()
        self.exchange = self.exchange or ExchangeClient(
            exchange_id=settings.exchange_id,
            timeout_ms=settings.request_timeout_ms,
            enable_rate_limit=settings.enable_rate_limit,
            max_retries=settings.max_retries,
            retry_backoff=settings.retry_backoff_factor,
        )
        try:
            async with self.exchange:
                self.status.exchange_connected = True
                await self.notifications.publish("daemon_started", "Paper-trading market loop started.")
                while not self._stop_event.is_set():
                    await self.run_cycle(settings.default_symbols, settings.default_timeframes)
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), self.cycle_interval_seconds)
                    except TimeoutError:
                        pass
        finally:
            self.status.exchange_connected = False
            await self.notifications.publish("daemon_stopped", "Paper-trading market loop stopped.")

    async def run_cycle(self, symbols: list[str], timeframes: list[str]) -> None:
        """Fetch and persist one complete market-data cycle."""
        manager = get_db_manager()
        heartbeat = datetime.now(UTC)
        self.status.last_heartbeat = heartbeat
        try:
            async with manager.session() as session:
                for symbol in symbols:
                    for timeframe in timeframes:
                        candles = await self._fetch_candles(symbol, timeframe)
                        await CandleRepository.upsert_candles(session, candles)
                        if self.on_candles is not None and candles:
                            await self.on_candles(symbol, timeframe)
                await session.commit()
            self.status.last_success = heartbeat
            self.status.last_error = None
            self.status.cycles_completed += 1
            logger.info("Market cycle %d completed for %d symbols and %d timeframes.", self.status.cycles_completed, len(symbols), len(timeframes))
        except Exception as exc:
            self.status.last_error = str(exc)
            self.status.errors_seen += 1
            logger.exception("Market cycle failed.")
            await self.notifications.publish("daemon_error", f"Market cycle failed: {exc}")

    async def stop(self) -> None:
        """Request a graceful stop after the current operation."""
        self._stop_event.set()

    async def _fetch_candles(self, symbol: str, timeframe: str):
        if self.exchange is None:
            raise RuntimeError("Exchange client is not initialized.")
        return await self.exchange.fetch_ohlcv(symbol, timeframe, limit=self.candle_limit)
