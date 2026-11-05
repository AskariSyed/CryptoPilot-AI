"""
CryptoPilot AI - Virtual Paper Trading Broker.
Provides a completely isolated, realistic exchange simulation layer supporting
micro-capital ($30) and research ($10,000) accounts with zero live-exchange order routing.
"""

from datetime import UTC, datetime
from typing import Any

from cryptopilot.data.models import Candle, Ticker
from cryptopilot.execution.matcher import OrderMatcher
from cryptopilot.execution.models import (
    BracketOrder,
    ExecutionAuditEvent,
    OrderSide,
    OrderStatus,
    OrderType,
    VirtualFill,
    VirtualOrder,
)
from cryptopilot.portfolio.manager import PortfolioManager
from cryptopilot.portfolio.models import AccountType
from cryptopilot.risk.models import SizedOrderProposal


class PaperBroker:
    """
    Simulated exchange broker executing virtual orders with sub-millisecond precision,
    strict account balance isolation, bracket order management, and complete audit trails.
    """

    def __init__(
        self,
        matcher: OrderMatcher | None = None,
        small_account_capital: float = 30.0,
        small_account_contribution: float = 10.0,
        research_capital: float = 10000.0,
    ) -> None:
        self.matcher = matcher or OrderMatcher()

        # Strict Account Isolation
        self._portfolios: dict[str, PortfolioManager] = {
            "small_account_01": PortfolioManager(
                account_id="small_account_01",
                account_type=AccountType.SMALL_ACCOUNT,
                initial_capital=small_account_capital,
                monthly_contribution=small_account_contribution,
            ),
            "research_lab_01": PortfolioManager(
                account_id="research_lab_01",
                account_type=AccountType.RESEARCH,
                initial_capital=research_capital,
                monthly_contribution=0.0,
            ),
        }

        # Order storage
        self._orders: dict[str, VirtualOrder] = {}
        self._active_brackets: dict[str, BracketOrder] = {}
        self._audit_log: list[ExecutionAuditEvent] = []

    def get_portfolio(self, account_id: str = "small_account_01") -> PortfolioManager:
        """Returns the isolated PortfolioManager for the specified account."""
        if account_id not in self._portfolios:
            raise KeyError(f"Account '{account_id}' does not exist.")
        return self._portfolios[account_id]

    def submit_order(
        self,
        order: VirtualOrder,
        reference_price: float,
        ticker: Ticker | None = None,
        timestamp: datetime | None = None,
    ) -> VirtualOrder:
        """
        Submits and processes a VirtualOrder.
        Market orders match immediately; limit orders enter the virtual order book.
        """
        ts = timestamp or datetime.now(UTC)
        pm = self.get_portfolio(order.account_id)

        # Store order
        self._orders[order.order_id] = order
        order.status = OrderStatus.SUBMITTED
        order.updated_at = ts

        self._record_audit_event(
            account_id=order.account_id,
            event_type="ORDER_SUBMITTED",
            order_id=order.order_id,
            symbol=order.symbol,
            details={
                "side": order.side.value,
                "order_type": order.order_type.value,
                "quantity": order.quantity,
                "price": order.price,
            },
            timestamp=ts,
        )

        if order.order_type == OrderType.MARKET:
            # Immediate fill
            fill = self.matcher.match_market_order(
                order=order,
                reference_price=reference_price,
                ticker=ticker,
                timestamp=ts,
            )

            # Update portfolio balances
            if order.side == OrderSide.BUY:
                pm.open_position(
                    symbol=order.symbol,
                    quantity=fill.quantity,
                    entry_price=fill.price,
                    stop_loss_price=order.stop_price or (fill.price * 0.95),
                    fee=fill.fee,
                    timestamp=ts,
                )
            elif order.side == OrderSide.SELL:
                if order.symbol in pm.positions:
                    pm.close_position(
                        symbol=order.symbol,
                        exit_price=fill.price,
                        fee=fill.fee,
                        timestamp=ts,
                    )

            self._record_audit_event(
                account_id=order.account_id,
                event_type="ORDER_FILLED",
                order_id=order.order_id,
                symbol=order.symbol,
                details={
                    "fill_id": fill.fill_id,
                    "fill_price": fill.price,
                    "quantity": fill.quantity,
                    "notional": fill.notional,
                    "fee": fill.fee,
                    "slippage_cost": fill.slippage_cost,
                },
                timestamp=ts,
            )

        return order

    def submit_bracket(
        self,
        proposal: SizedOrderProposal,
        account_id: str = "small_account_01",
        reference_price: float | None = None,
        ticker: Ticker | None = None,
        timestamp: datetime | None = None,
    ) -> BracketOrder:
        """
        Submits a risk-approved SizedOrderProposal as a linked BracketOrder.
        Executes the entry MARKET BUY, then sets up simultaneous virtual Stop-Loss
        and Take-Profit triggers.
        """
        ts = timestamp or datetime.now(UTC)
        entry_p = reference_price or proposal.entry_price

        # 1. Create and execute Entry Order
        entry_order = VirtualOrder(
            account_id=account_id,
            symbol=proposal.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=proposal.quantity,
            stop_price=proposal.stop_loss_price,
            remaining_quantity=proposal.quantity,
            created_at=ts,
            updated_at=ts,
        )

        self.submit_order(
            order=entry_order,
            reference_price=entry_p,
            ticker=ticker,
            timestamp=ts,
        )

        actual_entry_price = entry_order.average_fill_price or entry_p

        # 2. Spawn Stop-Loss Virtual Order
        sl_order = VirtualOrder(
            account_id=account_id,
            symbol=proposal.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.STOP_LOSS,
            quantity=entry_order.filled_quantity,
            stop_price=proposal.stop_loss_price,
            remaining_quantity=entry_order.filled_quantity,
            status=OrderStatus.SUBMITTED,
            created_at=ts,
            updated_at=ts,
        )
        self._orders[sl_order.order_id] = sl_order

        # 3. Spawn Take-Profit Virtual Order (if configured)
        tp_order: VirtualOrder | None = None
        if proposal.take_profit_price is not None:
            tp_order = VirtualOrder(
                account_id=account_id,
                symbol=proposal.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.TAKE_PROFIT,
                quantity=entry_order.filled_quantity,
                stop_price=proposal.take_profit_price,
                remaining_quantity=entry_order.filled_quantity,
                status=OrderStatus.SUBMITTED,
                created_at=ts,
                updated_at=ts,
            )
            self._orders[tp_order.order_id] = tp_order

        bracket = BracketOrder(
            account_id=account_id,
            symbol=proposal.symbol,
            entry_order=entry_order,
            stop_loss_order=sl_order,
            take_profit_order=tp_order,
            is_active=True,
            created_at=ts,
        )
        self._active_brackets[bracket.bracket_id] = bracket

        self._record_audit_event(
            account_id=account_id,
            event_type="BRACKET_OPENED",
            order_id=entry_order.order_id,
            symbol=proposal.symbol,
            details={
                "bracket_id": bracket.bracket_id,
                "entry_price": actual_entry_price,
                "stop_loss_price": proposal.stop_loss_price,
                "take_profit_price": proposal.take_profit_price,
                "quantity": entry_order.filled_quantity,
            },
            timestamp=ts,
        )

        return bracket

    def process_candle(
        self,
        candle: Candle,
        timestamp: datetime | None = None,
    ) -> list[VirtualFill]:
        """
        Processes candle prices against all pending limit orders and active brackets.
        Updates portfolio mark prices and returns any execution fills generated.
        """
        ts = timestamp or candle.timestamp
        fills: list[VirtualFill] = []

        # 1. Process pending limit orders
        for order in list(self._orders.values()):
            if (
                order.symbol == candle.symbol
                and order.status == OrderStatus.SUBMITTED
                and order.order_type == OrderType.LIMIT
            ):
                fill = self.matcher.match_limit_order(order=order, candle=candle, timestamp=ts)
                if fill is not None:
                    fills.append(fill)
                    pm = self.get_portfolio(order.account_id)
                    if order.side == OrderSide.BUY:
                        pm.open_position(
                            symbol=order.symbol,
                            quantity=fill.quantity,
                            entry_price=fill.price,
                            stop_loss_price=order.stop_price or (fill.price * 0.95),
                            fee=fill.fee,
                            timestamp=ts,
                        )
                    else:
                        if order.symbol in pm.positions:
                            pm.close_position(
                                symbol=order.symbol,
                                exit_price=fill.price,
                                fee=fill.fee,
                                timestamp=ts,
                            )
                    self._record_audit_event(
                        account_id=order.account_id,
                        event_type="ORDER_FILLED",
                        order_id=order.order_id,
                        symbol=order.symbol,
                        details={
                            "fill_price": fill.price,
                            "quantity": fill.quantity,
                            "fee": fill.fee,
                        },
                        timestamp=ts,
                    )

        # 2. Process active brackets (Stop-Loss and Take-Profit monitoring)
        for b_id, bracket in list(self._active_brackets.items()):
            if bracket.symbol == candle.symbol and bracket.is_active:
                exit_reason, fill = self.matcher.evaluate_bracket_triggers(
                    bracket=bracket,
                    candle=candle,
                    timestamp=ts,
                )
                if fill is not None:
                    fills.append(fill)
                    pm = self.get_portfolio(bracket.account_id)
                    # Close position in portfolio
                    if bracket.symbol in pm.positions:
                        pm.close_position(
                            symbol=bracket.symbol,
                            exit_price=fill.price,
                            fee=fill.fee,
                            timestamp=ts,
                        )

                    # Remove from active brackets
                    self._active_brackets.pop(b_id, None)

                    self._record_audit_event(
                        account_id=bracket.account_id,
                        event_type=f"BRACKET_{exit_reason}_TRIGGERED",
                        order_id=fill.order_id,
                        symbol=bracket.symbol,
                        details={
                            "bracket_id": b_id,
                            "exit_reason": exit_reason,
                            "exit_price": fill.price,
                            "quantity": fill.quantity,
                            "fee": fill.fee,
                        },
                        timestamp=ts,
                    )

        # 3. Update mark prices on all portfolios holding this symbol
        for pm in self._portfolios.values():
            if candle.symbol in pm.positions:
                pm.update_mark_prices({candle.symbol: candle.close}, timestamp=ts)

        return fills

    def cancel_order(self, order_id: str, reason: str = "") -> VirtualOrder:
        """Cancels a pending or submitted virtual order."""
        if order_id not in self._orders:
            raise KeyError(f"Order '{order_id}' not found.")

        order = self._orders[order_id]
        if order.status in (OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED):
            raise ValueError(f"Cannot cancel order in status '{order.status.value}'.")

        order.status = OrderStatus.CANCELED
        order.updated_at = datetime.now(UTC)
        order.rejection_reason = reason or "Manually canceled"

        self._record_audit_event(
            account_id=order.account_id,
            event_type="ORDER_CANCELED",
            order_id=order.order_id,
            symbol=order.symbol,
            details={"reason": order.rejection_reason},
        )
        return order

    def cancel_all_orders(self, account_id: str, symbol: str | None = None) -> int:
        """Cancels all active orders for an account and optional symbol."""
        count = 0
        for order in list(self._orders.values()):
            if order.account_id == account_id and order.status in (
                OrderStatus.PENDING,
                OrderStatus.SUBMITTED,
            ):
                if symbol is None or order.symbol == symbol:
                    self.cancel_order(order.order_id, reason="Batch cancel all orders")
                    count += 1
        return count

    def get_order(self, order_id: str) -> VirtualOrder | None:
        """Fetches order by UUID."""
        return self._orders.get(order_id)

    def get_open_orders(
        self, account_id: str = "small_account_01", symbol: str | None = None
    ) -> list[VirtualOrder]:
        """Returns list of all active pending/submitted orders."""
        return [
            o
            for o in self._orders.values()
            if o.account_id == account_id
            and o.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED)
            and (symbol is None or o.symbol == symbol)
        ]

    def get_active_brackets(
        self, account_id: str = "small_account_01", symbol: str | None = None
    ) -> list[BracketOrder]:
        """Returns list of active BracketOrder instances."""
        return [
            b
            for b in self._active_brackets.values()
            if b.account_id == account_id and b.is_active and (symbol is None or b.symbol == symbol)
        ]

    def get_audit_log(
        self, account_id: str | None = None, limit: int = 100
    ) -> list[ExecutionAuditEvent]:
        """Returns chronological audit log events."""
        events = [e for e in self._audit_log if account_id is None or e.account_id == account_id]
        return events[-limit:]

    def _record_audit_event(
        self,
        account_id: str,
        event_type: str,
        symbol: str,
        order_id: str | None = None,
        details: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> ExecutionAuditEvent:
        """Appends an immutable audit event to the internal ledger."""
        ts = timestamp or datetime.now(UTC)
        event = ExecutionAuditEvent(
            account_id=account_id,
            event_type=event_type,
            order_id=order_id,
            symbol=symbol,
            details=details or {},
            timestamp=ts,
        )
        self._audit_log.append(event)
        return event
