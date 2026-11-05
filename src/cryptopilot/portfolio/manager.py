"""
CryptoPilot AI - Portfolio State & Compounding Manager.
Manages cash allocations, active positions, dynamic profit compounding,
and real-time mark-to-market equity calculations.
"""

from datetime import UTC, datetime

from cryptopilot.portfolio.ledger import ContributionLedger
from cryptopilot.portfolio.models import (
    AccountType,
    LedgerEntryType,
    PortfolioSummary,
    PositionSnapshot,
)


class PortfolioManager:
    """
    Central portfolio manager enforcing atomic balance accounting,
    automatic profit compounding, and transparent separation of deposits from trading gains.
    """

    def __init__(
        self,
        account_id: str = "small_account_01",
        account_type: AccountType = AccountType.SMALL_ACCOUNT,
        initial_capital: float = 30.0,
        monthly_contribution: float = 10.0,
    ) -> None:
        if initial_capital <= 0.0:
            raise ValueError(f"Initial capital must be strictly positive, got {initial_capital}")

        self.account_id = account_id
        self.account_type = account_type
        self.cash = initial_capital
        self.monthly_contribution = max(0.0, monthly_contribution)

        self.ledger = ContributionLedger(account_id=account_id)
        # Record initial capital deposit in ledger
        self.ledger.record_deposit(
            amount=initial_capital,
            balance_after=initial_capital,
            entry_type=LedgerEntryType.INITIAL_DEPOSIT,
            description=f"Initial capital funding for {account_type.value}",
        )

        self.positions: dict[str, PositionSnapshot] = {}
        self.peak_equity: float = initial_capital

    @property
    def total_equity(self) -> float:
        """
        Total liquidation value of portfolio: Cash + Current Market Value of Open Positions.
        """
        position_market_val = sum(pos.current_notional for pos in self.positions.values())
        return self.cash + position_market_val

    @property
    def available_cash(self) -> float:
        """Unencumbered liquid cash available for position deployment."""
        return self.cash

    @property
    def invested_capital(self) -> float:
        """Total capital deployed at entry cost across open positions."""
        return sum(pos.notional_cost for pos in self.positions.values())

    @property
    def unrealized_pnl(self) -> float:
        """Total floating unrealized profit or loss across all open positions."""
        return sum(pos.unrealized_pnl for pos in self.positions.values())

    @property
    def realized_pnl(self) -> float:
        """Cumulative net trading profit/loss realized from closed trades."""
        return self.ledger.total_realized_pnl

    @property
    def total_deposits(self) -> float:
        """Cumulative external capital contributed to date."""
        return self.ledger.total_deposits

    @property
    def drawdown_pct(self) -> float:
        """Current drawdown from peak equity expressed in [0.0, 1.0]."""
        if self.peak_equity <= 0.0:
            return 0.0
        dd = (self.peak_equity - self.total_equity) / self.peak_equity
        return max(0.0, min(1.0, dd))

    def deposit(
        self,
        amount: float,
        description: str = "",
        entry_type: LedgerEntryType = LedgerEntryType.MONTHLY_CONTRIBUTION,
        timestamp: datetime | None = None,
    ) -> float:
        """
        Processes an external cash deposit, crediting liquid cash and logging to ledger.
        Returns updated cash balance.
        """
        if amount <= 0.0:
            raise ValueError(f"Deposit amount must be strictly positive, got {amount}")

        ts = timestamp or datetime.now(UTC)
        self.cash += amount
        self.ledger.record_deposit(
            amount=amount,
            balance_after=self.cash,
            entry_type=entry_type,
            description=description or f"External capital injection: ${amount:,.2f}",
            timestamp=ts,
        )
        self._update_peak()
        return self.cash

    def check_monthly_contribution(self, current_time: datetime) -> bool:
        """
        Checks calendar month boundary and applies the scheduled monthly contribution if due.
        """
        applied, new_cash = self.ledger.check_and_apply_monthly_contribution(
            current_time=current_time,
            current_cash=self.cash,
            contribution_amount=self.monthly_contribution,
        )
        if applied:
            self.cash = new_cash
            self._update_peak()
        return applied

    def open_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float | None = None,
        fee: float = 0.0,
        timestamp: datetime | None = None,
    ) -> PositionSnapshot:
        """
        Opens a new spot position, deducting notional cost and commissions from cash.
        """
        if quantity <= 0.0 or entry_price <= 0.0:
            raise ValueError(f"Invalid position parameters: qty={quantity}, price={entry_price}")
        if symbol in self.positions:
            raise ValueError(
                f"Position for {symbol} already exists. Multi-position stacking prohibited."
            )

        notional_cost = quantity * entry_price
        total_required = notional_cost + fee

        if total_required > (self.cash + 1e-9):
            raise ValueError(
                f"Insufficient funds: required ${total_required:,.4f}, available cash ${self.cash:,.4f}"
            )

        ts = timestamp or datetime.now(UTC)

        # Deduct cash
        self.cash -= total_required

        if fee > 0.0:
            self.ledger.record_fee(
                amount=fee,
                balance_after=self.cash,
                description=f"Opening commission for {quantity:.6f} {symbol}",
                timestamp=ts,
            )

        pos = PositionSnapshot(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            notional_cost=notional_cost,
            current_notional=notional_cost,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            opened_at=ts,
        )
        self.positions[symbol] = pos
        self._update_peak()
        return pos

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        fee: float = 0.0,
        timestamp: datetime | None = None,
    ) -> float:
        """
        Closes an active position, realizes PnL, credits liquidation proceeds to cash,
        and automatically compounds net trading profits into subsequent equity.
        Returns realized PnL.
        """
        if symbol not in self.positions:
            raise ValueError(f"No active position for {symbol} to close.")
        if exit_price <= 0.0:
            raise ValueError(f"Exit price must be strictly positive, got {exit_price}")

        pos = self.positions.pop(symbol)
        ts = timestamp or datetime.now(UTC)

        exit_notional = pos.quantity * exit_price
        net_cash_returned = exit_notional - fee
        realized_pnl = (exit_notional - pos.notional_cost) - fee

        # Credit net liquidation proceeds back to liquid cash
        self.cash += net_cash_returned

        if fee > 0.0:
            self.ledger.record_fee(
                amount=fee,
                balance_after=self.cash,
                description=f"Closing commission for {pos.quantity:.6f} {symbol}",
                timestamp=ts,
            )

        self.ledger.record_trade_realized_pnl(
            amount=realized_pnl,
            balance_after=self.cash,
            description=f"Closed {pos.quantity:.6f} {symbol} at ${exit_price:,.2f}",
            timestamp=ts,
        )

        self._update_peak()
        return realized_pnl

    def update_mark_prices(
        self,
        prices: dict[str, float],
        timestamp: datetime | None = None,
    ) -> None:
        """
        Updates mark-to-market valuations and unrealized PnL for active positions.
        """
        for sym, pos in list(self.positions.items()):
            if sym in prices and prices[sym] > 0.0:
                current_p = prices[sym]
                curr_notional = pos.quantity * current_p
                unrealized = curr_notional - pos.notional_cost
                unrealized_pct = unrealized / pos.notional_cost if pos.notional_cost > 0.0 else 0.0

                self.positions[sym] = PositionSnapshot(
                    position_id=pos.position_id,
                    symbol=sym,
                    quantity=pos.quantity,
                    entry_price=pos.entry_price,
                    current_price=current_p,
                    stop_loss_price=pos.stop_loss_price,
                    take_profit_price=pos.take_profit_price,
                    notional_cost=pos.notional_cost,
                    current_notional=curr_notional,
                    unrealized_pnl=unrealized,
                    unrealized_pnl_pct=unrealized_pct,
                    opened_at=pos.opened_at,
                )

        self._update_peak()

    def get_summary(self, current_time: datetime | None = None) -> PortfolioSummary:
        """
        Assembles comprehensive real-time balance and performance statistics.
        """
        ts = current_time or datetime.now(UTC)
        total_dep = self.total_deposits
        tot_eq = self.total_equity
        net_prof = tot_eq - total_dep
        ret_pct = (net_prof / total_dep) if total_dep > 0.0 else 0.0

        return PortfolioSummary(
            account_id=self.account_id,
            account_type=self.account_type,
            cash=self.cash,
            invested_capital=self.invested_capital,
            unrealized_pnl=self.unrealized_pnl,
            total_equity=tot_eq,
            total_deposits=total_dep,
            realized_pnl=self.realized_pnl,
            net_profit=net_prof,
            return_on_deposits_pct=ret_pct,
            active_positions_count=len(self.positions),
            peak_equity=self.peak_equity,
            drawdown_pct=self.drawdown_pct,
            timestamp=ts,
        )

    def _update_peak(self) -> None:
        """Updates highest equity mark achieved."""
        eq = self.total_equity
        if eq > self.peak_equity:
            self.peak_equity = eq
