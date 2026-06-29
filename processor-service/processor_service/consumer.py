"""RabbitMQ consumer for orders.created events."""
from __future__ import annotations

from typing import Optional

import aio_pika
import structlog
from aio_pika import IncomingMessage
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from processor_service.services.processor import OrderProcessor
from shared.config import get_settings
from shared.db import Database
from shared.messaging import (
    EVENT_ORDERS_CREATED,
    EventConsumer,
    EventPublisher,
    connect_rabbitmq,
    decode_message,
)

logger = structlog.get_logger()


class OrderCreatedConsumer:
    def __init__(self, database_url: str, rabbitmq_url: str) -> None:
        self.database_url = database_url
        self.rabbitmq_url = rabbitmq_url
        self.db = Database(database_url)
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.publisher: Optional[EventPublisher] = None
        self.consumer: Optional[EventConsumer] = None

    async def start(self) -> None:
        self.connection = await connect_rabbitmq(self.rabbitmq_url)
        self.publisher = EventPublisher(self.connection)
        await self.publisher.connect()

        self.consumer = EventConsumer(
            connection=self.connection,
            queue_name="processor.orders.created",
            routing_key=EVENT_ORDERS_CREATED,
            handler=self._handle_message,
            prefetch_count=10,
        )
        await self.consumer.start()
        logger.info("processor_consumer_started")

    async def stop(self) -> None:
        if self.consumer:
            await self.consumer.close()
        if self.publisher:
            await self.publisher.close()
        await self.db.close()
        logger.info("processor_consumer_stopped")

    async def _handle_message(self, message: IncomingMessage) -> None:
        async with message.process(ignore_processed=True):
            body = decode_message(message)
            order_id = body.get("order_id")
            trace_id = (message.headers or {}).get("trace_id") or body.get("trace_id") or "unknown"
            structlog.contextvars.bind_contextvars(trace_id=trace_id)

            if not order_id:
                logger.error("missing_order_id_in_message", body=body)
                return

            await self._process_with_retry(order_id, trace_id)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _process_with_retry(self, order_id: str, trace_id: str) -> None:
        async with self.db.session_factory() as session:
            processor = OrderProcessor(
                session=session,
                trace_id=trace_id,
                publisher=self.publisher,
            )
            success = await processor.process(order_id)
            if not success:
                # Non-retriable scenario (order missing); do not raise -> ack message.
                logger.warning(
                    "order_processing_skipped_non_retriable",
                    order_id=order_id,
                    trace_id=trace_id,
                )


_consumer: Optional[OrderCreatedConsumer] = None


async def start_consumer() -> None:
    global _consumer
    settings = get_settings()
    _consumer = OrderCreatedConsumer(
        database_url=settings.postgres_url,
        rabbitmq_url=settings.rabbitmq_url,
    )
    await _consumer.start()


async def stop_consumer() -> None:
    global _consumer
    if _consumer:
        await _consumer.stop()
        _consumer = None
