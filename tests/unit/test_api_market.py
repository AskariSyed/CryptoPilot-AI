"""
Unit tests for cryptopilot.api.routers.market.
Validates candle historical queries, limits, and real-time ticker quotes.
"""

from datetime import UTC, datetime

import httpx
import pytest

from cryptopilot.api.app import create_app
from cryptopilot.data.models import Candle
from cryptopilot.database.connection import get_db_manager, reset_db_manager
from cryptopilot.database.models import MarketSnapshotModel
from cryptopilot.database.repository import CandleRepository


@pytest.fixture
async def market_client():
    """Sets up an in-memory database with market candles and snapshot records."""
    reset_db_manager()
    db_mgr = get_db_manager("sqlite+aiosqlite:///:memory:", echo=False)
    await db_mgr.init_db()

    now = datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC)

    async with db_mgr.session() as session:
        # Seed candles
        c1 = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=now,
            open=50000.0,
            high=51000.0,
            low=49500.0,
            close=50500.0,
            volume=100.0,
        )
        await CandleRepository.upsert_candle(session, c1)

        # Seed snapshot for ETH
        snap = MarketSnapshotModel(
            symbol="ETH/USDT",
            timestamp=now,
            bid_price=3000.0,
            ask_price=3001.0,
            spread=1.0,
            mid_price=3000.5,
        )
        session.add(snap)
        await session.commit()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await db_mgr.drop_db()
    await db_mgr.close()
    reset_db_manager()


@pytest.mark.asyncio
async def test_get_candles(market_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/market/candles."""
    response = await market_client.get(
        "/api/v1/market/candles?symbol=BTC/USDT&timeframe=1h&limit=10"
    )
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["symbol"] == "BTC/USDT"
    assert data["count"] == 1
    candle = data["candles"][0]
    assert candle["close"] == 50500.0


@pytest.mark.asyncio
async def test_get_ticker(market_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/market/ticker with snapshot and fallback."""
    # 1. ETH/USDT has snapshot
    res_eth = await market_client.get("/api/v1/market/ticker?symbol=ETH/USDT")
    assert res_eth.status_code == 200
    data_eth = res_eth.json()["data"]
    assert data_eth["symbol"] == "ETH/USDT"
    assert data_eth["bid"] == 3000.0
    assert data_eth["ask"] == 3001.0

    # 2. BTC/USDT has candle fallback
    res_btc = await market_client.get("/api/v1/market/ticker?symbol=BTC/USDT")
    assert res_btc.status_code == 200
    data_btc = res_btc.json()["data"]
    assert data_btc["last"] == 50500.0
    assert data_btc["spread"] > 0.0

    # 3. Unknown symbol fallback
    res_sol = await market_client.get("/api/v1/market/ticker?symbol=SOL/USDT")
    assert res_sol.status_code == 200
    data_sol = res_sol.json()["data"]
    assert data_sol["last"] == 150.0
