from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from fastapi import HTTPException, status

from app.core.billing_deps import consume_request

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_consume_request_updates_and_commits_quota() -> None:
    db = AsyncMock()
    now = datetime.now(timezone.utc)
    # Мок для consume_reviews - возвращает success=True
    # Мок для get_status - возвращает полную структуру квоты
    db.execute.return_value = SimpleNamespace(
        fetchone=Mock(
            side_effect=[
                # Первый вызов - consume_reviews
                SimpleNamespace(success=True),
                # Второй вызов - get_status
                SimpleNamespace(
                    tenant_id=TENANT_ID,
                    max_llm_tokens=10000,
                    max_reviews=100,
                    used_llm_tokens=5000,
                    used_reviews=3,
                    reserved_llm_tokens=0,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
    )

    result = await consume_request(db, TENANT_ID)

    assert result == {"used": 3, "limit": 100}
    db.execute.assert_awaited()
    assert db.execute.await_count >= 2  # consume_reviews + get_status
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_consume_request_rejects_when_quota_cannot_be_updated() -> None:
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(fetchone=Mock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        await consume_request(db, TENANT_ID)

    assert exc_info.value.status_code == status.HTTP_402_PAYMENT_REQUIRED
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_consume_request_rejects_non_positive_amount() -> None:
    db = AsyncMock()

    with pytest.raises(ValueError, match="amount must be at least 1"):
        await consume_request(db, TENANT_ID, amount=0)

    db.execute.assert_not_awaited()
