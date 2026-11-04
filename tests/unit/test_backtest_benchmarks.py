"""
Unit tests for cryptopilot.backtesting.benchmarks.BenchmarkCalculator.
Covers: Buy & Hold BTC/ETH passive baselines, Cash benchmark, and edge cases.
"""

from datetime import UTC

import pandas as pd
import pytest

from cryptopilot.backtesting.benchmarks import BenchmarkCalculator


class TestBenchmarkCalculator:
    def test_buy_and_hold_positive_trend(self) -> None:
        dates = pd.date_range("2026-01-01", periods=10, freq="1D", tz=UTC)
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "close": [100.0, 105.0, 102.0, 110.0, 115.0, 120.0, 118.0, 125.0, 130.0, 140.0],
            }
        )
        bench = BenchmarkCalculator.calculate_buy_and_hold(
            "Buy & Hold BTC", df, initial_capital=100.0
        )
        assert bench.name == "Buy & Hold BTC"
        assert bench.initial_equity == 100.0
        assert bench.final_equity == 140.0
        assert pytest.approx(bench.total_return_pct) == 40.0
        assert bench.cagr_pct > 0.0
        assert bench.max_drawdown_pct > 0.0
        assert bench.sharpe_ratio > 0.0

    def test_buy_and_hold_downward_trend(self) -> None:
        dates = pd.date_range("2026-01-01", periods=5, freq="1D", tz=UTC)
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "close": [100.0, 90.0, 80.0, 70.0, 50.0],
            }
        )
        bench = BenchmarkCalculator.calculate_buy_and_hold(
            "Buy & Hold ETH", df, initial_capital=100.0
        )
        assert bench.final_equity == 50.0
        assert bench.total_return_pct == -50.0
        assert bench.max_drawdown_pct == 50.0

    def test_buy_and_hold_empty_or_invalid_df(self) -> None:
        bench_empty = BenchmarkCalculator.calculate_buy_and_hold(
            "BTC", pd.DataFrame(), initial_capital=50.0
        )
        assert bench_empty.final_equity == 50.0
        assert bench_empty.total_return_pct == 0.0

        df_no_close = pd.DataFrame({"open": [10.0, 20.0]})
        bench_no_close = BenchmarkCalculator.calculate_buy_and_hold(
            "BTC", df_no_close, initial_capital=50.0
        )
        assert bench_no_close.final_equity == 50.0

        df_zero_start = pd.DataFrame({"close": [0.0, 20.0]})
        bench_zero = BenchmarkCalculator.calculate_buy_and_hold(
            "BTC", df_zero_start, initial_capital=50.0
        )
        assert bench_zero.final_equity == 50.0

    def test_cash_benchmark_baseline(self) -> None:
        bench = BenchmarkCalculator.calculate_cash_benchmark(initial_capital=30.0)
        assert bench.name == "Cash (USD Baseline)"
        assert bench.initial_equity == 30.0
        assert bench.final_equity == 30.0
        assert bench.total_return_pct == 0.0
        assert bench.max_drawdown_pct == 0.0
        assert bench.sharpe_ratio == 0.0
