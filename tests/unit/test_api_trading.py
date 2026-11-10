"""
Unit tests for cryptopilot.api.routers.trading.
Validates positions, simulated orders, and trade execution endpoints.
"""

from datetime import UTC, datetime

import httpx
import pytest

from cryptopilot.api.app import create_app
from cryptopilot.database.connection import get_db_manager, reset_db_manager
from cryptopilot.database.models import OrderModel, PositionModel, TradeModel


@pytest.fixture
async def trading_client():
    """Sets up an in-memory database with positions, orders, and trades."""
    reset_db_manager()
    db_mgr = get_db_manager("sqlite+aiosqlite:///:memory:", echo=False)
    await db_mgr.init_db()

    now = datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC)

    async with db_mgr.session() as session:
        # 1. Position
        pos = PositionModel(
            id="pos-btc-1",
            portfolio_id="small_account_01",
            symbol="BTC/USDT",
            side="LONG",
            status="OPEN",
            quantity=0.0002,
            entry_price=50000.0,
            current_price=50500.0,
            stop_loss_price=49000.0,
            opened_at=now,
        )
        session.add(pos)

        # 2. Orders
        ord1 = OrderModel(
            id="ord-1",
            portfolio_id="small_account_01",
            symbol="BTC/USDT",
            client_order_id="cli-1",
            order_type="MARKET",
            side="BUY",
            quantity=0.0002,
            status="FILLED",
            filled_quantity=0.0002,
            average_fill_price=50000.0,
            created_at=now,
            updated_at=now,
        )
        session.add(ord1)

        # 3. Trade
        trd = TradeModel(
            id="trd-1",
            order_id="ord-1",
            portfolio_id="small_account_01",
            symbol="BTC/USDT",
            side="BUY",
            price=50000.0,
            quantity=0.0002,
            notional=10.0,
            fee=0.01,
            slippage=0.002,
            timestamp=now,
        )
        session.add(trd)
        await session.commit()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await db_mgr.drop_db()
    await db_mgr.close()
    reset_db_manager()


@pytest.mark.asyncio
async def test_get_positions(trading_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/positions filtering."""
    # OPEN
    res_open = await trading_client.get("/api/v1/positions?account_id=small_account_01&status=OPEN")
    assert res_open.status_code == 200
    data_open = res_open.json()["data"]
    assert len(data_open) == 1
    assert data_open[0]["status"] == "OPEN"

    # CLOSED (empty)
    res_closed = await trading_client.get(
        "/api/v1/positions?account_id=small_account_01&status=CLOSED"
    )
    assert res_closed.status_code == 200
    assert len(res_closed.json()["data"]) == 0


@pytest.mark.asyncio
async def test_get_orders(trading_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/orders with and without symbol filter."""
    res = await trading_client.get("/api/v1/orders?account_id=small_account_01")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["client_order_id"] == "cli-1"

    # Filter by symbol
    res_btc = await trading_client.get("/api/v1/orders?account_id=small_account_01&symbol=BTC/USDT")
    assert len(res_btc.json()["data"]) == 1

    res_eth = await trading_client.get("/api/v1/orders?account_id=small_account_01&symbol=ETH/USDT")
    assert len(res_eth.json()["data"]) == 0


@pytest.mark.asyncio
async def test_get_trades(trading_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/trades."""
    res = await trading_client.get("/api/v1/trades?account_id=small_account_01")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["price"] == 50000.0
    assert data[0]["fee"] == 0.01
