"""
Unit tests for cryptopilot.backtesting.execution.SimulatedExecutionEngine.
Covers: Spreads, slippage, taker commissions, and intrabar bracket resolution.
"""

from datetime import UTC, datetime

import pytest

from cryptopilot.backtesting.execution import SimulatedExecutionEngine
from cryptopilot.backtesting.models import (
    ExitReason,
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedOrder,
    SimulatedPosition,
)


class TestSimulatedExecutionEngine:
    def test_slippage_calculation(self) -> None:
        engine = SimulatedExecutionEngine(
            base_slippage_pct=0.0002,
            slippage_impact_factor=0.1,
            max_slippage_pct=0.03,
        )
        # Zero quantity
        assert engine.calculate_slippage(0.0, 1000.0) == 0.0

        # Normal small trade
        slip_normal = engine.calculate_slippage(1.0, 100.0)
        assert slip_normal > 0.0002
        assert slip_normal < 0.03

        # Giant trade hitting cap
        slip_giant = engine.calculate_slippage(1000.0, 10.0)
        assert slip_giant == 0.03

    def test_execute_market_buy_order(self) -> None:
        engine = SimulatedExecutionEngine(
            taker_fee_pct=0.001,
            default_spread_pct=0.0006,  # half-spread = 0.0003
            base_slippage_pct=0.0002,
        )
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        order = SimulatedOrder(
            order_id="buy_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.1,
            target_price=50000.0,
            created_at=now,
        )

        fill = engine.execute_market_order(
            order=order,
            bar_open=50000.0,
            bar_volume=100.0,
            timestamp=now,
        )
        assert fill.fill_price > 50000.0  # Buyer pays ask markup
        assert fill.quantity == 0.1
        assert fill.fee_paid > 0.0
        assert fill.slippage_paid > 0.0
        assert order.status == OrderStatus.FILLED
        assert order.fill_price == fill.fill_price

    def test_execute_market_sell_order(self) -> None:
        engine = SimulatedExecutionEngine(
            taker_fee_pct=0.001,
            default_spread_pct=0.0006,
            base_slippage_pct=0.0002,
        )
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        order = SimulatedOrder(
            order_id="sell_1",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=0.1,
            target_price=50000.0,
            created_at=now,
        )

        fill = engine.execute_market_order(
            order=order,
            bar_open=50000.0,
            bar_volume=100.0,
            timestamp=now,
        )
        assert fill.fill_price < 50000.0  # Seller receives bid markdown
        assert fill.exit_reason == ExitReason.SIGNAL

    def test_execute_invalid_bar_price(self) -> None:
        engine = SimulatedExecutionEngine()
        order = SimulatedOrder(
            order_id="bad_p",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.1,
            target_price=50000.0,
            created_at=datetime.now(UTC),
        )
        with pytest.raises(ValueError, match="Bar open price must be positive"):
            engine.execute_market_order(
                order, bar_open=0.0, bar_volume=100.0, timestamp=datetime.now(UTC)
            )

    def test_check_intrabar_bracket_no_trigger(self) -> None:
        engine = SimulatedExecutionEngine()
        pos = SimulatedPosition(
            position_id="p1",
            symbol="BTC/USDT",
            entry_price=50000.0,
            current_price=50000.0,
            quantity=0.1,
            stop_loss=49000.0,
            take_profit=52000.0,
            opened_at=datetime.now(UTC),
        )
        # Bar stays between 49500 and 51500
        fill = engine.check_intrabar_bracket(
            position=pos,
            bar_open=50000.0,
            bar_high=51500.0,
            bar_low=49500.0,
            bar_volume=100.0,
            timestamp=datetime.now(UTC),
        )
        assert fill is None

    def test_check_intrabar_bracket_stop_loss_trigger(self) -> None:
        engine = SimulatedExecutionEngine()
        pos = SimulatedPosition(
            position_id="p2",
            symbol="BTC/USDT",
            entry_price=50000.0,
            current_price=50000.0,
            quantity=0.1,
            stop_loss=49000.0,
            take_profit=52000.0,
            opened_at=datetime.now(UTC),
        )
        # Low drops to 48800 <= 49000
        fill = engine.check_intrabar_bracket(
            position=pos,
            bar_open=49500.0,
            bar_high=50500.0,
            bar_low=48800.0,
            bar_volume=100.0,
            timestamp=datetime.now(UTC),
        )
        assert fill is not None
        assert fill.exit_reason == ExitReason.STOP_LOSS
        assert fill.fill_price <= 49000.0  # Fills near or below stop loss

    def test_check_intrabar_bracket_take_profit_trigger(self) -> None:
        engine = SimulatedExecutionEngine()
        pos = SimulatedPosition(
            position_id="p3",
            symbol="BTC/USDT",
            entry_price=50000.0,
            current_price=50000.0,
            quantity=0.1,
            stop_loss=49000.0,
            take_profit=52000.0,
            opened_at=datetime.now(UTC),
        )
        # High reaches 52500 >= 52000
        fill = engine.check_intrabar_bracket(
            position=pos,
            bar_open=51000.0,
            bar_high=52500.0,
            bar_low=50500.0,
            bar_volume=100.0,
            timestamp=datetime.now(UTC),
        )
        assert fill is not None
        assert fill.exit_reason == ExitReason.TAKE_PROFIT
        assert fill.fill_price <= 52000.0  # Paying bid markdown from TP

    def test_check_intrabar_bracket_dual_trigger_stop_loss_priority(self) -> None:
        """Conservative simulation: if both SL and TP are touched in the same candle, SL triggers first."""
        engine = SimulatedExecutionEngine()
        pos = SimulatedPosition(
            position_id="p4",
            symbol="BTC/USDT",
            entry_price=50000.0,
            current_price=50000.0,
            quantity=0.1,
            stop_loss=49000.0,
            take_profit=52000.0,
            opened_at=datetime.now(UTC),
        )
        # Massive candle: High 53000 >= TP and Low 48000 <= SL
        fill = engine.check_intrabar_bracket(
            position=pos,
            bar_open=50000.0,
            bar_high=53000.0,
            bar_low=48000.0,
            bar_volume=100.0,
            timestamp=datetime.now(UTC),
        )
        assert fill is not None
        assert fill.exit_reason == ExitReason.STOP_LOSS

    def test_check_intrabar_bracket_closed_position_noop(self) -> None:
        engine = SimulatedExecutionEngine()
        pos = SimulatedPosition(
            position_id="p5",
            symbol="BTC/USDT",
            entry_price=50000.0,
            current_price=50000.0,
            quantity=0.1,
            stop_loss=49000.0,
            opened_at=datetime.now(UTC),
            closed_at=datetime.now(UTC),  # Already closed
        )
        fill = engine.check_intrabar_bracket(
            position=pos,
            bar_open=48000.0,
            bar_high=53000.0,
            bar_low=47000.0,
            bar_volume=100.0,
            timestamp=datetime.now(UTC),
        )
        assert fill is None
