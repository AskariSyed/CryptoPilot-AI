"""
Tests for CryptoPilot AI - Mathematical Invariants & Risk Accounting Properties.
Validates financial invariants across parameter sweeps and property-based assertions.
"""

import pytest

from cryptopilot.portfolio.manager import PortfolioManager
from cryptopilot.risk.sizer import PositionSizer


def test_invariant_position_notional_never_exceeds_30_percent_allocation():
    """
    Invariant: Calculated position notional must never exceed 30% of current equity,
    regardless of how tight the stop loss distance is.
    """
    sizer = PositionSizer(risk_budget_pct=0.01, max_allocation_pct=0.30, min_order_notional=5.0)

    # Sweep across various equity levels: $30 to $50,000
    equity_levels = [30.0, 50.0, 100.0, 500.0, 1000.0, 10000.0]
    # Sweep across stop distances from 0.05% to 5.0%
    stop_distances = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05]

    for eq in equity_levels:
        for stop_dist in stop_distances:
            entry_p = 50000.0
            stop_p = entry_p * (1.0 - stop_dist)
            proposal, err = sizer.calculate_size(
                symbol="BTC/USDT",
                current_equity=eq,
                available_cash=eq,
                entry_price=entry_p,
                stop_loss_price=stop_p,
            )

            if proposal is not None:
                max_allowed_allocation = eq * 0.30
                # Invariant 1: notional <= 30% of equity (within precision epsilon)
                assert proposal.notional_value <= (max_allowed_allocation + 1e-4), (
                    f"Invariant violated for equity ${eq}, stop {stop_dist:.2%}: "
                    f"notional ${proposal.notional_value} > max ${max_allowed_allocation}"
                )


def test_invariant_dollar_risk_never_exceeds_budget():
    """
    Invariant: Dollar risk risked must never exceed 1% of total equity.
    """
    sizer = PositionSizer(risk_budget_pct=0.01, max_allocation_pct=0.30, min_order_notional=5.0)

    for eq in [30.0, 75.0, 150.0, 1000.0]:
        for stop_dist in [0.01, 0.02, 0.03, 0.04]:
            entry_p = 50000.0
            stop_p = entry_p * (1.0 - stop_dist)
            proposal, _ = sizer.calculate_size(
                symbol="BTC/USDT",
                current_equity=eq,
                available_cash=eq,
                entry_price=entry_p,
                stop_loss_price=stop_p,
            )

            if proposal is not None:
                max_risk_allowed = eq * 0.01
                assert proposal.risk_budget_dollars <= (max_risk_allowed + 1e-4)


def test_invariant_cash_plus_invested_capital_equals_total_equity():
    """
    Invariant: Cash + Invested Capital must equal Total Equity (with zero unrealized PnL).
    """
    pm = PortfolioManager(initial_capital=30.0)

    # Initial state
    assert pm.cash + pm.invested_capital == pytest.approx(pm.total_equity)

    # Open position
    pm.open_position("BTC/USDT", 0.0001, 50000.0, 48000.0)
    assert pm.cash + pm.invested_capital == pytest.approx(pm.total_equity)

    # Close position
    pm.close_position("BTC/USDT", 55000.0)
    assert pm.cash + pm.invested_capital == pytest.approx(pm.total_equity)


def test_invariant_never_increase_size_to_meet_min_notional():
    """
    Crucial Rule: Sizer must reject rather than artificially increasing size to satisfy min notional.
    """
    # $30 account, 10% stop distance -> raw size $2.94 < $5.00 min notional
    sizer = PositionSizer(min_order_notional=5.0)
    proposal, err = sizer.calculate_size("BTC/USDT", 30.0, 30.0, 50000.0, 45000.0)

    assert proposal is None
    assert err is not None
    assert "below exchange minimum order notional" in err
