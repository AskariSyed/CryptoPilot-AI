"""
CryptoPilot AI - Market Data Domain Models.
Strictly typed via Pydantic v2 with UTC datetime enforcement and precision helpers.
"""

import math
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Timeframe(StrEnum):
    M1 = "1m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"

    @property
    def duration_seconds(self) -> int:
        mapping = {
            Timeframe.M1: 60,
            Timeframe.M15: 15 * 60,
            Timeframe.H1: 60 * 60,
            Timeframe.H4: 4 * 60 * 60,
        }
        return mapping[self]

    @property
    def duration_ms(self) -> int:
        return self.duration_seconds * 1000

    def round_down_timestamp(self, dt: datetime) -> datetime:
        """Rounds down a UTC datetime to the nearest timeframe boundary."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        else:
            dt = dt.astimezone(UTC)
        epoch = int(dt.timestamp())
        interval = self.duration_seconds
        rounded_epoch = (epoch // interval) * interval
        return datetime.fromtimestamp(rounded_epoch, tz=UTC)


class Symbol(BaseModel):
    raw: str = Field(description="Trading pair symbol e.g. BTC/USDT")
    base: str = Field(description="Base asset e.g. BTC")
    quote: str = Field(description="Quote asset e.g. USDT")

    @classmethod
    def from_string(cls, symbol_str: str) -> "Symbol":
        cleaned = symbol_str.strip().upper()
        if "/" not in cleaned:
            raise ValueError(
                f"Symbol must contain '/' separator (e.g. BTC/USDT), got '{symbol_str}'"
            )
        parts = cleaned.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid symbol structure: '{symbol_str}'")
        return cls(raw=cleaned, base=parts[0], quote=parts[1])

    def __str__(self) -> str:
        return self.raw


class Candle(BaseModel):
    symbol: str = Field(description="Trading pair symbol e.g. BTC/USDT")
    timeframe: str = Field(description="Timeframe string e.g. 1m, 15m, 1h, 4h")
    timestamp: datetime = Field(description="Candle open timestamp in UTC")
    open: float = Field(gt=0.0, description="Opening price")
    high: float = Field(gt=0.0, description="Highest price")
    low: float = Field(gt=0.0, description="Lowest price")
    close: float = Field(gt=0.0, description="Closing price")
    volume: float = Field(ge=0.0, description="Traded volume in base asset")
    is_closed: bool = Field(default=True, description="True if bar is confirmed closed")

    @field_validator("timestamp")
    @classmethod
    def enforce_utc_timestamp(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("high")
    @classmethod
    def validate_high(cls, v: float, info: object) -> float:
        # Pydantic v2 field validation
        return v

    @property
    def return_pct(self) -> float:
        """Percentage return from open to close."""
        return ((self.close - self.open) / self.open) * 100.0

    @property
    def hl_spread(self) -> float:
        """High-low spread absolute value."""
        return self.high - self.low

    @property
    def body_size(self) -> float:
        """Absolute candle body size."""
        return abs(self.close - self.open)

    @classmethod
    def from_ccxt_tuple(
        cls,
        raw_tuple: tuple[int, float, float, float, float, float] | list[float],
        symbol: str,
        timeframe: str,
        is_closed: bool = True,
    ) -> "Candle":
        """
        Parses CCXT standard OHLCV list: [timestamp_ms, open, high, low, close, volume]
        """
        if len(raw_tuple) < 6:
            raise ValueError(
                f"CCXT OHLCV tuple must have at least 6 elements, got {len(raw_tuple)}"
            )
        ts_ms, open_p, high_p, low_p, close_p, vol = (
            int(raw_tuple[0]),
            float(raw_tuple[1]),
            float(raw_tuple[2]),
            float(raw_tuple[3]),
            float(raw_tuple[4]),
            float(raw_tuple[5]),
        )
        dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC)
        return cls(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=dt,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=vol,
            is_closed=is_closed,
        )


class Ticker(BaseModel):
    symbol: str
    bid: float = Field(gt=0.0)
    ask: float = Field(gt=0.0)
    last: float = Field(gt=0.0)
    volume_24h: float = Field(ge=0.0)
    timestamp: datetime = Field(description="UTC timestamp")

    @field_validator("timestamp")
    @classmethod
    def enforce_utc_timestamp(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @property
    def spread(self) -> float:
        """Absolute bid-ask spread."""
        return self.ask - self.bid

    @property
    def spread_pct(self) -> float:
        """Bid-ask spread percentage relative to mid price."""
        mid = (self.ask + self.bid) / 2.0
        if mid <= 0:
            return 0.0
        return (self.spread / mid) * 100.0

    @property
    def mid_price(self) -> float:
        """Mid price between bid and ask."""
        return (self.ask + self.bid) / 2.0


class OrderBookLevel(BaseModel):
    price: float = Field(gt=0.0)
    amount: float = Field(ge=0.0)


class OrderBook(BaseModel):
    symbol: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def enforce_utc_timestamp(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @property
    def best_bid(self) -> float | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0].price if self.asks else None

    @property
    def spread(self) -> float | None:
        if self.best_ask is not None and self.best_bid is not None:
            return self.best_ask - self.best_bid
        return None

    @property
    def spread_bps(self) -> float | None:
        if self.best_ask is not None and self.best_bid is not None:
            mid = (self.best_ask + self.best_bid) / 2.0
            if mid > 0:
                return ((self.best_ask - self.best_bid) / mid) * 10000.0
        return None


class MarketMetadata(BaseModel):
    symbol: str
    base: str
    quote: str
    price_precision: int = Field(ge=0, default=2)
    quantity_precision: int = Field(ge=0, default=6)
    min_quantity: float = Field(gt=0.0, default=0.0001)
    min_notional: float = Field(ge=0.0, default=5.0)
    maker_fee: float = Field(ge=0.0, default=0.001)
    taker_fee: float = Field(ge=0.0, default=0.001)

    def round_price(self, price: float) -> float:
        """Round price to exchange allowed precision without floating-point artifacts."""
        if price <= 0:
            return 0.0
        factor = float(10**self.price_precision)
        return float(math.floor(price * factor + 0.5) / factor)

    def round_quantity(self, quantity: float) -> float:
        """
        Floor quantity to exchange allowed step size to prevent 'insufficient balance'
        due to round-up errors.
        """
        if quantity <= 0:
            return 0.0
        factor = float(10**self.quantity_precision)
        return float(math.floor(quantity * factor) / factor)

    def satisfies_min_notional(self, price: float, quantity: float) -> bool:
        """Checks if order total value satisfies exchange min_notional requirement."""
        notional = price * quantity
        return notional >= self.min_notional and quantity >= self.min_quantity
