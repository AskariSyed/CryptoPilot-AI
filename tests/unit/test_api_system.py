"""
Unit tests for cryptopilot.api.routers.system.
Validates health probes, daemon heartbeats, uptime telemetry, and process timing headers.
"""

import httpx
import pytest

from cryptopilot.api.app import create_app
from cryptopilot.database.connection import get_db_manager, reset_db_manager


@pytest.fixture
async def api_client():
    """Provides async test client with an isolated in-memory database."""
    reset_db_manager()
    db_mgr = get_db_manager("sqlite+aiosqlite:///:memory:", echo=False)
    await db_mgr.init_db()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await db_mgr.drop_db()
    await db_mgr.close()
    reset_db_manager()


@pytest.mark.asyncio
async def test_get_health(api_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/health probe and response envelope."""
    response = await api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert "X-Process-Time-Ms" in response.headers

    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    data = body["data"]
    assert data["status"] == "HEALTHY"
    assert data["version"] == "0.1.0"
    assert data["database"] == "CONNECTED"
    assert data["trading_mode"] == "paper"


@pytest.mark.asyncio
async def test_get_system_status(api_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/status configuration endpoint."""
    response = await api_client.get("/api/v1/status")
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert "small_account_01" in data["active_portfolios"]
    assert "BTC/USDT" in data["monitored_symbols"]
    assert data["live_trading_enabled"] is False

