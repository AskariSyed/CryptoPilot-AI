"""initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-11-07 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. exchanges
    op.create_table(
        "exchanges",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("rate_limit_ms", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. trading_pairs
    op.create_table(
        "trading_pairs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("exchange_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("base_asset", sa.String(length=10), nullable=False),
        sa.Column("quote_asset", sa.String(length=10), nullable=False),
        sa.Column("price_precision", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("quantity_precision", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("min_quantity", sa.Float(), nullable=False, server_default="0.0001"),
        sa.Column("min_notional", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["exchange_id"], ["exchanges.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_id", "symbol", name="uq_exchange_trading_pair"),
    )
    op.create_index("ix_trading_pairs_symbol", "trading_pairs", ["symbol"])

    # 3. market_candles
    op.create_table(
        "market_candles",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("pair_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["pair_id"], ["trading_pairs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "timeframe", "open_time", name="uq_candle_symbol_tf_open"),
    )
    op.create_index("ix_candle_open_time_desc", "market_candles", [sa.text("open_time DESC")])
    op.create_index(
        "ix_candle_sym_tf_open_desc",
        "market_candles",
        ["symbol", "timeframe", sa.text("open_time DESC")],
    )
    op.create_index("ix_market_candles_symbol", "market_candles", ["symbol"])
    op.create_index("ix_market_candles_timeframe", "market_candles", ["timeframe"])

    # 4. market_snapshots
    op.create_table(
        "market_snapshots",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bid_price", sa.Float(), nullable=False),
        sa.Column("ask_price", sa.Float(), nullable=False),
        sa.Column("spread", sa.Float(), nullable=False),
        sa.Column("mid_price", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_snapshot_sym_ts_desc", "market_snapshots", ["symbol", sa.text("timestamp DESC")]
    )
    op.create_index("ix_market_snapshots_symbol", "market_snapshots", ["symbol"])
    op.create_index("ix_market_snapshots_timestamp", "market_snapshots", ["timestamp"])

    # 5. portfolios
    op.create_table(
        "portfolios",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("account_type", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USDT"),
        sa.Column("initial_balance", sa.Float(), nullable=False),
        sa.Column("current_cash", sa.Float(), nullable=False),
        sa.Column("invested_capital", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_deposits", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_fees_paid", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_trading_halted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. deposits
    op.create_table(
        "deposits",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("portfolio_id", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USDT"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deposits_portfolio_id", "deposits", ["portfolio_id"])
    op.create_index("ix_deposits_timestamp", "deposits", ["timestamp"])

    # 7. positions
    op.create_table(
        "positions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("portfolio_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False, server_default="LONG"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="OPEN"),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("stop_loss_price", sa.Float(), nullable=False),
        sa.Column("take_profit_price", sa.Float(), nullable=True),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_port_status", "positions", ["portfolio_id", "status"])
    op.create_index("ix_pos_sym_status", "positions", ["symbol", "status"])
    op.create_index("ix_positions_portfolio_id", "positions", ["portfolio_id"])
    op.create_index("ix_positions_symbol", "positions", ["symbol"])
    op.create_index("ix_positions_status", "positions", ["status"])

    # 8. orders
    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("portfolio_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("client_order_id", sa.String(length=64), nullable=False),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("stop_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("filled_quantity", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("average_fill_price", sa.Float(), nullable=True),
        sa.Column("fee", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("slippage_paid", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("rejection_reason", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_order_id"),
    )
    op.create_index("ix_orders_port_status", "orders", ["portfolio_id", "status"])
    op.create_index("ix_orders_sym_created", "orders", ["symbol", sa.text("created_at DESC")])
    op.create_index("ix_orders_portfolio_id", "orders", ["portfolio_id"])
    op.create_index("ix_orders_symbol", "orders", ["symbol"])
    op.create_index("ix_orders_status", "orders", ["status"])

    # 9. trades
    op.create_table(
        "trades",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("position_id", sa.String(length=64), nullable=True),
        sa.Column("portfolio_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("notional", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("fee_currency", sa.String(length=10), nullable=False, server_default="USDT"),
        sa.Column("slippage", sa.Float(), nullable=False, server_default="0.0"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trades_port_ts_desc", "trades", ["portfolio_id", sa.text("timestamp DESC")])
    op.create_index("ix_trades_sym_ts_desc", "trades", ["symbol", sa.text("timestamp DESC")])
    op.create_index("ix_trades_order_id", "trades", ["order_id"])
    op.create_index("ix_trades_position_id", "trades", ["position_id"])
    op.create_index("ix_trades_portfolio_id", "trades", ["portfolio_id"])
    op.create_index("ix_trades_symbol", "trades", ["symbol"])
    op.create_index("ix_trades_timestamp", "trades", ["timestamp"])

    # 10. risk_events
    json_type = sa.JSON().with_variant(SQLiteJSON, "sqlite")
    op.create_table(
        "risk_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("portfolio_id", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="INFO"),
        sa.Column("details", json_type, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_risk_events_port_ts_desc", "risk_events", ["portfolio_id", sa.text("timestamp DESC")]
    )
    op.create_index("ix_risk_events_portfolio_id", "risk_events", ["portfolio_id"])
    op.create_index("ix_risk_events_timestamp", "risk_events", ["timestamp"])

    # 11. agent_decisions
    op.create_table(
        "agent_decisions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decision", sa.String(length=10), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("market_regime", sa.String(length=32), nullable=False),
        sa.Column("strategy_signals_json", json_type, nullable=False),
        sa.Column("ml_prediction_json", json_type, nullable=True),
        sa.Column("sentiment_summary_json", json_type, nullable=True),
        sa.Column("risk_approved", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("rejection_reason", sa.String(length=256), nullable=True),
        sa.Column("explanation_text", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_decisions_sym_ts_desc", "agent_decisions", ["symbol", sa.text("timestamp DESC")]
    )
    op.create_index("ix_agent_decisions_symbol", "agent_decisions", ["symbol"])
    op.create_index("ix_agent_decisions_timestamp", "agent_decisions", ["timestamp"])


def downgrade() -> None:
    op.drop_table("agent_decisions")
    op.drop_table("risk_events")
    op.drop_table("trades")
    op.drop_table("orders")
    op.drop_table("positions")
    op.drop_table("deposits")
    op.drop_table("portfolios")
    op.drop_table("market_snapshots")
    op.drop_table("market_candles")
    op.drop_table("trading_pairs")
    op.drop_table("exchanges")
