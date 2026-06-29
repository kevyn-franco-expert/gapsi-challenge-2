"""Unit tests for notification repository logic."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from notifier_service.repositories.notification_repository import NotificationRepository


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=MagicMock())
    return db


@pytest.fixture
def repo(mock_db):
    return NotificationRepository(mock_db)


@pytest.mark.asyncio
async def test_create_notification(repo):
    repo.collection = MagicMock()
    repo.collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="nid-1"))

    result = await repo.create("order-1", "abc123", "Ready!")

    assert result["customer_id"] == "abc123"
    assert result["order_id"] == "order-1"
    repo.collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_older_than(repo):
    repo.collection = MagicMock()
    repo.collection.delete_many = AsyncMock(return_value=MagicMock(deleted_count=3))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    count = await repo.delete_older_than(cutoff)

    assert count == 3
    repo.collection.delete_many.assert_awaited_once()
