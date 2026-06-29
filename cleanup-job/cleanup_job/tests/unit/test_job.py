"""Unit tests for cleanup job logic."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from cleanup_job.job import CleanupJob


@pytest.mark.asyncio
async def test_cleanup_deletes_old_notifications():
    db = AsyncMock()
    collection = AsyncMock()
    db.__getitem__ = lambda _, key: collection if key == "notifications" else AsyncMock()

    repo = CleanupJob(db)
    repo.collection = collection
    collection.delete_many = AsyncMock()
    collection.delete_many.return_value = AsyncMock(deleted_count=5)

    count = await repo.run()

    assert count == 5
    collection.delete_many.assert_awaited_once()
    call_args = collection.delete_many.await_args.args[0]
    assert "$lt" in call_args["created_at"]


def test_cutoff_is_24_hours_ago():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    assert (now - cutoff).total_seconds() == 86400
