"""Notification cleanup job logic."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

import structlog
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from shared.config import get_settings

logger = structlog.get_logger()


class CleanupJob:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["notifications"]

    async def run(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await self.collection.delete_many({"created_at": {"$lt": cutoff}})
        logger.info(
            "cleanup_job_finished",
            deleted_count=result.deleted_count,
            cutoff=cutoff.isoformat(),
        )
        return result.deleted_count
