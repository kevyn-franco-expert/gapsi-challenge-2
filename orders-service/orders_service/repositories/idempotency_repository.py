"""Idempotency key data access layer."""
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import IdempotencyKey


class IdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_order_id(self, key: str) -> str | None:
        result = await self.session.execute(
            select(IdempotencyKey.order_id).where(IdempotencyKey.key == key)
        )
        return result.scalar_one_or_none()

    async def save(self, key: str, order_id: str) -> None:
        self.session.add(IdempotencyKey(key=key, order_id=order_id))
