"""Orders API endpoints."""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from orders_service.schemas.order import OrderCreateRequest, OrderResponse
from orders_service.services.order_service import OrderService
from shared.config import get_settings
from shared.db import Database

router = APIRouter(prefix="/orders", tags=["orders"])

settings = get_settings()
database = Database(settings.postgres_url)


async def get_db_session():
    async with database.session_factory() as session:
        yield session


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order (idempotent)",
)
async def create_order(
    request: OrderCreateRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    session: AsyncSession = Depends(get_db_session),
) -> OrderResponse:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )

    trace_id = str(uuid4())
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    service = OrderService(session=session, trace_id=trace_id)
    response = await service.create_order(request, idempotency_key.strip())
    await session.commit()
    return response
