"""
CryptoPilot AI - Database Query Repositories.
Provides typed, high-performance data access objects with composite index optimization
for market candles, portfolios, positions, orders, trades, decisions, and risk telemetry.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cryptopilot.data.models import Candle, Timeframe
from cryptopilot.database.models import (
    AgentDecisionModel,
    MarketCandleModel,
    OrderModel,
    PortfolioModel,
    PositionModel,
    RiskEventModel,
)
from cryptopilot.execution.models import OrderStatus, VirtualOrder


class CandleRepository:
    """Repository managing OHLCV market candle persistence and queries."""

    @staticmethod
    async def upsert_candle(session: AsyncSession, candle: Candle) -> MarketCandleModel:
        """Inserts or updates a single OHLCV candle."""
        query = select(MarketCandleModel).where(
            MarketCandleModel.symbol == candle.symbol,
            MarketCandleModel.timeframe == candle.timeframe,
            MarketCandleModel.open_time == candle.timestamp,
        )
        res = await session.execute(query)
        existing = res.scalar_one_or_none()

        if existing is not None:
            existing.open = candle.open
            existing.high = candle.high
            existing.low = candle.low
            existing.close = candle.close
            existing.volume = candle.volume
            existing.is_closed = candle.is_closed
            model = existing
        else:
            try:
                tf = Timeframe(candle.timeframe)
                close_time = candle.timestamp + timedelta(seconds=tf.duration_seconds)
            except (ValueError, KeyError):
                close_time = candle.timestamp

            model = MarketCandleModel(
                symbol=candle.symbol,
                timeframe=candle.timeframe,
                open_time=candle.timestamp,
                close_time=close_time,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                is_closed=candle.is_closed,
            )
            session.add(model)

        await session.flush()
        return model

    @staticmethod
    async def upsert_candles(
        session: AsyncSession, candles: list[Candle]
    ) -> list[MarketCandleModel]:
        """Batch upserts multiple candles."""
        models: list[MarketCandleModel] = []
        for c in candles:
            m = await CandleRepository.upsert_candle(session, c)
            models.append(m)
        return models

    @staticmethod
    async def get_candles(
        session: AsyncSession,
        symbol: str,
        timeframe: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> list[MarketCandleModel]:
        """Queries candles within an optional timestamp range ordered chronologically."""
        query = select(MarketCandleModel).where(
            MarketCandleModel.symbol == symbol,
            MarketCandleModel.timeframe == timeframe,
        )
        if start_time is not None:
            query = query.where(MarketCandleModel.open_time >= start_time)
        if end_time is not None:
            query = query.where(MarketCandleModel.open_time <= end_time)

        query = query.order_by(MarketCandleModel.open_time.asc()).limit(limit)
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def get_latest_candle(
        session: AsyncSession,
        symbol: str,
        timeframe: str,
    ) -> MarketCandleModel | None:
        """Returns the most recent candle for the requested symbol and timeframe."""
        query = (
            select(MarketCandleModel)
            .where(
                MarketCandleModel.symbol == symbol,
                MarketCandleModel.timeframe == timeframe,
            )
            .order_by(desc(MarketCandleModel.open_time))
            .limit(1)
        )
        res = await session.execute(query)
        return res.scalar_one_or_none()

    @staticmethod
    async def count_candles(
        session: AsyncSession,
        symbol: str,
        timeframe: str,
    ) -> int:
        """Returns total candle count for the specified pair and timeframe."""
        query = select(func.count(MarketCandleModel.id)).where(
            MarketCandleModel.symbol == symbol,
            MarketCandleModel.timeframe == timeframe,
        )
        res = await session.execute(query)
        return int(res.scalar_one() or 0)


class PortfolioRepository:
    """Repository managing portfolio ledger accounts."""

    @staticmethod
    async def get_or_create(
        session: AsyncSession,
        portfolio_id: str,
        account_type: str,
        initial_balance: float,
        currency: str = "USDT",
    ) -> PortfolioModel:
        """Fetches existing portfolio or initializes a new one."""
        query = select(PortfolioModel).where(PortfolioModel.id == portfolio_id)
        res = await session.execute(query)
        existing = res.scalar_one_or_none()

        if existing is not None:
            return existing

        portfolio = PortfolioModel(
            id=portfolio_id,
            account_type=account_type,
            currency=currency,
            initial_balance=initial_balance,
            current_cash=initial_balance,
            invested_capital=0.0,
            realized_pnl=0.0,
            total_deposits=0.0,
            total_fees_paid=0.0,
            is_trading_halted=False,
            updated_at=datetime.now(UTC),
        )
        session.add(portfolio)
        await session.flush()
        return portfolio

    @staticmethod
    async def get_by_id(session: AsyncSession, portfolio_id: str) -> PortfolioModel | None:
        """Fetches portfolio by ID."""
        query = select(PortfolioModel).where(PortfolioModel.id == portfolio_id)
        res = await session.execute(query)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_all(session: AsyncSession) -> list[PortfolioModel]:
        """Lists all registered portfolio accounts."""
        query = select(PortfolioModel).order_by(PortfolioModel.id.asc())
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def update_balances(
        session: AsyncSession,
        portfolio_id: str,
        cash: float,
        invested: float,
        realized_pnl: float,
        is_halted: bool = False,
    ) -> PortfolioModel | None:
        """Updates portfolio cash, invested capital, and halt state."""
        portfolio = await PortfolioRepository.get_by_id(session, portfolio_id)
        if portfolio is not None:
            portfolio.current_cash = cash
            portfolio.invested_capital = invested
            portfolio.realized_pnl = realized_pnl
            portfolio.is_trading_halted = is_halted
            portfolio.updated_at = datetime.now(UTC)
            await session.flush()
        return portfolio


class OrderRepository:
    """Repository managing virtual orders."""

    @staticmethod
    async def create_order(
        session: AsyncSession,
        order: VirtualOrder | OrderModel,
    ) -> OrderModel:
        """Persists a new virtual order."""
        if isinstance(order, OrderModel):
            session.add(order)
            await session.flush()
            return order

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
            rejection_reason=order.rejection_reason,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )
        session.add(db_order)
        await session.flush()
        return db_order

    @staticmethod
    async def get_by_id(session: AsyncSession, order_id: str) -> OrderModel | None:
        """Queries order by ID."""
        query = select(OrderModel).where(OrderModel.id == order_id)
        res = await session.execute(query)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_by_client_order_id(
        session: AsyncSession, client_order_id: str
    ) -> OrderModel | None:
        """Queries order by client order ID."""
        query = select(OrderModel).where(OrderModel.client_order_id == client_order_id)
        res = await session.execute(query)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_open_orders(
        session: AsyncSession,
        portfolio_id: str,
        symbol: str | None = None,
    ) -> list[OrderModel]:
        """Lists active pending/submitted orders."""
        query = select(OrderModel).where(
            OrderModel.portfolio_id == portfolio_id,
            OrderModel.status.in_([OrderStatus.PENDING.value, OrderStatus.SUBMITTED.value]),
        )
        if symbol is not None:
            query = query.where(OrderModel.symbol == symbol)
        query = query.order_by(OrderModel.created_at.desc())
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def list_orders(
        session: AsyncSession,
        portfolio_id: str,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[OrderModel]:
        """Queries order history for an account."""
        query = select(OrderModel).where(OrderModel.portfolio_id == portfolio_id)
        if symbol is not None:
            query = query.where(OrderModel.symbol == symbol)
        query = query.order_by(OrderModel.created_at.desc()).limit(limit)
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def update_order_status(
        session: AsyncSession,
        order_id: str,
        status: OrderStatus,
        filled_quantity: float | None = None,
        average_fill_price: float | None = None,
        fee: float | None = None,
    ) -> OrderModel | None:
        """Updates lifecycle status and execution fills for an order."""
        order = await OrderRepository.get_by_id(session, order_id)
        if order is not None:
            order.status = status.value
            if filled_quantity is not None:
                order.filled_quantity = filled_quantity
            if average_fill_price is not None:
                order.average_fill_price = average_fill_price
            if fee is not None:
                order.fee = fee
            order.updated_at = datetime.now(UTC)
            await session.flush()
        return order


class PositionRepository:
    """Repository managing open and closed trading positions."""

    @staticmethod
    async def get_open_position(
        session: AsyncSession,
        portfolio_id: str,
        symbol: str,
    ) -> PositionModel | None:
        """Returns active OPEN position for portfolio and symbol, if any."""
        query = select(PositionModel).where(
            PositionModel.portfolio_id == portfolio_id,
            PositionModel.symbol == symbol,
            PositionModel.status == "OPEN",
        )
        res = await session.execute(query)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_open_positions(
        session: AsyncSession,
        portfolio_id: str,
    ) -> list[PositionModel]:
        """Lists all open positions held by a portfolio."""
        query = (
            select(PositionModel)
            .where(
                PositionModel.portfolio_id == portfolio_id,
                PositionModel.status == "OPEN",
            )
            .order_by(PositionModel.opened_at.desc())
        )
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def list_positions(
        session: AsyncSession,
        portfolio_id: str,
        limit: int = 50,
    ) -> list[PositionModel]:
        """Queries position history (both open and closed)."""
        query = (
            select(PositionModel)
            .where(PositionModel.portfolio_id == portfolio_id)
            .order_by(PositionModel.opened_at.desc())
            .limit(limit)
        )
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def close_position(
        session: AsyncSession,
        position_id: str,
        exit_price: float,
        realized_pnl: float,
        closed_at: datetime | None = None,
    ) -> PositionModel | None:
        """Marks position as CLOSED and updates realized PnL."""
        query = select(PositionModel).where(PositionModel.id == position_id)
        res = await session.execute(query)
        position = res.scalar_one_or_none()
        if position is not None:
            position.status = "CLOSED"
            position.exit_price = exit_price
            position.realized_pnl = realized_pnl
            position.closed_at = closed_at or datetime.now(UTC)
            await session.flush()
        return position


class DecisionRepository:
    """Repository managing Autonomous Decision Arbiter audit trails."""

    @staticmethod
    async def save_decision(
        session: AsyncSession,
        decision: AgentDecisionModel,
    ) -> AgentDecisionModel:
        """Persists an agent decision audit entry."""
        session.add(decision)
        await session.flush()
        return decision

    @staticmethod
    async def get_latest_decision(
        session: AsyncSession,
        symbol: str,
    ) -> AgentDecisionModel | None:
        """Returns the most recent decision record for the specified symbol."""
        query = (
            select(AgentDecisionModel)
            .where(AgentDecisionModel.symbol == symbol)
            .order_by(desc(AgentDecisionModel.timestamp))
            .limit(1)
        )
        res = await session.execute(query)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_decisions(
        session: AsyncSession,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[AgentDecisionModel]:
        """Queries decision audit history."""
        query = select(AgentDecisionModel)
        if symbol is not None:
            query = query.where(AgentDecisionModel.symbol == symbol)
        query = query.order_by(desc(AgentDecisionModel.timestamp)).limit(limit)
        res = await session.execute(query)
        return list(res.scalars().all())


class RiskEventRepository:
    """Repository managing circuit breaker and risk audit events."""

    @staticmethod
    async def save_event(
        session: AsyncSession,
        event: RiskEventModel,
    ) -> RiskEventModel:
        """Persists a risk telemetry record."""
        session.add(event)
        await session.flush()
        return event

    @staticmethod
    async def list_events(
        session: AsyncSession,
        portfolio_id: str | None = None,
        limit: int = 100,
    ) -> list[RiskEventModel]:
        """Queries recent risk events."""
        query = select(RiskEventModel)
        if portfolio_id is not None:
            query = query.where(RiskEventModel.portfolio_id == portfolio_id)
        query = query.order_by(desc(RiskEventModel.timestamp)).limit(limit)
        res = await session.execute(query)
        return list(res.scalars().all())
