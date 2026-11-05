"""
CryptoPilot AI - Quantitative Risk Manager & Supreme Gatekeeper.
Evaluates trade proposals against portfolio equity, 1% risk budget, 30% max allocation,
1-position concurrency limit, and the 2% daily loss circuit breaker.
"""

from datetime import UTC, datetime

from cryptopilot.agent.models import TradeDecision
from cryptopilot.portfolio.manager import PortfolioManager
from cryptopilot.risk.circuit_breaker import CircuitBreaker
from cryptopilot.risk.models import (
    CircuitBreakerState,
    RiskEvaluationResult,
    SizedOrderProposal,
)
from cryptopilot.risk.sizer import PositionSizer
from cryptopilot.strategies.base import SignalType


class RiskManager:
    """
    Supreme controlling risk authority within CryptoPilot AI.
    Possesses non-negotiable veto power over every proposed trade.
    """

    def __init__(
        self,
        sizer: PositionSizer | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        max_positions: int = 1,
    ) -> None:
        self.sizer = sizer or PositionSizer()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.max_positions = max(1, max_positions)

    def evaluate_and_size(
        self,
        decision: TradeDecision,
        portfolio: PortfolioManager,
        current_time: datetime | None = None,
    ) -> RiskEvaluationResult:
        """
        Evaluates incoming TradeDecision against all capital and risk constraints.
        Returns RiskEvaluationResult containing approved proposal or rejection rationale.
        """
        ts = current_time or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        equity = portfolio.total_equity
        cash = portfolio.available_cash

        # 1. Update circuit breaker daily starting equity & evaluate daily drawdown
        self.circuit_breaker.update_daily_equity(current_equity=equity, current_time=ts)
        cb_state = self.circuit_breaker.get_state(current_equity=equity, current_time=ts)

        if cb_state.is_tripped:
            reason = f"Circuit breaker active: {cb_state.trip_reason}"
            decision.risk_approved = False
            decision.rejection_reason = reason
            return RiskEvaluationResult(
                is_approved=False,
                rejection_reason=reason,
                proposal=None,
                evaluated_equity=equity,
                risk_budget_dollars=0.0,
                position_notional=0.0,
                allocation_pct=0.0,
                circuit_breaker_active=True,
                timestamp=ts,
            )

        # 2. Check Decision Action
        if decision.action == SignalType.HOLD:
            reason = "TradeDecision action is HOLD. No order execution required."
            decision.risk_approved = False
            decision.rejection_reason = reason
            return RiskEvaluationResult(
                is_approved=False,
                rejection_reason=reason,
                proposal=None,
                evaluated_equity=equity,
                risk_budget_dollars=0.0,
                position_notional=0.0,
                allocation_pct=0.0,
                circuit_breaker_active=False,
                timestamp=ts,
            )

        # 3. Handle SELL Action (Closing an existing spot position)
        if decision.action == SignalType.SELL:
            if decision.symbol not in portfolio.positions:
                reason = f"No open spot position exists for {decision.symbol} to SELL/close."
                decision.risk_approved = False
                decision.rejection_reason = reason
                return RiskEvaluationResult(
                    is_approved=False,
                    rejection_reason=reason,
                    proposal=None,
                    evaluated_equity=equity,
                    risk_budget_dollars=0.0,
                    position_notional=0.0,
                    allocation_pct=0.0,
                    circuit_breaker_active=False,
                    timestamp=ts,
                )

            # Close existing position
            existing_pos = portfolio.positions[decision.symbol]
            sell_notional = round(existing_pos.quantity * decision.suggested_entry_price, 4)
            proposal = SizedOrderProposal(
                symbol=decision.symbol,
                action=SignalType.SELL,
                quantity=existing_pos.quantity,
                notional_value=sell_notional,
                entry_price=decision.suggested_entry_price,
                stop_loss_price=decision.suggested_stop_loss
                or (decision.suggested_entry_price * 1.05),
                take_profit_price=decision.suggested_take_profit,
                risk_budget_dollars=0.0,
                risk_budget_pct=0.0,
                allocation_pct=round(sell_notional / equity, 4) if equity > 0.0 else 0.0,
                estimated_fees=round(sell_notional * self.sizer.round_trip_fee_pct * 0.5, 4),
                rationale=f"Approved closing active position for {existing_pos.quantity:.6f} {decision.symbol}.",
                timestamp=ts,
            )
            decision.risk_approved = True
            decision.rejection_reason = None
            return RiskEvaluationResult(
                is_approved=True,
                rejection_reason=None,
                proposal=proposal,
                evaluated_equity=equity,
                risk_budget_dollars=0.0,
                position_notional=sell_notional,
                allocation_pct=proposal.allocation_pct,
                circuit_breaker_active=False,
                timestamp=ts,
            )

        # 4. Handle BUY Action (Opening a new spot position)
        # Check concurrency constraint
        if len(portfolio.positions) >= self.max_positions:
            reason = (
                f"Maximum open positions limit ({self.max_positions}) already reached. "
                f"Micro-capital accounts are restricted from opening multiple concurrent positions."
            )
            decision.risk_approved = False
            decision.rejection_reason = reason
            return RiskEvaluationResult(
                is_approved=False,
                rejection_reason=reason,
                proposal=None,
                evaluated_equity=equity,
                risk_budget_dollars=0.0,
                position_notional=0.0,
                allocation_pct=0.0,
                circuit_breaker_active=False,
                timestamp=ts,
            )

        if decision.symbol in portfolio.positions:
            reason = f"Active position for {decision.symbol} already exists. Multi-position stacking prohibited."
            decision.risk_approved = False
            decision.rejection_reason = reason
            return RiskEvaluationResult(
                is_approved=False,
                rejection_reason=reason,
                proposal=None,
                evaluated_equity=equity,
                risk_budget_dollars=0.0,
                position_notional=0.0,
                allocation_pct=0.0,
                circuit_breaker_active=False,
                timestamp=ts,
            )

        # Check valid stop-loss
        if (
            decision.suggested_stop_loss is None
            or decision.suggested_stop_loss >= decision.suggested_entry_price
        ):
            reason = (
                f"BUY decision requires an objective stop-loss strictly below entry price. "
                f"Got stop_loss=${decision.suggested_stop_loss}, entry=${decision.suggested_entry_price}."
            )
            decision.risk_approved = False
            decision.rejection_reason = reason
            return RiskEvaluationResult(
                is_approved=False,
                rejection_reason=reason,
                proposal=None,
                evaluated_equity=equity,
                risk_budget_dollars=0.0,
                position_notional=0.0,
                allocation_pct=0.0,
                circuit_breaker_active=False,
                timestamp=ts,
            )

        # 5. Execute Mathematical Sizing
        buy_proposal, sizer_rejection = self.sizer.calculate_size(
            symbol=decision.symbol,
            current_equity=equity,
            available_cash=cash,
            entry_price=decision.suggested_entry_price,
            stop_loss_price=decision.suggested_stop_loss,
            action=SignalType.BUY,
            take_profit_price=decision.suggested_take_profit,
        )

        if buy_proposal is None or sizer_rejection is not None:
            decision.risk_approved = False
            decision.rejection_reason = sizer_rejection
            return RiskEvaluationResult(
                is_approved=False,
                rejection_reason=sizer_rejection,
                proposal=None,
                evaluated_equity=equity,
                risk_budget_dollars=round(equity * self.sizer.risk_budget_pct, 4),
                position_notional=0.0,
                allocation_pct=0.0,
                circuit_breaker_active=False,
                timestamp=ts,
            )

        # Sizing and risk bounds approved!
        decision.risk_approved = True
        decision.rejection_reason = None
        return RiskEvaluationResult(
            is_approved=True,
            rejection_reason=None,
            proposal=buy_proposal,
            evaluated_equity=equity,
            risk_budget_dollars=buy_proposal.risk_budget_dollars,
            position_notional=buy_proposal.notional_value,
            allocation_pct=buy_proposal.allocation_pct,
            circuit_breaker_active=False,
            timestamp=ts,
        )

    def get_circuit_breaker_state(
        self,
        current_equity: float,
        current_time: datetime | None = None,
    ) -> CircuitBreakerState:
        """Returns active circuit breaker telemetry."""
        return self.circuit_breaker.get_state(
            current_equity=current_equity, current_time=current_time
        )
