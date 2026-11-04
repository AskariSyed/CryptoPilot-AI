"""
Unit tests for cryptopilot.backtesting.portfolio.SimulatedPortfolio.
Covers: Cash management, position sizing, 1% risk budget, 30% allocation cap,
monthly deposit separation, and 2% daily loss circuit breaker.
"""

from datetime import UTC, datetime

import pytest

from cryptopilot.backtesting.execution import ExecutionFill
from cryptopilot.backtesting.models import ExitReason
from cryptopilot.backtesting.portfolio import SimulatedPortfolio


class TestSimulatedPortfolio:
    def test_portfolio_initialization(self) -> None:
        p = SimulatedPortfolio(initial_capital=30.0, monthly_contribution=10.0)
        assert p.cash == 30.0
        assert p.total_equity == 30.0
        assert p.cumulative_deposits == 0.0
        assert p.net_trading_profit == 0.0
        assert p.is_circuit_breaker_active is False

        with pytest.raises(ValueError, match="Initial capital must be positive"):
            SimulatedPortfolio(initial_capital=0.0)

    def test_monthly_contribution_ledger_separation(self) -> None:
        """Verifies that $10 monthly deposits increment cash without inflating net trading profit."""
        p = SimulatedPortfolio(initial_capital=30.0, monthly_contribution=10.0)

        # Month 1: Jan 2026
        p.check_calendar_events(datetime(2026, 1, 15, tzinfo=UTC))
        assert p.cash == 30.0
        assert p.cumulative_deposits == 0.0

        # Month 2: Feb 2026 -> +$10 deposit
        p.check_calendar_events(datetime(2026, 2, 1, tzinfo=UTC))
        assert p.cash == 40.0
        assert p.cumulative_deposits == 10.0
        assert p.total_equity == 40.0
        assert p.net_trading_profit == 0.0  # Still zero trading profit!

        # Multi-month leap: April 2026 (2 elapsed months: March and April)
        p.check_calendar_events(datetime(2026, 4, 1, tzinfo=UTC))
        assert p.cash == 60.0
        assert p.cumulative_deposits == 30.0
        assert p.net_trading_profit == 0.0

    def test_daily_circuit_breaker_halts_trading(self) -> None:
        """2% daily drawdown triggers circuit breaker and resets at 00:00 UTC."""
        p = SimulatedPortfolio(initial_capital=100.0, daily_loss_limit_pct=0.02)

        # Day 1 start
        day1 = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        p.check_calendar_events(day1)
        assert p.is_circuit_breaker_active is False

        # Drop cash by 3% (equity drops from 100 to 97)
        p.cash = 97.0
        p.check_calendar_events(datetime(2026, 1, 1, 14, 0, tzinfo=UTC))
        assert p.is_circuit_breaker_active is True

        # Size calculation must reject during circuit breaker
        size = p.calculate_position_size(entry_price=100.0, stop_loss=95.0)
        assert size == 0.0

        # Day 2 start: circuit breaker resets
        day2 = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
        p.check_calendar_events(day2)
        assert p.is_circuit_breaker_active is False

    def test_position_sizing_risk_budget_and_allocation_caps(self) -> None:
        # $100 equity, 1% risk budget ($1.00 risk), 30% max allocation ($30.00 max notional)
        p = SimulatedPortfolio(
            initial_capital=100.0,
            risk_budget_pct=0.01,
            max_allocation_pct=0.30,
            min_order_notional=5.0,
        )

        # Case 1: Wide stop-loss -> risk budget governs sizing
        # Entry 100, SL 90 -> distance = 10.0 + fees ~ 10.2 -> Qty ~ 1.00 / 10.2 ~ 0.098
        # Notional = 0.098 * 100 = $9.80 < $30.00 cap
        size_wide = p.calculate_position_size(entry_price=100.0, stop_loss=90.0)
        assert size_wide > 0.0
        assert (size_wide * 100.0) <= 30.0
        assert (size_wide * 10.0) <= 1.05  # Within ~$1.00 risk

        # Case 2: Tight stop-loss -> 30% allocation cap governs sizing
        # Entry 100, SL 99.9 -> distance = 0.1 -> Raw risk qty = 1.0 / 0.3 = 3.33 units ($333)
        # But max allocation is 30% of $100 = $30.00 -> Qty must be capped at 0.30 units!
        size_tight = p.calculate_position_size(entry_price=100.0, stop_loss=99.9)
        assert pytest.approx(size_tight * 100.0, rel=1e-3) == 30.0

        # Case 3: Small account below min notional -> rejected
        p_small = SimulatedPortfolio(
            initial_capital=10.0, min_order_notional=5.0, max_allocation_pct=0.30
        )
        # 30% of $10 = $3.00 < $5.00 min notional
        size_too_small = p_small.calculate_position_size(entry_price=100.0, stop_loss=95.0)
        assert size_too_small == 0.0

        # Case 4: Invalid price checks
        assert p.calculate_position_size(0.0, 90.0) == 0.0
        assert p.calculate_position_size(100.0, 105.0) == 0.0  # SL above entry
        assert p.calculate_position_size(100.0, -10.0) == 0.0

    def test_open_and_close_position_lifecycle(self) -> None:
        p = SimulatedPortfolio(initial_capital=100.0)
        open_time = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)

        fill_buy = ExecutionFill(
            order_id="b1",
            fill_price=100.0,
            quantity=0.2,  # Cost = 20.0, Fee = 0.02
            fee_paid=0.02,
            slippage_paid=0.01,
            filled_at=open_time,
        )

        pos = p.open_position("BTC/USDT", fill_buy, stop_loss=95.0, take_profit=110.0)
        assert pos is not None
        assert p.cash == pytest.approx(100.0 - 20.02)
        assert "BTC/USDT" in p.positions
        assert p.total_equity == pytest.approx(100.0 - 0.02)

        # Max 1 position check
        assert p.calculate_position_size(entry_price=100.0, stop_loss=95.0) == 0.0

        # Mark-to-market price move up to 105
        p.update_bar_prices({"BTC/USDT": 105.0})
        assert p.positions["BTC/USDT"].unrealized_pnl == pytest.approx((105.0 - 100.0) * 0.2)
        assert p.total_equity == pytest.approx((100.0 - 20.02) + (105.0 * 0.2))

        # Close position with Take Profit fill at 110
        close_time = datetime(2026, 1, 1, 14, 0, tzinfo=UTC)
        fill_sell = ExecutionFill(
            order_id="s1",
            fill_price=110.0,
            quantity=0.2,  # Gross proceeds = 22.0, Fee = 0.022
            fee_paid=0.022,
            slippage_paid=0.01,
            filled_at=close_time,
            exit_reason=ExitReason.TAKE_PROFIT,
        )

        trade = p.close_position("BTC/USDT", fill_sell, bars_held=4)
        assert trade is not None
        assert trade.symbol == "BTC/USDT"
        assert trade.gross_pnl == pytest.approx(2.0)
        assert trade.net_pnl == pytest.approx(2.0 - (0.02 + 0.022))
        assert trade.return_pct > 0.0
        assert trade.bars_held == 4
        assert "BTC/USDT" not in p.positions
        assert len(p.trades) == 1
        assert p.net_trading_profit > 0.0

    def test_open_position_insufficient_cash(self) -> None:
        p = SimulatedPortfolio(initial_capital=10.0)
        fill_huge = ExecutionFill(
            order_id="b_huge",
            fill_price=100.0,
            quantity=1.0,  # Cost = 100.0 > Cash 10.0
            fee_paid=0.1,
            slippage_paid=0.0,
            filled_at=datetime.now(UTC),
        )
        assert p.open_position("BTC/USDT", fill_huge, stop_loss=90.0) is None

    def test_close_unknown_position_returns_none(self) -> None:
        p = SimulatedPortfolio(initial_capital=100.0)
        fill = ExecutionFill(
            order_id="s_none",
            fill_price=100.0,
            quantity=0.1,
            fee_paid=0.01,
            slippage_paid=0.0,
            filled_at=datetime.now(UTC),
        )
        assert p.close_position("NONEXISTENT", fill) is None

    def test_record_equity_snapshot_and_drawdown(self) -> None:
        p = SimulatedPortfolio(initial_capital=100.0)
        t1 = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
        snap1 = p.record_equity_snapshot(t1)
        assert snap1.total_equity == 100.0
        assert snap1.drawdown_pct == 0.0

        # Equity rises to 120
        p.cash = 120.0
        t2 = datetime(2026, 1, 1, 2, 0, tzinfo=UTC)
        snap2 = p.record_equity_snapshot(t2)
        assert snap2.total_equity == 120.0
        assert snap2.drawdown_pct == 0.0
        assert p.peak_equity == 120.0

        # Equity drops to 108 (10% drawdown from 120)
        p.cash = 108.0
        t3 = datetime(2026, 1, 1, 3, 0, tzinfo=UTC)
        snap3 = p.record_equity_snapshot(t3)
        assert snap3.drawdown_pct == pytest.approx(10.0)
