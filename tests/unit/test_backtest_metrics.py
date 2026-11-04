"""
Unit tests for cryptopilot.backtesting.metrics.PerformanceMetricsCalculator.
Covers: Quantitative performance metrics, risk ratios, CAGR, and zero-division edge cases.
"""

from datetime import UTC, datetime, timedelta

import pytest

from cryptopilot.backtesting.metrics import PerformanceMetricsCalculator
from cryptopilot.backtesting.models import EquityPoint, ExitReason, OrderSide, Trade


class TestPerformanceMetricsCalculator:
    def test_empty_equity_curve_fallback(self) -> None:
        metrics = PerformanceMetricsCalculator.calculate([], [], initial_capital=30.0)
        assert metrics.initial_capital == 30.0
        assert metrics.final_equity == 30.0
        assert metrics.total_trades == 0
        assert metrics.net_profit == 0.0
        assert metrics.sharpe_ratio == 0.0

    def test_standard_profitable_backtest_metrics(self) -> None:
        start_t = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        equity_curve = [
            EquityPoint(
                timestamp=start_t,
                cash=100.0,
                invested_value=0.0,
                total_equity=100.0,
                cumulative_deposits=0.0,
                net_profit=0.0,
                drawdown_pct=0.0,
            ),
            EquityPoint(
                timestamp=start_t + timedelta(days=10),
                cash=110.0,
                invested_value=0.0,
                total_equity=110.0,
                cumulative_deposits=0.0,
                net_profit=10.0,
                drawdown_pct=0.0,
            ),
            EquityPoint(
                timestamp=start_t + timedelta(days=20),
                cash=105.0,
                invested_value=0.0,
                total_equity=105.0,
                cumulative_deposits=0.0,
                net_profit=5.0,
                drawdown_pct=4.54,
            ),
            EquityPoint(
                timestamp=start_t + timedelta(days=30),
                cash=120.0,
                invested_value=0.0,
                total_equity=120.0,
                cumulative_deposits=0.0,
                net_profit=20.0,
                drawdown_pct=0.0,
            ),
        ]
        trades = [
            Trade(
                trade_id="t1",
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                entry_time=start_t,
                exit_time=start_t + timedelta(days=10),
                entry_price=100.0,
                exit_price=110.0,
                quantity=1.0,
                gross_pnl=10.0,
                net_pnl=9.8,
                fees_paid=0.2,
                exit_reason=ExitReason.TAKE_PROFIT,
                return_pct=9.8,
            ),
            Trade(
                trade_id="t2",
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                entry_time=start_t + timedelta(days=12),
                exit_time=start_t + timedelta(days=18),
                entry_price=110.0,
                exit_price=105.0,
                quantity=1.0,
                gross_pnl=-5.0,
                net_pnl=-5.2,
                fees_paid=0.2,
                exit_reason=ExitReason.STOP_LOSS,
                return_pct=-4.7,
            ),
            Trade(
                trade_id="t3",
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                entry_time=start_t + timedelta(days=22),
                exit_time=start_t + timedelta(days=28),
                entry_price=105.0,
                exit_price=120.0,
                quantity=1.0,
                gross_pnl=15.0,
                net_pnl=14.8,
                fees_paid=0.2,
                exit_reason=ExitReason.TAKE_PROFIT,
                return_pct=14.1,
            ),
        ]

        metrics = PerformanceMetricsCalculator.calculate(
            equity_curve, trades, initial_capital=100.0
        )
        assert metrics.final_equity == 120.0
        assert metrics.net_profit == 20.0
        assert metrics.net_return_pct == 20.0
        assert metrics.cagr_pct > 0.0
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.win_rate_pct == pytest.approx(66.67, abs=0.01)
        assert metrics.profit_factor > 1.0
        assert metrics.max_drawdown_pct > 0.0
        assert metrics.sharpe_ratio > 0.0
        assert metrics.sortino_ratio > 0.0
        assert metrics.expectancy > 0.0
        assert metrics.total_fees_paid == pytest.approx(0.6)

    def test_all_winning_trades_profit_factor_cap(self) -> None:
        start_t = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        equity_curve = [
            EquityPoint(
                timestamp=start_t,
                cash=100.0,
                invested_value=0.0,
                total_equity=100.0,
                cumulative_deposits=0.0,
                net_profit=0.0,
                drawdown_pct=0.0,
            ),
            EquityPoint(
                timestamp=start_t + timedelta(days=1),
                cash=110.0,
                invested_value=0.0,
                total_equity=110.0,
                cumulative_deposits=0.0,
                net_profit=10.0,
                drawdown_pct=0.0,
            ),
        ]
        trade = Trade(
            trade_id="t1",
            symbol="ETH/USDT",
            side=OrderSide.BUY,
            entry_time=start_t,
            exit_time=start_t + timedelta(days=1),
            entry_price=100.0,
            exit_price=110.0,
            quantity=1.0,
            gross_pnl=10.0,
            net_pnl=9.8,
            fees_paid=0.2,
            exit_reason=ExitReason.TAKE_PROFIT,
            return_pct=9.8,
        )
        metrics = PerformanceMetricsCalculator.calculate(
            equity_curve, [trade], initial_capital=100.0
        )
        assert metrics.profit_factor == 999.0  # Zero loss cap
        assert metrics.win_rate_pct == 100.0
        assert metrics.sortino_ratio == 999.0

    def test_all_losing_trades(self) -> None:
        start_t = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        equity_curve = [
            EquityPoint(
                timestamp=start_t,
                cash=100.0,
                invested_value=0.0,
                total_equity=100.0,
                cumulative_deposits=0.0,
                net_profit=0.0,
                drawdown_pct=0.0,
            ),
            EquityPoint(
                timestamp=start_t + timedelta(days=1),
                cash=90.0,
                invested_value=0.0,
                total_equity=90.0,
                cumulative_deposits=0.0,
                net_profit=-10.0,
                drawdown_pct=10.0,
            ),
        ]
        trade = Trade(
            trade_id="t1",
            symbol="ETH/USDT",
            side=OrderSide.BUY,
            entry_time=start_t,
            exit_time=start_t + timedelta(days=1),
            entry_price=100.0,
            exit_price=90.0,
            quantity=1.0,
            gross_pnl=-10.0,
            net_pnl=-10.2,
            fees_paid=0.2,
            exit_reason=ExitReason.STOP_LOSS,
            return_pct=-10.2,
        )
        metrics = PerformanceMetricsCalculator.calculate(
            equity_curve, [trade], initial_capital=100.0
        )
        assert metrics.profit_factor == 0.0
        assert metrics.win_rate_pct == 0.0
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 1

    def test_flat_equity_zero_variance(self) -> None:
        start_t = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        equity_curve = [
            EquityPoint(
                timestamp=start_t,
                cash=100.0,
                invested_value=0.0,
                total_equity=100.0,
                cumulative_deposits=0.0,
                net_profit=0.0,
                drawdown_pct=0.0,
            ),
            EquityPoint(
                timestamp=start_t + timedelta(days=1),
                cash=100.0,
                invested_value=0.0,
                total_equity=100.0,
                cumulative_deposits=0.0,
                net_profit=0.0,
                drawdown_pct=0.0,
            ),
        ]
        metrics = PerformanceMetricsCalculator.calculate(equity_curve, [], initial_capital=100.0)
        assert metrics.sharpe_ratio == 0.0
        assert metrics.sortino_ratio == 0.0
        assert metrics.net_return_pct == 0.0
