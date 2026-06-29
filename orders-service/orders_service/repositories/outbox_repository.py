"""Outbox data access layer."""
from __future__ import annotations
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Outbox


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        topic: str,
        payload: dict,
        headers: Optional[dict] = None,
    ) -> Outbox:
        entry = Outbox(topic=topic, payload=payload, headers=headers or {})
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def get_unprocessed(self, batch_size: int = 100) -> list[Outbox]:
        result = await self.session.execute(
            select(Outbox)
            .where(Outbox.processed_at.is_(None))
            .order_by(Outbox.id)
            .limit(batch_size)
        )
        return list(result.scalars().all())

    async def mark_processed(self, entry_id: int) -> None:
        from shared.models import utc_now

        entry = await self.session.get(Outbox, entry_id)
        if entry:
            entry.processed_at = utc_now()
