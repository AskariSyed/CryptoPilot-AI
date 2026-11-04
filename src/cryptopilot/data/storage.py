"""
CryptoPilot AI - Market Data Storage Layer.
Separates raw exchange inputs from validated, processed data.
Supports atomic writes and JSON/CSV persistence.
"""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptopilot.data.models import Candle


class MarketDataStorage:
    """
    Manages local filesystem persistence for raw and validated candle series.
    Enforces atomic file writes and directory segregation.
    """

    def __init__(self, base_dir: str = "data") -> None:
        self.base_dir = Path(base_dir)
        self.raw_dir = self.base_dir / "historical"
        self.processed_dir = self.base_dir / "processed"

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def _get_filename(self, symbol: str, timeframe: str) -> str:
        safe_sym = symbol.replace("/", "_").lower()
        return f"{safe_sym}_{timeframe}.json"

    def get_path(self, symbol: str, timeframe: str, processed: bool = False) -> Path:
        folder = self.processed_dir if processed else self.raw_dir
        return folder / self._get_filename(symbol, timeframe)

    def _atomic_write_json(self, target_path: Path, data: list[dict[str, Any]]) -> None:
        """Writes JSON atomically using a temp file to prevent partial file writes."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        dir_name = str(target_path.parent)

        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, indent=2, default=str)
            temp_name = tf.name

        os.replace(temp_name, str(target_path))

    def save_raw_candles(self, symbol: str, timeframe: str, candles: list[Candle]) -> Path:
        """Persists raw ingested candles to data/historical/."""
        target_path = self.get_path(symbol, timeframe, processed=False)
        data = [
            {
                "symbol": c.symbol,
                "timeframe": c.timeframe,
                "timestamp": c.timestamp.isoformat(),
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
                "is_closed": c.is_closed,
            }
            for c in candles
        ]
        self._atomic_write_json(target_path, data)
        return target_path

    def save_processed_candles(self, symbol: str, timeframe: str, candles: list[Candle]) -> Path:
        """Persists validated, gap-free candles to data/processed/."""
        target_path = self.get_path(symbol, timeframe, processed=True)
        data = [
            {
                "symbol": c.symbol,
                "timeframe": c.timeframe,
                "timestamp": c.timestamp.isoformat(),
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
                "is_closed": c.is_closed,
            }
            for c in candles
        ]
        self._atomic_write_json(target_path, data)
        return target_path

    def load_candles(self, symbol: str, timeframe: str, processed: bool = False) -> list[Candle]:
        """Loads candles from disk. Returns empty list if file does not exist."""
        path = self.get_path(symbol, timeframe, processed=processed)
        if not path.exists():
            return []

        with open(path, encoding="utf-8") as f:
            raw_list = json.load(f)

        candles: list[Candle] = []
        for item in raw_list:
            dt = datetime.fromisoformat(item["timestamp"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            candles.append(
                Candle(
                    symbol=item["symbol"],
                    timeframe=item["timeframe"],
                    timestamp=dt,
                    open=float(item["open"]),
                    high=float(item["high"]),
                    low=float(item["low"]),
                    close=float(item["close"]),
                    volume=float(item["volume"]),
                    is_closed=bool(item.get("is_closed", True)),
                )
            )
        return candles

    def exists(self, symbol: str, timeframe: str, processed: bool = False) -> bool:
        """Returns True if the stored file exists."""
        return self.get_path(symbol, timeframe, processed=processed).exists()
