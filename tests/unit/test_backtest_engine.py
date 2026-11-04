"""
Unit tests for cryptopilot.backtesting.engine.BacktestEngine.
Covers: Event-driven bar-by-bar execution, bracket exits, zero-lookahead order fills,
micro-capital ($30) vs research ($10,000) environments, and multi-timeframe backtesting.
"""

from datetime import UTC

import pandas as pd
import pytest

from cryptopilot.backtesting.engine import BacktestEngine
from cryptopilot.backtesting.models import ExitReason
from cryptopilot.strategies.base import BaseStrategy, SignalType, StrategySignal
from cryptopilot.strategies.multi_timeframe import MultiTimeframeTrendStrategy


class MockAlternatingStrategy(BaseStrategy):
    """Deterministic mock strategy: buys on bar 10, sells on bar 15."""

    def __init__(self) -> None:
        super().__init__(strategy_id="mock_strat", name="Mock Strategy", min_bars=5)

    def evaluate(self, df: pd.DataFrame, symbol: str) -> StrategySignal:
        curr_bar = len(df) - 1
        curr_p = float(df["close"].iloc[-1])
        ts = df["timestamp"].iloc[-1]

        if curr_bar == 10:
            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.BUY,
                confidence=0.80,
                entry_price=curr_p,
                suggested_stop_loss=curr_p * 0.95,  # 5% SL
                suggested_take_profit=curr_p * 1.10,  # 10% TP
                rationale="Mock buy trigger at bar 10",
                invalidation_condition="Price drops below stop loss",
                timestamp=ts,
            )
        elif curr_bar == 15:
            return StrategySignal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                signal=SignalType.SELL,
                confidence=0.80,
                entry_price=curr_p,
                suggested_stop_loss=curr_p * 1.05,
                rationale="Mock sell trigger at bar 15",
                invalidation_condition="Price breaks above upper band",
                timestamp=ts,
            )

        return self.create_hold_signal(symbol, curr_p, "Hold", timestamp=ts)


class TestBacktestEngine:
    @pytest.fixture
    def sample_ohlcv(self) -> pd.DataFrame:
        n = 30
        dates = pd.date_range("2026-01-01 00:00", periods=n, freq="15min", tz=UTC)
        # Moderate price rise from 100 to 115
        closes = [100.0 + (i * 0.5) for i in range(n)]
        opens = [c - 0.2 for c in closes]
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        volumes = [500.0] * n

        return pd.DataFrame(
            {
                "timestamp": dates,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            }
        )

    def test_backtest_execution_flow_and_zero_lookahead(self, sample_ohlcv: pd.DataFrame) -> None:
        """
        Verifies:
        1. Buy signal fired at bar 10 close -> Order fills at bar 11 open.
        2. Sell signal fired at bar 15 close -> Order fills at bar 16 open.
        """
        strat = MockAlternatingStrategy()
        engine = BacktestEngine(
            strategy=strat,
            initial_capital=100.0,
            monthly_contribution=0.0,
            risk_budget_pct=0.02,
            max_allocation_pct=0.30,
        )

        result = engine.run(sample_ohlcv, symbol="BTC/USDT", timeframe="15m")
        assert result.strategy_id == "mock_strat"
        assert result.initial_capital == 100.0
        assert len(result.trades) == 1

        trade = result.trades[0]
        # Bar 10 timestamp is 02:30, Bar 11 is 02:45
        # Order must be filled at Bar 11 Open, NOT Bar 10!
        expected_entry_time = sample_ohlcv["timestamp"].iloc[11]
        assert trade.entry_time == expected_entry_time

        # Bar 15 timestamp is 03:45, Bar 16 is 04:00
        # Exit order must fill at Bar 16 Open!
        expected_exit_time = sample_ohlcv["timestamp"].iloc[16]
        assert trade.exit_time == expected_exit_time
        assert trade.exit_reason == ExitReason.SIGNAL
        assert trade.net_pnl > 0.0  # Profitable trade
        assert len(result.benchmarks) >= 2  # Asset B&H + Cash

    def test_backtest_intrabar_stop_loss_trigger(self, sample_ohlcv: pd.DataFrame) -> None:
        """Verifies intrabar Stop-Loss trigger when bar low breaches SL."""
        strat = MockAlternatingStrategy()
        engine = BacktestEngine(strategy=strat, initial_capital=100.0)

        # In bar 12 (right after entry at bar 11), cause a price crash below SL
        df_crash = sample_ohlcv.copy()
        # Entry at bar 11 is around ~105, SL is ~99.75. Drop bar 12 low to 90.0!
        df_crash.loc[12, "low"] = 90.0

        result = engine.run(df_crash, symbol="BTC/USDT")
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_reason == ExitReason.STOP_LOSS
        assert trade.net_pnl < 0.0

    def test_backtest_intrabar_take_profit_trigger(self, sample_ohlcv: pd.DataFrame) -> None:
        """Verifies intrabar Take-Profit trigger when bar high reaches TP."""
        strat = MockAlternatingStrategy()
        engine = BacktestEngine(strategy=strat, initial_capital=100.0)

        # In bar 13, spike price above TP (~115)
        df_spike = sample_ohlcv.copy()
        df_spike.loc[13, "high"] = 130.0

        result = engine.run(df_spike, symbol="BTC/USDT")
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_reason == ExitReason.TAKE_PROFIT
        assert trade.net_pnl > 0.0

    def test_backtest_micro_capital_small_account(self, sample_ohlcv: pd.DataFrame) -> None:
        """Verifies $30 account with $10 monthly deposit and 1% risk budgeting."""
        strat = MockAlternatingStrategy()
        engine = BacktestEngine(
            strategy=strat,
            initial_capital=30.0,
            monthly_contribution=10.0,
            risk_budget_pct=0.01,
            max_allocation_pct=0.30,
        )

        result = engine.run(sample_ohlcv, symbol="BTC/USDT")
        assert result.initial_capital == 30.0
        assert result.final_equity > 0.0
        # Position notional must not exceed 30% of $30 = $9.00
        if result.trades:
            trade = result.trades[0]
            notional = trade.entry_price * trade.quantity
            assert notional <= 9.05  # within buffer

    def test_backtest_research_environment_balance(self, sample_ohlcv: pd.DataFrame) -> None:
        """Verifies $10,000 research balance executes with scaled position sizing."""
        strat = MockAlternatingStrategy()
        engine = BacktestEngine(
            strategy=strat,
            initial_capital=10000.0,
            monthly_contribution=0.0,
            risk_budget_pct=0.01,
            max_allocation_pct=0.30,
        )

        result = engine.run(sample_ohlcv, symbol="BTC/USDT")
        assert result.initial_capital == 10000.0
        if result.trades:
            trade = result.trades[0]
            notional = trade.entry_price * trade.quantity
            assert notional <= 3005.0  # Max 30% of $10,000

    def test_backtest_multi_timeframe_strategy(self) -> None:
        """Verifies MultiTimeframeTrendStrategy runs with aligned df_macro."""
        n_micro = 80
        dates_micro = pd.date_range("2026-01-01 00:00", periods=n_micro, freq="15min", tz=UTC)
        df_micro = pd.DataFrame(
            {
                "timestamp": dates_micro,
                "open": [100.0] * n_micro,
                "high": [105.0] * n_micro,
                "low": [95.0] * n_micro,
                "close": [102.0] * n_micro,
                "volume": [500.0] * n_micro,
            }
        )

        n_macro = 70
        dates_macro = pd.date_range("2025-12-29 00:00", periods=n_macro, freq="1h", tz=UTC)
        df_macro = pd.DataFrame(
            {
                "timestamp": dates_macro,
                "open": [100.0] * n_macro,
                "high": [105.0] * n_macro,
                "low": [95.0] * n_macro,
                "close": [104.0] * n_macro,
                "volume": [1000.0] * n_macro,
            }
        )

        mtf_strat = MultiTimeframeTrendStrategy(macro_ema_period=10, micro_ema_period=10)
        engine = BacktestEngine(strategy=mtf_strat, initial_capital=100.0)

        result = engine.run(df_micro, symbol="BTC/USDT", df_macro=df_macro)
        assert result.strategy_id == "multi_timeframe"
        assert len(result.equity_curve) == n_micro

    def test_backtest_invalid_inputs(self) -> None:
        strat = MockAlternatingStrategy()
        engine = BacktestEngine(strategy=strat)

        with pytest.raises(
            ValueError, match="Input DataFrame for backtest cannot be None or empty"
        ):
            engine.run(pd.DataFrame(), symbol="BTC/USDT")

        df_missing_cols = pd.DataFrame({"close": [100.0, 101.0]})
        with pytest.raises(ValueError, match="DataFrame missing required columns"):
            engine.run(df_missing_cols, symbol="BTC/USDT")

    def test_backtest_auto_generates_timestamps_if_missing(self) -> None:
        strat = MockAlternatingStrategy()
        engine = BacktestEngine(strategy=strat, initial_capital=100.0)
        n = 20
        df_no_ts = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [105.0] * n,
                "low": [95.0] * n,
                "close": [102.0] * n,
                "volume": [500.0] * n,
            }
        )
        result = engine.run(df_no_ts, symbol="BTC/USDT")
        assert len(result.equity_curve) == n
        assert result.equity_curve[0].timestamp.tzinfo == UTC

    def test_backtest_force_close_at_end_and_custom_benchmarks(
        self, sample_ohlcv: pd.DataFrame
    ) -> None:
        """When a position is still open on the final bar, it must be force-closed cleanly."""

        class BuyOnlyStrategy(BaseStrategy):
            def __init__(self) -> None:
                super().__init__(strategy_id="buy_only", name="Buy Only", min_bars=5)

            def evaluate(self, df: pd.DataFrame, symbol: str) -> StrategySignal:
                curr_bar = len(df) - 1
                curr_p = float(df["close"].iloc[-1])
                ts = df["timestamp"].iloc[-1]
                if curr_bar == 10:
                    return StrategySignal(
                        strategy_id=self.strategy_id,
                        symbol=symbol,
                        signal=SignalType.BUY,
                        confidence=0.80,
                        entry_price=curr_p,
                        suggested_stop_loss=curr_p * 0.95,  # 5% SL, well within notional threshold
                        suggested_take_profit=curr_p * 2.0,  # Far TP, will not hit
                        rationale="Buy and hold to end",
                        invalidation_condition="Price breaks 50",
                        timestamp=ts,
                    )
                return self.create_hold_signal(symbol, curr_p, "Hold", timestamp=ts)

        strat = BuyOnlyStrategy()
        engine = BacktestEngine(strategy=strat, initial_capital=100.0)
        result = engine.run(
            sample_ohlcv,
            symbol="BTC/USDT",
            df_benchmarks={"ETH/USDT": sample_ohlcv},
        )
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_reason == ExitReason.FORCE_CLOSE
        assert any(b.name == "Buy & Hold ETH/USDT" for b in result.benchmarks)
