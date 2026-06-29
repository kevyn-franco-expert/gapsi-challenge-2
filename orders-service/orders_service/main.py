"""Orders service entrypoint."""
from __future__ import annotations
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from orders_service.api import orders
from orders_service.services.outbox_publisher import (
    start_outbox_publisher,
    stop_outbox_publisher,
)
from shared.config import get_settings
from shared.health import health_router
from shared.logging_config import configure_logging

configure_logging(service_name="orders-service")
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "orders_service_starting",
        postgres_host=settings.postgres_host,
        rabbitmq_host=settings.rabbitmq_host,
    )
    await start_outbox_publisher()
    yield
    await stop_outbox_publisher()
    logger.info("orders_service_stopped")


app = FastAPI(
    title="Café Cloud — Orders Service",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(orders.router)
