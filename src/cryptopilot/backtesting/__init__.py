"""
CryptoPilot AI - Backtesting Module.
Provides event-driven historical simulation, realistic execution modeling (spreads, fees, slippage),
portfolio risk constraints, performance analytics, and walk-forward validation.
"""

from cryptopilot.backtesting.benchmarks import BenchmarkCalculator
from cryptopilot.backtesting.engine import BacktestEngine
from cryptopilot.backtesting.execution import ExecutionFill, SimulatedExecutionEngine
from cryptopilot.backtesting.metrics import PerformanceMetricsCalculator
from cryptopilot.backtesting.models import (
    BacktestResult,
    BenchmarkComparison,
    EquityPoint,
    ExitReason,
    OrderSide,
    OrderStatus,
    OrderType,
    PerformanceMetrics,
    SimulatedOrder,
    SimulatedPosition,
    Trade,
)
from cryptopilot.backtesting.portfolio import SimulatedPortfolio
from cryptopilot.backtesting.walk_forward import WalkForwardPartition, WalkForwardPartitioner

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "BenchmarkCalculator",
    "BenchmarkComparison",
    "EquityPoint",
    "ExecutionFill",
    "ExitReason",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PerformanceMetrics",
    "PerformanceMetricsCalculator",
    "SimulatedExecutionEngine",
    "SimulatedOrder",
    "SimulatedPortfolio",
    "SimulatedPosition",
    "Trade",
    "WalkForwardPartition",
    "WalkForwardPartitioner",
]
