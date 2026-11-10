"""
CryptoPilot AI - Database Connection & Session Management.
Provides AsyncEngine lifecycle, async_sessionmaker, automated table migrations,
and dependency injection generators using SQLAlchemy 2.0.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cryptopilot.config.settings import get_settings
from cryptopilot.database.models import Base


class DatabaseManager:
    """
    Manages SQLAlchemy 2.0 asynchronous engine and session factory lifecycles.
    """

    def __init__(self, database_url: str | None = None, echo: bool = False) -> None:
        if database_url is None:
            settings = get_settings()
            database_url = settings.database_url

        self.database_url = database_url
        self.echo = echo

        # Engine arguments
        engine_kwargs: dict[str, object] = {
            "echo": self.echo,
            "future": True,
        }

        # Handle SQLite vs PostgreSQL specific parameters
        if "sqlite" in self.database_url:
            if ":memory:" in self.database_url:
                from sqlalchemy.pool import StaticPool

                engine_kwargs["connect_args"] = {"check_same_thread": False}
                engine_kwargs["poolclass"] = StaticPool
        else:
            engine_kwargs["pool_pre_ping"] = True
            engine_kwargs["pool_size"] = 10
            engine_kwargs["max_overflow"] = 20

        self.engine: AsyncEngine = create_async_engine(self.database_url, **engine_kwargs)
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    async def init_db(self) -> None:
        """Initializes database schema by creating all registered tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_db(self) -> None:
        """Drops all database tables. Used primarily in test suites."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager providing an isolated AsyncSession with automatic cleanup."""
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self) -> None:
        """Disposes the underlying connection pool."""
        await self.engine.dispose()


_db_manager_instance: DatabaseManager | None = None


def get_db_manager(database_url: str | None = None, echo: bool = False) -> DatabaseManager:
    """Returns singleton DatabaseManager instance."""
    global _db_manager_instance
    if _db_manager_instance is None or (
        database_url is not None and _db_manager_instance.database_url != database_url
    ):
        _db_manager_instance = DatabaseManager(database_url=database_url, echo=echo)
    return _db_manager_instance


def reset_db_manager() -> None:
    """Resets the singleton DatabaseManager instance (for test isolation)."""
    global _db_manager_instance
    _db_manager_instance = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection generator for FastAPI and service endpoints."""
    manager = get_db_manager()
    async with manager.session() as session:
        yield session
