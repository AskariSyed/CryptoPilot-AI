"""
Tests for CryptoPilot AI - Position Sizer and Quantitative Risk Models.
"""

import pytest

from cryptopilot.risk.models import SizedOrderProposal
from cryptopilot.risk.sizer import PositionSizer
from cryptopilot.strategies.base import SignalType


def test_position_sizer_invalid_init():
    with pytest.raises(ValueError, match="risk_budget_pct"):
        PositionSizer(risk_budget_pct=0.0)

    with pytest.raises(ValueError, match="risk_budget_pct"):
        PositionSizer(risk_budget_pct=0.15)

    with pytest.raises(ValueError, match="max_allocation_pct"):
        PositionSizer(max_allocation_pct=0.0)

    with pytest.raises(ValueError, match="max_allocation_pct"):
        PositionSizer(max_allocation_pct=1.5)

    with pytest.raises(ValueError, match="min_order_notional"):
        PositionSizer(min_order_notional=-1.0)


def test_position_sizer_standard_calculation():
    # Sizer at $30 equity, 1% risk budget ($0.30 risk), entry $50,000, stop $48,000 (4% stop distance)
    # Unit risk = 0.04 + 0.002 = 0.042
    # Target notional = 0.30 / 0.042 = 7.142857
    sizer = PositionSizer(
        risk_budget_pct=0.01,
        max_allocation_pct=0.30,
        round_trip_fee_pct=0.002,
        min_order_notional=5.0,
        qty_precision=6,
    )

    proposal, err = sizer.calculate_size(
        symbol="BTC/USDT",
        current_equity=30.0,
        available_cash=30.0,
        entry_price=50000.0,
        stop_loss_price=48000.0,
        action=SignalType.BUY,
        take_profit_price=54000.0,
    )

    assert err is None
    assert proposal is not None
    assert isinstance(proposal, SizedOrderProposal)
    assert proposal.symbol == "BTC/USDT"
    assert proposal.action == SignalType.BUY
    # Target notional should be ~7.14
    assert proposal.notional_value == pytest.approx(7.14, abs=0.1)
    # Allocation pct should be ~ 7.14 / 30 = 23.8% <= 30%
    assert proposal.allocation_pct <= 0.30
    assert proposal.risk_budget_dollars == pytest.approx(0.30, abs=0.01)
    assert proposal.notional_value >= 5.0  # >= min notional


def test_position_sizer_max_allocation_cap():
    # Stop distance is very tight (0.5% = $250 on $50,000)
    # Target notional = 0.30 / (0.005 + 0.002) = 0.30 / 0.007 = $42.85
    # Max allocation (30% of $30) = $9.00
    # Must cap strictly at $9.00!
    sizer = PositionSizer(
        risk_budget_pct=0.01,
        max_allocation_pct=0.30,
        min_order_notional=5.0,
    )

    proposal, err = sizer.calculate_size(
        symbol="BTC/USDT",
        current_equity=30.0,
        available_cash=30.0,
        entry_price=50000.0,
        stop_loss_price=49750.0,  # 0.5% stop
    )

    assert err is None
    assert proposal is not None
    assert proposal.notional_value <= 9.00 + 1e-4
    assert proposal.allocation_pct <= 0.3001


def test_position_sizer_min_notional_rejection():
    # Wide stop distance: 10% on $50,000 ($45,000 stop)
    # Target notional = 0.30 / (0.10 + 0.002) = 0.30 / 0.102 = $2.94
    # $2.94 < $5.00 min notional!
    # Sizer MUST reject: NEVER increase size to violate risk!
    sizer = PositionSizer(
        risk_budget_pct=0.01,
        max_allocation_pct=0.30,
        min_order_notional=5.0,
    )

    proposal, err = sizer.calculate_size(
        symbol="BTC/USDT",
        current_equity=30.0,
        available_cash=30.0,
        entry_price=50000.0,
        stop_loss_price=45000.0,  # 10% stop
    )

    assert proposal is None
    assert err is not None
    assert "below exchange minimum order notional" in err
    assert "Trade rejected for risk preservation" in err


def test_position_sizer_cash_boundary_and_quantization():
    sizer = PositionSizer(
        risk_budget_pct=0.01,
        max_allocation_pct=0.50,
        min_order_notional=5.0,
    )

    # Available cash is only $6.00 (below target notional $7.14)
    proposal, err = sizer.calculate_size(
        symbol="BTC/USDT",
        current_equity=30.0,
        available_cash=6.0,
        entry_price=50000.0,
        stop_loss_price=48000.0,
    )
    assert err is None
    assert proposal is not None
    assert proposal.notional_value <= 6.00 + 1e-4


def test_position_sizer_edge_cases():
    sizer = PositionSizer()

    # Zero equity
    p, err = sizer.calculate_size("BTC/USDT", 0.0, 30.0, 50000.0, 48000.0)
    assert p is None
    assert "equity must be positive" in err.lower()

    # Zero cash
    p, err = sizer.calculate_size("BTC/USDT", 30.0, 0.0, 50000.0, 48000.0)
    assert p is None
    assert "insufficient cash" in err.lower()

    # Invalid prices
    p, err = sizer.calculate_size("BTC/USDT", 30.0, 30.0, 0.0, 48000.0)
    assert p is None
    assert "must be strictly positive" in err.lower()

    # Stop loss == entry price
    p, err = sizer.calculate_size("BTC/USDT", 30.0, 30.0, 50000.0, 50000.0)
    assert p is None
    assert "stop-loss distance is zero" in err.lower()


def test_position_sizer_quantization_stepdown_and_min_notional_breach():
    # Sizer where rounding up exceeds cash and stepping down drops below min notional
    sizer = PositionSizer(
        risk_budget_pct=0.05,
        max_allocation_pct=0.50,
        min_order_notional=5.0,
        qty_precision=1,  # Coarse precision to force rounding behavior
    )

    # Cash = 5.05, entry_price = 3.0
    # raw_quantity = 5.05 / 3.0 = 1.6833 -> round(1.6833, 1) = 1.7 -> notional = 5.10 > 5.05
    # Steps down to 1.6 -> 1.6 * 3.0 = 4.80 < 5.0 min notional!
    proposal, err = sizer.calculate_size(
        symbol="TEST/USDT",
        current_equity=100.0,
        available_cash=5.05,
        entry_price=3.0,
        stop_loss_price=2.85,
    )
    assert proposal is None
    assert err is not None
    assert "Quantized position notional" in err
