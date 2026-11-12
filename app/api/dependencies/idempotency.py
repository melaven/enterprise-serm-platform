"""Idempotency checks for externally ingested review events."""

import hashlib
import json
from typing import Protocol
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from app.api.dependencies.tenant import verify_tenant_access
from app.api.errors import DuplicateWebhookError
from app.api.schemas.ingest import ReviewIngestPayload


class _RedisSetClient(Protocol):
    async def set(
        self,
        name: str,
        value: str,
        *,
        nx: bool,
        ex: int,
    ) -> bool | None: ...


def build_review_idempotency_key(
    tenant_id: UUID,
    platform: str,
    external_review_id: str,
) -> str:
    """Build a stable, tenant-scoped key without exposing event identifiers."""
    identity = json.dumps(
        {
            "tenant_id": str(tenant_id),
            "platform": platform.strip().lower(),
            "external_review_id": external_review_id.strip(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(identity).hexdigest()
    return f"idempotency:review:{digest}"


async def verify_review_idempotency(
    request: Request,
    payload: ReviewIngestPayload,
    tenant_id: UUID = Depends(verify_tenant_access),
) -> None:
    """Atomically claim an incoming review event for processing."""
    redis: _RedisSetClient | None = getattr(request.app.state, "redis_pool", None)
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review ingestion idempotency service is unavailable",
        )

    hash_key = build_review_idempotency_key(
        tenant_id,
        payload.platform,
        payload.external_id,
    )
    claimed = await redis.set(
        name=hash_key,
        value="processing",
        nx=True,
        ex=60,
    )
    if not claimed:
        raise DuplicateWebhookError
