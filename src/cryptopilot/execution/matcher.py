"""
CryptoPilot AI - Virtual Order Matching Engine.
Simulates realistic exchange order fills against public ticker and candle data,
incorporating bid/ask spreads, non-linear volume slippage, maker/taker fees,
and strict intrabar stop-loss priority resolution.
"""

from datetime import UTC, datetime

from cryptopilot.data.models import Candle, Ticker
from cryptopilot.execution.models import (
    BracketOrder,
    OrderSide,
    OrderStatus,
    VirtualFill,
    VirtualOrder,
)


class OrderMatcher:
    """
    Simulates exchange execution mechanics: spreads, slippage, and candle matching.
    """

    def __init__(
        self,
        taker_fee_rate: float = 0.0010,  # 0.10% taker fee
        maker_fee_rate: float = 0.0005,  # 0.05% maker fee
        base_slippage: float = 0.0002,  # 0.02% base slippage
        impact_factor: float = 0.05,  # Quadratic volume impact factor
        reference_volume: float = 100000.0,  # Reference pool liquidity in USD
        max_slippage: float = 0.02,  # 2.0% maximum slippage cap
        default_half_spread_pct: float = 0.00025,  # 0.025% half-spread
    ) -> None:
        self.taker_fee_rate = max(0.0, taker_fee_rate)
        self.maker_fee_rate = max(0.0, maker_fee_rate)
        self.base_slippage = max(0.0, base_slippage)
        self.impact_factor = max(0.0, impact_factor)
        self.reference_volume = max(0.0, reference_volume)
        self.max_slippage = max(0.0, max_slippage)
        self.default_half_spread_pct = max(0.0, default_half_spread_pct)

    def calculate_slippage_rate(self, notional: float) -> float:
        """
        Computes non-linear volume-dependent slippage:
        slippage = base_slippage + impact_factor * (notional / reference_volume)^2
        """
        if self.reference_volume <= 0.0:
            return self.base_slippage
        volume_ratio = notional / self.reference_volume
        rate = self.base_slippage + self.impact_factor * (volume_ratio**2)
        return min(self.max_slippage, max(0.0, rate))

    def match_market_order(
        self,
        order: VirtualOrder,
        reference_price: float,
        ticker: Ticker | None = None,
        timestamp: datetime | None = None,
    ) -> VirtualFill:
        """
        Matches a MARKET order immediately against best bid/ask and slippage.
        """
        if order.status not in (OrderStatus.PENDING, OrderStatus.SUBMITTED):
            raise ValueError(f"Cannot match order in status {order.status.value}")
        if reference_price <= 0.0:
            raise ValueError(f"Invalid reference price: {reference_price}")

        ts = timestamp or datetime.now(UTC)
        raw_notional = order.quantity * reference_price
        slip_rate = self.calculate_slippage_rate(raw_notional)

        # Spread handling
        if ticker is not None and ticker.bid > 0 and ticker.ask > 0:
            if order.side == OrderSide.BUY:
                base_exec_price = ticker.ask
            else:
                base_exec_price = ticker.bid
        else:
            half_spread = reference_price * self.default_half_spread_pct
            if order.side == OrderSide.BUY:
                base_exec_price = reference_price + half_spread
            else:
                base_exec_price = reference_price - half_spread

        # Slippage application
        if order.side == OrderSide.BUY:
            fill_price = base_exec_price * (1.0 + slip_rate)
        else:
            fill_price = base_exec_price * (1.0 - slip_rate)

        fill_price = round(fill_price, 4)
        actual_notional = round(order.quantity * fill_price, 4)
        slippage_cost = round(abs(fill_price - reference_price) * order.quantity, 4)
        fee = round(actual_notional * self.taker_fee_rate, 4)

        # Update order state
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.remaining_quantity = 0.0
        order.average_fill_price = fill_price
        order.fee_paid = fee
        order.slippage_paid = slippage_cost
        order.updated_at = ts

        return VirtualFill(
            order_id=order.order_id,
            account_id=order.account_id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=order.quantity,
            notional=actual_notional,
            fee=fee,
            fee_rate=self.taker_fee_rate,
            slippage_rate=slip_rate,
            slippage_cost=slippage_cost,
            timestamp=ts,
        )

    def match_limit_order(
        self,
        order: VirtualOrder,
        candle: Candle,
        timestamp: datetime | None = None,
    ) -> VirtualFill | None:
        """
        Matches a LIMIT order against OHLC candle extremes.
        """
        if order.status not in (OrderStatus.PENDING, OrderStatus.SUBMITTED):
            return None
        if order.price is None or order.price <= 0.0:
            return None

        ts = timestamp or candle.timestamp

        if order.side == OrderSide.BUY:
            # BUY Limit fills if candle low drops to or below order price
            if candle.low <= order.price:
                # Execution price: favorable gap down takes candle.open, otherwise limit price
                fill_price = (
                    min(order.price, candle.open) if candle.open <= order.price else order.price
                )
                fill_notional = round(order.quantity * fill_price, 4)
                fee = round(fill_notional * self.maker_fee_rate, 4)

                order.status = OrderStatus.FILLED
                order.filled_quantity = order.quantity
                order.remaining_quantity = 0.0
                order.average_fill_price = fill_price
                order.fee_paid = fee
                order.slippage_paid = 0.0
                order.updated_at = ts

                return VirtualFill(
                    order_id=order.order_id,
                    account_id=order.account_id,
                    symbol=order.symbol,
                    side=order.side,
                    price=fill_price,
                    quantity=order.quantity,
                    notional=fill_notional,
                    fee=fee,
                    fee_rate=self.maker_fee_rate,
                    slippage_rate=0.0,
                    slippage_cost=0.0,
                    timestamp=ts,
                )

        elif order.side == OrderSide.SELL:
            # SELL Limit fills if candle high rises to or above order price
            if candle.high >= order.price:
                fill_price = (
                    max(order.price, candle.open) if candle.open >= order.price else order.price
                )
                fill_notional = round(order.quantity * fill_price, 4)
                fee = round(fill_notional * self.maker_fee_rate, 4)

                order.status = OrderStatus.FILLED
                order.filled_quantity = order.quantity
                order.remaining_quantity = 0.0
                order.average_fill_price = fill_price
                order.fee_paid = fee
                order.slippage_paid = 0.0
                order.updated_at = ts

                return VirtualFill(
                    order_id=order.order_id,
                    account_id=order.account_id,
                    symbol=order.symbol,
                    side=order.side,
                    price=fill_price,
                    quantity=order.quantity,
                    notional=fill_notional,
                    fee=fee,
                    fee_rate=self.maker_fee_rate,
                    slippage_rate=0.0,
                    slippage_cost=0.0,
                    timestamp=ts,
                )

        return None

    def evaluate_bracket_triggers(
        self,
        bracket: BracketOrder,
        candle: Candle,
        timestamp: datetime | None = None,
    ) -> tuple[str | None, VirtualFill | None]:
        """
        Evaluates Stop-Loss and Take-Profit triggers against candle extremes.
        Strict Priority Invariant: On dual-touch candles (extreme volatility where both
        SL and TP are touched), Stop-Loss is ALWAYS executed first to protect capital!
        Returns (exit_reason: 'STOP_LOSS' | 'TAKE_PROFIT' | None, fill: VirtualFill | None).
        """
        if not bracket.is_active:
            return None, None

        ts = timestamp or candle.timestamp
        sl_order = bracket.stop_loss_order
        tp_order = bracket.take_profit_order

        sl_triggered = False
        tp_triggered = False

        if sl_order is not None and sl_order.stop_price is not None:
            # For LONG positions, SL triggers if low <= stop_price
            if candle.low <= sl_order.stop_price:
                sl_triggered = True

        if tp_order is not None and tp_order.stop_price is not None:
            # For LONG positions, TP triggers if high >= take_profit_price
            if candle.high >= tp_order.stop_price:
                tp_triggered = True

        # Priority Check: Stop Loss beats Take Profit on dual touch
        if sl_triggered:
            assert sl_order is not None and sl_order.stop_price is not None
            # Execute stop loss (market order at stop_price or gap down open)
            exec_price = (
                min(sl_order.stop_price, candle.open)
                if candle.open <= sl_order.stop_price
                else sl_order.stop_price
            )
            fill = self.match_market_order(
                order=sl_order,
                reference_price=exec_price,
                timestamp=ts,
            )
            bracket.is_active = False
            bracket.exit_reason = "STOP_LOSS"
            bracket.closed_at = ts
            if tp_order is not None:
                tp_order.status = OrderStatus.CANCELED
                tp_order.updated_at = ts
            return "STOP_LOSS", fill

        elif tp_triggered:
            assert tp_order is not None and tp_order.stop_price is not None
            # Execute take profit (limit/market order at target price or gap up open)
            exec_price = (
                max(tp_order.stop_price, candle.open)
                if candle.open >= tp_order.stop_price
                else tp_order.stop_price
            )
            fill = self.match_market_order(
                order=tp_order,
                reference_price=exec_price,
                timestamp=ts,
            )
            bracket.is_active = False
            bracket.exit_reason = "TAKE_PROFIT"
            bracket.closed_at = ts
            if sl_order is not None:
                sl_order.status = OrderStatus.CANCELED
                sl_order.updated_at = ts
            return "TAKE_PROFIT", fill

        return None, None
