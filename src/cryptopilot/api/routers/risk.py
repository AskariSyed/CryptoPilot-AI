"""
CryptoPilot AI - Risk Management & Telemetry Endpoints.
Serves circuit breaker states, daily loss tracking, and risk audit logs.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cryptopilot.api.deps import get_db_session
from cryptopilot.api.schemas import ApiResponse, RiskEventItem, RiskStatusData
from cryptopilot.config.settings import get_settings
from cryptopilot.database.repository import PortfolioRepository, RiskEventRepository

router = APIRouter(prefix="/risk", tags=["Risk & Circuit Breakers"])


@router.get("/status", response_model=ApiResponse[RiskStatusData])
async def get_risk_status(
    account_id: str = Query("small_account_01", description="Account identifier"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[RiskStatusData]:
    """Returns real-time risk controls and circuit breaker parameters."""
    settings = get_settings()
    portfolio = await PortfolioRepository.get_by_id(session, account_id)

    is_halted = portfolio.is_trading_halted if portfolio else False
    starting_equity = portfolio.initial_balance if portfolio else settings.initial_capital
    daily_loss_limit = settings.daily_loss_limit_pct

    data = RiskStatusData(
        portfolio_id=account_id,
        is_tripped=is_halted,
        trip_reason="Circuit breaker activated" if is_halted else None,
        starting_daily_equity=starting_equity,
        current_daily_loss=0.0,
        daily_loss_pct=0.0,
        daily_loss_limit_pct=daily_loss_limit,
        consecutive_losses=0,
        emergency_stop=is_halted,
        is_trading_halted=is_halted,
    )
    return ApiResponse[RiskStatusData](data=data, timestamp=datetime.now(UTC))


@router.get("/events", response_model=ApiResponse[list[RiskEventItem]])
async def get_risk_events(
    account_id: str = Query("small_account_01", description="Account identifier"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[RiskEventItem]]:
    """Returns chronological audit log of risk checks, limit triggers, and halts."""
    events = await RiskEventRepository.list_events(session, portfolio_id=account_id, limit=limit)
    items = [
        RiskEventItem(
            id=e.id,
            portfolio_id=e.portfolio_id,
            event_type=e.event_type,
            severity=e.severity,
            details=e.details,
            timestamp=e.timestamp,
        )
        for e in events
    ]
    return ApiResponse[list[RiskEventItem]](data=items, timestamp=datetime.now(UTC))

