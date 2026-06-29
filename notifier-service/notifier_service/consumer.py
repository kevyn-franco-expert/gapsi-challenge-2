"""RabbitMQ consumer for orders.completed events."""
from __future__ import annotations

from typing import Optional

import structlog
from aio_pika import IncomingMessage
from motor.motor_asyncio import AsyncIOMotorClient
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from notifier_service.repositories.notification_repository import NotificationRepository
from shared.config import get_settings
from shared.messaging import (
    EVENT_ORDERS_COMPLETED,
    EventConsumer,
    connect_rabbitmq,
    decode_message,
)

logger = structlog.get_logger()


class OrderCompletedConsumer:
    def __init__(self, mongodb_url: str, rabbitmq_url: str, db_name: str) -> None:
        self.mongodb_url = mongodb_url
        self.rabbitmq_url = rabbitmq_url
        self.db_name = db_name
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.consumer: Optional[EventConsumer] = None

    async def start(self) -> None:
        self.mongo_client = AsyncIOMotorClient(self.mongodb_url)
        db = self.mongo_client[self.db_name]
        self.notification_repo = NotificationRepository(db)

        connection = await connect_rabbitmq(self.rabbitmq_url)
        self.consumer = EventConsumer(
            connection=connection,
            queue_name="notifier.orders.completed",
            routing_key=EVENT_ORDERS_COMPLETED,
            handler=self._handle_message,
            prefetch_count=10,
        )
        await self.consumer.start()
        logger.info("notifier_consumer_started")

    async def stop(self) -> None:
        if self.consumer:
            await self.consumer.close()
        if self.mongo_client:
            self.mongo_client.close()
        logger.info("notifier_consumer_stopped")

    async def _handle_message(self, message: IncomingMessage) -> None:
        async with message.process(ignore_processed=True):
            body = decode_message(message)
            order_id = body.get("order_id")
            customer_id = body.get("customer_id")
            trace_id = (message.headers or {}).get("trace_id") or body.get("trace_id") or "unknown"
            structlog.contextvars.bind_contextvars(trace_id=trace_id)

            if not order_id or not customer_id:
                logger.error("invalid_completed_event", body=body)
                return

            await self._create_notification_with_retry(order_id, customer_id, trace_id)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def _create_notification_with_retry(
        self, order_id: str, customer_id: str, trace_id: str
    ) -> None:
        message_text = f"Your order {order_id} is ready for pickup!"
        await self.notification_repo.create(
            order_id=order_id,
            customer_id=customer_id,
            message=message_text,
        )
        logger.info(
            "notification_created",
            order_id=order_id,
            customer_id=customer_id,
            trace_id=trace_id,
        )


_consumer: Optional[OrderCompletedConsumer] = None


async def start_consumer() -> None:
    global _consumer
    settings = get_settings()
    _consumer = OrderCompletedConsumer(
        mongodb_url=settings.mongodb_url,
        rabbitmq_url=settings.rabbitmq_url,
        db_name=settings.mongodb_db,
    )
    await _consumer.start()


async def stop_consumer() -> None:
    global _consumer
    if _consumer:
        await _consumer.stop()
        _consumer = None
