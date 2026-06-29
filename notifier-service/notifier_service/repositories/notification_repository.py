"""Notification data access layer for MongoDB."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


class NotificationRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["notifications"]

    async def create(
        self,
        order_id: str,
        customer_id: str,
        message: str,
    ) -> Any:
        document = {
            "order_id": order_id,
            "customer_id": customer_id,
            "message": message,
            "created_at": datetime.now(timezone.utc),
        }
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def find_by_customer(self, customer_id: str) -> list[dict]:
        cursor = (
            self.collection.find({"customer_id": customer_id})
            .sort("created_at", -1)
            .limit(100)
        )
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    async def delete_older_than(self, cutoff: datetime) -> int:
        result = await self.collection.delete_many({"created_at": {"$lt": cutoff}})
        return result.deleted_count
