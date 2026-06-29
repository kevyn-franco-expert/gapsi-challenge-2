"""Unit tests for order processing logic."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from processor_service.repositories.order_repository import OrderRepository
from processor_service.services.processor import OrderProcessor
from shared.messaging import EVENT_ORDERS_COMPLETED
from shared.models import Order


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_publisher():
    return AsyncMock()


@pytest.fixture
def processor(mock_session, mock_publisher):
    return OrderProcessor(session=mock_session, trace_id="trace-456", publisher=mock_publisher)


@pytest.mark.asyncio
async def test_process_completes_pending_order(processor, mock_publisher):
    processor.order_repo = AsyncMock(spec=OrderRepository)

    order = Order(
        id="order-1",
        customer_id="abc123",
        items=[{"name": "latte", "qty": 1}],
        status="PENDING",
    )
    processor.order_repo.get_by_id.return_value = order

    result = await processor.process("order-1")

    assert result is True
    processor.order_repo.mark_completed.assert_awaited_once_with("order-1")
    mock_publisher.publish.assert_awaited_once()
    call_kwargs = mock_publisher.publish.await_args.kwargs
    assert call_kwargs["routing_key"] == EVENT_ORDERS_COMPLETED


@pytest.mark.asyncio
async def test_process_skips_already_completed_order(processor, mock_publisher):
    processor.order_repo = AsyncMock(spec=OrderRepository)

    order = Order(
        id="order-1",
        customer_id="abc123",
        items=[{"name": "latte", "qty": 1}],
        status="COMPLETED",
    )
    processor.order_repo.get_by_id.return_value = order

    result = await processor.process("order-1")

    assert result is True
    processor.order_repo.mark_completed.assert_not_awaited()
    mock_publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_returns_false_when_order_missing(processor, mock_publisher):
    processor.order_repo = AsyncMock(spec=OrderRepository)
    processor.order_repo.get_by_id.return_value = None

    result = await processor.process("missing-order")

    assert result is False
    mock_publisher.publish.assert_not_awaited()
