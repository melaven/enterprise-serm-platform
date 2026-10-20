"""Signed delivery of review-analysis events to tenant webhook endpoints."""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.tenant_session import get_tenant_session
from app.models.economics import WebhookEndpoint

logger = logging.getLogger(__name__)
WEBHOOK_TIMEOUT_SECONDS = 10.0
MAX_CONCURRENT_DELIVERIES = 5


async def _assert_public_https_destination(url: str) -> None:
    parsed = urlsplit(url)
    hostname = parsed.hostname
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("Webhook destination must be a valid HTTPS URL")

    normalized_host = hostname.lower().rstrip(".")
    if normalized_host == "localhost" or normalized_host.endswith(".localhost"):
        raise ValueError("Webhook destination must not target localhost")

    try:
        address = ipaddress.ip_address(normalized_host)
    except ValueError:
        loop = asyncio.get_running_loop()
        resolved = await loop.getaddrinfo(
            normalized_host,
            parsed.port or 443,
            type=socket.SOCK_STREAM,
        )
        addresses = {ipaddress.ip_address(item[4][0]) for item in resolved}
    else:
        addresses = {address}

    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Webhook destination must resolve only to public IPs")


def _serialize_payload(tenant_id: UUID, review_data: Mapping[str, Any]) -> bytes:
    payload = {
        "event": "review.analyzed",
        "tenant_id": str(tenant_id),
        "data": dict(review_data),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


async def dispatch_review_analyzed_event(
    tenant_id: UUID, review_data: Mapping[str, Any]
) -> dict[str, int]:
    """Deliver one signed event to all active endpoints belonging to a tenant."""
    session = await get_tenant_session(
        factory=AsyncSessionLocal,
        tenant_id=tenant_id,
    )
    try:
        result = await session.scalars(
            select(WebhookEndpoint).where(
                WebhookEndpoint.company_id == tenant_id,
                WebhookEndpoint.is_active.is_(True),
            )
        )
        endpoints = list(result.all())
    finally:
        await session.close()

    if not endpoints:
        return {"sent": 0, "failed": 0}

    body = _serialize_payload(tenant_id, review_data)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DELIVERIES)
    sent = 0
    failed = 0

    async with httpx.AsyncClient(
        timeout=WEBHOOK_TIMEOUT_SECONDS,
        follow_redirects=False,
        trust_env=False,
    ) as client:

        async def deliver(endpoint: WebhookEndpoint) -> bool:
            try:
                await _assert_public_https_destination(endpoint.url)
                signature = hmac.new(
                    endpoint.secret_key.encode("utf-8"),
                    body,
                    hashlib.sha256,
                ).hexdigest()
                async with semaphore:
                    response = await client.post(
                        endpoint.url,
                        content=body,
                        headers={
                            "Content-Type": "application/json",
                            "X-Tenable-Signature": f"sha256={signature}",
                        },
                    )
                response.raise_for_status()
                return True
            except (httpx.HTTPError, OSError, ValueError) as exc:
                logger.warning(
                    "Review webhook delivery failed",
                    extra={
                        "tenant_id": str(tenant_id),
                        "endpoint_id": str(endpoint.id),
                        "error_type": type(exc).__name__,
                    },
                )
                return False

        results = await asyncio.gather(*(deliver(endpoint) for endpoint in endpoints))

    sent = sum(results)
    failed = len(results) - sent
    return {"sent": sent, "failed": failed}
