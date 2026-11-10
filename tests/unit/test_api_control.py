"""
Unit tests for cryptopilot.api.routers.control.
Validates administrative control endpoints, authentication barriers,
deposit injections, emergency kill-switches, and order cancellations.
"""

from datetime import UTC, datetime

import httpx
import pytest

from cryptopilot.api.app import create_app
from cryptopilot.config.settings import get_settings
from cryptopilot.database.connection import DatabaseManager, reset_db_manager
from cryptopilot.database.models import OrderModel, PortfolioModel


@pytest.fixture
async def control_client():
    """Sets up an in-memory database with portfolio and order records for control tests."""
    reset_db_manager()
    db_mgr = DatabaseManager("sqlite+aiosqlite:///:memory:", echo=False)
    await db_mgr.init_db()

    now = datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC)

    async with db_mgr.session() as session:
        port = PortfolioModel(
            id="small_account_01",
            account_type="small_account",
            currency="USDT",
            initial_balance=30.0,
            current_cash=30.0,
            total_deposits=0.0,
            is_trading_halted=False,
        )
        session.add(port)

        ord1 = OrderModel(
            id="ord-cancel-target",
            portfolio_id="small_account_01",
            symbol="BTC/USDT",
            client_order_id="cli-target",
            order_type="LIMIT",
            side="BUY",
            quantity=0.0001,
            price=49000.0,
            status="SUBMITTED",
            created_at=now,
            updated_at=now,
        )
        session.add(ord1)
        await session.commit()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await db_mgr.drop_db()
    await db_mgr.close()
    reset_db_manager()


@pytest.mark.asyncio
async def test_control_auth_barriers(control_client: httpx.AsyncClient) -> None:
    """Verifies that unauthenticated or invalidly authenticated requests are rejected."""
    # 1. Missing Authorization header -> 401
    res_no_auth = await control_client.post(
        "/api/v1/control/deposit",
        json={"portfolio_id": "small_account_01", "amount": 10.0},
    )
    assert res_no_auth.status_code == 401

    # 2. Invalid Bearer token -> 403
    res_bad_auth = await control_client.post(
        "/api/v1/control/deposit",
        headers={"Authorization": "Bearer wrong-secret"},
        json={"portfolio_id": "small_account_01", "amount": 10.0},
    )
    assert res_bad_auth.status_code == 403


@pytest.mark.asyncio
async def test_post_deposit_success_and_validation(control_client: httpx.AsyncClient) -> None:
    """Tests POST /api/v1/control/deposit with valid bearer auth."""
    secret = get_settings().api_secret_key
    auth_headers = {"Authorization": f"Bearer {secret}"}

    # 1. Successful deposit of $10.00
    res = await control_client.post(
        "/api/v1/control/deposit",
        headers=auth_headers,
        json={"portfolio_id": "small_account_01", "amount": 10.0, "note": "November deposit"},
    )
    assert res.status_code == 200

    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["amount_deposited"] == 10.0
    assert data["new_cash_balance"] == 40.0
    assert data["total_deposits"] == 10.0

    # 2. Negative amount rejected by Pydantic validation (422)
    res_neg = await control_client.post(
        "/api/v1/control/deposit",
        headers=auth_headers,
        json={"portfolio_id": "small_account_01", "amount": -10.0},
    )
    assert res_neg.status_code == 422


@pytest.mark.asyncio
async def test_emergency_halt_and_resume(control_client: httpx.AsyncClient) -> None:
    """Tests emergency kill-switch activation and resume controls."""
    secret = get_settings().api_secret_key
    auth_headers = {"Authorization": f"Bearer {secret}"}

    # 1. Trigger emergency halt
    res_halt = await control_client.post(
        "/api/v1/control/emergency-halt",
        headers=auth_headers,
        json={"portfolio_id": "small_account_01", "reason": "High volatility spike detected"},
    )
    assert res_halt.status_code == 200
    assert res_halt.json()["data"]["is_trading_halted"] is True

    # 2. Resume trading
    res_resume = await control_client.post(
        "/api/v1/control/resume-trading?portfolio_id=small_account_01",
        headers=auth_headers,
    )
    assert res_resume.status_code == 200
    assert res_resume.json()["data"]["is_trading_halted"] is False

    # 3. Resume non-existent portfolio -> 404
    res_404 = await control_client.post(
        "/api/v1/control/resume-trading?portfolio_id=unknown_portfolio",
        headers=auth_headers,
    )
    assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_cancel_order(control_client: httpx.AsyncClient) -> None:
    """Tests POST /api/v1/control/cancel-order."""
    secret = get_settings().api_secret_key
    auth_headers = {"Authorization": f"Bearer {secret}"}

    res = await control_client.post(
        "/api/v1/control/cancel-order",
        headers=auth_headers,
        json={
            "portfolio_id": "small_account_01",
            "order_id": "ord-cancel-target",
            "reason": "Test manual cancellation",
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "CANCELED"
