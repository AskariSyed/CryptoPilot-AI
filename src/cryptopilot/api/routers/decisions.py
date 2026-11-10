"""
CryptoPilot AI - Autonomous Decisions & Explainability Endpoints.
Serves transparent arbitration logs, consensus rationales, and factor attributions.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cryptopilot.api.deps import get_db_session
from cryptopilot.api.schemas import ApiResponse, DecisionItem
from cryptopilot.database.repository import DecisionRepository

router = APIRouter(prefix="/decisions", tags=["Decisions & Explainability"])


@router.get("", response_model=ApiResponse[list[DecisionItem]])
async def get_decisions(
    symbol: str | None = Query(None, description="Optional symbol filter e.g. BTC/USDT"),
    limit: int = Query(20, ge=1, le=100, description="Max decision records to return"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[DecisionItem]]:
    """Returns recent autonomous trading decisions with interpretable rationales."""
    decisions = await DecisionRepository.list_decisions(session, symbol=symbol, limit=limit)
    items = [
        DecisionItem(
            id=d.id,
            symbol=d.symbol,
            timestamp=d.timestamp,
            decision=d.decision,
            confidence=d.confidence,
            market_regime=d.market_regime,
            strategy_signals=d.strategy_signals_json,
            ml_prediction=d.ml_prediction_json,
            sentiment_summary=d.sentiment_summary_json,
            risk_approved=d.risk_approved,
            rejection_reason=d.rejection_reason,
            explanation=d.explanation_text,
        )
        for d in decisions
    ]
    return ApiResponse[list[DecisionItem]](data=items, timestamp=datetime.now(UTC))
