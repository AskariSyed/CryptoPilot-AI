"""
CryptoPilot AI - Exponential Time-Decay Calculator.
Applies exponential decay weighting to news headlines to model the rapid
evaporation of predictive value in cryptocurrency markets.
"""

import math
from datetime import UTC, datetime


class ExponentialTimeDecay:
    """
    Computes exponential time-decay weights:
    w(dt) = exp(-ln(2) / half_life * dt) for dt <= max_age_hours, else 0.0.
    """

    def __init__(self, half_life_hours: float = 2.0, max_age_hours: float = 24.0) -> None:
        if half_life_hours <= 0.0:
            raise ValueError(f"half_life_hours must be positive, got {half_life_hours}")
        if max_age_hours <= 0.0:
            raise ValueError(f"max_age_hours must be positive, got {max_age_hours}")

        self.half_life_hours = half_life_hours
        self.max_age_hours = max_age_hours
        self._decay_constant = math.log(2.0) / half_life_hours

    def calculate_weight(
        self, published_at: datetime, current_time: datetime | None = None
    ) -> float:
        """
        Calculates the time-decay weight in [0.0, 1.0].
        Returns 0.0 if the article is older than max_age_hours.
        """
        now = current_time or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)

        # Elapsed hours
        elapsed_seconds = (now - published_at).total_seconds()
        # Protect against minor future clock drift
        elapsed_hours = max(0.0, elapsed_seconds / 3600.0)

        if elapsed_hours >= self.max_age_hours:
            return 0.0

        weight = math.exp(-self._decay_constant * elapsed_hours)
        return float(min(1.0, max(0.0, weight)))

    def is_expired(self, published_at: datetime, current_time: datetime | None = None) -> bool:
        """Returns True if article exceeds max_age_hours."""
        return self.calculate_weight(published_at, current_time) == 0.0
