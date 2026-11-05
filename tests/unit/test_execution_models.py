"""
Unit tests for cryptopilot.execution.models.
Validates schemas, enums, UTC timestamp coercions, and defaults for virtual trading domain models.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cryptopilot.execution.models import (
    BracketOrder,
    ExecutionAuditEvent,
    OrderSide,
    OrderStatus,
    OrderType,
    VirtualFill,
    VirtualOrder,
)


def test_execution_enums() -> None:
    """Verifies enum values and string compatibility."""
    assert OrderStatus.PENDING == "PENDING"
    assert OrderStatus.SUBMITTED == "SUBMITTED"
    assert OrderStatus.PARTIALLY_FILLED == "PARTIALLY_FILLED"
    assert OrderStatus.FILLED == "FILLED"
    assert OrderStatus.CANCELED == "CANCELED"
    assert OrderStatus.REJECTED == "REJECTED"

    assert OrderType.MARKET == "MARKET"
    assert OrderType.LIMIT == "LIMIT"
    assert OrderType.STOP_LOSS == "STOP_LOSS"
    assert OrderType.TAKE_PROFIT == "TAKE_PROFIT"

    assert OrderSide.BUY == "BUY"
    assert OrderSide.SELL == "SELL"


def test_virtual_order_creation_defaults() -> None:
    """Tests VirtualOrder default values, UUID generation, and UTC handling."""
    order = VirtualOrder(
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.001,
        remaining_quantity=0.001,
    )

    assert len(order.order_id) > 0
    assert order.status == OrderStatus.PENDING
    assert order.price is None
    assert order.stop_price is None
    assert order.filled_quantity == 0.0
    assert order.fee_paid == 0.0
    assert order.slippage_paid == 0.0
    assert order.rejection_reason is None
    assert order.created_at.tzinfo == UTC
    assert order.updated_at.tzinfo == UTC


def test_virtual_order_naive_datetime_coercion() -> None:
    """Tests that naive datetimes passed to VirtualOrder are converted to UTC."""
    naive_dt = datetime(2026, 11, 5, 12, 0, 0)
    order = VirtualOrder(
        account_id="small_account_01",
        symbol="ETH/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=0.5,
        remaining_quantity=0.5,
        price=3200.0,
        created_at=naive_dt,
        updated_at=naive_dt,
    )
    assert order.created_at.tzinfo == UTC
    assert order.updated_at.tzinfo == UTC


def test_virtual_order_validation_errors() -> None:
    """Tests validation constraints on VirtualOrder fields."""
    with pytest.raises(ValidationError):
        # Quantity must be > 0
        VirtualOrder(
            account_id="small_account_01",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.0,
            remaining_quantity=0.0,
        )

    with pytest.raises(ValidationError):
        # Remaining quantity must be >= 0
        VirtualOrder(
            account_id="small_account_01",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.1,
            remaining_quantity=-0.1,
        )


def test_virtual_fill_creation_and_utc_coercion() -> None:
    """Tests VirtualFill model construction and UTC timestamp validation."""
    fill = VirtualFill(
        order_id="ord-123",
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        price=50000.0,
        quantity=0.001,
        notional=50.0,
        fee=0.05,
        fee_rate=0.0010,
        slippage_rate=0.0002,
        slippage_cost=0.01,
        timestamp=datetime(2026, 11, 5, 12, 0, 0),  # Naive
    )

    assert fill.fill_id is not None
    assert fill.price == 50000.0
    assert fill.quantity == 0.001
    assert fill.timestamp.tzinfo == UTC

    # Test aware timestamp passes through
    aware_dt = datetime.now(UTC)
    fill_aware = VirtualFill(
        order_id="ord-124",
        account_id="small_account_01",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        price=51000.0,
        quantity=0.001,
        notional=51.0,
        fee=0.051,
        fee_rate=0.0010,
        slippage_rate=0.0002,
        slippage_cost=0.01,
        timestamp=aware_dt,
    )
    assert fill_aware.timestamp == aware_dt


def test_virtual_fill_validation_errors() -> None:
    """Verifies that invalid numbers raise validation errors on VirtualFill."""
    with pytest.raises(ValidationError):
        VirtualFill(
            order_id="ord-err",
            account_id="small_account_01",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            price=0.0,  # Must be gt=0
            quantity=0.001,
            notional=50.0,
            fee=0.05,
            fee_rate=0.001,
            slippage_rate=0.0,
            slippage_cost=0.0,
        )

    with pytest.raises(ValidationError):
        VirtualFill(
            order_id="ord-err2",
            account_id="small_account_01",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            price=50000.0,
            quantity=-1.0,  # Must be gt=0
            notional=50.0,
            fee=0.05,
            fee_rate=0.001,
            slippage_rate=0.0,
            slippage_cost=0.0,
        )


def test_bracket_order_creation() -> None:
    """Tests BracketOrder creation, active state, and closed_at timestamp coercion."""
    entry = VirtualOrder(
        account_id="small_account_01",
        symbol="SOL/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=1.0,
        remaining_quantity=1.0,
    )
    sl = VirtualOrder(
        account_id="small_account_01",
        symbol="SOL/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.STOP_LOSS,
        quantity=1.0,
        stop_price=140.0,
        remaining_quantity=1.0,
    )

    bracket = BracketOrder(
        account_id="small_account_01",
        symbol="SOL/USDT",
        entry_order=entry,
        stop_loss_order=sl,
        created_at=datetime(2026, 11, 5, 10, 0, 0),  # Naive
        closed_at=datetime(2026, 11, 5, 11, 0, 0),  # Naive
    )

    assert bracket.bracket_id is not None
    assert bracket.is_active is True
    assert bracket.take_profit_order is None
    assert bracket.created_at.tzinfo == UTC
    assert bracket.closed_at is not None and bracket.closed_at.tzinfo == UTC


def test_execution_audit_event() -> None:
    """Tests ExecutionAuditEvent logging model."""
    event = ExecutionAuditEvent(
        account_id="small_account_01",
        event_type="ORDER_SUBMITTED",
        order_id="ord-999",
        symbol="BTC/USDT",
        details={"side": "BUY", "quantity": 0.005},
        timestamp=datetime(2026, 11, 5, 14, 0, 0),  # Naive
    )

    assert event.event_id is not None
    assert event.event_type == "ORDER_SUBMITTED"
    assert event.details["side"] == "BUY"
    assert event.timestamp.tzinfo == UTC
