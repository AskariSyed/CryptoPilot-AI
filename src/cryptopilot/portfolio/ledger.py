"""
CryptoPilot AI - Contribution Ledger & Capital Accounting.
Maintains an immutable double-entry style audit log isolating external deposits
($10/month contributions) from organic trading profit and loss.
"""

from datetime import UTC, datetime

from cryptopilot.portfolio.models import LedgerEntry, LedgerEntryType


class ContributionLedger:
    """
    Manages cash ledger transactions, deposits, and contribution schedule tracking.
    """

    def __init__(self, account_id: str) -> None:
        self.account_id = account_id
        self._entries: list[LedgerEntry] = []
        self._total_deposits: float = 0.0
        self._total_realized_pnl: float = 0.0
        self._total_fees_paid: float = 0.0
        self._last_contribution_month: tuple[int, int] | None = None  # (year, month)

    @property
    def total_deposits(self) -> float:
        """Total cumulative external capital contributed (initial + monthly)."""
        return self._total_deposits

    @property
    def total_realized_pnl(self) -> float:
        """Total cumulative net trading profit and loss from closed positions."""
        return self._total_realized_pnl

    @property
    def total_fees_paid(self) -> float:
        """Total cumulative transaction and exchange commissions paid."""
        return self._total_fees_paid

    @property
    def entries(self) -> list[LedgerEntry]:
        """Returns a copy of all immutable transaction entries in chronological order."""
        return list(self._entries)

    def record_deposit(
        self,
        amount: float,
        balance_after: float,
        entry_type: LedgerEntryType = LedgerEntryType.INITIAL_DEPOSIT,
        description: str = "",
        timestamp: datetime | None = None,
    ) -> LedgerEntry:
        """Records an external capital deposit (initial or monthly contribution)."""
        if amount <= 0.0:
            raise ValueError(f"Deposit amount must be strictly positive, got {amount}")

        ts = timestamp or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        entry = LedgerEntry(
            account_id=self.account_id,
            entry_type=entry_type,
            amount=amount,
            balance_after=balance_after,
            description=description or f"Capital injection: {entry_type.value}",
            timestamp=ts,
        )
        self._entries.append(entry)
        self._total_deposits += amount

        # Track contribution month if it was a monthly contribution
        if entry_type == LedgerEntryType.MONTHLY_CONTRIBUTION:
            self._last_contribution_month = (ts.year, ts.month)

        return entry

    def record_trade_realized_pnl(
        self,
        amount: float,
        balance_after: float,
        description: str = "",
        timestamp: datetime | None = None,
    ) -> LedgerEntry:
        """Records realized gain or loss resulting from a closed market position."""
        ts = timestamp or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        entry = LedgerEntry(
            account_id=self.account_id,
            entry_type=LedgerEntryType.TRADE_REALIZED_PNL,
            amount=amount,
            balance_after=balance_after,
            description=description or f"Trade realized PnL: ${amount:+,.4f}",
            timestamp=ts,
        )
        self._entries.append(entry)
        self._total_realized_pnl += amount
        return entry

    def record_fee(
        self,
        amount: float,
        balance_after: float,
        description: str = "",
        timestamp: datetime | None = None,
    ) -> LedgerEntry:
        """Records commission or slippage fee deduction."""
        if amount <= 0.0:
            raise ValueError(f"Fee amount must be positive, got {amount}")

        ts = timestamp or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        entry = LedgerEntry(
            account_id=self.account_id,
            entry_type=LedgerEntryType.FEE_DEDUCTION,
            amount=-amount,
            balance_after=balance_after,
            description=description or f"Commission deduction: -${amount:,.4f}",
            timestamp=ts,
        )
        self._entries.append(entry)
        self._total_fees_paid += amount
        return entry

    def check_and_apply_monthly_contribution(
        self,
        current_time: datetime,
        current_cash: float,
        contribution_amount: float = 10.0,
    ) -> tuple[bool, float]:
        """
        Evaluates whether a new calendar month has elapsed since the last contribution.
        If a new month has arrived and monthly contributions are configured (> 0),
        records the deposit and returns (True, new_cash_balance).
        Otherwise returns (False, current_cash).
        """
        if contribution_amount <= 0.0:
            return False, current_cash

        ts = current_time
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        current_month = (ts.year, ts.month)
        if self._last_contribution_month is None:
            # First month initial state: record current month as initialized
            self._last_contribution_month = current_month
            return False, current_cash

        if current_month > self._last_contribution_month:
            # Rollover into new calendar month!
            new_cash = current_cash + contribution_amount
            self.record_deposit(
                amount=contribution_amount,
                balance_after=new_cash,
                entry_type=LedgerEntryType.MONTHLY_CONTRIBUTION,
                description=f"Automated recurring monthly contribution for {ts.year}-{ts.month:02d}",
                timestamp=ts,
            )
            self._last_contribution_month = current_month
            return True, new_cash

        return False, current_cash
