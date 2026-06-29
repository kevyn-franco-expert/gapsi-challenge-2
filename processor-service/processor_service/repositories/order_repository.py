"""Order data access for processor-service."""
from __future__ import annotations
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Order


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, order_id: str) -> Optional[Order]:
        result = await self.session.execute(select(Order).where(Order.id == order_id))
        return result.scalar_one_or_none()

    async def mark_completed(self, order_id: str) -> Optional[Order]:
        order = await self.get_by_id(order_id)
        if not order:
            return None
        order.status = "COMPLETED"
        await self.session.flush()
        await self.session.refresh(order)
        return order
