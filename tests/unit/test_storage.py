"""
Unit tests for cryptopilot.data.storage.MarketDataStorage.
Covers atomic file saving, loading, path resolution, and directory management.
"""

import tempfile
from datetime import UTC, datetime

import pytest

from cryptopilot.data.models import Candle
from cryptopilot.data.storage import MarketDataStorage


class TestMarketDataStorage:
    @pytest.fixture
    def temp_storage(self) -> MarketDataStorage:
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield MarketDataStorage(base_dir=tmp_dir)

    def test_directory_creation(self, temp_storage: MarketDataStorage) -> None:
        assert temp_storage.raw_dir.exists()
        assert temp_storage.processed_dir.exists()

    def test_save_and_load_raw_candles(self, temp_storage: MarketDataStorage) -> None:
        dt = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
        candle = Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=dt,
            open=50000.0,
            high=51000.0,
            low=49500.0,
            close=50500.0,
            volume=10.0,
            is_closed=True,
        )

        saved_path = temp_storage.save_raw_candles("BTC/USDT", "1h", [candle])
        assert saved_path.exists()
        assert temp_storage.exists("BTC/USDT", "1h", processed=False) is True
        assert temp_storage.exists("BTC/USDT", "1h", processed=True) is False

        loaded = temp_storage.load_candles("BTC/USDT", "1h", processed=False)
        assert len(loaded) == 1
        assert loaded[0].symbol == "BTC/USDT"
        assert loaded[0].open == 50000.0
        assert loaded[0].timestamp == dt

    def test_save_and_load_processed_candles(self, temp_storage: MarketDataStorage) -> None:
        dt = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
        candle = Candle(
            symbol="ETH/USDT",
            timeframe="15m",
            timestamp=dt,
            open=2500.0,
            high=2600.0,
            low=2400.0,
            close=2550.0,
            volume=20.0,
            is_closed=True,
        )

        saved_path = temp_storage.save_processed_candles("ETH/USDT", "15m", [candle])
        assert saved_path.exists()
        assert temp_storage.exists("ETH/USDT", "15m", processed=True) is True

        loaded = temp_storage.load_candles("ETH/USDT", "15m", processed=True)
        assert len(loaded) == 1
        assert loaded[0].symbol == "ETH/USDT"
        assert loaded[0].close == 2550.0

    def test_load_non_existent_file(self, temp_storage: MarketDataStorage) -> None:
        loaded = temp_storage.load_candles("SOL/USDT", "4h", processed=False)
        assert loaded == []
        assert temp_storage.exists("SOL/USDT", "4h") is False
