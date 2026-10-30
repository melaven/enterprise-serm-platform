from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.infrastructure.repositories.bulk_reviews import BulkReviewRepository


class _Result:
    def fetchall(self) -> list[tuple[str]]:
        return [("review-1",), ("review-2",)]


@pytest.mark.asyncio
async def test_bulk_upsert_uses_unnest_and_updates_existing_rows() -> None:
    company_id = uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[object(), _Result()])
    repository = BulkReviewRepository(session)
    batch = [
        {
            "tenant_id": company_id,
            "platform": "yandex",
            "external_id": "usr_000000000000000000000000",
            "author_hash": "usr_111111111111111111111111",
            "author_display": "Клиент",
            "clean_text": "Санитизированный отзыв",
            "rating": 5,
            "published_at": datetime(2026, 10, 30, tzinfo=timezone.utc),
        }
    ]

    affected = await repository.bulk_upsert_reviews(batch)

    assert affected == 2
    statement, parameters = session.execute.await_args_list[1].args
    sql = str(statement)
    assert "UNNEST(" in sql
    assert "ON CONFLICT (company_id, platform, external_id)" in sql
    assert "ON CONFLICT (company_id, platform, external_id)\n        WHERE" not in sql
    assert "text = EXCLUDED.text" in sql
    assert "updated_at = NOW()" in sql
    assert parameters["company_ids"] == [company_id]
    assert parameters["clean_texts"] == ["Санитизированный отзыв"]


@pytest.mark.asyncio
async def test_bulk_upsert_empty_batch_skips_database() -> None:
    session = AsyncMock()

    assert await BulkReviewRepository(session).bulk_upsert_reviews([]) == 0
    session.execute.assert_not_awaited()
