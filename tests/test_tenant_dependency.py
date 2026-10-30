from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.dependencies.tenant import get_current_user, verify_tenant_access
from app.api.schemas.auth import AuthContext, JWTPayload
from app.core.auth import get_current_tenant


@pytest.mark.asyncio
async def test_verify_tenant_access_returns_current_company() -> None:
    company_id = uuid4()
    current_user = AuthContext(user_id=uuid4(), company_id=company_id)

    authorized_company_id = await verify_tenant_access(company_id, current_user)

    assert authorized_company_id == company_id


@pytest.mark.asyncio
async def test_verify_tenant_access_rejects_another_company() -> None:
    current_user = AuthContext(user_id=uuid4(), company_id=uuid4())

    with pytest.raises(HTTPException) as error:
        await verify_tenant_access(uuid4(), current_user)

    assert error.value.status_code == 403
    assert error.value.detail == "Access denied to this tenant"


@pytest.mark.asyncio
async def test_current_tenant_accepts_explicit_company_id_claim() -> None:
    company_id = uuid4()
    payload = JWTPayload(sub=uuid4(), company_id=company_id)

    assert await get_current_tenant(payload) == company_id


@pytest.mark.asyncio
async def test_current_tenant_does_not_fall_back_to_user_id() -> None:
    payload = JWTPayload(sub=uuid4())

    with pytest.raises(HTTPException) as error:
        await get_current_tenant(payload)

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid authentication token: missing tenant context"


@pytest.mark.asyncio
async def test_get_current_user_rejects_payload_without_tenant_context() -> None:
    payload = JWTPayload(sub=uuid4())

    with pytest.raises(HTTPException) as error:
        await get_current_user(payload)

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid authentication token: missing tenant context"
