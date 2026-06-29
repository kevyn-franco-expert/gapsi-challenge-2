"""Unit tests for Pydantic schemas."""
from __future__ import annotations
import pytest
from pydantic import ValidationError

from orders_service.schemas.order import OrderCreateRequest, OrderItem


def test_order_item_requires_positive_qty():
    with pytest.raises(ValidationError):
        OrderItem(name="latte", qty=0)


def test_order_create_requires_items():
    with pytest.raises(ValidationError):
        OrderCreateRequest(customer_id="abc", items=[])


def test_order_create_valid():
    request = OrderCreateRequest(
        customer_id="abc123",
        items=[OrderItem(name="latte", qty=1), OrderItem(name="muffin", qty=2)],
    )
    assert request.customer_id == "abc123"
    assert len(request.items) == 2
