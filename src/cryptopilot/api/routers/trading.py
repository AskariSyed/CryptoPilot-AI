"""
CryptoPilot AI - Virtual Trading Endpoints.
Serves active positions, simulated order history, and trade execution receipts.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from cryptopilot.api.deps import get_db_session
from cryptopilot.api.schemas import (
    ApiResponse,
    OrderItem,
    PositionItem,
    TradeItem,
)
from cryptopilot.database.models import TradeModel
from cryptopilot.database.repository import OrderRepository, PositionRepository

router = APIRouter(tags=["Trading & Virtual Execution"])


@router.get("/positions", response_model=ApiResponse[list[PositionItem]])
async def get_positions(
    account_id: str = Query("small_account_01", description="Account identifier"),
    status: str | None = Query(None, description="Position status filter: OPEN or CLOSED"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[PositionItem]]:
    """Returns list of active or historical positions."""
    if status == "OPEN":
        positions = await PositionRepository.list_open_positions(session, account_id)
    else:
        positions = await PositionRepository.list_positions(session, account_id, limit=limit)
        if status is not None:
            positions = [p for p in positions if p.status == status]

    items = [
        PositionItem(
            id=p.id,
            portfolio_id=p.portfolio_id,
            symbol=p.symbol,
            side=p.side,
            status=p.status,
            quantity=p.quantity,
            entry_price=p.entry_price,
            current_price=p.current_price,
            exit_price=p.exit_price,
            stop_loss_price=p.stop_loss_price,
            take_profit_price=p.take_profit_price,
            unrealized_pnl=p.unrealized_pnl,
            realized_pnl=p.realized_pnl,
            opened_at=p.opened_at,
            closed_at=p.closed_at,
        )
        for p in positions
    ]
    return ApiResponse[list[PositionItem]](data=items, timestamp=datetime.now(UTC))


@router.get("/orders", response_model=ApiResponse[list[OrderItem]])
async def get_orders(
    account_id: str = Query("small_account_01", description="Account identifier"),
    symbol: str | None = Query(None, description="Optional symbol filter"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[OrderItem]]:
    """Returns order history with lifecycle statuses and fills."""
    orders = await OrderRepository.list_orders(
        session, portfolio_id=account_id, symbol=symbol, limit=limit
    )
    items = [
        OrderItem(
            id=o.id,
            portfolio_id=o.portfolio_id,
            symbol=o.symbol,
            client_order_id=o.client_order_id,
            order_type=o.order_type,
            side=o.side,
            quantity=o.quantity,
            price=o.price,
            stop_price=o.stop_price,
            status=o.status,
            filled_quantity=o.filled_quantity,
            average_fill_price=o.average_fill_price,
            fee=o.fee,
            slippage_paid=o.slippage_paid,
            rejection_reason=o.rejection_reason,
            created_at=o.created_at,
            updated_at=o.updated_at,
        )
        for o in orders
    ]
    return ApiResponse[list[OrderItem]](data=items, timestamp=datetime.now(UTC))


@router.get("/trades", response_model=ApiResponse[list[TradeItem]])
async def get_trades(
    account_id: str = Query("small_account_01", description="Account identifier"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[TradeItem]]:
    """Returns execution trade fills history."""
    query = (
        select(TradeModel)
        .where(TradeModel.portfolio_id == account_id)
        .order_by(desc(TradeModel.timestamp))
        .limit(limit)
    )
    res = await session.execute(query)
    trades = list(res.scalars().all())

    items = [
        TradeItem(
            id=t.id,
            order_id=t.order_id,
            position_id=t.position_id,
            portfolio_id=t.portfolio_id,
            symbol=t.symbol,
            side=t.side,
            price=t.price,
            quantity=t.quantity,
            notional=t.notional,
            fee=t.fee,
            fee_currency=t.fee_currency,
            slippage=t.slippage,
            timestamp=t.timestamp,
        )
        for t in trades
    ]
    return ApiResponse[list[TradeItem]](data=items, timestamp=datetime.now(UTC))
