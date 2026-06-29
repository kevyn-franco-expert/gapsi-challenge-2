"""Notification API endpoints."""
from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from notifier_service.repositories.notification_repository import NotificationRepository
from shared.config import CommonSettings, get_settings

router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_db_client():
    from notifier_service.main import mongo_client

    return mongo_client


def get_notification_repository(
    client=Depends(get_db_client),
    settings: CommonSettings = Depends(get_settings),
) -> NotificationRepository:
    return NotificationRepository(client[settings.mongodb_db])


def api_key_auth(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    settings: CommonSettings = Depends(get_settings),
):
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


@router.get(
    "/{customer_id}",
    summary="List notifications for a customer",
    dependencies=[Depends(api_key_auth)] if get_settings().api_key else [],
)
async def list_notifications(
    customer_id: str,
    repo: NotificationRepository = Depends(get_notification_repository),
) -> list[dict]:
    return await repo.find_by_customer(customer_id)
