"""
CryptoPilot AI - Portfolio & Balance Accounting Endpoints.
Serves real-time mark-to-market balances, separated deposit metrics, and performance analytics.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cryptopilot.api.deps import get_db_session
from cryptopilot.api.schemas import ApiResponse, PortfolioSummaryData
from cryptopilot.config.settings import get_settings
from cryptopilot.database.analytics import (
    PerformanceAnalyticsService,
    PerformanceReport,
)
from cryptopilot.database.repository import PortfolioRepository, PositionRepository

router = APIRouter(prefix="/portfolio", tags=["Portfolio & Balances"])


@router.get("", response_model=ApiResponse[PortfolioSummaryData])
async def get_portfolio(
    account_id: str = Query(
        "small_account_01", description="Account identifier: small_account_01 or research_lab_01"
    ),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[PortfolioSummaryData]:
    """Returns current portfolio balance, invested equity, and deposit metrics."""
    settings = get_settings()

    # Determine default initial capital if creating
    initial_cap = settings.initial_capital if account_id == "small_account_01" else 10000.0
    account_type = "small_account" if account_id == "small_account_01" else "research"

    portfolio = await PortfolioRepository.get_or_create(
        session=session,
        portfolio_id=account_id,
        account_type=account_type,
        initial_balance=initial_cap,
    )

    # Calculate unrealized PnL across active open positions
    open_positions = await PositionRepository.list_open_positions(session, account_id)
    total_unrealized_pnl = sum(p.unrealized_pnl for p in open_positions)

    current_equity = round(
        portfolio.current_cash + portfolio.invested_capital + total_unrealized_pnl, 4
    )
    net_return_pct = (
        round(
            ((portfolio.realized_pnl + total_unrealized_pnl) / portfolio.initial_balance) * 100.0, 2
        )
        if portfolio.initial_balance > 0.0
        else 0.0
    )

    data = PortfolioSummaryData(
        portfolio_id=portfolio.id,
        account_type=portfolio.account_type,
        currency=portfolio.currency,
        initial_capital=portfolio.initial_balance,
        total_deposits=portfolio.total_deposits,
        total_cash=portfolio.current_cash,
        invested_capital=portfolio.invested_capital,
        current_equity=current_equity,
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=total_unrealized_pnl,
        total_fees_paid=portfolio.total_fees_paid,
        net_trading_return_pct=net_return_pct,
        max_drawdown_pct=0.0,
        is_trading_halted=portfolio.is_trading_halted,
    )
    return ApiResponse[PortfolioSummaryData](data=data, timestamp=datetime.now(UTC))


@router.get("/performance", response_model=ApiResponse[PerformanceReport])
async def get_portfolio_performance(
    account_id: str = Query("small_account_01", description="Account identifier"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[PerformanceReport]:
    """Computes comprehensive performance report (Sharpe, Sortino, Win Rate, Drawdown)."""
    try:
        report = await PerformanceAnalyticsService.compute_portfolio_report(session, account_id)
    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio '{account_id}' not found.",
        ) from err

    return ApiResponse[PerformanceReport](data=report, timestamp=datetime.now(UTC))
