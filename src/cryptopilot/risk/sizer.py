"""
CryptoPilot AI - Mathematical Position Sizer.
Calculates risk-adjusted position sizes based on current equity, stop loss distance,
and transaction costs, strictly bounding allocations to 30% equity and 1% risk budget.
"""

from cryptopilot.risk.models import SizedOrderProposal
from cryptopilot.strategies.base import SignalType


class PositionSizer:
    """
    Solves optimal order notional and asset quantity:
    Size = (Equity * RiskBudget) / (StopLossDistance% + RoundTripFees%)
    Subject to:
    1. Size <= 30% Equity (Allocation Cap)
    2. Size <= Available Cash
    3. Size >= Minimum Exchange Notional (Otherwise Reject; Never increase size)
    """

    def __init__(
        self,
        risk_budget_pct: float = 0.01,  # 1% equity risk per trade
        max_allocation_pct: float = 0.30,  # 30% max equity allocation per position
        round_trip_fee_pct: float = 0.002,  # 0.20% round-trip fees (0.10% entry + 0.10% exit)
        min_order_notional: float = 5.0,  # Minimum trade notional in USD
        qty_precision: int = 6,
    ) -> None:
        if risk_budget_pct <= 0.0 or risk_budget_pct > 0.10:
            raise ValueError(f"risk_budget_pct must be in (0.0, 0.10], got {risk_budget_pct}")
        if max_allocation_pct <= 0.0 or max_allocation_pct > 1.0:
            raise ValueError(f"max_allocation_pct must be in (0.0, 1.0], got {max_allocation_pct}")
        if min_order_notional < 0.0:
            raise ValueError(f"min_order_notional cannot be negative, got {min_order_notional}")

        self.risk_budget_pct = risk_budget_pct
        self.max_allocation_pct = max_allocation_pct
        self.round_trip_fee_pct = max(0.0, round_trip_fee_pct)
        self.min_order_notional = min_order_notional
        self.qty_precision = max(0, qty_precision)

    def calculate_size(
        self,
        symbol: str,
        current_equity: float,
        available_cash: float,
        entry_price: float,
        stop_loss_price: float,
        action: SignalType = SignalType.BUY,
        take_profit_price: float | None = None,
    ) -> tuple[SizedOrderProposal | None, str | None]:
        """
        Calculates mathematically constrained position size.
        Returns (SizedOrderProposal, None) on success, or (None, rejection_reason) on veto.
        """
        if current_equity <= 0.0:
            return None, f"Current portfolio equity must be positive, got ${current_equity:,.2f}."
        if available_cash <= 0.0:
            return None, f"Insufficient cash available: ${available_cash:,.2f}."
        if entry_price <= 0.0 or stop_loss_price <= 0.0:
            return None, "Entry price and stop-loss price must be strictly positive."

        # Calculate stop loss distance percentage
        stop_dist_pct = abs(entry_price - stop_loss_price) / entry_price
        if stop_dist_pct <= 1e-6:
            return None, "Stop-loss distance is zero or negligible."

        # Risk budget dollars
        risk_budget_dollars = current_equity * self.risk_budget_pct

        # Total unit risk percentage = stop distance + round trip trading fees
        total_unit_risk = stop_dist_pct + self.round_trip_fee_pct

        # Target notional from risk budget formula
        target_notional = risk_budget_dollars / total_unit_risk

        # 1. Enforce Max Allocation Cap (30% of Equity)
        max_allocation_dollars = current_equity * self.max_allocation_pct
        capped_notional = min(target_notional, max_allocation_dollars)

        # 2. Enforce Available Cash Constraint
        cash_constrained_notional = min(capped_notional, available_cash)

        # 3. Enforce Exchange Minimum Notional Constraint
        # Mandatory Rule: NEVER increase position size to satisfy minimum notional!
        if cash_constrained_notional < self.min_order_notional:
            return (
                None,
                f"Calculated safe position notional (${cash_constrained_notional:,.2f}) is below exchange "
                f"minimum order notional (${self.min_order_notional:,.2f}). Trade rejected for risk preservation.",
            )

        # 4. Precision Quantization
        raw_quantity = cash_constrained_notional / entry_price
        quantity = round(raw_quantity, self.qty_precision)

        actual_notional = round(quantity * entry_price, 4)

        # Ensure quantization didn't breach available cash
        if actual_notional > available_cash:
            # Step down one precision unit
            step = 10 ** (-self.qty_precision)
            quantity = max(0.0, round(quantity - step, self.qty_precision))
            actual_notional = round(quantity * entry_price, 4)

        if actual_notional < self.min_order_notional:
            return (
                None,
                f"Quantized position notional (${actual_notional:,.2f}) is below exchange minimum "
                f"order notional (${self.min_order_notional:,.2f}). Trade rejected.",
            )

        actual_allocation_pct = round(actual_notional / current_equity, 4)
        estimated_fees = round(actual_notional * self.round_trip_fee_pct, 4)

        proposal = SizedOrderProposal(
            symbol=symbol,
            action=action,
            quantity=quantity,
            notional_value=actual_notional,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            risk_budget_dollars=round(risk_budget_dollars, 4),
            risk_budget_pct=self.risk_budget_pct,
            allocation_pct=actual_allocation_pct,
            estimated_fees=estimated_fees,
            rationale=(
                f"Sized {quantity:.6f} {symbol} (${actual_notional:,.2f}, {actual_allocation_pct:.1%} equity). "
                f"Risk budget ${risk_budget_dollars:,.2f} ({self.risk_budget_pct:.1%}) with "
                f"{stop_dist_pct:.2%} stop-loss distance and {self.round_trip_fee_pct:.2%} estimated fees."
            ),
        )

        return proposal, None
