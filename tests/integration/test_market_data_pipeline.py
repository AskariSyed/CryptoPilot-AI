"""
Integration tests for Phase 1 Market Data Pipeline.
Verifies the end-to-end flow: ExchangeClient -> Validator -> Storage -> Verification.
"""

import tempfile
from datetime import UTC
from unittest.mock import AsyncMock

import pytest

from cryptopilot.data.exchange_client import ExchangeClient
from cryptopilot.data.models import Timeframe
from cryptopilot.data.storage import MarketDataStorage
from cryptopilot.data.validator import CandleValidator


class MockExchange:
    def __init__(self) -> None:
        self.load_markets = AsyncMock(return_value={})
        self.close = AsyncMock()
        self.fetch_ohlcv = AsyncMock()
        self.markets = {
            "BTC/USDT": {
                "precision": {"price": 2, "amount": 6},
                "limits": {"amount": {"min": 0.0001}, "cost": {"min": 5.0}},
            }
        }


@pytest.mark.asyncio
async def test_end_to_end_market_data_pipeline() -> None:
    """Verifies complete ingestion, validation, and storage pipeline."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = MarketDataStorage(base_dir=tmp_dir)

        # 1. Setup mock exchange with 3 valid 1h candles
        mock_ex = MockExchange()
        base_ms = 1704067200000  # 2024-01-01 00:00:00 UTC
        mock_ex.fetch_ohlcv.return_value = [
            [base_ms, 42000.0, 42500.0, 41800.0, 42300.0, 100.0],
            [base_ms + 3600000, 42300.0, 42600.0, 42100.0, 42550.0, 120.0],
            [base_ms + 7200000, 42550.0, 42800.0, 42400.0, 42700.0, 90.0],
        ]

        # 2. Ingest via ExchangeClient
        client = ExchangeClient(exchange_id="binance", custom_exchange=mock_ex)
        raw_candles = await client.fetch_ohlcv("BTC/USDT", Timeframe.H1)
        assert len(raw_candles) == 3

        # 3. Save raw data
        storage.save_raw_candles("BTC/USDT", "1h", raw_candles)
        assert storage.exists("BTC/USDT", "1h", processed=False) is True

        # 4. Validate through 4-stage pipeline
        validation_res = CandleValidator.validate_series(raw_candles, "1h", require_closed=True)
        assert validation_res.is_valid is True
        assert len(validation_res.validated_candles) == 3
        assert len(validation_res.errors) == 0

        # 5. Save processed data
        storage.save_processed_candles("BTC/USDT", "1h", validation_res.validated_candles)
        assert storage.exists("BTC/USDT", "1h", processed=True) is True

        # 6. Reload and verify round-trip integrity
        loaded = storage.load_candles("BTC/USDT", "1h", processed=True)
        assert len(loaded) == 3
        assert loaded[0].open == 42000.0
        assert loaded[2].close == 42700.0
        assert loaded[0].timestamp.tzinfo == UTC
