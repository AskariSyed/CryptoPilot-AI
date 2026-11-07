"""
Unit tests for Alembic database migrations.
Validates upgrading schema to head and downgrading back to base on a temporary SQLite database.
"""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from cryptopilot.config.settings import get_settings


def test_alembic_migration_upgrade_and_downgrade(tmp_path: Path) -> None:
    """Verifies complete upgrade to head and downgrade to base cycle."""
    db_file = tmp_path / "migration_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

    # Temporarily override settings database_url
    settings = get_settings()
    original_url = settings.database_url
    settings.database_url = db_url

    try:
        # Load alembic config
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        # 1. Run upgrade to head
        command.upgrade(alembic_cfg, "head")

        # Verify tables created using synchronous sqlite inspection
        sync_url = f"sqlite:///{db_file.as_posix()}"
        sync_engine = create_engine(sync_url)
        inspector = inspect(sync_engine)
        tables = set(inspector.get_table_names())

        expected_tables = {
            "exchanges",
            "trading_pairs",
            "market_candles",
            "market_snapshots",
            "portfolios",
            "deposits",
            "positions",
            "orders",
            "trades",
            "risk_events",
            "agent_decisions",
            "alembic_version",
        }
        assert expected_tables.issubset(tables)

        # 2. Run downgrade back to base
        command.downgrade(alembic_cfg, "base")

        # Verify tables dropped
        inspector_after = inspect(sync_engine)
        tables_after = set(inspector_after.get_table_names())
        assert "portfolios" not in tables_after
        assert "market_candles" not in tables_after
        sync_engine.dispose()

    finally:
        settings.database_url = original_url
