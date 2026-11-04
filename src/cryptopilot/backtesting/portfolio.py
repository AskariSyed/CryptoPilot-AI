"""
CryptoPilot AI - Simulated Portfolio & Risk Accounting Engine.
Manages cash, position ledger, monthly deposits ($10/month separation from trading PnL),
1% risk budget position sizing, 30% max allocation limit, and 2% daily loss circuit breaker.
"""

from datetime import UTC, date, datetime

from cryptopilot.backtesting.execution import ExecutionFill
from cryptopilot.backtesting.models import (
    EquityPoint,
    ExitReason,
    OrderSide,
    SimulatedPosition,
    Trade,
)


class SimulatedPortfolio:
    """
    Manages portfolio state, cash ledger, monthly contributions, and risk constraints.
    """

    def __init__(
        self,
        initial_capital: float = 30.0,
        monthly_contribution: float = 10.0,
        max_positions: int = 1,
        max_allocation_pct: float = 0.30,  # Max 30% of equity per position
        risk_budget_pct: float = 0.01,  # 1% equity risk per trade
        daily_loss_limit_pct: float = 0.02,  # 2% daily loss circuit breaker
        min_order_notional: float = 5.0,  # Minimum trade notional in USD
    ) -> None:
        if initial_capital <= 0.0:
            raise ValueError(f"Initial capital must be positive, got {initial_capital}")

        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.monthly_contribution = max(0.0, monthly_contribution)
        self.max_positions = max(1, max_positions)
        self.max_allocation_pct = min(1.0, max(0.01, max_allocation_pct))
        self.risk_budget_pct = min(0.10, max(0.001, risk_budget_pct))
        self.daily_loss_limit_pct = min(0.20, max(0.005, daily_loss_limit_pct))
        self.min_order_notional = max(0.0, min_order_notional)

        self.cumulative_deposits: float = 0.0
        self.positions: dict[str, SimulatedPosition] = {}  # symbol -> position
        self.trades: list[Trade] = []
        self.equity_curve: list[EquityPoint] = []
        self.peak_equity: float = initial_capital

        # Calendar tracking for monthly deposits and daily circuit breakers
        self._last_deposit_month: tuple[int, int] | None = None
        self._current_day: date | None = None
        self._daily_starting_equity: float = initial_capital
        self._circuit_breaker_active: bool = False
        self._next_position_id: int = 1
        self._next_trade_id: int = 1

    @property
    def total_equity(self) -> float:
        """Total portfolio equity = Cash + Current Market Value of Open Positions."""
        invested = sum(pos.quantity * pos.current_price for pos in self.positions.values())
        return self.cash + invested

    @property
    def net_trading_profit(self) -> float:
        """Genuinely earned trading profit = Total Equity - (Initial Capital + Cumulative Deposits)."""
        return self.total_equity - (self.initial_capital + self.cumulative_deposits)

    @property
    def is_circuit_breaker_active(self) -> bool:
        return self._circuit_breaker_active

    def check_calendar_events(self, timestamp: datetime) -> None:
        """
        Processes date-based events:
        1. Monthly deposits ($10 added at the start of each new month).
        2. Daily circuit breaker reset at 00:00 UTC.
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        # 1. Monthly contribution tracking
        current_month = (timestamp.year, timestamp.month)
        if self._last_deposit_month is None:
            self._last_deposit_month = current_month
        elif current_month > self._last_deposit_month:
            # Advance deposits for each elapsed month
            year_diff = timestamp.year - self._last_deposit_month[0]
            month_diff = timestamp.month - self._last_deposit_month[1]
            elapsed_months = year_diff * 12 + month_diff
            if elapsed_months > 0 and self.monthly_contribution > 0.0:
                deposit_amount = elapsed_months * self.monthly_contribution
                self.cash += deposit_amount
                self.cumulative_deposits += deposit_amount
            self._last_deposit_month = current_month

        # 2. Daily circuit breaker reset and monitoring
        current_date = timestamp.date()
        if self._current_day is None or current_date > self._current_day:
            self._current_day = current_date
            self._daily_starting_equity = self.total_equity
            self._circuit_breaker_active = False

        # Evaluate intraday daily drawdown against starting daily equity
        if self._daily_starting_equity > 0.0:
            daily_loss = (
                self._daily_starting_equity - self.total_equity
            ) / self._daily_starting_equity
            if daily_loss >= self.daily_loss_limit_pct:
                self._circuit_breaker_active = True

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        est_taker_fee_pct: float = 0.001,
    ) -> float:
        """
        Calculates position quantity adhering to:
        1. Risk budget: Max 1% equity loss if stop-loss is hit.
        2. Max allocation: Max 30% of total equity allocated to one position.
        3. Available cash: Cannot exceed cash balance.
        4. Minimum notional requirement: Returns 0.0 if notional < min_order_notional.
        """
        if entry_price <= 0.0 or stop_loss <= 0.0 or stop_loss >= entry_price:
            return 0.0

        if len(self.positions) >= self.max_positions:
            return 0.0

        if self._circuit_breaker_active:
            return 0.0

        equity = self.total_equity
        if equity <= 0.0 or self.cash <= 0.0:
            return 0.0

        # Risk budget sizing: Quantity = (Equity * RiskBudget) / (Distance + Fees)
        target_risk_dollars = equity * self.risk_budget_pct
        price_distance = abs(entry_price - stop_loss)
        fee_per_unit = entry_price * est_taker_fee_pct * 2.0  # entry + exit fee estimate
        risk_per_unit = price_distance + fee_per_unit

        if risk_per_unit <= 0.0:
            return 0.0

        raw_risk_quantity = target_risk_dollars / risk_per_unit

        # Max allocation cap (30% of equity)
        max_capital_for_pos = equity * self.max_allocation_pct
        max_alloc_quantity = max_capital_for_pos / entry_price

        # Available cash cap (accounting for entry fee buffer)
        max_cash_quantity = (self.cash * 0.998) / entry_price

        chosen_quantity = min(raw_risk_quantity, max_alloc_quantity, max_cash_quantity)
        notional = chosen_quantity * entry_price

        if notional < self.min_order_notional or chosen_quantity <= 0.0:
            return 0.0

        return chosen_quantity

    def open_position(
        self,
        symbol: str,
        fill: ExecutionFill,
        stop_loss: float,
        take_profit: float | None = None,
    ) -> SimulatedPosition | None:
        """
        Opens a position from a completed BUY execution fill.
        Deducts cash for purchase cost and fees.
        """
        total_cost = (fill.fill_price * fill.quantity) + fill.fee_paid
        if total_cost > self.cash:
            # Cannot fund fill
            return None

        self.cash -= total_cost
        pos_id = f"pos_{self._next_position_id}"
        self._next_position_id += 1

        position = SimulatedPosition(
            position_id=pos_id,
            symbol=symbol,
            side=OrderSide.BUY,
            entry_price=fill.fill_price,
            current_price=fill.fill_price,
            quantity=fill.quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_at=fill.filled_at,
            fees_paid=fill.fee_paid,
        )
        self.positions[symbol] = position
        return position

    def close_position(
        self,
        symbol: str,
        fill: ExecutionFill,
        bars_held: int = 0,
    ) -> Trade | None:
        """
        Closes an open position from an execution fill.
        Adds proceeds minus fees to cash and creates a completed Trade record.
        """
        position = self.positions.pop(symbol, None)
        if position is None:
            return None

        gross_proceeds = fill.fill_price * fill.quantity
        net_proceeds = gross_proceeds - fill.fee_paid
        self.cash += net_proceeds

        total_entry_cost = position.entry_price * fill.quantity
        gross_pnl = gross_proceeds - total_entry_cost
        total_fees = position.fees_paid + fill.fee_paid
        net_pnl = gross_pnl - total_fees
        return_pct = (net_pnl / total_entry_cost) * 100.0 if total_entry_cost > 0.0 else 0.0

        trade_id = f"trd_{self._next_trade_id}"
        self._next_trade_id += 1

        trade = Trade(
            trade_id=trade_id,
            symbol=symbol,
            side=position.side,
            entry_time=position.opened_at,
            exit_time=fill.filled_at,
            entry_price=position.entry_price,
            exit_price=fill.fill_price,
            quantity=fill.quantity,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            fees_paid=total_fees,
            exit_reason=fill.exit_reason or ExitReason.SIGNAL,
            return_pct=return_pct,
            bars_held=bars_held,
        )
        self.trades.append(trade)
        return trade

    def update_bar_prices(self, current_prices: dict[str, float]) -> None:
        """Updates current price for all open positions."""
        for symbol, pos in self.positions.items():
            if symbol in current_prices:
                price = current_prices[symbol]
                if price > 0.0:
                    pos.current_price = price
                    pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity

    def record_equity_snapshot(self, timestamp: datetime) -> EquityPoint:
        """Takes an equity snapshot and records it in the equity curve."""
        current_eq = self.total_equity
        if current_eq > self.peak_equity:
            self.peak_equity = current_eq

        drawdown = 0.0
        if self.peak_equity > 0.0:
            drawdown = max(0.0, (self.peak_equity - current_eq) / self.peak_equity) * 100.0

        invested = sum(pos.quantity * pos.current_price for pos in self.positions.values())
        point = EquityPoint(
            timestamp=timestamp,
            cash=self.cash,
            invested_value=invested,
            total_equity=current_eq,
            cumulative_deposits=self.cumulative_deposits,
            net_profit=self.net_trading_profit,
            drawdown_pct=drawdown,
        )
        self.equity_curve.append(point)
        return point
