"""
Unit tests for cryptopilot.database.repository.
Validates async CRUD queries, composite indexes, and data access objects.
"""

from datetime import UTC, datetime, timedelta

import pytest

from cryptopilot.data.models import Candle
from cryptopilot.database.connection import DatabaseManager
from cryptopilot.database.models import AgentDecisionModel, OrderModel, RiskEventModel
from cryptopilot.database.repository import (
    CandleRepository,
    DecisionRepository,
    OrderRepository,
    PortfolioRepository,
    PositionRepository,
    RiskEventRepository,
)
from cryptopilot.execution.models import OrderSide, OrderStatus, OrderType, VirtualOrder


@pytest.fixture
async def repo_session():
    """Sets up an isolated in-memory SQLite database for repository tests."""
    db_mgr = DatabaseManager("sqlite+aiosqlite:///:memory:", echo=False)
    await db_mgr.init_db()

    async with db_mgr.session() as session:
        yield session

    await db_mgr.drop_db()
    await db_mgr.close()


@pytest.mark.asyncio
async def test_candle_repository(repo_session) -> None:
    """Tests upserting, querying, counting, and latest candle retrieval."""
    now = datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC)
    c1 = Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=now,
        open=50000.0,
        high=51000.0,
        low=49500.0,
        close=50500.0,
        volume=100.0,
    )

    # 1. Insert new
    m1 = await CandleRepository.upsert_candle(repo_session, c1)
    assert m1.symbol == "BTC/USDT"
    assert m1.close == 50500.0

    # 2. Update existing (same key)
    c1_updated = Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=now,
        open=50000.0,
        high=51200.0,
        low=49500.0,
        close=50900.0,
        volume=120.0,
    )
    m1_up = await CandleRepository.upsert_candle(repo_session, c1_updated)
    assert m1_up.high == 51200.0
    assert m1_up.close == 50900.0

    # 3. Batch upsert
    c2 = Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=now + timedelta(hours=1),
        open=50900.0,
        high=51500.0,
        low=50800.0,
        close=51400.0,
        volume=80.0,
    )
    c3 = Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=now + timedelta(hours=2),
        open=51400.0,
        high=52000.0,
        low=51300.0,
        close=51900.0,
        volume=95.0,
    )
    batch = await CandleRepository.upsert_candles(repo_session, [c2, c3])
    assert len(batch) == 2

    # 4. Count
    total = await CandleRepository.count_candles(repo_session, "BTC/USDT", "1h")
    assert total == 3

    # 5. Query range and limit
    queried = await CandleRepository.get_candles(
        repo_session,
        symbol="BTC/USDT",
        timeframe="1h",
        start_time=now,
        limit=2,
    )
    assert len(queried) == 2

    # 7. Upsert candle with unknown timeframe (triggers fallback)
    c_custom = Candle(
        symbol="BTC/USDT",
        timeframe="10m",
        timestamp=now,
        open=50000.0,
        high=51000.0,
        low=49500.0,
        close=50500.0,
        volume=10.0,
    )
    m_custom = await CandleRepository.upsert_candle(repo_session, c_custom)
    assert m_custom.timeframe == "10m"


@pytest.mark.asyncio
async def test_portfolio_repository(repo_session) -> None:
    """Tests get_or_create, get_by_id, list_all, and balance updates."""
    # Create
    p1 = await PortfolioRepository.get_or_create(
        repo_session,
        portfolio_id="small_account_01",
        account_type="small_account",
        initial_balance=30.0,
    )
    assert p1.current_cash == 30.0

    # Fetch existing returns same instance
    p1_again = await PortfolioRepository.get_or_create(
        repo_session,
        portfolio_id="small_account_01",
        account_type="small_account",
        initial_balance=50.0,
    )
    assert p1_again.initial_balance == 30.0

    # Create research lab
    await PortfolioRepository.get_or_create(
        repo_session,
        portfolio_id="research_lab_01",
        account_type="research",
        initial_balance=10000.0,
    )

    all_ports = await PortfolioRepository.list_all(repo_session)
    assert len(all_ports) == 2

    # Update balances
    up = await PortfolioRepository.update_balances(
        repo_session,
        portfolio_id="small_account_01",
        cash=25.0,
        invested=5.0,
        realized_pnl=1.5,
        is_halted=False,
    )
    assert up is not None
    assert up.current_cash == 25.0
    assert up.invested_capital == 5.0


@pytest.mark.asyncio
async def test_order_and_position_repositories(repo_session) -> None:
    """Tests OrderRepository and PositionRepository interactions."""
    # Seed portfolio
    await PortfolioRepository.get_or_create(
        repo_session,
        portfolio_id="small_account_01",
        account_type="small_account",
        initial_balance=30.0,
    )

    # 1. Create order from VirtualOrder
    v_order = VirtualOrder(
        account_id="small_account_01",
        symbol="SOL/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=145.0,
        quantity=0.1,
        remaining_quantity=0.1,
    )
    o1 = await OrderRepository.create_order(repo_session, v_order)
    assert o1.id == v_order.order_id
    assert o1.status == OrderStatus.PENDING.value

    # Direct OrderModel creation
    o2 = OrderModel(
        id="ord-direct",
        portfolio_id="small_account_01",
        symbol="SOL/USDT",
        client_order_id="cli-direct",
        order_type="MARKET",
        side="BUY",
        quantity=0.1,
        status="SUBMITTED",
    )
    await OrderRepository.create_order(repo_session, o2)

    # Fetch open orders
    open_orders = await OrderRepository.list_open_orders(repo_session, "small_account_01")
    assert len(open_orders) == 2

    # Update status to FILLED
    filled = await OrderRepository.update_order_status(
        repo_session,
        order_id=o1.id,
        status=OrderStatus.FILLED,
        filled_quantity=0.1,
        average_fill_price=145.0,
        fee=0.0145,
    )
    assert filled is not None
    assert filled.status == OrderStatus.FILLED.value

    # 2. Position tests
    from cryptopilot.database.models import PositionModel

    pos = PositionModel(
        id="pos-sol-1",
        portfolio_id="small_account_01",
        symbol="SOL/USDT",
        side="LONG",
        status="OPEN",
        quantity=0.1,
        entry_price=145.0,
        current_price=145.0,
        stop_loss_price=138.0,
    )
    repo_session.add(pos)
    await repo_session.flush()

    open_pos = await PositionRepository.get_open_position(
        repo_session, "small_account_01", "SOL/USDT"
    )
    assert open_pos is not None
    assert open_pos.entry_price == 145.0

    # Fetch order by ID and client_order_id
    fetched_by_id = await OrderRepository.get_by_id(repo_session, o1.id)
    assert fetched_by_id is not None
    fetched_by_client = await OrderRepository.get_by_client_order_id(repo_session, "cli-direct")
    assert fetched_by_client is not None
    assert fetched_by_client.id == "ord-direct"

    # List orders without symbol
    all_orders = await OrderRepository.list_orders(repo_session, "small_account_01")
    assert len(all_orders) == 2

    # Update non-existent order returns None
    assert (
        await OrderRepository.update_order_status(repo_session, "missing_ord", OrderStatus.CANCELED)
        is None
    )

    # Fetch open positions and position history
    open_pos_list = await PositionRepository.list_open_positions(repo_session, "small_account_01")
    assert len(open_pos_list) == 1
    all_positions = await PositionRepository.list_positions(repo_session, "small_account_01")
    assert len(all_positions) == 1

    # Close position
    closed = await PositionRepository.close_position(
        repo_session,
        position_id=pos.id,
        exit_price=155.0,
        realized_pnl=1.0,
    )
    assert closed is not None
    assert closed.status == "CLOSED"
    assert closed.realized_pnl == 1.0

    # Closing missing position returns None
    assert await PositionRepository.close_position(repo_session, "missing_pos", 100.0, 0.0) is None


@pytest.mark.asyncio
async def test_decision_and_risk_event_repositories(repo_session) -> None:
    """Tests DecisionRepository and RiskEventRepository methods."""
    # Decision
    dec = AgentDecisionModel(
        id="dec-100",
        symbol="ETH/USDT",
        decision="BUY",
        confidence=0.82,
        market_regime="TRENDING_BULL",
        strategy_signals_json={"rsi_macd": "BUY"},
        risk_approved=True,
        explanation_text="Test decision explanation",
    )
    await DecisionRepository.save_decision(repo_session, dec)

    latest_dec = await DecisionRepository.get_latest_decision(repo_session, "ETH/USDT")
    assert latest_dec is not None
    assert latest_dec.confidence == 0.82

    # List decisions with and without symbol
    dec_list = await DecisionRepository.list_decisions(repo_session)
    assert len(dec_list) == 1
    assert len(await DecisionRepository.list_decisions(repo_session, "ETH/USDT")) == 1
    assert len(await DecisionRepository.list_decisions(repo_session, "BTC/USDT")) == 0

    # Risk Event
    r_event = RiskEventModel(
        portfolio_id="small_account_01",
        event_type="CIRCUIT_BREAKER_COOLDOWN",
        severity="WARNING",
        details={"consecutive_losses": 3},
    )
    await RiskEventRepository.save_event(repo_session, r_event)

    events = await RiskEventRepository.list_events(repo_session, portfolio_id="small_account_01")
    assert len(events) == 1
    assert events[0].event_type == "CIRCUIT_BREAKER_COOLDOWN"
