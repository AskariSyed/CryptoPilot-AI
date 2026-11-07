"""
CryptoPilot AI - Quantitative Performance Analytics Service.
Computes institutional-grade risk and performance metrics: Sharpe Ratio, Sortino Ratio,
Maximum Drawdown, Win Rate, Profit Factor, Payoff Ratio, and Calmar Ratio.
"""

import math
from datetime import UTC, datetime
from typing import Any

import numpy as np
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cryptopilot.database.models import PortfolioModel, PositionModel


class PerformanceReport(BaseModel):
    """Structured report detailing portfolio execution and mathematical performance."""

    portfolio_id: str
    total_trades: int = Field(ge=0)
    winning_trades: int = Field(ge=0)
    losing_trades: int = Field(ge=0)
    win_rate: float = Field(ge=0.0, le=1.0)
    total_realized_pnl: float
    gross_profit: float = Field(ge=0.0)
    gross_loss: float = Field(ge=0.0)
    profit_factor: float = Field(ge=0.0)
    average_win: float = Field(ge=0.0)
    average_loss: float = Field(ge=0.0)
    payoff_ratio: float = Field(ge=0.0)
    max_drawdown_pct: float = Field(ge=0.0, le=1.0)
    sharpe_ratio: float
    sortino_ratio: float
    total_fees_paid: float = Field(ge=0.0)
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PerformanceAnalyticsService:
    """
    Mathematical performance calculation engine operating on trade histories and equity curves.
    """

    @staticmethod
    def calculate_sharpe_ratio(
        returns: list[float] | np.ndarray,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 365,
    ) -> float:
        """
        Annualized Sharpe Ratio:
        Sharpe = sqrt(N) * (mean(R) - Rf) / std(R)
        """
        arr = np.asarray(returns, dtype=np.float64)
        if len(arr) < 2:
            return 0.0

        std = float(np.std(arr, ddof=1))
        if std <= 1e-12:
            return 0.0

        mean = float(np.mean(arr))
        excess = mean - (risk_free_rate / periods_per_year)
        sharpe = math.sqrt(periods_per_year) * (excess / std)
        return round(float(sharpe), 4)

    @staticmethod
    def calculate_sortino_ratio(
        returns: list[float] | np.ndarray,
        target_return: float = 0.0,
        periods_per_year: int = 365,
    ) -> float:
        """
        Annualized Sortino Ratio:
        Sortino = sqrt(N) * (mean(R) - Target) / DownsideDeviation
        """
        arr = np.asarray(returns, dtype=np.float64)
        if len(arr) < 2:
            return 0.0

        downside = arr[arr < target_return] - target_return
        if len(downside) == 0:
            return 0.0

        downside_std = float(math.sqrt(np.mean(downside**2)))
        if downside_std <= 1e-12:
            return 0.0

        mean = float(np.mean(arr))
        excess = mean - (target_return / periods_per_year)
        sortino = math.sqrt(periods_per_year) * (excess / downside_std)
        return round(float(sortino), 4)

    @staticmethod
    def calculate_max_drawdown(equity_curve: list[float] | np.ndarray) -> tuple[float, float]:
        """
        Computes maximum peak-to-trough drawdown in absolute dollars and percentage.
        Returns: (max_drawdown_dollars, max_drawdown_pct)
        """
        arr = np.asarray(equity_curve, dtype=np.float64)
        if len(arr) < 2:
            return 0.0, 0.0

        peak = arr[0]
        max_dd_dollars = 0.0
        max_dd_pct = 0.0

        for val in arr:
            if val > peak:
                peak = val
            dd_dollars = peak - val
            dd_pct = dd_dollars / peak if peak > 0.0 else 0.0

            if dd_dollars > max_dd_dollars:
                max_dd_dollars = dd_dollars
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        return round(float(max_dd_dollars), 4), round(float(min(1.0, max_dd_pct)), 4)

    @staticmethod
    def calculate_trade_metrics(realized_pnls: list[float]) -> dict[str, Any]:
        """
        Analyzes a sequence of trade PnLs to extract win rate, profit factor, and payoffs.
        """
        if not realized_pnls:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_realized_pnl": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "profit_factor": 0.0,
                "average_win": 0.0,
                "average_loss": 0.0,
                "payoff_ratio": 0.0,
            }

        wins = [p for p in realized_pnls if p > 0.0]
        losses = [abs(p) for p in realized_pnls if p < 0.0]

        total_trades = len(realized_pnls)
        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        gross_profit = sum(wins)
        gross_loss = sum(losses)
        profit_factor = (
            (gross_profit / gross_loss)
            if gross_loss > 0.0
            else (999.0 if gross_profit > 0 else 0.0)
        )

        avg_win = (gross_profit / winning_trades) if winning_trades > 0 else 0.0
        avg_loss = (gross_loss / losing_trades) if losing_trades > 0 else 0.0
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0.0 else 0.0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 4),
            "total_realized_pnl": round(sum(realized_pnls), 4),
            "gross_profit": round(gross_profit, 4),
            "gross_loss": round(gross_loss, 4),
            "profit_factor": round(min(999.0, profit_factor), 4),
            "average_win": round(avg_win, 4),
            "average_loss": round(avg_loss, 4),
            "payoff_ratio": round(payoff_ratio, 4),
        }

    @staticmethod
    async def compute_portfolio_report(
        session: AsyncSession,
        portfolio_id: str,
    ) -> PerformanceReport:
        """
        Asynchronously computes institutional performance telemetry for a portfolio.
        """
        res_p = await session.execute(
            select(PortfolioModel).where(PortfolioModel.id == portfolio_id)
        )
        portfolio = res_p.scalar_one_or_none()
        if portfolio is None:
            raise KeyError(f"Portfolio '{portfolio_id}' not found.")

        # Query closed positions
        res_pos = await session.execute(
            select(PositionModel)
            .where(
                PositionModel.portfolio_id == portfolio_id,
                PositionModel.status == "CLOSED",
            )
            .order_by(PositionModel.closed_at.asc())
        )
        positions = list(res_pos.scalars().all())

        pnls: list[float] = [p.realized_pnl or 0.0 for p in positions]
        trade_metrics = PerformanceAnalyticsService.calculate_trade_metrics(pnls)

        # Build simulated equity trajectory from closed positions
        running_equity = portfolio.initial_balance
        equity_series = [running_equity]
        returns_series: list[float] = []

        for pnl in pnls:
            prev = running_equity
            running_equity += pnl
            equity_series.append(running_equity)
            if prev > 0.0:
                returns_series.append(pnl / prev)

        _, max_dd_pct = PerformanceAnalyticsService.calculate_max_drawdown(equity_series)
        sharpe = PerformanceAnalyticsService.calculate_sharpe_ratio(returns_series)
        sortino = PerformanceAnalyticsService.calculate_sortino_ratio(returns_series)

        return PerformanceReport(
            portfolio_id=portfolio_id,
            total_trades=trade_metrics["total_trades"],
            winning_trades=trade_metrics["winning_trades"],
            losing_trades=trade_metrics["losing_trades"],
            win_rate=trade_metrics["win_rate"],
            total_realized_pnl=trade_metrics["total_realized_pnl"],
            gross_profit=trade_metrics["gross_profit"],
            gross_loss=trade_metrics["gross_loss"],
            profit_factor=trade_metrics["profit_factor"],
            average_win=trade_metrics["average_win"],
            average_loss=trade_metrics["average_loss"],
            payoff_ratio=trade_metrics["payoff_ratio"],
            max_drawdown_pct=max_dd_pct,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            total_fees_paid=portfolio.total_fees_paid,
            calculated_at=datetime.now(UTC),
        )
