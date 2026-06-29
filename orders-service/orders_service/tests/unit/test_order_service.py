"""Unit tests for order creation and idempotency logic."""
from __future__ import annotations
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from orders_service.repositories.idempotency_repository import IdempotencyRepository
from orders_service.repositories.order_repository import OrderRepository
from orders_service.repositories.outbox_repository import OutboxRepository
from orders_service.schemas.order import OrderCreateRequest, OrderItem
from orders_service.services.order_service import OrderService
from shared.models import Order, utc_now


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def service(mock_session):
    return OrderService(session=mock_session, trace_id="trace-123")


@pytest.fixture
def sample_request():
    return OrderCreateRequest(
        customer_id="abc123",
        items=[OrderItem(name="latte", qty=1)],
    )


@pytest.mark.asyncio
async def test_create_order_persists_and_outboxes(service, sample_request):
    service.order_repo = AsyncMock(spec=OrderRepository)
    service.idempotency_repo = AsyncMock(spec=IdempotencyRepository)
    service.outbox_repo = AsyncMock(spec=OutboxRepository)

    service.idempotency_repo.get_order_id.return_value = None
    order = Order(
        id="order-1",
        customer_id=sample_request.customer_id,
        items=[{"name": "latte", "qty": 1}],
        status="PENDING",
        created_at=utc_now(),
    )
    service.order_repo.create.return_value = order

    result = await service.create_order(sample_request, "idem-key-1")

    assert result.order_id == "order-1"
    assert result.status == "PENDING"
    service.idempotency_repo.save.assert_awaited_once_with("idem-key-1", "order-1")
    service.outbox_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_order_is_idempotent(service, sample_request):
    service.order_repo = AsyncMock(spec=OrderRepository)
    service.idempotency_repo = AsyncMock(spec=IdempotencyRepository)
    service.outbox_repo = AsyncMock(spec=OutboxRepository)

    service.idempotency_repo.get_order_id.return_value = "order-1"
    existing = Order(
        id="order-1",
        customer_id=sample_request.customer_id,
        items=[{"name": "latte", "qty": 1}],
        status="PENDING",
        created_at=utc_now(),
    )
    service.order_repo.get_by_id.return_value = existing

    result = await service.create_order(sample_request, "idem-key-1")

    assert result.order_id == "order-1"
    service.order_repo.create.assert_not_awaited()
    service.outbox_repo.create.assert_not_awaited()
