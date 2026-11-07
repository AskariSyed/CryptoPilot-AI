"""
CryptoPilot AI - Atomic Database Transactions.
Encapsulates ACID-compliant transaction boundaries for virtual order fills,
portfolio balance adjustments, deposit ledgering, and circuit breaker trip events.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cryptopilot.database.models import (
    AgentDecisionModel,
    DepositModel,
    OrderModel,
    PortfolioModel,
    PositionModel,
    RiskEventModel,
    TradeModel,
)
from cryptopilot.execution.models import OrderSide, OrderStatus, VirtualFill, VirtualOrder


@asynccontextmanager
async def atomic_transaction(session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """
    Guarantees atomic ACID transaction execution.
    Commits on successful block completion; automatically rolls back on exception.
    """
    if session.in_transaction():
        # Already inside a transaction block
        yield session
    else:
        async with session.begin():
            yield session


async def record_deposit_and_update_balance(
    session: AsyncSession,
    portfolio_id: str,
    amount: float,
    currency: str = "USDT",
    note: str | None = None,
    timestamp: datetime | None = None,
) -> tuple[DepositModel, PortfolioModel]:
    """
    Atomically records an external deposit and increments portfolio cash and deposits ledger.
    """
    if amount <= 0.0:
        raise ValueError(f"Deposit amount must be positive, got {amount}")

    ts = timestamp or datetime.now(UTC)

    async with atomic_transaction(session):
        res = await session.execute(
            select(PortfolioModel).where(PortfolioModel.id == portfolio_id).with_for_update()
        )
        portfolio = res.scalar_one_or_none()
        if portfolio is None:
            raise KeyError(f"Portfolio '{portfolio_id}' not found.")

        deposit = DepositModel(
            portfolio_id=portfolio_id,
            amount=amount,
            currency=currency,
            note=note,
            timestamp=ts,
        )
        session.add(deposit)

        # Update portfolio cash and contribution ledger
        portfolio.current_cash += amount
        portfolio.total_deposits += amount
        portfolio.updated_at = ts

        await session.flush()
        return deposit, portfolio


async def record_fill_and_update_portfolio(
    session: AsyncSession,
    fill: VirtualFill,
    order: VirtualOrder | None = None,
    stop_loss_price: float | None = None,
    take_profit_price: float | None = None,
) -> tuple[TradeModel, PortfolioModel, PositionModel | None]:
    """
    Atomically records an executed order fill:
    1. Updates/persists OrderModel.
    2. Creates TradeModel execution record.
    3. Opens or closes PositionModel.
    4. Updates PortfolioModel cash, invested capital, realized PnL, and fees.
    """
    ts = fill.timestamp or datetime.now(UTC)

    async with atomic_transaction(session):
        # 1. Fetch and lock Portfolio
        res_p = await session.execute(
            select(PortfolioModel).where(PortfolioModel.id == fill.account_id).with_for_update()
        )
        portfolio = res_p.scalar_one_or_none()
        if portfolio is None:
            raise KeyError(f"Portfolio '{fill.account_id}' not found.")

        # 2. Fetch or update Order
        res_o = await session.execute(
            select(OrderModel).where(OrderModel.id == fill.order_id).with_for_update()
        )
        db_order = res_o.scalar_one_or_none()
        if db_order is None and order is not None:
            db_order = OrderModel(
                id=order.order_id,
                portfolio_id=order.account_id,
                symbol=order.symbol,
                client_order_id=order.order_id,
                order_type=order.order_type.value,
                side=order.side.value,
                quantity=order.quantity,
                price=order.price,
                stop_price=order.stop_price,
                status=order.status.value,
                filled_quantity=order.filled_quantity,
                average_fill_price=order.average_fill_price,
                fee=order.fee_paid,
                slippage_paid=order.slippage_paid,
                created_at=order.created_at,
                updated_at=ts,
            )
            session.add(db_order)
            await session.flush()
        elif db_order is not None:
            db_order.status = OrderStatus.FILLED.value
            db_order.filled_quantity = fill.quantity
            db_order.average_fill_price = fill.price
            db_order.fee += fill.fee
            db_order.slippage_paid += fill.slippage_cost
            db_order.updated_at = ts

        # 3. Position and Balance Accounting
        position: PositionModel | None = None

        if fill.side == OrderSide.BUY:
            # Check for existing open position
            res_pos = await session.execute(
                select(PositionModel)
                .where(
                    PositionModel.portfolio_id == fill.account_id,
                    PositionModel.symbol == fill.symbol,
                    PositionModel.status == "OPEN",
                )
                .with_for_update()
            )
            position = res_pos.scalar_one_or_none()

            sl = stop_loss_price or (fill.price * 0.95)
            tp = take_profit_price or (fill.price * 1.10)

            if position is None:
                position = PositionModel(
                    portfolio_id=fill.account_id,
                    symbol=fill.symbol,
                    side="LONG",
                    status="OPEN",
                    quantity=fill.quantity,
                    entry_price=fill.price,
                    current_price=fill.price,
                    stop_loss_price=sl,
                    take_profit_price=tp,
                    opened_at=ts,
                )
                session.add(position)
                await session.flush()
            else:
                # Add to existing position
                total_qty = position.quantity + fill.quantity
                avg_entry = (
                    (position.entry_price * position.quantity) + (fill.price * fill.quantity)
                ) / total_qty
                position.quantity = total_qty
                position.entry_price = round(avg_entry, 8)
                position.current_price = fill.price

            # Deduct notional and fee from portfolio cash
            total_outlay = fill.notional + fill.fee
            portfolio.current_cash -= total_outlay
            portfolio.invested_capital += fill.notional
            portfolio.total_fees_paid += fill.fee
            portfolio.updated_at = ts

        else:  # SELL
            res_pos = await session.execute(
                select(PositionModel)
                .where(
                    PositionModel.portfolio_id == fill.account_id,
                    PositionModel.symbol == fill.symbol,
                    PositionModel.status == "OPEN",
                )
                .with_for_update()
            )
            position = res_pos.scalar_one_or_none()

            gross_proceeds = fill.notional
            net_proceeds = gross_proceeds - fill.fee

            if position is not None:
                cost_basis = position.entry_price * fill.quantity
                trade_pnl = (fill.price - position.entry_price) * fill.quantity - fill.fee

                # Close or reduce position
                if position.quantity <= fill.quantity:
                    position.status = "CLOSED"
                    position.exit_price = fill.price
                    position.realized_pnl = round(trade_pnl, 8)
                    position.closed_at = ts
                    portfolio.invested_capital = max(0.0, portfolio.invested_capital - cost_basis)
                else:
                    position.quantity -= fill.quantity
                    portfolio.invested_capital = max(0.0, portfolio.invested_capital - cost_basis)

                portfolio.realized_pnl += trade_pnl
            else:
                trade_pnl = 0.0

            portfolio.current_cash += net_proceeds
            portfolio.total_fees_paid += fill.fee
            portfolio.updated_at = ts

        # 4. Insert Trade Record
        trade = TradeModel(
            order_id=fill.order_id,
            position_id=position.id if position else None,
            portfolio_id=fill.account_id,
            symbol=fill.symbol,
            side=fill.side.value,
            timestamp=ts,
            price=fill.price,
            quantity=fill.quantity,
            notional=fill.notional,
            fee=fill.fee,
            fee_currency="USDT",
            slippage=fill.slippage_cost,
        )
        session.add(trade)
        await session.flush()

        return trade, portfolio, position


async def record_risk_event(
    session: AsyncSession,
    portfolio_id: str,
    event_type: str,
    severity: str = "INFO",
    details: dict[str, Any] | None = None,
    timestamp: datetime | None = None,
) -> RiskEventModel:
    """
    Atomically logs a risk telemetry event and toggles trading halt if critical.
    """
    ts = timestamp or datetime.now(UTC)

    async with atomic_transaction(session):
        res = await session.execute(
            select(PortfolioModel).where(PortfolioModel.id == portfolio_id).with_for_update()
        )
        portfolio = res.scalar_one_or_none()

        event = RiskEventModel(
            portfolio_id=portfolio_id,
            event_type=event_type,
            severity=severity,
            details=details or {},
            timestamp=ts,
        )
        session.add(event)

        if portfolio is not None and event_type in ("EMERGENCY_HALT", "DAILY_LOSS_LIMIT"):
            portfolio.is_trading_halted = True
            portfolio.updated_at = ts

        await session.flush()
        return event


async def record_agent_decision(
    session: AsyncSession,
    symbol: str,
    decision: str,
    confidence: float,
    market_regime: str,
    explanation_text: str,
    strategy_signals: dict[str, Any] | None = None,
    ml_prediction: dict[str, Any] | None = None,
    sentiment_summary: dict[str, Any] | None = None,
    risk_approved: bool = True,
    rejection_reason: str | None = None,
    timestamp: datetime | None = None,
) -> AgentDecisionModel:
    """
    Atomically logs an autonomous decision arbiter decision event.
    """
    ts = timestamp or datetime.now(UTC)

    async with atomic_transaction(session):
        entry = AgentDecisionModel(
            symbol=symbol,
            timestamp=ts,
            decision=decision,
            confidence=confidence,
            market_regime=market_regime,
            strategy_signals_json=strategy_signals or {},
            ml_prediction_json=ml_prediction,
            sentiment_summary_json=sentiment_summary,
            risk_approved=risk_approved,
            rejection_reason=rejection_reason,
            explanation_text=explanation_text,
        )
        session.add(entry)
        await session.flush()
        return entry
