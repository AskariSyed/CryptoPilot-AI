"""
Unit tests for cryptopilot.api.routers.portfolio.
Validates mark-to-market portfolio accounting, separated deposit metrics, and performance analytics.
"""

from datetime import UTC, datetime

import httpx
import pytest

from cryptopilot.api.app import create_app
from cryptopilot.database.connection import get_db_manager, reset_db_manager
from cryptopilot.database.models import PositionModel
from cryptopilot.database.repository import PortfolioRepository


@pytest.fixture
async def portfolio_client():
    """Sets up an in-memory database with portfolio balances and positions."""
    reset_db_manager()
    db_mgr = get_db_manager("sqlite+aiosqlite:///:memory:", echo=False)
    await db_mgr.init_db()

    now = datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC)

    async with db_mgr.session() as session:
        # Create small_account_01 with initial $30 and $10 deposit
        port = await PortfolioRepository.get_or_create(
            session=session,
            portfolio_id="small_account_01",
            account_type="small_account",
            initial_balance=30.0,
        )
        port.total_deposits = 10.0
        port.current_cash = 25.0
        port.invested_capital = 15.0
        port.realized_pnl = 2.0

        # Add open position with unrealized PnL
        open_pos = PositionModel(
            id="pos-open",
            portfolio_id="small_account_01",
            symbol="BTC/USDT",
            side="LONG",
            status="OPEN",
            quantity=0.0003,
            entry_price=50000.0,
            current_price=51000.0,
            stop_loss_price=49000.0,
            unrealized_pnl=0.30,
            opened_at=now,
        )

        # Add closed position
        closed_pos = PositionModel(
            id="pos-closed",
            portfolio_id="small_account_01",
            symbol="ETH/USDT",
            side="LONG",
            status="CLOSED",
            quantity=0.005,
            entry_price=3000.0,
            current_price=3100.0,
            exit_price=3100.0,
            stop_loss_price=2900.0,
            realized_pnl=0.50,
            opened_at=now,
            closed_at=now,
        )
        session.add_all([open_pos, closed_pos])
        await session.commit()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await db_mgr.drop_db()
    await db_mgr.close()
    reset_db_manager()


@pytest.mark.asyncio
async def test_get_portfolio_summary(portfolio_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/portfolio calculation."""
    response = await portfolio_client.get("/api/v1/portfolio?account_id=small_account_01")
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["portfolio_id"] == "small_account_01"
    assert data["total_cash"] == 25.0
    assert data["invested_capital"] == 15.0
    assert data["unrealized_pnl"] == 0.30
    assert data["current_equity"] == pytest.approx(40.30, abs=1e-2)
    assert data["realized_pnl"] == 2.0
    assert data["total_deposits"] == 10.0


@pytest.mark.asyncio
async def test_get_portfolio_performance(portfolio_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/portfolio/performance."""
    response = await portfolio_client.get(
        "/api/v1/portfolio/performance?account_id=small_account_01"
    )
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    report = body["data"]
    assert report["portfolio_id"] == "small_account_01"
    assert report["total_trades"] == 1
    assert report["winning_trades"] == 1
    assert report["win_rate"] == 1.0

    # Non-existent portfolio -> 404
    res_404 = await portfolio_client.get("/api/v1/portfolio/performance?account_id=unknown_account")
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["error"].lower()
