"""Tenant-scoped management API for external-client keys."""

import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.api_keys import APIKeyCreate, APIKeyCreated, APIKeyOut
from app.core.api_keys import hash_api_key
from app.core.auth import get_current_tenant
from app.core.dependencies import get_tenant_db
from app.infrastructure.persistence.models.api_key import APIKey

router = APIRouter(prefix="/api/v1/api-keys", tags=["API Keys"])


@router.post("", response_model=APIKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: APIKeyCreate,
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> APIKeyCreated:
    api_key = f"serm_live_{secrets.token_urlsafe(32)}"
    record = APIKey(
        tenant_id=tenant_id,
        name=body.name,
        key_hash=hash_api_key(api_key),
    )
    db.add(record)
    await db.flush()

    return APIKeyCreated(
        id=record.id,
        name=record.name,
        created_at=record.created_at,
        revoked_at=record.revoked_at,
        key=api_key,
    )


@router.get("", response_model=list[APIKeyOut])
async def list_api_keys(
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[APIKey]:
    result = await db.scalars(
        select(APIKey)
        .where(APIKey.tenant_id == tenant_id)
        .order_by(APIKey.created_at.desc())
    )
    return list(result.all())


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    request: Request,
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> Response:
    record = await db.scalar(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.tenant_id == tenant_id,
            APIKey.revoked_at.is_(None),
        )
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    record.revoked_at = datetime.now(timezone.utc)
    redis_pool = getattr(request.app.state, "redis_pool", None)
    if redis_pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key cache is unavailable",
        )
    try:
        await redis_pool.delete(f"api_key:tenant:{record.key_hash}")
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key cache is unavailable",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
