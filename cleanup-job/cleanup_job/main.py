"""Cleanup job entrypoint with APScheduler + small FastAPI for manual trigger."""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Optional

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from cleanup_job.job import CleanupJob
from shared.config import get_settings
from shared.health import health_router
from shared.logging_config import configure_logging

configure_logging(service_name="cleanup-job")
logger = structlog.get_logger()

settings = get_settings()
mongo_client: Optional[AsyncIOMotorClient] = None
scheduler: Optional[AsyncIOScheduler] = None


def get_database():
    return mongo_client[settings.mongodb_db]


async def run_cleanup() -> int:
    job = CleanupJob(get_database())
    return await job.run()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo_client, scheduler
    logger.info("cleanup_job_starting", mongodb_host=settings.mongodb_host)
    mongo_client = AsyncIOMotorClient(settings.mongodb_url)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_cleanup, "interval", minutes=1, id="cleanup_notifications")
    scheduler.start()

    yield

    if scheduler:
        scheduler.shutdown()
    if mongo_client:
        mongo_client.close()
    logger.info("cleanup_job_stopped")


app = FastAPI(
    title="Café Cloud — Cleanup Job",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health_router)


@app.post("/jobs/cleanup/run", summary="Manually trigger cleanup")
async def trigger_cleanup() -> dict:
    deleted = await run_cleanup()
    return {"deleted_count": deleted}
