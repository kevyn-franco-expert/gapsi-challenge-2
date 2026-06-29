"""Business logic for order creation and idempotency."""
from __future__ import annotations
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from orders_service.repositories.idempotency_repository import IdempotencyRepository
from orders_service.repositories.order_repository import OrderRepository
from orders_service.repositories.outbox_repository import OutboxRepository
from orders_service.schemas.order import OrderCreateRequest, OrderResponse
from shared.messaging import EVENT_ORDERS_CREATED

logger = structlog.get_logger()


class OrderService:
    def __init__(
        self,
        session: AsyncSession,
        trace_id: str,
    ) -> None:
        self.session = session
        self.trace_id = trace_id
        self.order_repo = OrderRepository(session)
        self.idempotency_repo = IdempotencyRepository(session)
        self.outbox_repo = OutboxRepository(session)

    async def create_order(self, request: OrderCreateRequest, idempotency_key: str) -> OrderResponse:
        # 1. Idempotency check inside the same transaction that will create the order.
        existing_order_id = await self.idempotency_repo.get_order_id(idempotency_key)
        if existing_order_id:
            order = await self.order_repo.get_by_id(existing_order_id)
            if order:
                logger.info(
                    "idempotent_request_returned_existing_order",
                    idempotency_key=idempotency_key,
                    order_id=order.id,
                    trace_id=self.trace_id,
                )
                return self._to_response(order)

        # 2. Persist order.
        items = [item.model_dump() for item in request.items]
        order = await self.order_repo.create(
            customer_id=request.customer_id,
            items=items,
            status="PENDING",
        )

        # 3. Save idempotency key.
        await self.idempotency_repo.save(idempotency_key, order.id)

        # 4. Write event to outbox (same transaction -> Transactional Outbox pattern).
        payload = {
            "order_id": order.id,
            "customer_id": order.customer_id,
            "items": order.items,
            "status": order.status,
            "created_at": order.created_at.isoformat(),
        }
        await self.outbox_repo.create(
            topic=EVENT_ORDERS_CREATED,
            payload=payload,
            headers={"trace_id": self.trace_id, "event_type": EVENT_ORDERS_CREATED},
        )

        logger.info(
            "order_created_and_outboxed",
            order_id=order.id,
            customer_id=order.customer_id,
            trace_id=self.trace_id,
        )
        return self._to_response(order)

    def _to_response(self, order) -> OrderResponse:
        return OrderResponse(
            order_id=order.id,
            customer_id=order.customer_id,
            status=order.status,
            created_at=order.created_at,
            items=order.items,
        )
