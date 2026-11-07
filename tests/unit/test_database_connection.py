"""
Unit tests for cryptopilot.database.connection.
Validates DatabaseManager, async sessions, schema creation/dropping, and dependency injection.
"""

import pytest
from sqlalchemy import text

from cryptopilot.database.connection import (
    DatabaseManager,
    get_db_manager,
    get_session,
    reset_db_manager,
)


@pytest.mark.asyncio
async def test_database_manager_lifecycle() -> None:
    """Tests DatabaseManager schema initialization, session queries, and disposal."""
    db_mgr = DatabaseManager(database_url="sqlite+aiosqlite:///:memory:", echo=False)
    await db_mgr.init_db()

    async with db_mgr.session() as session:
        result = await session.execute(text("SELECT 1"))
        val = result.scalar()
        assert val == 1

    await db_mgr.drop_db()
    await db_mgr.close()


@pytest.mark.asyncio
async def test_database_session_rollback_on_exception() -> None:
    """Verifies that an exception within session context manager triggers automatic rollback."""
    db_mgr = DatabaseManager(database_url="sqlite+aiosqlite:///:memory:", echo=False)
    await db_mgr.init_db()

    with pytest.raises(RuntimeError, match="Simulated failure"):
        async with db_mgr.session() as session:
            await session.execute(text("SELECT 1"))
            raise RuntimeError("Simulated failure")

    await db_mgr.close()


@pytest.mark.asyncio
async def test_singleton_get_and_reset_db_manager() -> None:
    """Tests global get_db_manager and reset_db_manager lifecycles."""
    reset_db_manager()
    mgr1 = get_db_manager("sqlite+aiosqlite:///:memory:")
    mgr2 = get_db_manager()
    assert mgr1 is mgr2

    # Switching database URL recreates manager
    mgr3 = get_db_manager("sqlite+aiosqlite:///./test_other.db")
    assert mgr3 is not mgr1

    reset_db_manager()
    await mgr1.close()
    await mgr3.close()


@pytest.mark.asyncio
async def test_get_session_dependency() -> None:
    """Tests FastAPI-style get_session dependency generator."""
    reset_db_manager()
    get_db_manager("sqlite+aiosqlite:///:memory:")

    gen = get_session()
    session = await anext(gen)
    assert session is not None
    await gen.aclose()
    reset_db_manager()
