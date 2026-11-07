"""
Unit tests for cryptopilot.database.transactions.
Validates ACID atomic transactions, balance updates, order fills, position accounting,
and risk event logging on an isolated in-memory SQLite database.
"""

import pytest
from sqlalchemy import select

from cryptopilot.database.connection import DatabaseManager
from cryptopilot.database.models import (
    DepositModel,
    OrderModel,
    PortfolioModel,
)
from cryptopilot.database.transactions import (
    atomic_transaction,
    record_agent_decision,
    record_deposit_and_update_balance,
    record_fill_and_update_portfolio,
    record_risk_event,
)
from cryptopilot.execution.models import (
    OrderSide,
    OrderStatus,
    OrderType,
    VirtualFill,
    VirtualOrder,
)


@pytest.fixture
async def db_session():
    """Sets up an in-memory database, creates all tables, and yields an active session."""
    db_mgr = DatabaseManager("sqlite+aiosqlite:///:memory:", echo=False)
    await db_mgr.init_db()

    async with db_mgr.session() as session:
        # Create small_account_01
        portfolio = PortfolioModel(
            id="small_account_01",
            account_type="small_account",
            currency="USDT",
            initial_balance=30.0,
            current_cash=30.0,
            invested_capital=0.0,
            realized_pnl=0.0,
            total_deposits=0.0,
            total_fees_paid=0.0,
            is_trading_halted=False,
        )
        session.add(portfolio)
        await session.commit()

    async with db_mgr.session() as session:
        yield session

    await db_mgr.drop_db()
    await db_mgr.close()


@pytest.mark.asyncio
async def test_atomic_transaction_commit_and_rollback(db_session) -> None:
    """Verifies atomic_transaction commits on normal exit and rolls back on exception."""
    # 1. Success commit
    async with atomic_transaction(db_session):
        dep = DepositModel(portfolio_id="small_account_01", amount=15.0, currency="USDT")
        db_session.add(dep)

    res = await db_session.execute(select(DepositModel).where(DepositModel.amount == 15.0))
    assert res.scalar_one_or_none() is not None

    # 2. Rollback on exception
    with pytest.raises(ValueError, match="Forced abort"):
        async with atomic_transaction(db_session):
            dep2 = DepositModel(portfolio_id="small_account_01", amount=999.0, currency="USDT")
            db_session.add(dep2)
            raise ValueError("Forced abort")

    res2 = await db_session.execute(select(DepositModel).where(DepositModel.amount == 999.0))
    assert res2.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_record_deposit_and_update_balance(db_session) -> None:
    """Tests depositing funds into portfolio."""
    deposit, port = await record_deposit_and_update_balance(
        session=db_session,
        portfolio_id="small_account_01",
        amount=10.0,
        currency="USDT",
        note="Monthly savings",
    )
    assert deposit.amount == 10.0
    assert port.current_cash == 40.0
    assert port.total_deposits == 10.0

    # Negative deposit should raise ValueError
    with pytest.raises(ValueError, match="must be positive"):
        await record_deposit_and_update_balance(
            session=db_session,
            portfolio_id="small_account_01",
            amount=-5.0,
        )

    # Missing portfolio raises KeyError
    with pytest.raises(KeyError, match="Portfolio 'unknown' not found"):
        await record_deposit_and_update_balance(
            session=db_session,
            portfolio_id="unknown",
            amount=10.0,
        )


@pytest.mark.asyncio
async def test_record_fill_buy_and_sell(db_session) -> None:
    """Tests atomic BUY fill opening position followed by SELL fill closing position."""
    # 1. MARKET BUY 0.0002 BTC @ 50,000 ($10 notional + $0.01 fee)
    order = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.0002,
        remaining_quantity=0.0002,
    )
    fill_buy = VirtualFill(
        order_id=order.order_id,
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        price=50000.0,
        quantity=0.0002,
        notional=10.0,
        fee=0.01,
        fee_rate=0.001,
        slippage_rate=0.0002,
        slippage_cost=0.002,
    )

    trade, port, pos = await record_fill_and_update_portfolio(
        session=db_session,
        fill=fill_buy,
        order=order,
        stop_loss_price=49000.0,
        take_profit_price=53000.0,
    )

    assert trade is not None
    assert pos is not None
    assert pos.status == "OPEN"
    assert pos.quantity == 0.0002
    assert pos.entry_price == 50000.0
    assert port.current_cash == pytest.approx(30.0 - 10.01, abs=1e-4)
    assert port.invested_capital == 10.0
    assert port.total_fees_paid == 0.01

    # Add to position (second BUY fill)
    fill_buy_2 = VirtualFill(
        order_id=order.order_id,
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        price=51000.0,
        quantity=0.0002,
        notional=10.20,
        fee=0.0102,
        fee_rate=0.001,
        slippage_rate=0.0002,
        slippage_cost=0.002,
    )
    _, _, pos2 = await record_fill_and_update_portfolio(
        session=db_session,
        fill=fill_buy_2,
        order=order,
    )
    assert pos2 is not None
    assert pos2.quantity == 0.0004
    assert pos2.entry_price == 50500.0

    # 2. MARKET SELL 0.0004 BTC @ 53,000 ($21.20 gross - $0.0212 fee)
    sell_order = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.0004,
        remaining_quantity=0.0004,
    )
    fill_sell = VirtualFill(
        order_id=sell_order.order_id,
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        price=53000.0,
        quantity=0.0004,
        notional=21.20,
        fee=0.0212,
        fee_rate=0.001,
        slippage_rate=0.0002,
        slippage_cost=0.004,
    )

    trade_sell, port_sell, pos_sell = await record_fill_and_update_portfolio(
        session=db_session,
        fill=fill_sell,
        order=sell_order,
    )

    assert pos_sell is not None
    assert pos_sell.status == "CLOSED"
    assert pos_sell.exit_price == 53000.0
    assert pos_sell.realized_pnl > 0.0
    assert port_sell.invested_capital == 0.0
    assert port_sell.current_cash > 30.0  # Profitable round-trip!

    # 3. Fill against an order already stored in DB
    pre_order = OrderModel(
        id="ord-pre-existing",
        portfolio_id="small_account_01",
        symbol="BTC/USDT",
        client_order_id="cli-pre-existing",
        order_type="MARKET",
        side="BUY",
        quantity=0.0001,
        status="SUBMITTED",
    )
    db_session.add(pre_order)
    await db_session.flush()

    fill_pre = VirtualFill(
        order_id="ord-pre-existing",
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        price=50000.0,
        quantity=0.0001,
        notional=5.0,
        fee=0.005,
        fee_rate=0.001,
        slippage_rate=0.0,
        slippage_cost=0.0,
    )
    _, _, _ = await record_fill_and_update_portfolio(
        session=db_session,
        fill=fill_pre,
    )
    assert pre_order.status == OrderStatus.FILLED.value
    assert pre_order.filled_quantity == 0.0001


@pytest.mark.asyncio
async def test_record_risk_event_and_emergency_halt(db_session) -> None:
    """Tests recording risk event and triggering emergency trading halt."""
    event = await record_risk_event(
        session=db_session,
        portfolio_id="small_account_01",
        event_type="EMERGENCY_HALT",
        severity="CRITICAL",
        details={"reason": "Manual operator kill-switch activated"},
    )
    assert event.event_type == "EMERGENCY_HALT"

    # Verify portfolio was halted
    res = await db_session.execute(
        select(PortfolioModel).where(PortfolioModel.id == "small_account_01")
    )
    port = res.scalar_one()
    assert port.is_trading_halted is True

    # Record event on non-existent portfolio still records audit event
    evt_none = await record_risk_event(
        session=db_session,
        portfolio_id="non_existent",
        event_type="CIRCUIT_BREAKER_RESET",
        severity="INFO",
    )
    assert evt_none.portfolio_id == "non_existent"


@pytest.mark.asyncio
async def test_record_agent_decision(db_session) -> None:
    """Tests recording an agent decision."""
    decision = await record_agent_decision(
        session=db_session,
        symbol="ETH/USDT",
        decision="HOLD",
        confidence=0.50,
        market_regime="RANGING",
        explanation_text="Conflicting signals in ranging market; safety guard default-to-HOLD.",
        risk_approved=False,
        rejection_reason="LOW_CONVICTION",
    )
    assert decision.symbol == "ETH/USDT"
    assert decision.decision == "HOLD"
    assert decision.risk_approved is False
    assert decision.rejection_reason == "LOW_CONVICTION"
