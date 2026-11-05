"""
Tests for CryptoPilot AI - Portfolio Manager & Dynamic Compounding.
"""

from datetime import UTC, datetime

import pytest

from cryptopilot.portfolio.manager import PortfolioManager
from cryptopilot.portfolio.models import AccountType


def test_portfolio_manager_initialization():
    pm = PortfolioManager(
        account_id="test_small",
        account_type=AccountType.SMALL_ACCOUNT,
        initial_capital=30.0,
        monthly_contribution=10.0,
    )
    assert pm.cash == 30.0
    assert pm.total_equity == 30.0
    assert pm.total_deposits == 30.0
    assert pm.peak_equity == 30.0
    assert pm.invested_capital == 0.0
    assert pm.unrealized_pnl == 0.0
    assert pm.realized_pnl == 0.0
    assert pm.drawdown_pct == 0.0

    with pytest.raises(ValueError, match="strictly positive"):
        PortfolioManager(initial_capital=0.0)


def test_portfolio_deposit():
    pm = PortfolioManager(initial_capital=30.0)
    new_cash = pm.deposit(amount=10.0, description="Manual deposit")
    assert new_cash == 40.0
    assert pm.total_equity == 40.0
    assert pm.total_deposits == 40.0
    assert pm.peak_equity == 40.0

    with pytest.raises(ValueError, match="strictly positive"):
        pm.deposit(amount=-5.0)


def test_portfolio_open_position():
    pm = PortfolioManager(initial_capital=30.0)
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    # Open position for 0.0001 BTC at $50,000 (cost = $5.00, fee = $0.01)
    pos = pm.open_position(
        symbol="BTC/USDT",
        quantity=0.0001,
        entry_price=50000.0,
        stop_loss_price=48000.0,
        take_profit_price=54000.0,
        fee=0.01,
        timestamp=now,
    )
    assert pos.symbol == "BTC/USDT"
    assert pos.notional_cost == 5.0
    assert pm.cash == pytest.approx(24.99)
    assert pm.invested_capital == 5.0
    assert pm.total_equity == pytest.approx(29.99)  # 24.99 cash + 5.0 position

    # Attempting to open duplicate position on same symbol raises ValueError
    with pytest.raises(ValueError, match="Multi-position stacking prohibited"):
        pm.open_position(
            symbol="BTC/USDT",
            quantity=0.0001,
            entry_price=50000.0,
            stop_loss_price=48000.0,
        )

    # Attempting to open position exceeding available cash raises ValueError
    with pytest.raises(ValueError, match="Insufficient funds"):
        pm.open_position(
            symbol="ETH/USDT",
            quantity=1.0,
            entry_price=3000.0,
            stop_loss_price=2900.0,
        )

    # Invalid parameters
    with pytest.raises(ValueError, match="Invalid position parameters"):
        pm.open_position(
            symbol="SOL/USDT",
            quantity=0.0,
            entry_price=100.0,
            stop_loss_price=90.0,
        )


def test_portfolio_close_position_and_compounding():
    pm = PortfolioManager(initial_capital=30.0)
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    # Open $5.00 position
    pm.open_position(
        symbol="BTC/USDT",
        quantity=0.0001,
        entry_price=50000.0,
        stop_loss_price=48000.0,
        fee=0.01,
        timestamp=now,
    )

    # Close at $60,000 (+20% gain -> exit notional $6.00, fee $0.01)
    realized_pnl = pm.close_position(
        symbol="BTC/USDT",
        exit_price=60000.0,
        fee=0.01,
        timestamp=now,
    )
    # Gross gain = $1.00, net gain after closing fee = $0.99
    assert realized_pnl == pytest.approx(0.99)
    # Cash was 24.99 + 5.99 = 30.98
    assert pm.cash == pytest.approx(30.98)
    assert pm.total_equity == pytest.approx(30.98)
    assert pm.peak_equity == pytest.approx(30.98)
    assert pm.realized_pnl == pytest.approx(0.99)
    assert len(pm.positions) == 0

    # Closing non-existent position raises ValueError
    with pytest.raises(ValueError, match="No active position"):
        pm.close_position(symbol="BTC/USDT", exit_price=60000.0)

    # Closing with non-positive price
    with pytest.raises(ValueError, match="must be strictly positive"):
        pm.open_position("ETH/USDT", 0.001, 3000.0, 2900.0)
        pm.close_position("ETH/USDT", exit_price=0.0)


def test_portfolio_mark_prices_and_drawdown():
    pm = PortfolioManager(initial_capital=30.0)
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    pm.open_position(
        "BTC/USDT", quantity=0.0001, entry_price=50000.0, stop_loss_price=48000.0, timestamp=now
    )
    # Cash = 25.0, Invested = 5.0, Equity = 30.0, Peak = 30.0

    # Mark price rises to $55,000 -> Value = $5.50 -> Equity = 30.50 -> Peak = 30.50
    pm.update_mark_prices({"BTC/USDT": 55000.0}, timestamp=now)
    assert pm.unrealized_pnl == pytest.approx(0.50)
    assert pm.total_equity == pytest.approx(30.50)
    assert pm.peak_equity == pytest.approx(30.50)
    assert pm.drawdown_pct == 0.0

    # Mark price crashes to $40,000 -> Value = $4.00 -> Equity = 29.00
    pm.update_mark_prices({"BTC/USDT": 40000.0}, timestamp=now)
    assert pm.unrealized_pnl == pytest.approx(-1.00)
    assert pm.total_equity == pytest.approx(29.00)
    assert pm.peak_equity == pytest.approx(30.50)
    # Drawdown = (30.50 - 29.00) / 30.50 = 1.50 / 30.50 ~= 0.04918
    assert pm.drawdown_pct == pytest.approx(1.50 / 30.50, abs=1e-4)


def test_portfolio_summary_and_rollover():
    pm = PortfolioManager(initial_capital=30.0, monthly_contribution=10.0)
    t1 = datetime(2026, 1, 10, tzinfo=UTC)
    pm.check_monthly_contribution(t1)

    t2 = datetime(2026, 2, 10, tzinfo=UTC)
    applied = pm.check_monthly_contribution(t2)
    assert applied is True
    assert pm.cash == 40.0

    summary = pm.get_summary(current_time=t2)
    assert summary.total_deposits == 40.0
    assert summary.cash == 40.0
    assert summary.total_equity == 40.0
    assert summary.net_profit == 0.0
    assert summary.return_on_deposits_pct == 0.0
