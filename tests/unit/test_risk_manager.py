"""
Tests for CryptoPilot AI - Risk Manager & Gatekeeper.
"""

from datetime import UTC, datetime

from cryptopilot.agent.models import MarketRegime, TradeDecision
from cryptopilot.portfolio.manager import PortfolioManager
from cryptopilot.risk.circuit_breaker import CircuitBreaker
from cryptopilot.risk.manager import RiskManager
from cryptopilot.risk.sizer import PositionSizer
from cryptopilot.strategies.base import SignalType


def _make_decision(
    symbol: str = "BTC/USDT",
    action: SignalType = SignalType.BUY,
    entry_price: float = 50000.0,
    stop_loss: float = 48000.0,
    take_profit: float = 54000.0,
) -> TradeDecision:
    return TradeDecision(
        symbol=symbol,
        action=action,
        confidence=0.80,
        suggested_entry_price=entry_price,
        suggested_stop_loss=stop_loss,
        suggested_take_profit=take_profit,
        market_regime=MarketRegime.TRENDING_BULL,
        technical_consensus_score=0.75,
        composite_score=0.70,
        explanation="Test trade decision",
        timestamp=datetime.now(UTC),
    )


def test_risk_manager_evaluate_hold():
    rm = RiskManager()
    pm = PortfolioManager(initial_capital=30.0)
    decision = _make_decision(action=SignalType.HOLD)

    res = rm.evaluate_and_size(decision, pm)
    assert res.is_approved is False
    assert "HOLD" in res.rejection_reason
    assert res.proposal is None
    assert decision.risk_approved is False


def test_risk_manager_evaluate_buy_approved():
    rm = RiskManager()
    pm = PortfolioManager(initial_capital=30.0)
    # 4% stop distance: 1% risk ($0.30) / 0.042 = $7.14
    decision = _make_decision(
        symbol="BTC/USDT",
        action=SignalType.BUY,
        entry_price=50000.0,
        stop_loss=48000.0,
    )

    res = rm.evaluate_and_size(decision, pm)
    assert res.is_approved is True
    assert res.rejection_reason is None
    assert res.proposal is not None
    assert res.proposal.symbol == "BTC/USDT"
    assert res.proposal.action == SignalType.BUY
    assert res.proposal.notional_value >= 5.0  # >= min notional
    assert res.proposal.notional_value <= 9.0  # <= 30% equity
    assert decision.risk_approved is True


def test_risk_manager_evaluate_buy_max_positions_veto():
    rm = RiskManager(max_positions=1)
    pm = PortfolioManager(initial_capital=30.0)

    # Open 1 position for BTC
    pm.open_position("BTC/USDT", 0.0001, 50000.0, 48000.0)

    # Now decision asks to BUY ETH
    decision = _make_decision(
        symbol="ETH/USDT", action=SignalType.BUY, entry_price=3000.0, stop_loss=2900.0
    )
    res = rm.evaluate_and_size(decision, pm)

    assert res.is_approved is False
    assert "Maximum open positions limit (1) already reached" in res.rejection_reason
    assert decision.risk_approved is False


def test_risk_manager_evaluate_buy_duplicate_symbol_veto():
    rm = RiskManager(max_positions=3)
    pm = PortfolioManager(initial_capital=100.0)

    pm.open_position("BTC/USDT", 0.0001, 50000.0, 48000.0)

    # Trying to open another BTC position
    decision = _make_decision(symbol="BTC/USDT", action=SignalType.BUY)
    res = rm.evaluate_and_size(decision, pm)

    assert res.is_approved is False
    assert "Multi-position stacking prohibited" in res.rejection_reason


def test_risk_manager_evaluate_buy_invalid_stop_loss():
    rm = RiskManager()
    pm = PortfolioManager(initial_capital=30.0)

    # Stop loss >= entry price
    decision = _make_decision(entry_price=50000.0, stop_loss=51000.0)
    res = rm.evaluate_and_size(decision, pm)

    assert res.is_approved is False
    assert "requires an objective stop-loss strictly below entry price" in res.rejection_reason


def test_risk_manager_evaluate_sell():
    rm = RiskManager()
    pm = PortfolioManager(initial_capital=30.0)

    # No position exists -> SELL must be rejected
    decision_sell = _make_decision(
        symbol="BTC/USDT", action=SignalType.SELL, entry_price=50000.0, stop_loss=52000.0
    )
    res = rm.evaluate_and_size(decision_sell, pm)
    assert res.is_approved is False
    assert "No open spot position exists" in res.rejection_reason

    # Now open position and test valid SELL
    pm.open_position("BTC/USDT", 0.0001, 50000.0, 48000.0)
    res_valid = rm.evaluate_and_size(decision_sell, pm)
    assert res_valid.is_approved is True
    assert res_valid.proposal is not None
    assert res_valid.proposal.action == SignalType.SELL
    assert res_valid.proposal.quantity == 0.0001


def test_risk_manager_circuit_breaker_veto():
    cb = CircuitBreaker()
    cb.trigger_emergency_stop("Manual halt")
    rm = RiskManager(circuit_breaker=cb)
    pm = PortfolioManager(initial_capital=30.0)

    decision = _make_decision(action=SignalType.BUY)
    res = rm.evaluate_and_size(decision, pm)

    assert res.is_approved is False
    assert "Circuit breaker active" in res.rejection_reason
    assert res.circuit_breaker_active is True
    assert rm.get_circuit_breaker_state(30.0).is_tripped is True


def test_risk_manager_sizer_rejection_pass_through():
    # Wide stop loss resulting in notional below $5 min notional
    sizer = PositionSizer(min_order_notional=5.0)
    rm = RiskManager(sizer=sizer)
    pm = PortfolioManager(initial_capital=30.0)

    decision = _make_decision(entry_price=50000.0, stop_loss=40000.0)  # 20% stop
    res = rm.evaluate_and_size(decision, pm)

    assert res.is_approved is False
    assert "below exchange minimum order notional" in res.rejection_reason


def test_risk_manager_naive_timestamp_and_circuit_breaker_naive():
    rm = RiskManager()
    pm = PortfolioManager(initial_capital=30.0)
    decision = _make_decision(entry_price=50000.0, stop_loss=48000.0)
    naive_dt = datetime(2026, 11, 5, 12, 0, 0)

    res = rm.evaluate_and_size(decision, pm, current_time=naive_dt)
    assert res.is_approved is True
    assert res.timestamp.tzinfo == UTC
