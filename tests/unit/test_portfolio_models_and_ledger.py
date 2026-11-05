"""
Tests for CryptoPilot AI - Portfolio Models and Contribution Ledger.
"""

from datetime import UTC, datetime

import pytest

from cryptopilot.portfolio.ledger import ContributionLedger
from cryptopilot.portfolio.models import (
    AccountType,
    LedgerEntry,
    LedgerEntryType,
    PortfolioSummary,
    PositionSnapshot,
)


def test_portfolio_models_creation():
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    # PositionSnapshot
    pos = PositionSnapshot(
        symbol="BTC/USDT",
        quantity=0.0001,
        entry_price=50000.0,
        current_price=52000.0,
        stop_loss_price=48000.0,
        take_profit_price=55000.0,
        notional_cost=5.0,
        current_notional=5.2,
        unrealized_pnl=0.2,
        unrealized_pnl_pct=0.04,
        opened_at=now,
    )
    assert pos.symbol == "BTC/USDT"
    assert pos.unrealized_pnl == pytest.approx(0.2)

    # PortfolioSummary
    summary = PortfolioSummary(
        account_id="acc_01",
        account_type=AccountType.SMALL_ACCOUNT,
        cash=25.0,
        invested_capital=5.0,
        unrealized_pnl=0.2,
        total_equity=30.2,
        total_deposits=30.0,
        realized_pnl=0.0,
        net_profit=0.2,
        return_on_deposits_pct=0.2 / 30.0,
        active_positions_count=1,
        peak_equity=30.2,
        drawdown_pct=0.0,
        timestamp=now,
    )
    assert summary.account_id == "acc_01"
    assert summary.total_equity == 30.2


def test_ledger_initial_and_recurring_deposit():
    ledger = ContributionLedger(account_id="test_acc")
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    # Initial deposit
    e1 = ledger.record_deposit(
        amount=30.0,
        balance_after=30.0,
        entry_type=LedgerEntryType.INITIAL_DEPOSIT,
        timestamp=now,
    )
    assert e1.amount == 30.0
    assert ledger.total_deposits == 30.0
    assert len(ledger.entries) == 1

    # Monthly contribution
    e2 = ledger.record_deposit(
        amount=10.0,
        balance_after=40.0,
        entry_type=LedgerEntryType.MONTHLY_CONTRIBUTION,
        timestamp=now,
    )
    assert e2.amount == 10.0
    assert ledger.total_deposits == 40.0
    assert len(ledger.entries) == 2


def test_ledger_invalid_deposit_and_fee():
    ledger = ContributionLedger(account_id="test_acc")

    with pytest.raises(ValueError, match="strictly positive"):
        ledger.record_deposit(amount=0.0, balance_after=0.0)

    with pytest.raises(ValueError, match="strictly positive"):
        ledger.record_deposit(amount=-5.0, balance_after=0.0)

    with pytest.raises(ValueError, match="Fee amount must be positive"):
        ledger.record_fee(amount=0.0, balance_after=10.0)


def test_ledger_fee_and_trade_pnl():
    ledger = ContributionLedger(account_id="test_acc")
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    ledger.record_deposit(amount=30.0, balance_after=30.0, timestamp=now)

    # Fee deduction
    ledger.record_fee(amount=0.05, balance_after=29.95, timestamp=now)
    assert ledger.total_fees_paid == pytest.approx(0.05)

    # Realized trade profit
    ledger.record_trade_realized_pnl(amount=1.50, balance_after=31.45, timestamp=now)
    assert ledger.total_realized_pnl == pytest.approx(1.50)

    # Realized trade loss
    ledger.record_trade_realized_pnl(amount=-0.30, balance_after=31.15, timestamp=now)
    assert ledger.total_realized_pnl == pytest.approx(1.20)


def test_ledger_monthly_rollover_logic():
    ledger = ContributionLedger(account_id="test_acc")

    # Initial time: Jan 2026
    t_jan = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    applied_init, cash = ledger.check_and_apply_monthly_contribution(
        current_time=t_jan,
        current_cash=30.0,
        contribution_amount=10.0,
    )
    # First month registers initial state, no duplicate contribution applied
    assert applied_init is False
    assert cash == 30.0

    # Same month: Jan 25
    t_jan_late = datetime(2026, 1, 25, 12, 0, 0, tzinfo=UTC)
    applied_same, cash = ledger.check_and_apply_monthly_contribution(
        current_time=t_jan_late,
        current_cash=30.0,
        contribution_amount=10.0,
    )
    assert applied_same is False
    assert cash == 30.0

    # Next month: Feb 1 -> Rollover triggered!
    t_feb = datetime(2026, 2, 1, 0, 5, 0, tzinfo=UTC)
    applied_feb, cash_feb = ledger.check_and_apply_monthly_contribution(
        current_time=t_feb,
        current_cash=30.0,
        contribution_amount=10.0,
    )
    assert applied_feb is True
    assert cash_feb == 40.0
    assert ledger.total_deposits == 10.0

    # Disabled monthly contribution (amount = 0)
    applied_zero, _ = ledger.check_and_apply_monthly_contribution(
        current_time=datetime(2026, 3, 1, tzinfo=UTC),
        current_cash=40.0,
        contribution_amount=0.0,
    )
    assert applied_zero is False


def test_ledger_naive_timestamps_handling():
    ledger = ContributionLedger(account_id="test_naive")
    naive_dt = datetime(2026, 11, 5, 12, 0, 0)  # No tzinfo

    e1 = ledger.record_deposit(10.0, 10.0, timestamp=naive_dt)
    assert e1.timestamp.tzinfo == UTC

    e2 = ledger.record_trade_realized_pnl(1.0, 11.0, timestamp=naive_dt)
    assert e2.timestamp.tzinfo == UTC

    e3 = ledger.record_fee(0.1, 10.9, timestamp=naive_dt)
    assert e3.timestamp.tzinfo == UTC

    # LedgerEntry model validator directly
    entry = LedgerEntry(
        account_id="test_naive",
        entry_type=LedgerEntryType.INITIAL_DEPOSIT,
        amount=10.0,
        balance_after=10.0,
        timestamp=naive_dt,
    )
    assert entry.timestamp.tzinfo == UTC
