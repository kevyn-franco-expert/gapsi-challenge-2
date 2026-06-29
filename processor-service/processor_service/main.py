"""Processor service entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from processor_service.consumer import start_consumer, stop_consumer
from shared.config import get_settings
from shared.health import health_router
from shared.logging_config import configure_logging

configure_logging(service_name="processor-service")
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "processor_service_starting",
        postgres_host=settings.postgres_host,
        rabbitmq_host=settings.rabbitmq_host,
    )
    await start_consumer()
    yield
    await stop_consumer()
    logger.info("processor_service_stopped")


app = FastAPI(
    title="Café Cloud — Processor Service",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health_router)
