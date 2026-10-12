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
    db.execute.return_value = SimpleNamespace(fetchone=Mock(return_value=(3, 100)))

    result = await consume_request(db, TENANT_ID)

    assert result == {"used": 3, "limit": 100}
    db.execute.assert_awaited_once()
    query, params = db.execute.await_args.args
    assert "UPDATE organization_quotas" in str(query)
    assert "FROM billing_plans" in str(query)
    assert "o.requests_used + :amount <= p.max_requests" in str(query)
    assert params == {"tenant_id": TENANT_ID, "amount": 1}
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
