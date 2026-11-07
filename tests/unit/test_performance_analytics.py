"""
Unit tests for cryptopilot.database.analytics.PerformanceAnalyticsService.
Validates Sharpe ratio, Sortino ratio, drawdown, win rates, and database report computation.
"""

from datetime import UTC, datetime

import pytest

from cryptopilot.database.analytics import (
    PerformanceAnalyticsService,
    PerformanceReport,
)
from cryptopilot.database.connection import DatabaseManager
from cryptopilot.database.models import PortfolioModel, PositionModel


def test_sharpe_ratio_calculation() -> None:
    """Tests annualized Sharpe ratio under normal and edge conditions."""
    # Empty or single observation
    assert PerformanceAnalyticsService.calculate_sharpe_ratio([]) == 0.0
    assert PerformanceAnalyticsService.calculate_sharpe_ratio([0.01]) == 0.0

    # Flat returns (zero variance)
    assert PerformanceAnalyticsService.calculate_sharpe_ratio([0.01, 0.01, 0.01]) == 0.0

    # Positive returns series
    returns = [0.01, 0.02, -0.005, 0.015, 0.03, -0.01]
    sharpe = PerformanceAnalyticsService.calculate_sharpe_ratio(returns)
    assert sharpe > 0.0

    # Risk-free rate adjustment
    sharpe_rf = PerformanceAnalyticsService.calculate_sharpe_ratio(returns, risk_free_rate=0.05)
    assert sharpe_rf < sharpe


def test_sortino_ratio_calculation() -> None:
    """Tests Sortino ratio with downside volatility isolation."""
    assert PerformanceAnalyticsService.calculate_sortino_ratio([]) == 0.0
    assert PerformanceAnalyticsService.calculate_sortino_ratio([0.02]) == 0.0

    # Only positive returns (no downside deviation)
    assert PerformanceAnalyticsService.calculate_sortino_ratio([0.01, 0.02, 0.03]) == 0.0

    # Mixed returns
    returns = [0.02, -0.01, 0.03, -0.02, 0.015, 0.04]
    sortino = PerformanceAnalyticsService.calculate_sortino_ratio(returns)
    assert sortino > 0.0


def test_max_drawdown_calculation() -> None:
    """Tests peak-to-trough drawdown calculation."""
    assert PerformanceAnalyticsService.calculate_max_drawdown([]) == (0.0, 0.0)
    assert PerformanceAnalyticsService.calculate_max_drawdown([100.0]) == (0.0, 0.0)

    # Monotonically increasing curve
    assert PerformanceAnalyticsService.calculate_max_drawdown([100.0, 110.0, 120.0]) == (0.0, 0.0)

    # Known drawdown: peak 120 drops to 80 (drawdown 40 / 120 = 33.33%)
    equity_curve = [100.0, 120.0, 90.0, 110.0, 80.0, 130.0]
    dd_dollars, dd_pct = PerformanceAnalyticsService.calculate_max_drawdown(equity_curve)
    assert dd_dollars == 40.0
    assert pytest.approx(dd_pct, abs=1e-3) == 0.3333


def test_trade_metrics_calculation() -> None:
    """Tests win rate, profit factor, and payoff calculations."""
    empty = PerformanceAnalyticsService.calculate_trade_metrics([])
    assert empty["total_trades"] == 0
    assert empty["win_rate"] == 0.0

    # 2 wins ($20, $10), 1 loss ($10) -> total pnl = $20, PF = 30 / 10 = 3.0
    pnls = [20.0, -10.0, 10.0]
    metrics = PerformanceAnalyticsService.calculate_trade_metrics(pnls)
    assert metrics["total_trades"] == 3
    assert metrics["winning_trades"] == 2
    assert metrics["losing_trades"] == 1
    assert pytest.approx(metrics["win_rate"], abs=1e-3) == 0.6667
    assert metrics["total_realized_pnl"] == 20.0
    assert metrics["profit_factor"] == 3.0
    assert metrics["average_win"] == 15.0
    assert metrics["average_loss"] == 10.0
    assert metrics["payoff_ratio"] == 1.5

    # All wins
    all_wins = PerformanceAnalyticsService.calculate_trade_metrics([10.0, 15.0])
    assert all_wins["profit_factor"] == 999.0


@pytest.mark.asyncio
async def test_compute_portfolio_report() -> None:
    """Tests end-to-end database report generation from closed positions."""
    db_mgr = DatabaseManager("sqlite+aiosqlite:///:memory:", echo=False)
    await db_mgr.init_db()

    now = datetime.now(UTC)

    async with db_mgr.session() as session:
        # Create portfolio
        port = PortfolioModel(
            id="small_account_01",
            account_type="small_account",
            currency="USDT",
            initial_balance=30.0,
            current_cash=35.0,
            invested_capital=0.0,
            realized_pnl=5.0,
            total_deposits=0.0,
            total_fees_paid=0.05,
        )
        session.add(port)

        # Add closed positions
        pos1 = PositionModel(
            id="pos-1",
            portfolio_id="small_account_01",
            symbol="BTC/USDT",
            side="LONG",
            status="CLOSED",
            quantity=0.0002,
            entry_price=50000.0,
            current_price=52000.0,
            exit_price=52000.0,
            stop_loss_price=49000.0,
            realized_pnl=4.0,
            opened_at=now,
            closed_at=now,
        )
        pos2 = PositionModel(
            id="pos-2",
            portfolio_id="small_account_01",
            symbol="ETH/USDT",
            side="LONG",
            status="CLOSED",
            quantity=0.005,
            entry_price=3000.0,
            current_price=2900.0,
            exit_price=2900.0,
            stop_loss_price=2900.0,
            realized_pnl=-0.50,
            opened_at=now,
            closed_at=now,
        )
        pos3 = PositionModel(
            id="pos-3",
            portfolio_id="small_account_01",
            symbol="SOL/USDT",
            side="LONG",
            status="CLOSED",
            quantity=0.1,
            entry_price=150.0,
            current_price=165.0,
            exit_price=165.0,
            stop_loss_price=145.0,
            realized_pnl=1.50,
            opened_at=now,
            closed_at=now,
        )
        session.add_all([pos1, pos2, pos3])
        await session.commit()

    async with db_mgr.session() as session:
        report = await PerformanceAnalyticsService.compute_portfolio_report(
            session=session,
            portfolio_id="small_account_01",
        )
        assert isinstance(report, PerformanceReport)
        assert report.portfolio_id == "small_account_01"
        assert report.total_trades == 3
        assert report.winning_trades == 2
        assert report.losing_trades == 1
        assert pytest.approx(report.win_rate, abs=1e-3) == 0.6667
        assert report.total_realized_pnl == 5.0
        assert report.total_fees_paid == 0.05

    # Non-existent portfolio raises KeyError
    async with db_mgr.session() as session:
        with pytest.raises(KeyError, match="Portfolio 'unknown' not found"):
            await PerformanceAnalyticsService.compute_portfolio_report(session, "unknown")

    await db_mgr.drop_db()
    await db_mgr.close()
