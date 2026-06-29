"""Order data access layer."""
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

    async def create(self, customer_id: str, items: list[dict], status: str = "PENDING") -> Order:
        order = Order(customer_id=customer_id, items=items, status=status)
        self.session.add(order)
        await self.session.flush()
        await self.session.refresh(order)
        return order

    async def update_status(self, order_id: str, status: str) -> Optional[Order]:
        order = await self.get_by_id(order_id)
        if order:
            order.status = status
            await self.session.flush()
            await self.session.refresh(order)
        return order
