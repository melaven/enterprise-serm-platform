"""API-key authentication for external B2B clients."""

import hashlib
from uuid import UUID

from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError
from sqlalchemy import text

from app.core.database import AsyncSessionLocal

API_KEY_CACHE_TTL_SECONDS = 300
_CACHE_KEY_PREFIX = "api_key:tenant:"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


async def resolve_api_key_tenant_id(request: Request) -> UUID:
    """Validate a presented API key, using Redis before consulting PostgreSQL."""
    request_tenant_id = getattr(request.state, "api_key_tenant_id", None)
    if request_tenant_id is not None:
        return request_tenant_id

    api_key = request.headers.get("x-api-key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    redis_pool = getattr(request.app.state, "redis_pool", None)
    if redis_pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key storage is unavailable",
        )

    cache_key = f"{_CACHE_KEY_PREFIX}{hash_api_key(api_key)}"
    try:
        cached_tenant_id = await redis_pool.get(cache_key)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key cache is unavailable",
        ) from exc

    if isinstance(cached_tenant_id, bytes):
        cached_tenant_id = cached_tenant_id.decode("ascii")
    if cached_tenant_id:
        try:
            tenant_id = UUID(cached_tenant_id)
        except ValueError:
            try:
                await redis_pool.delete(cache_key)
            except RedisError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="API key cache is unavailable",
                ) from exc
        else:
            request.state.api_key_tenant_id = tenant_id
            return tenant_id

    key_hash = hash_api_key(api_key)
    async with AsyncSessionLocal() as db:
        tenant_value = await db.scalar(
            text("SELECT public.lookup_api_key_tenant(:key_hash)"),
            {"key_hash": key_hash},
        )

    if tenant_value is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    tenant_id = tenant_value if isinstance(tenant_value, UUID) else UUID(tenant_value)
    try:
        await redis_pool.set(cache_key, str(tenant_id), ex=API_KEY_CACHE_TTL_SECONDS)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key cache is unavailable",
        ) from exc

    request.state.api_key_tenant_id = tenant_id
    return tenant_id


async def verify_api_key(request: Request) -> UUID:
    """FastAPI dependency that returns the tenant bound to X-API-Key."""
    return await resolve_api_key_tenant_id(request)
