"""
CryptoPilot AI - Administrative & Operational Control Endpoints.
Guarded by Bearer token authorization; handles manual deposits, emergency halts, and order cancels.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cryptopilot.api.deps import get_db_session, get_paper_broker, verify_admin_token
from cryptopilot.api.schemas import (
    ApiResponse,
    DepositRequest,
    EmergencyHaltRequest,
    OrderCancelRequest,
)
from cryptopilot.database.repository import OrderRepository, PortfolioRepository
from cryptopilot.database.transactions import (
    record_deposit_and_update_balance,
    record_risk_event,
)
from cryptopilot.execution.broker import PaperBroker
from cryptopilot.execution.models import OrderStatus

router = APIRouter(prefix="/control", tags=["Administrative & Control"])


@router.post("/deposit", response_model=ApiResponse[dict[str, str | float]])
async def post_deposit(
    request: DepositRequest,
    session: AsyncSession = Depends(get_db_session),
    _token: str = Depends(verify_admin_token),
) -> ApiResponse[dict[str, str | float]]:
    """Records a simulated capital injection (e.g. $10/month) into the portfolio."""
    try:
        deposit, port = await record_deposit_and_update_balance(
            session=session,
            portfolio_id=request.portfolio_id,
            amount=request.amount,
            currency=request.currency,
            note=request.note,
        )
    except (KeyError, ValueError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    data: dict[str, str | float] = {
        "portfolio_id": port.id,
        "amount_deposited": deposit.amount,
        "new_cash_balance": port.current_cash,
        "total_deposits": port.total_deposits,
    }
    return ApiResponse[dict[str, str | float]](data=data, timestamp=datetime.now(UTC))


@router.post("/emergency-halt", response_model=ApiResponse[dict[str, str | bool]])
async def post_emergency_halt(
    request: EmergencyHaltRequest,
    session: AsyncSession = Depends(get_db_session),
    broker: PaperBroker = Depends(get_paper_broker),
    _token: str = Depends(verify_admin_token),
) -> ApiResponse[dict[str, str | bool]]:
    """Activates emergency kill-switch, halting all trading and canceling pending orders."""
    await record_risk_event(
        session=session,
        portfolio_id=request.portfolio_id,
        event_type="EMERGENCY_HALT",
        severity="CRITICAL",
        details={"reason": request.reason},
    )

    # Cancel open orders in virtual broker
    canceled_count = broker.cancel_all_orders(request.portfolio_id)

    data: dict[str, str | bool] = {
        "portfolio_id": request.portfolio_id,
        "is_trading_halted": True,
        "orders_canceled": canceled_count > 0,
    }
    return ApiResponse[dict[str, str | bool]](data=data, timestamp=datetime.now(UTC))


@router.post("/resume-trading", response_model=ApiResponse[dict[str, str | bool]])
async def post_resume_trading(
    portfolio_id: str = "small_account_01",
    session: AsyncSession = Depends(get_db_session),
    _token: str = Depends(verify_admin_token),
) -> ApiResponse[dict[str, str | bool]]:
    """Manually resets circuit breaker and resumes autonomous operations."""
    port = await PortfolioRepository.get_by_id(session, portfolio_id)
    if port is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio '{portfolio_id}' not found.",
        )

    await PortfolioRepository.update_balances(
        session=session,
        portfolio_id=portfolio_id,
        cash=port.current_cash,
        invested=port.invested_capital,
        realized_pnl=port.realized_pnl,
        is_halted=False,
    )

    await record_risk_event(
        session=session,
        portfolio_id=portfolio_id,
        event_type="EMERGENCY_HALT_RESET",
        severity="INFO",
        details={"note": "Trading manually resumed by administrator"},
    )

    data: dict[str, str | bool] = {
        "portfolio_id": portfolio_id,
        "is_trading_halted": False,
    }
    return ApiResponse[dict[str, str | bool]](data=data, timestamp=datetime.now(UTC))


@router.post("/cancel-order", response_model=ApiResponse[dict[str, str]])
async def post_cancel_order(
    request: OrderCancelRequest,
    session: AsyncSession = Depends(get_db_session),
    broker: PaperBroker = Depends(get_paper_broker),
    _token: str = Depends(verify_admin_token),
) -> ApiResponse[dict[str, str]]:
    """Cancels a pending or open virtual order."""
    # Update DB
    updated = await OrderRepository.update_order_status(
        session=session,
        order_id=request.order_id,
        status=OrderStatus.CANCELED,
    )

    # Cancel in memory broker if active
    try:
        broker.cancel_order(request.order_id, reason=request.reason)
    except (KeyError, ValueError):
        pass

    data = {
        "order_id": request.order_id,
        "status": "CANCELED" if updated else "UNKNOWN",
    }
    return ApiResponse[dict[str, str]](data=data, timestamp=datetime.now(UTC))
