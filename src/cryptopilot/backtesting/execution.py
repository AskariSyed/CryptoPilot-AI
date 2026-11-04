"""
CryptoPilot AI - Simulated Execution Engine.
Models realistic trade execution with bid/ask spreads, volume-dependent slippage,
maker/taker commissions, and intrabar boundary checks for stop-loss / take-profit.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from cryptopilot.backtesting.models import (
    ExitReason,
    OrderSide,
    OrderStatus,
    SimulatedOrder,
    SimulatedPosition,
)


class ExecutionFill(BaseModel):
    """Result of an order execution fill."""

    order_id: str
    fill_price: float = Field(gt=0.0)
    quantity: float = Field(gt=0.0)
    fee_paid: float = Field(ge=0.0)
    slippage_paid: float = Field(ge=0.0)
    filled_at: datetime
    exit_reason: ExitReason | None = None


class SimulatedExecutionEngine:
    """
    Simulates realistic exchange order matching with fees, spreads, and slippage.
    """

    def __init__(
        self,
        maker_fee_pct: float = 0.001,  # 0.10% maker fee
        taker_fee_pct: float = 0.001,  # 0.10% taker fee
        default_spread_pct: float = 0.0005,  # 0.05% (5 bps) typical BTC/ETH spread
        base_slippage_pct: float = 0.0002,  # 0.02% (2 bps) baseline slippage
        slippage_impact_factor: float = 0.1,  # Quadratic market impact factor
        max_slippage_pct: float = 0.03,  # 3.0% cap on slippage penalty
    ) -> None:
        self.maker_fee_pct = max(0.0, maker_fee_pct)
        self.taker_fee_pct = max(0.0, taker_fee_pct)
        self.default_spread_pct = max(0.0, default_spread_pct)
        self.base_slippage_pct = max(0.0, base_slippage_pct)
        self.slippage_impact_factor = max(0.0, slippage_impact_factor)
        self.max_slippage_pct = max(0.0, max_slippage_pct)

    def calculate_slippage(self, order_quantity: float, bar_volume: float) -> float:
        """
        Calculates volume-dependent quadratic market impact slippage.
        Slippage = base + impact * (order_volume / bar_volume)^2, bounded by max_slippage.
        """
        if order_quantity <= 0.0:
            return 0.0

        safe_volume = max(1.0, bar_volume)
        volume_ratio = order_quantity / safe_volume
        impact = self.slippage_impact_factor * (volume_ratio**2)
        total_slippage = self.base_slippage_pct + impact
        return min(self.max_slippage_pct, total_slippage)

    def execute_market_order(
        self,
        order: SimulatedOrder,
        bar_open: float,
        bar_volume: float,
        timestamp: datetime,
        spread_pct: float | None = None,
    ) -> ExecutionFill:
        """
        Executes a market order at Bar Open price adjusted for spread and slippage.
        Market orders incur taker commissions.
        """
        if bar_open <= 0.0:
            raise ValueError(f"Bar open price must be positive, got {bar_open}")

        effective_spread = self.default_spread_pct if spread_pct is None else max(0.0, spread_pct)
        half_spread = effective_spread / 2.0
        slippage_pct = self.calculate_slippage(order.quantity, bar_volume)

        if order.side == OrderSide.BUY:
            # Buyers pay ask: price marked up by half-spread and positive slippage
            fill_price = bar_open * (1.0 + half_spread) * (1.0 + slippage_pct)
        else:
            # Sellers receive bid: price marked down by half-spread and slippage
            fill_price = bar_open * (1.0 - half_spread) * (1.0 - slippage_pct)

        fill_price = max(0.00000001, fill_price)
        notional = fill_price * order.quantity
        fee_paid = notional * self.taker_fee_pct
        slippage_paid = abs(fill_price - bar_open) * order.quantity

        order.status = OrderStatus.FILLED
        order.fill_price = fill_price
        order.filled_at = timestamp
        order.fee_paid = fee_paid
        order.slippage_paid = slippage_paid

        return ExecutionFill(
            order_id=order.order_id,
            fill_price=fill_price,
            quantity=order.quantity,
            fee_paid=fee_paid,
            slippage_paid=slippage_paid,
            filled_at=timestamp,
            exit_reason=ExitReason.SIGNAL if order.side == OrderSide.SELL else None,
        )

    def check_intrabar_bracket(
        self,
        position: SimulatedPosition,
        bar_open: float,
        bar_high: float,
        bar_low: float,
        bar_volume: float,
        timestamp: datetime,
    ) -> ExecutionFill | None:
        """
        Evaluates whether an active position triggered a Stop-Loss or Take-Profit intrabar.
        Conservative assumption: If both SL and TP could trigger in the same candle,
        the Stop-Loss is assumed to trigger first.
        """
        if not position.is_open:
            return None

        hit_stop_loss = bar_low <= position.stop_loss
        hit_take_profit = position.take_profit is not None and bar_high >= position.take_profit

        if not hit_stop_loss and not hit_take_profit:
            return None

        # Conservative tie-breaking: stop-loss hit first
        if hit_stop_loss:
            exit_reason = ExitReason.STOP_LOSS
            # Gap handling: if bar opened below stop loss, execute at open or lower
            target_price = min(bar_open, position.stop_loss)
        else:
            exit_reason = ExitReason.TAKE_PROFIT
            assert position.take_profit is not None
            # Gap handling: if bar opened above take profit, execute at open or higher
            target_price = max(bar_open, position.take_profit)

        # Apply spread and slippage on exit execution
        half_spread = self.default_spread_pct / 2.0
        slippage_pct = self.calculate_slippage(position.quantity, bar_volume)

        # Position is LONG, so closing exit is SELL (paying bid)
        fill_price = target_price * (1.0 - half_spread) * (1.0 - slippage_pct)
        fill_price = max(0.00000001, fill_price)

        notional = fill_price * position.quantity
        fee_paid = notional * self.taker_fee_pct
        slippage_paid = abs(fill_price - target_price) * position.quantity

        return ExecutionFill(
            order_id=f"bracket_exit_{position.position_id}",
            fill_price=fill_price,
            quantity=position.quantity,
            fee_paid=fee_paid,
            slippage_paid=slippage_paid,
            filled_at=timestamp,
            exit_reason=exit_reason,
        )
