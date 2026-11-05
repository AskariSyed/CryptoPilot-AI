"""
CryptoPilot AI - Quantitative Circuit Breakers & Emergency Protocols.
Enforces the 2% daily loss limit (calculated on starting daily equity),
consecutive loss cooldown, and manual/automated emergency halt switches.
"""

from datetime import UTC, date, datetime, timedelta

from cryptopilot.risk.models import CircuitBreakerState


class CircuitBreaker:
    """
    Monitors daily portfolio drawdown and consecutive trade failures.
    Halts autonomous order generation immediately upon breach of risk thresholds.
    """

    def __init__(
        self,
        daily_loss_limit_pct: float = 0.02,  # 2.0% max daily loss on starting equity
        max_consecutive_losses: int = 3,  # 3 consecutive losses trigger 12h cooldown
        cooldown_hours: float = 12.0,  # 12 hours pause after consecutive loss threshold
    ) -> None:
        if daily_loss_limit_pct <= 0.0 or daily_loss_limit_pct > 0.20:
            raise ValueError(
                f"daily_loss_limit_pct must be in (0.0, 0.20], got {daily_loss_limit_pct}"
            )
        if max_consecutive_losses < 1:
            raise ValueError(f"max_consecutive_losses must be >= 1, got {max_consecutive_losses}")

        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_hours = max(1.0, cooldown_hours)

        self._current_date: date | None = None
        self._starting_daily_equity: float = 0.0
        self._is_tripped: bool = False
        self._trip_reason: str | None = None
        self._tripped_at: datetime | None = None
        self._resets_at: datetime | None = None
        self._consecutive_losses: int = 0
        self._emergency_stop: bool = False

    def update_daily_equity(
        self,
        current_equity: float,
        current_time: datetime | None = None,
    ) -> None:
        """
        Snapshots daily starting equity at 00:00:00 UTC and checks for 2% daily loss breach.
        """
        ts = current_time or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        current_day = ts.date()

        # New UTC calendar day rollover
        if self._current_date != current_day:
            self._current_date = current_day
            self._starting_daily_equity = current_equity
            # If previously tripped due to daily limit, reset for the new day
            if self._is_tripped and not self._emergency_stop:
                if self._trip_reason and "daily loss" in self._trip_reason.lower():
                    self._is_tripped = False
                    self._trip_reason = None
                    self._tripped_at = None
                    self._resets_at = None

        if self._starting_daily_equity <= 0.0:
            self._starting_daily_equity = current_equity

        # Evaluate daily loss
        if not self._is_tripped and not self._emergency_stop:
            daily_loss = self._starting_daily_equity - current_equity
            max_allowed_loss = self._starting_daily_equity * self.daily_loss_limit_pct

            if daily_loss >= max_allowed_loss:
                # 2% Daily Loss Limit Breached!
                self._is_tripped = True
                self._tripped_at = ts
                # Calculate next midnight UTC for reset
                next_midnight = datetime(
                    ts.year, ts.month, ts.day, 0, 0, 0, tzinfo=UTC
                ) + timedelta(days=1)
                self._resets_at = next_midnight
                self._trip_reason = (
                    f"Daily loss limit (2.0%) reached: lost ${daily_loss:,.2f} "
                    f"({(daily_loss / self._starting_daily_equity):.2%} of starting ${self._starting_daily_equity:,.2f}). "
                    f"Trading halted until {next_midnight.isoformat()}."
                )

    def record_trade_result(
        self,
        realized_pnl: float,
        current_time: datetime | None = None,
    ) -> None:
        """
        Updates consecutive loss count and triggers cooldown if threshold is reached.
        """
        ts = current_time or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        if realized_pnl < 0.0:
            self._consecutive_losses += 1
            if (
                self._consecutive_losses >= self.max_consecutive_losses
                and not self._is_tripped
                and not self._emergency_stop
            ):
                self._is_tripped = True
                self._tripped_at = ts
                self._resets_at = ts + timedelta(hours=self.cooldown_hours)
                self._trip_reason = (
                    f"Consecutive loss limit ({self.max_consecutive_losses}) reached. "
                    f"Mandatory cooldown active for {self.cooldown_hours:.1f} hours until {self._resets_at.isoformat()}."
                )
        else:
            # Positive or zero trade resets consecutive losses
            self._consecutive_losses = 0

    def trigger_emergency_stop(self, reason: str = "Manual emergency stop triggered") -> None:
        """Immediately halts all trading operations until manually reset."""
        self._emergency_stop = True
        self._is_tripped = True
        self._tripped_at = datetime.now(UTC)
        self._resets_at = None
        self._trip_reason = f"EMERGENCY HALT: {reason}"

    def reset_emergency_stop(self) -> None:
        """Clears emergency stop and restores normal trading state."""
        self._emergency_stop = False
        self._is_tripped = False
        self._trip_reason = None
        self._tripped_at = None
        self._resets_at = None

    def is_active(self, current_time: datetime | None = None) -> bool:
        """
        Returns True if trading is currently halted by any circuit breaker.
        Automatically clears expired time-based cooldowns.
        """
        if self._emergency_stop:
            return True

        if not self._is_tripped:
            return False

        ts = current_time or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        # Check if time-based reset has arrived
        if self._resets_at is not None and ts >= self._resets_at:
            self._is_tripped = False
            self._trip_reason = None
            self._tripped_at = None
            self._resets_at = None
            return False

        return True

    def get_state(
        self,
        current_equity: float,
        current_time: datetime | None = None,
    ) -> CircuitBreakerState:
        """Returns comprehensive state telemetry for monitoring and UI."""
        ts = current_time or datetime.now(UTC)
        active = self.is_active(current_time=ts)

        daily_loss = max(0.0, self._starting_daily_equity - current_equity)
        loss_pct = (
            daily_loss / self._starting_daily_equity if self._starting_daily_equity > 0.0 else 0.0
        )

        return CircuitBreakerState(
            is_tripped=active,
            trip_reason=self._trip_reason if active else None,
            tripped_at=self._tripped_at,
            resets_at=self._resets_at,
            starting_daily_equity=self._starting_daily_equity,
            current_daily_loss=daily_loss,
            daily_loss_pct=loss_pct,
            consecutive_losses=self._consecutive_losses,
            emergency_stop=self._emergency_stop,
            timestamp=ts,
        )
