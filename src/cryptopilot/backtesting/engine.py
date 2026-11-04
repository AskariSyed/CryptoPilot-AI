"""
CryptoPilot AI - Event-Driven Backtesting Engine.
Executes bar-by-bar historical simulation with zero lookahead bias, realistic
execution modeling (spreads, fees, slippage), portfolio risk constraints,
bracket order matching, and comprehensive benchmark reporting.
"""

from datetime import UTC, datetime

import pandas as pd

from cryptopilot.backtesting.benchmarks import BenchmarkCalculator
from cryptopilot.backtesting.execution import SimulatedExecutionEngine
from cryptopilot.backtesting.metrics import PerformanceMetricsCalculator
from cryptopilot.backtesting.models import (
    BacktestResult,
    BenchmarkComparison,
    ExitReason,
    OrderSide,
    OrderType,
    SimulatedOrder,
)
from cryptopilot.backtesting.portfolio import SimulatedPortfolio
from cryptopilot.strategies.base import BaseStrategy, SignalType, StrategySignal
from cryptopilot.strategies.multi_timeframe import MultiTimeframeTrendStrategy


class BacktestEngine:
    """
    Event-driven bar-by-bar backtesting engine connecting historical data feeds,
    quantitative strategies, risk-managed portfolio accounting, and execution modeling.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_capital: float = 30.0,
        monthly_contribution: float = 10.0,
        max_positions: int = 1,
        max_allocation_pct: float = 0.30,
        risk_budget_pct: float = 0.01,
        daily_loss_limit_pct: float = 0.02,
        execution_engine: SimulatedExecutionEngine | None = None,
    ) -> None:
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.monthly_contribution = monthly_contribution
        self.max_positions = max_positions
        self.max_allocation_pct = max_allocation_pct
        self.risk_budget_pct = risk_budget_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.execution_engine = execution_engine or SimulatedExecutionEngine()

    def run(
        self,
        df: pd.DataFrame,
        symbol: str = "BTC/USDT",
        timeframe: str = "15m",
        df_macro: pd.DataFrame | None = None,
        df_benchmarks: dict[str, pd.DataFrame] | None = None,
    ) -> BacktestResult:
        """
        Runs the complete event-driven backtest across historical OHLCV data.
        """
        if df is None or df.empty:
            raise ValueError("Input DataFrame for backtest cannot be None or empty")

        required_cols = {"open", "high", "low", "close", "volume"}
        if not required_cols.issubset(df.columns):
            raise ValueError(f"DataFrame missing required columns. Required: {required_cols}")

        df = df.copy()
        if "timestamp" not in df.columns:
            # Generate synthetic UTC timestamps if none present
            df["timestamp"] = pd.date_range("2026-01-01", periods=len(df), freq="15min", tz=UTC)

        portfolio = SimulatedPortfolio(
            initial_capital=self.initial_capital,
            monthly_contribution=self.monthly_contribution,
            max_positions=self.max_positions,
            max_allocation_pct=self.max_allocation_pct,
            risk_budget_pct=self.risk_budget_pct,
            daily_loss_limit_pct=self.daily_loss_limit_pct,
        )

        n_bars = len(df)
        pending_buy_order: tuple[SimulatedOrder, StrategySignal] | None = None
        pending_sell_order: SimulatedOrder | None = None
        position_bars_held: dict[str, int] = {}

        # Bar-by-bar event simulation
        for i in range(n_bars):
            row = df.iloc[i]
            ts = row["timestamp"]
            if hasattr(ts, "to_pydatetime"):
                ts = ts.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)

            b_open = float(row["open"])
            b_high = float(row["high"])
            b_low = float(row["low"])
            b_close = float(row["close"])
            b_vol = float(row["volume"])

            # 1. Calendar updates (Monthly contribution & Daily circuit breaker)
            portfolio.check_calendar_events(ts)

            # 2. Execute pending market orders queued from previous bar at Bar Open
            if pending_sell_order is not None and symbol in portfolio.positions:
                fill = self.execution_engine.execute_market_order(
                    order=pending_sell_order,
                    bar_open=b_open,
                    bar_volume=b_vol,
                    timestamp=ts,
                )
                bars_held = position_bars_held.pop(symbol, 0)
                portfolio.close_position(symbol, fill, bars_held=bars_held)
                pending_sell_order = None

            if pending_buy_order is not None and symbol not in portfolio.positions:
                order, sig = pending_buy_order
                fill = self.execution_engine.execute_market_order(
                    order=order,
                    bar_open=b_open,
                    bar_volume=b_vol,
                    timestamp=ts,
                )
                pos = portfolio.open_position(
                    symbol=symbol,
                    fill=fill,
                    stop_loss=sig.suggested_stop_loss,
                    take_profit=sig.suggested_take_profit,
                )
                if pos is not None:
                    position_bars_held[symbol] = 0
                pending_buy_order = None

            # 3. Check intrabar bracket triggers (Stop-Loss and Take-Profit)
            if symbol in portfolio.positions:
                active_pos = portfolio.positions[symbol]
                bracket_fill = self.execution_engine.check_intrabar_bracket(
                    position=active_pos,
                    bar_open=b_open,
                    bar_high=b_high,
                    bar_low=b_low,
                    bar_volume=b_vol,
                    timestamp=ts,
                )
                if bracket_fill is not None:
                    bars_held = position_bars_held.pop(symbol, 0)
                    portfolio.close_position(symbol, bracket_fill, bars_held=bars_held)

            # 4. Mark-to-market position price update
            portfolio.update_bar_prices({symbol: b_close})
            if symbol in portfolio.positions:
                position_bars_held[symbol] = position_bars_held.get(symbol, 0) + 1

            # 5. Evaluate strategy at Bar Close on historical slice up to current bar
            # Avoid lookahead: strategy ONLY sees bars up to current index i
            df_slice = df.iloc[: i + 1]

            if isinstance(self.strategy, MultiTimeframeTrendStrategy) and df_macro is not None:
                # Align macro data slice up to current timestamp
                macro_slice = df_macro[df_macro["timestamp"] <= ts]
                if len(macro_slice) >= self.strategy.min_bars:
                    signal = self.strategy.evaluate_multi(macro_slice, df_slice, symbol)
                else:
                    signal = self.strategy.create_hold_signal(
                        symbol, b_close, "Macro warmup incomplete", timestamp=ts
                    )
            else:
                signal = self.strategy.evaluate(df_slice, symbol)

            # 6. Queue signals for execution on next bar open
            if (
                signal.signal == SignalType.BUY
                and symbol not in portfolio.positions
                and pending_buy_order is None
            ):
                qty = portfolio.calculate_position_size(
                    entry_price=signal.entry_price,
                    stop_loss=signal.suggested_stop_loss,
                )
                if qty > 0.0:
                    order = SimulatedOrder(
                        order_id=f"ord_buy_{i}",
                        symbol=symbol,
                        side=OrderSide.BUY,
                        order_type=OrderType.MARKET,
                        quantity=qty,
                        target_price=signal.entry_price,
                        created_at=ts,
                        rationale=signal.rationale,
                    )
                    pending_buy_order = (order, signal)

            elif (
                signal.signal == SignalType.SELL
                and symbol in portfolio.positions
                and pending_sell_order is None
            ):
                pos = portfolio.positions[symbol]
                order = SimulatedOrder(
                    order_id=f"ord_sell_{i}",
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=pos.quantity,
                    target_price=b_close,
                    created_at=ts,
                    rationale=signal.rationale,
                )
                pending_sell_order = order

            # 7. Record bar equity snapshot
            portfolio.record_equity_snapshot(ts)

        # 8. Close any open position at final bar close for clean accounting
        if symbol in portfolio.positions:
            last_row = df.iloc[-1]
            last_close = float(last_row["close"])
            last_vol = float(last_row["volume"])
            last_ts = (
                portfolio.equity_curve[-1].timestamp
                if portfolio.equity_curve
                else datetime.now(UTC)
            )
            pos = portfolio.positions[symbol]

            force_order = SimulatedOrder(
                order_id="ord_force_close",
                symbol=symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=pos.quantity,
                target_price=last_close,
                created_at=last_ts,
                rationale="End of backtest period force close",
            )
            force_fill = self.execution_engine.execute_market_order(
                order=force_order,
                bar_open=last_close,
                bar_volume=last_vol,
                timestamp=last_ts,
            )
            force_fill.exit_reason = ExitReason.FORCE_CLOSE
            bars_held = position_bars_held.pop(symbol, 0)
            portfolio.close_position(symbol, force_fill, bars_held=bars_held)
            # Update final snapshot
            if portfolio.equity_curve:
                portfolio.equity_curve[-1] = portfolio.record_equity_snapshot(last_ts)

        # 9. Compute Performance Metrics
        metrics = PerformanceMetricsCalculator.calculate(
            equity_curve=portfolio.equity_curve,
            trades=portfolio.trades,
            initial_capital=self.initial_capital,
        )

        # 10. Compute Benchmark Comparisons
        benchmarks: list[BenchmarkComparison] = []
        if df_benchmarks:
            for b_name, b_df in df_benchmarks.items():
                benchmarks.append(
                    BenchmarkCalculator.calculate_buy_and_hold(
                        name=f"Buy & Hold {b_name}",
                        df_asset=b_df,
                        initial_capital=self.initial_capital,
                    )
                )
        else:
            # Default to Buy & Hold on the backtested asset itself
            benchmarks.append(
                BenchmarkCalculator.calculate_buy_and_hold(
                    name=f"Buy & Hold {symbol}",
                    df_asset=df,
                    initial_capital=self.initial_capital,
                )
            )

        benchmarks.append(BenchmarkCalculator.calculate_cash_benchmark(self.initial_capital))

        start_time = (
            portfolio.equity_curve[0].timestamp if portfolio.equity_curve else datetime.now(UTC)
        )
        end_time = (
            portfolio.equity_curve[-1].timestamp if portfolio.equity_curve else datetime.now(UTC)
        )

        return BacktestResult(
            strategy_id=self.strategy.strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            initial_capital=self.initial_capital,
            final_equity=portfolio.total_equity,
            total_deposits=portfolio.cumulative_deposits,
            metrics=metrics,
            benchmarks=benchmarks,
            equity_curve=portfolio.equity_curve,
            trades=portfolio.trades,
            metadata={
                "strategy_name": self.strategy.name,
                "max_allocation_pct": self.max_allocation_pct,
                "risk_budget_pct": self.risk_budget_pct,
                "daily_loss_limit_pct": self.daily_loss_limit_pct,
                "bars_processed": n_bars,
            },
        )
