"""
Unit tests for cryptopilot.api.routers.decisions and risk.
Validates decision explanation telemetry, circuit breaker metrics, and risk event audit logs.
"""

from datetime import UTC, datetime

import httpx
import pytest

from cryptopilot.api.app import create_app
from cryptopilot.database.connection import DatabaseManager, reset_db_manager
from cryptopilot.database.models import AgentDecisionModel, PortfolioModel, RiskEventModel


@pytest.fixture
async def decisions_risk_client():
    """Sets up an in-memory database with decision and risk event records."""
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
            is_trading_halted=False,
        )
        session.add(port)

        # 1. Decision
        dec = AgentDecisionModel(
            id="dec-1",
            symbol="BTC/USDT",
            timestamp=now,
            decision="BUY",
            confidence=0.88,
            market_regime="TRENDING_BULL",
            strategy_signals_json={"ema_trend": "BUY", "rsi_macd": "BUY"},
            ml_prediction_json={"prob": 0.75},
            sentiment_summary_json={"score": 0.50},
            risk_approved=True,
            explanation_text="Strong alignment across all strategies.",
        )
        session.add(dec)

        # 2. Risk Event
        evt = RiskEventModel(
            portfolio_id="small_account_01",
            event_type="CIRCUIT_BREAKER_CHECK",
            severity="INFO",
            details={"loss_pct": 0.0},
            timestamp=now,
        )
        session.add(evt)
        await session.commit()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await db_mgr.drop_db()
    await db_mgr.close()
    reset_db_manager()


@pytest.mark.asyncio
async def test_get_decisions(decisions_risk_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/decisions."""
    res = await decisions_risk_client.get("/api/v1/decisions?symbol=BTC/USDT")
    assert res.status_code == 200

    body = res.json()
    assert body["success"] is True
    decisions = body["data"]
    assert len(decisions) == 1
    assert decisions[0]["decision"] == "BUY"
    assert decisions[0]["confidence"] == 0.88
    assert "Strong alignment" in decisions[0]["explanation"]


@pytest.mark.asyncio
async def test_get_risk_status(decisions_risk_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/risk/status."""
    res = await decisions_risk_client.get("/api/v1/risk/status?account_id=small_account_01")
    assert res.status_code == 200

    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["portfolio_id"] == "small_account_01"
    assert data["is_tripped"] is False
    assert data["daily_loss_limit_pct"] == 0.02


@pytest.mark.asyncio
async def test_get_risk_events(decisions_risk_client: httpx.AsyncClient) -> None:
    """Tests GET /api/v1/risk/events."""
    res = await decisions_risk_client.get("/api/v1/risk/events?account_id=small_account_01")
    assert res.status_code == 200

    body = res.json()
    assert body["success"] is True
    events = body["data"]
    assert len(events) == 1
    assert events[0]["event_type"] == "CIRCUIT_BREAKER_CHECK"

