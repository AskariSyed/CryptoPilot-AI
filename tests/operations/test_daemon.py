from datetime import UTC, datetime

import pytest

from cryptopilot.data.models import Candle
from cryptopilot.operations.daemon import TradingDaemon


class FakeExchange:
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> list[Candle]:
        return [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime(2025, 1, 1, tzinfo=UTC),
                open=100,
                high=101,
                low=99,
                close=100.5,
                volume=10,
            )
        ]


@pytest.mark.asyncio
async def test_cycle_persists_candles_and_updates_heartbeat(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'daemon.db'}"
    from cryptopilot.database.connection import get_db_manager, reset_db_manager

    reset_db_manager()
    manager = get_db_manager(database_url)
    await manager.init_db()
    daemon = TradingDaemon(exchange=FakeExchange())

    await daemon.run_cycle(["BTC/USDT"], ["1h"])

    assert daemon.status.cycles_completed == 1
    assert daemon.status.last_heartbeat is not None
    async with manager.session() as session:
        from cryptopilot.database.repository import CandleRepository

        assert await CandleRepository.count_candles(session, "BTC/USDT", "1h") == 1
    await manager.close()
    reset_db_manager()


@pytest.mark.asyncio
async def test_cycle_records_errors_and_notifies():
    class BrokenExchange:
        async def fetch_ohlcv(self, *args, **kwargs):
            raise RuntimeError("exchange unavailable")

    daemon = TradingDaemon(exchange=BrokenExchange())
    await daemon.run_cycle(["BTC/USDT"], ["1h"])

    assert daemon.status.errors_seen == 1
    assert daemon.status.last_error == "exchange unavailable"
