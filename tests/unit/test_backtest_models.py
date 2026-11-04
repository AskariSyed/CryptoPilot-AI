"""
Unit tests for cryptopilot.backtesting.models.
Covers: Schema validation, UTC enforcement, enum types, and edge cases.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cryptopilot.backtesting.models import (
    BacktestResult,
    BenchmarkComparison,
    EquityPoint,
    ExitReason,
    OrderSide,
    OrderStatus,
    OrderType,
    PerformanceMetrics,
    SimulatedOrder,
    SimulatedPosition,
    Trade,
)


class TestBacktestModels:
    def test_simulated_order_valid_and_utc_normalization(self) -> None:
        naive_dt = datetime(2026, 1, 1, 12, 0, 0)
        order = SimulatedOrder(
            order_id="ord_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01,
            target_price=50000.0,
            created_at=naive_dt,
        )
        assert order.created_at.tzinfo == UTC
        assert order.status == OrderStatus.PENDING
        assert order.fill_price is None

    def test_simulated_order_validation_errors(self) -> None:
        with pytest.raises(ValidationError):
            SimulatedOrder(
                order_id="ord_bad",
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=-1.0,  # Invalid
                target_price=50000.0,
                created_at=datetime.now(UTC),
            )

        with pytest.raises(ValidationError):
            SimulatedOrder(
                order_id="ord_bad2",
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=0.01,
                target_price=0.0,  # Invalid
                created_at=datetime.now(UTC),
            )

    def test_simulated_position_properties(self) -> None:
        naive_dt = datetime(2026, 1, 1, 12, 0, 0)
        pos = SimulatedPosition(
            position_id="pos_1",
            symbol="ETH/USDT",
            entry_price=3000.0,
            current_price=3100.0,
            quantity=0.5,
            stop_loss=2900.0,
            take_profit=3300.0,
            opened_at=naive_dt,
        )
        assert pos.opened_at.tzinfo == UTC
        assert pos.is_open is True

        pos.closed_at = datetime(2026, 1, 2, 12, 0, 0)
        assert pos.closed_at.tzinfo == UTC
        assert pos.is_open is False

    def test_trade_model_validation(self) -> None:
        trade = Trade(
            trade_id="trd_1",
            symbol="SOL/USDT",
            side=OrderSide.BUY,
            entry_time=datetime(2026, 1, 1, 0, 0, 0),
            exit_time=datetime(2026, 1, 2, 0, 0, 0),
            entry_price=100.0,
            exit_price=110.0,
            quantity=1.0,
            gross_pnl=10.0,
            net_pnl=9.8,
            fees_paid=0.2,
            exit_reason=ExitReason.TAKE_PROFIT,
            return_pct=9.8,
            bars_held=24,
        )
        assert trade.entry_time.tzinfo == UTC
        assert trade.exit_time.tzinfo == UTC
        assert trade.net_pnl == 9.8

    def test_equity_point_model(self) -> None:
        point = EquityPoint(
            timestamp=datetime(2026, 1, 1, 0, 0, 0),
            cash=25.0,
            invested_value=5.0,
            total_equity=30.0,
            cumulative_deposits=0.0,
            net_profit=0.0,
            drawdown_pct=0.0,
        )
        assert point.timestamp.tzinfo == UTC
        assert point.total_equity == 30.0

    def test_performance_metrics_and_backtest_result(self) -> None:
        metrics = PerformanceMetrics(
            initial_capital=30.0,
            final_equity=33.0,
            total_deposits=10.0,
            net_profit=3.0,
            net_return_pct=10.0,
            cagr_pct=12.5,
            max_drawdown_pct=3.5,
            max_drawdown_duration_bars=5,
            total_trades=4,
            winning_trades=3,
            losing_trades=1,
            breakeven_trades=0,
            win_rate_pct=75.0,
            profit_factor=3.0,
            sharpe_ratio=1.8,
            sortino_ratio=2.5,
            expectancy=0.75,
            avg_trade_pnl=0.75,
            avg_win=1.2,
            avg_loss=0.6,
            profit_loss_ratio=2.0,
            total_fees_paid=0.4,
        )
        benchmark = BenchmarkComparison(
            name="Buy & Hold BTC",
            initial_equity=30.0,
            final_equity=32.0,
            total_return_pct=6.67,
            cagr_pct=8.0,
            max_drawdown_pct=5.0,
            sharpe_ratio=1.2,
        )
        result = BacktestResult(
            strategy_id="ema_trend",
            symbol="BTC/USDT",
            timeframe="15m",
            start_time=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            end_time=datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC),
            initial_capital=30.0,
            final_equity=33.0,
            total_deposits=10.0,
            metrics=metrics,
            benchmarks=[benchmark],
        )
        assert result.strategy_id == "ema_trend"
        assert len(result.benchmarks) == 1
        assert result.metrics.win_rate_pct == 75.0
