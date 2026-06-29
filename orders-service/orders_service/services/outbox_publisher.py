"""Background relay that publishes outbox rows to RabbitMQ."""
from __future__ import annotations
import asyncio
from typing import Optional

import structlog

from orders_service.repositories.outbox_repository import OutboxRepository
from shared.config import get_settings
from shared.db import Database
from shared.messaging import EventPublisher, connect_rabbitmq

logger = structlog.get_logger()


class OutboxPublisher:
    """Poll the outbox table and publish unprocessed events to RabbitMQ."""

    def __init__(self, database_url: str, rabbitmq_url: str, poll_interval: float = 2.0) -> None:
        self.database_url = database_url
        self.rabbitmq_url = rabbitmq_url
        self.poll_interval = poll_interval
        self.db = Database(database_url)
        self.publisher: Optional[EventPublisher] = None
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        connection = await connect_rabbitmq(self.rabbitmq_url)
        self.publisher = EventPublisher(connection)
        await self.publisher.connect()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("outbox_publisher_started")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.publisher:
            await self.publisher.close()
        await self.db.close()
        logger.info("outbox_publisher_stopped")

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._process_batch()
            except Exception:
                logger.exception("outbox_batch_failed")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                pass

    async def _process_batch(self) -> None:
        async with self.db.session_factory() as session:
            outbox_repo = OutboxRepository(session)
            rows = await outbox_repo.get_unprocessed(batch_size=100)
            if not rows:
                return

            for row in rows:
                if not self.publisher:
                    return
                await self.publisher.publish(
                    routing_key=row.topic,
                    payload=row.payload,
                    headers=row.headers,
                )
                await outbox_repo.mark_processed(row.id)
                await session.commit()
                logger.info(
                    "outbox_event_published",
                    topic=row.topic,
                    outbox_id=row.id,
                    trace_id=row.headers.get("trace_id"),
                )


# Global singleton used by the FastAPI lifespan.
_outbox_publisher: Optional[OutboxPublisher] = None


async def start_outbox_publisher() -> None:
    global _outbox_publisher
    settings = get_settings()
    _outbox_publisher = OutboxPublisher(
        database_url=settings.postgres_url,
        rabbitmq_url=settings.rabbitmq_url,
    )
    await _outbox_publisher.start()


async def stop_outbox_publisher() -> None:
    global _outbox_publisher
    if _outbox_publisher:
        await _outbox_publisher.stop()
        _outbox_publisher = None
