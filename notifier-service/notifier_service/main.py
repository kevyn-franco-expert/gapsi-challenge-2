"""Notifier service entrypoint."""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Optional

import structlog
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from notifier_service.api import notifications
from notifier_service.consumer import start_consumer, stop_consumer
from shared.config import get_settings
from shared.health import health_router
from shared.logging_config import configure_logging

configure_logging(service_name="notifier-service")
logger = structlog.get_logger()

settings = get_settings()
mongo_client: Optional[AsyncIOMotorClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo_client
    logger.info(
        "notifier_service_starting",
        mongodb_host=settings.mongodb_host,
        rabbitmq_host=settings.rabbitmq_host,
    )
    mongo_client = AsyncIOMotorClient(settings.mongodb_url)
    await start_consumer()
    yield
    await stop_consumer()
    if mongo_client:
        mongo_client.close()
    logger.info("notifier_service_stopped")


app = FastAPI(
    title="Cafe Cloud — Notifier Service",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(notifications.router)
