"""
CryptoPilot AI - Market Data Endpoints.
Serves historical OHLCV candles and real-time public ticker metrics.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from cryptopilot.api.deps import get_db_session
from cryptopilot.api.schemas import (
    ApiResponse,
    MarketCandleItem,
    MarketCandlesResponse,
    MarketTickerData,
)
from cryptopilot.database.models import MarketSnapshotModel
from cryptopilot.database.repository import CandleRepository

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/candles", response_model=ApiResponse[MarketCandlesResponse])
async def get_candles(
    symbol: str = Query(..., description="Trading pair e.g. BTC/USDT"),
    timeframe: str = Query("1h", description="Timeframe e.g. 1m, 15m, 1h, 4h"),
    limit: int = Query(100, ge=1, le=1000, description="Max candle records to return"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[MarketCandlesResponse]:
    """Retrieves historical validated OHLCV market candles."""
    candles = await CandleRepository.get_candles(
        session=session,
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
    )

    items = [
        MarketCandleItem(
            symbol=c.symbol,
            timeframe=c.timeframe,
            timestamp=c.open_time,
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
            is_closed=c.is_closed,
        )
        for c in candles
    ]

    response_data = MarketCandlesResponse(
        symbol=symbol,
        timeframe=timeframe,
        count=len(items),
        candles=items,
    )
    return ApiResponse[MarketCandlesResponse](data=response_data, timestamp=datetime.now(UTC))


@router.get("/ticker", response_model=ApiResponse[MarketTickerData])
async def get_ticker(
    symbol: str = Query("BTC/USDT", description="Trading pair symbol"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[MarketTickerData]:
    """Returns the latest ticker quote with bid/ask and spread."""
    # Check for snapshot
    query_snap = (
        select(MarketSnapshotModel)
        .where(MarketSnapshotModel.symbol == symbol)
        .order_by(desc(MarketSnapshotModel.timestamp))
        .limit(1)
    )
    res_snap = await session.execute(query_snap)
    snap = res_snap.scalar_one_or_none()

    if snap is not None:
        ticker = MarketTickerData(
            symbol=snap.symbol,
            bid=snap.bid_price,
            ask=snap.ask_price,
            last=snap.mid_price,
            spread=snap.spread,
            mid_price=snap.mid_price,
            timestamp=snap.timestamp,
        )
        return ApiResponse[MarketTickerData](data=ticker, timestamp=datetime.now(UTC))

    # Fallback to latest candle close with 0.05% synthetic spread
    latest_candle = await CandleRepository.get_latest_candle(session, symbol, "1h")
    if latest_candle is None:
        # Default seed reference prices if no data yet in DB
        defaults = {"BTC/USDT": 50000.0, "ETH/USDT": 3000.0, "SOL/USDT": 150.0}
        ref_price = defaults.get(symbol, 100.0)
        ts = datetime.now(UTC)
    else:
        ref_price = latest_candle.close
        ts = latest_candle.open_time

    half_spread = ref_price * 0.00025
    ticker = MarketTickerData(
        symbol=symbol,
        bid=round(ref_price - half_spread, 4),
        ask=round(ref_price + half_spread, 4),
        last=ref_price,
        spread=round(half_spread * 2.0, 4),
        mid_price=ref_price,
        timestamp=ts,
    )
    return ApiResponse[MarketTickerData](data=ticker, timestamp=datetime.now(UTC))
