"""Business logic for processing orders."""
from __future__ import annotations

import asyncio
import random
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from processor_service.repositories.order_repository import OrderRepository
from shared.messaging import EVENT_ORDERS_COMPLETED, EventPublisher

logger = structlog.get_logger()


class OrderProcessor:
    def __init__(
        self,
        session: AsyncSession,
        trace_id: str,
        publisher: Optional[EventPublisher] = None,
        min_sleep: float = 2.0,
        max_sleep: float = 5.0,
    ) -> None:
        self.session = session
        self.trace_id = trace_id
        self.publisher = publisher
        self.min_sleep = min_sleep
        self.max_sleep = max_sleep
        self.order_repo = OrderRepository(session)

    async def process(self, order_id: str) -> bool:
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            logger.warning(
                "order_not_found_for_processing",
                order_id=order_id,
                trace_id=self.trace_id,
            )
            return False

        # Idempotent consumer: avoid re-processing completed orders.
        if order.status == "COMPLETED":
            logger.info(
                "order_already_completed_skipping",
                order_id=order_id,
                trace_id=self.trace_id,
            )
            return True

        # Simulate coffee preparation.
        sleep_seconds = random.uniform(self.min_sleep, self.max_sleep)
        logger.info(
            "preparing_order",
            order_id=order_id,
            sleep_seconds=round(sleep_seconds, 2),
            trace_id=self.trace_id,
        )
        await asyncio.sleep(sleep_seconds)

        # Persist completion.
        await self.order_repo.mark_completed(order_id)
        await self.session.commit()

        # Publish completion event directly to RabbitMQ.
        if self.publisher:
            await self.publisher.publish(
                routing_key=EVENT_ORDERS_COMPLETED,
                payload={
                    "order_id": order.id,
                    "customer_id": order.customer_id,
                    "status": "COMPLETED",
                    "completed_at": order.updated_at.isoformat() if order.updated_at else None,
                },
                headers={"trace_id": self.trace_id, "event_type": EVENT_ORDERS_COMPLETED},
            )

        logger.info(
            "order_completed",
            order_id=order_id,
            customer_id=order.customer_id,
            trace_id=self.trace_id,
        )
        return True
