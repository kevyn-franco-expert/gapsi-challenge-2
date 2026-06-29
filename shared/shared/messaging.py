"""Async RabbitMQ helpers built on aio-pika."""
from __future__ import annotations

import json
from typing import Any, Callable, Coroutine, Optional

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, IncomingMessage, Queue


EVENT_ORDERS_CREATED = "orders.created"
EVENT_ORDERS_COMPLETED = "orders.completed"

EXCHANGE_EVENTS = "events"
DLX_EXCHANGE = "events.dlx"


async def connect_rabbitmq(url: str) -> aio_pika.RobustConnection:
    """Create a robust (auto-reconnecting) connection to RabbitMQ."""
    return await aio_pika.connect_robust(url)


async def declare_event_exchange(channel: aio_pika.Channel):
    """Declare the main topic exchange used for domain events."""
    return await channel.declare_exchange(
        EXCHANGE_EVENTS,
        ExchangeType.TOPIC,
        durable=True,
    )


async def declare_dead_letter_exchange(channel: aio_pika.Channel):
    """Declare DLX exchange for messages that exceed the consumer retry budget."""
    return await channel.declare_exchange(
        DLX_EXCHANGE,
        ExchangeType.TOPIC,
        durable=True,
    )


async def declare_queue_with_dlq(
    channel: aio_pika.Channel,
    queue_name: str,
    routing_key: str,
    prefetch_count: int = 10,
) -> Queue:
    """Declare a durable queue bound to the events exchange; failed messages go to a DLQ."""
    dlx_queue_name = f"{queue_name}.dlq"

    dlx_exchange = await declare_dead_letter_exchange(channel)
    events_exchange = await declare_event_exchange(channel)

    # Dead-letter queue holds messages for manual inspection.
    dlx_queue = await channel.declare_queue(dlx_queue_name, durable=True)
    await dlx_queue.bind(dlx_exchange, routing_key)

    # Main queue: rejected messages are routed to the DLX.
    queue = await channel.declare_queue(
        queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": routing_key,
        },
    )
    await queue.bind(events_exchange, routing_key)

    await channel.set_qos(prefetch_count=prefetch_count)
    return queue


class EventPublisher:
    """Reliable event publisher with publisher confirms."""

    def __init__(self, connection: aio_pika.RobustConnection) -> None:
        self.connection = connection
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None

    async def connect(self) -> None:
        self.channel = await self.connection.channel(publisher_confirms=True)
        self.exchange = await declare_event_exchange(self.channel)

    async def publish(
        self,
        routing_key: str,
        payload: dict[str, Any],
        headers: Optional[dict[str, Any]] = None,
    ) -> None:
        if not self.channel or not self.exchange:
            raise RuntimeError("Publisher not connected")

        message = aio_pika.Message(
            body=json.dumps(payload, default=str).encode("utf-8"),
            headers=headers or {},
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self.exchange.publish(message, routing_key=routing_key, mandatory=False)

    async def close(self) -> None:
        if self.channel and not self.channel.is_closed:
            await self.channel.close()


class EventConsumer:
    """Base async consumer with manual ack and graceful shutdown."""

    def __init__(
        self,
        connection: aio_pika.RobustConnection,
        queue_name: str,
        routing_key: str,
        handler: Callable[[IncomingMessage], Coroutine[Any, Any, None]],
        prefetch_count: int = 10,
    ) -> None:
        self.connection = connection
        self.queue_name = queue_name
        self.routing_key = routing_key
        self.handler = handler
        self.prefetch_count = prefetch_count
        self.channel: Optional[aio_pika.Channel] = None
        self.queue: Optional[Queue] = None

    async def start(self) -> None:
        self.channel = await self.connection.channel()
        self.queue = await declare_queue_with_dlq(
            self.channel,
            self.queue_name,
            self.routing_key,
            self.prefetch_count,
        )
        await self.queue.consume(self.handler)

    async def close(self) -> None:
        if self.channel and not self.channel.is_closed:
            await self.channel.close()


def decode_message(message: IncomingMessage) -> dict[str, Any]:
    """Decode JSON body from an incoming RabbitMQ message."""
    return json.loads(message.body.decode("utf-8"))
