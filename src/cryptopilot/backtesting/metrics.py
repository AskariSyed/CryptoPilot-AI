"""
CryptoPilot AI - Quantitative Performance Metrics Calculator.
Computes Net Return, CAGR, Max Drawdown, Drawdown Duration, Win Rate,
Profit Factor, Sharpe Ratio, Sortino Ratio, Expectancy, and Fee drag.
"""

import math

import numpy as np

from cryptopilot.backtesting.models import EquityPoint, PerformanceMetrics, Trade


class PerformanceMetricsCalculator:
    """
    Calculates comprehensive quantitative performance and risk metrics.
    Guarantees mathematical correctness, edge-case safety, and zero-division protection.
    """

    @classmethod
    def calculate(
        cls,
        equity_curve: list[EquityPoint],
        trades: list[Trade],
        initial_capital: float,
        risk_free_rate: float = 0.0,
        annualization_periods: float = 365.0,
    ) -> PerformanceMetrics:
        """
        Calculates all performance metrics from the simulated equity curve and trades.
        """
        if not equity_curve:
            # Empty backtest fallback
            return PerformanceMetrics(
                initial_capital=initial_capital,
                final_equity=initial_capital,
                total_deposits=0.0,
                net_profit=0.0,
                net_return_pct=0.0,
                cagr_pct=0.0,
                max_drawdown_pct=0.0,
                max_drawdown_duration_bars=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                breakeven_trades=0,
                win_rate_pct=0.0,
                profit_factor=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                expectancy=0.0,
                avg_trade_pnl=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_loss_ratio=0.0,
                total_fees_paid=0.0,
            )

        final_equity = equity_curve[-1].total_equity
        total_deposits = equity_curve[-1].cumulative_deposits
        total_basis = initial_capital + total_deposits
        net_profit = final_equity - total_basis
        net_return_pct = (net_profit / total_basis) * 100.0 if total_basis > 0.0 else 0.0

        # 1. CAGR Calculation
        start_time = equity_curve[0].timestamp
        end_time = equity_curve[-1].timestamp
        duration_days = max(1.0, (end_time - start_time).total_seconds() / 86400.0)
        years = duration_days / 365.25

        if years > 0.0 and total_basis > 0.0 and final_equity > 0.0:
            growth_multiple = final_equity / total_basis
            try:
                cagr_pct = ((growth_multiple ** (1.0 / years)) - 1.0) * 100.0
            except (OverflowError, ValueError):
                cagr_pct = 0.0
        else:
            cagr_pct = 0.0

        # 2. Drawdown & Underwater Duration
        equities = [p.total_equity for p in equity_curve]
        peak = equities[0]
        max_dd_pct = 0.0
        max_dd_duration = 0
        current_dd_duration = 0

        for eq in equities:
            if eq > peak:
                peak = eq
                current_dd_duration = 0
            else:
                dd = ((peak - eq) / peak) * 100.0 if peak > 0.0 else 0.0
                if dd > max_dd_pct:
                    max_dd_pct = dd
                current_dd_duration += 1
                if current_dd_duration > max_dd_duration:
                    max_dd_duration = current_dd_duration

        # 3. Trade Statistics
        total_trades = len(trades)
        wins = [t for t in trades if t.net_pnl > 0.0]
        losses = [t for t in trades if t.net_pnl < 0.0]
        breakevens = [t for t in trades if t.net_pnl == 0.0]

        winning_trades = len(wins)
        losing_trades = len(losses)
        breakeven_trades = len(breakevens)

        win_rate_pct = (winning_trades / total_trades) * 100.0 if total_trades > 0 else 0.0

        gross_wins = sum(t.net_pnl for t in wins)
        gross_losses = abs(sum(t.net_pnl for t in losses))

        if gross_losses == 0.0 and gross_wins > 0.0:
            profit_factor = 999.0
        elif gross_losses == 0.0 and gross_wins == 0.0:
            profit_factor = 1.0 if total_trades > 0 else 0.0
        else:
            profit_factor = gross_wins / gross_losses

        avg_trade_pnl = sum(t.net_pnl for t in trades) / total_trades if total_trades > 0 else 0.0
        avg_win = gross_wins / winning_trades if winning_trades > 0 else 0.0
        avg_loss = gross_losses / losing_trades if losing_trades > 0 else 0.0
        profit_loss_ratio = (
            (avg_win / avg_loss) if avg_loss > 0 else (999.0 if avg_win > 0 else 0.0)
        )

        # Mathematical expectancy = (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
        win_prob = winning_trades / total_trades if total_trades > 0 else 0.0
        loss_prob = losing_trades / total_trades if total_trades > 0 else 0.0
        expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

        total_fees_paid = sum(t.fees_paid for t in trades)

        # 4. Returns & Risk-Adjusted Ratios (Sharpe & Sortino)
        if len(equities) >= 2:
            eq_arr = np.array(equities, dtype=np.float64)
            # Filter non-positive values to prevent inf/nan
            eq_arr = np.maximum(eq_arr, 1e-8)
            period_returns = (eq_arr[1:] - eq_arr[:-1]) / eq_arr[:-1]

            mean_ret = float(np.mean(period_returns))
            std_ret = float(np.std(period_returns))

            # Annualization scaling
            sqrt_periods = math.sqrt(annualization_periods)

            # Sharpe Ratio
            if std_ret > 1e-8:
                sharpe_ratio = float(
                    (mean_ret - (risk_free_rate / annualization_periods)) / std_ret * sqrt_periods
                )
            else:
                sharpe_ratio = 0.0

            # Sortino Ratio (Downside deviation only)
            downside_returns = period_returns[period_returns < 0.0]
            if len(downside_returns) > 0:
                downside_std = float(np.sqrt(np.mean(downside_returns**2)))
                if downside_std > 1e-8:
                    sortino_ratio = float(
                        (mean_ret - (risk_free_rate / annualization_periods))
                        / downside_std
                        * sqrt_periods
                    )
                else:
                    sortino_ratio = 999.0 if mean_ret > 0 else 0.0
            else:
                sortino_ratio = 999.0 if mean_ret > 0 else 0.0
        else:
            sharpe_ratio = 0.0
            sortino_ratio = 0.0

        return PerformanceMetrics(
            initial_capital=initial_capital,
            final_equity=final_equity,
            total_deposits=total_deposits,
            net_profit=net_profit,
            net_return_pct=net_return_pct,
            cagr_pct=cagr_pct,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_duration_bars=max_dd_duration,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            breakeven_trades=breakeven_trades,
            win_rate_pct=win_rate_pct,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            expectancy=expectancy,
            avg_trade_pnl=avg_trade_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_loss_ratio=profit_loss_ratio,
            total_fees_paid=total_fees_paid,
        )
