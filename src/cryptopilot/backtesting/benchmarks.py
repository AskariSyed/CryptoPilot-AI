"""
CryptoPilot AI - Benchmark Comparison Calculator.
Calculates comparative performance against standard Buy & Hold benchmarks (BTC, ETH) and Cash.
"""

import math

import numpy as np
import pandas as pd

from cryptopilot.backtesting.models import BenchmarkComparison


class BenchmarkCalculator:
    """
    Computes passive Buy-and-Hold benchmark comparisons over identical historical windows.
    """

    @classmethod
    def calculate_buy_and_hold(
        cls,
        name: str,
        df_asset: pd.DataFrame,
        initial_capital: float,
        annualization_periods: float = 365.0,
    ) -> BenchmarkComparison:
        """
        Simulates 100% passive Buy & Hold of an asset across the dataframe.
        """
        if (
            df_asset is None
            or df_asset.empty
            or "close" not in df_asset.columns
            or len(df_asset) < 2
        ):
            return BenchmarkComparison(
                name=name,
                initial_equity=initial_capital,
                final_equity=initial_capital,
                total_return_pct=0.0,
                cagr_pct=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
            )

        close_prices: np.ndarray = np.asarray(
            df_asset["close"].astype(float).values, dtype=np.float64
        )
        p_start = float(close_prices[0])
        p_end = float(close_prices[-1])

        if p_start <= 0.0:
            return BenchmarkComparison(
                name=name,
                initial_equity=initial_capital,
                final_equity=initial_capital,
                total_return_pct=0.0,
                cagr_pct=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
            )

        asset_return_ratio = p_end / p_start
        final_equity = initial_capital * asset_return_ratio
        total_return_pct = (asset_return_ratio - 1.0) * 100.0

        # Duration & CAGR
        if "timestamp" in df_asset.columns and len(df_asset["timestamp"]) >= 2:
            t_start = df_asset["timestamp"].iloc[0]
            t_end = df_asset["timestamp"].iloc[-1]
            if hasattr(t_start, "to_pydatetime"):
                t_start = t_start.to_pydatetime()
            if hasattr(t_end, "to_pydatetime"):
                t_end = t_end.to_pydatetime()
            duration_days = max(1.0, (t_end - t_start).total_seconds() / 86400.0)
            years = duration_days / 365.25
        else:
            years = len(df_asset) / annualization_periods

        if years > 0.0 and asset_return_ratio > 0.0:
            try:
                cagr_pct = ((asset_return_ratio ** (1.0 / years)) - 1.0) * 100.0
            except (OverflowError, ValueError):
                cagr_pct = 0.0
        else:
            cagr_pct = 0.0

        # Drawdown calculation
        cumulative_max = np.maximum.accumulate(close_prices)
        drawdowns = (cumulative_max - close_prices) / np.maximum(cumulative_max, 1e-8) * 100.0
        max_drawdown_pct = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Sharpe ratio
        returns = (close_prices[1:] - close_prices[:-1]) / np.maximum(close_prices[:-1], 1e-8)
        std = float(np.std(returns))
        mean = float(np.mean(returns))
        sqrt_periods = math.sqrt(annualization_periods)
        sharpe_ratio = float((mean / std) * sqrt_periods) if std > 1e-8 else 0.0

        return BenchmarkComparison(
            name=name,
            initial_equity=initial_capital,
            final_equity=final_equity,
            total_return_pct=total_return_pct,
            cagr_pct=cagr_pct,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
        )

    @classmethod
    def calculate_cash_benchmark(cls, initial_capital: float) -> BenchmarkComparison:
        """Returns the 0% return risk-free cash benchmark baseline."""
        return BenchmarkComparison(
            name="Cash (USD Baseline)",
            initial_equity=initial_capital,
            final_equity=initial_capital,
            total_return_pct=0.0,
            cagr_pct=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
        )
