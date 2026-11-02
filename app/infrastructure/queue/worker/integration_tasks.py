"""ARQ jobs for publishing approved replies to external platforms."""

import json
from typing import Any
from uuid import UUID

from arq import Retry
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.logger import get_logger
from app.core.security import decrypt_token
from app.core.tenant_session import set_tenant_rls_context
from app.infrastructure.external.base import (
    PermanentAPIError,
    PlatformAdapterRegistry,
    TransientAPIError,
)
from app.infrastructure.external.yandex import YandexBusinessAdapter

logger = get_logger(__name__)
DEFAULT_RETRY_DELAY_SECONDS = 5.0

PLATFORM_ADAPTER_REGISTRY = PlatformAdapterRegistry()
PLATFORM_ADAPTER_REGISTRY.register("yandex", YandexBusinessAdapter)


def _required_payload_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Integration payload requires a non-empty {key}")
    return value


def _parse_credentials(encrypted_credentials: str) -> dict[str, object]:
    decrypted = decrypt_token(encrypted_credentials)
    decoded = json.loads(decrypted)
    if not isinstance(decoded, dict) or not all(
        isinstance(key, str) for key in decoded
    ):
        raise ValueError("Integration credentials must be a JSON object")
    return decoded


async def process_outbox_integration_job(
    ctx: dict[str, Any],
    event_id: str,
    tenant_id: str,
    payload: dict[str, Any],
) -> None:
    """Publish an outbox reply event without keeping a DB transaction open."""
    event_uuid = UUID(event_id)
    tenant_uuid = UUID(tenant_id)
    payload_tenant_id = UUID(_required_payload_text(payload, "tenant_id"))
    if payload_tenant_id != tenant_uuid:
        raise ValueError("Integration event tenant does not match job tenant")

    platform = _required_payload_text(payload, "platform").strip().lower()
    review_external_id = _required_payload_text(payload, "review_external_id")
    reply_text = _required_payload_text(payload, "text")

    async with AsyncSessionLocal() as session:
        await set_tenant_rls_context(session, tenant_uuid)
        result = await session.execute(
            text(
                "SELECT encrypted_credentials "
                "FROM public.tenant_integrations "
                "WHERE company_id = :tenant_id AND platform = :platform"
            ),
            {"tenant_id": tenant_uuid, "platform": platform},
        )
        encrypted_credentials = result.scalar_one_or_none()

    if not isinstance(encrypted_credentials, str) or not encrypted_credentials:
        raise RuntimeError(
            f"No credentials configured for tenant integration {platform!r}"
        )
    credentials = _parse_credentials(encrypted_credentials)
    adapter = PLATFORM_ADAPTER_REGISTRY.get_adapter(platform)

    try:
        external_reply_id = await adapter.publish_reply(
            review_external_id,
            reply_text,
            credentials,
        )
    except TransientAPIError as exc:
        defer = (
            exc.retry_after
            if exc.retry_after is not None
            else DEFAULT_RETRY_DELAY_SECONDS
        )
        logger.warning(
            "outbox_integration_transient_failure",
            event_id=str(event_uuid),
            tenant_id=str(tenant_uuid),
            platform=platform,
            retry_after=defer,
            error=str(exc),
        )
        raise Retry(defer=defer) from exc
    except PermanentAPIError as exc:
        logger.error(
            "outbox_integration_permanent_failure",
            event_id=str(event_uuid),
            tenant_id=str(tenant_uuid),
            platform=platform,
            error=str(exc),
        )
        return

    logger.info(
        "outbox_integration_reply_published",
        event_id=str(event_uuid),
        tenant_id=str(tenant_uuid),
        platform=platform,
        review_external_id=review_external_id,
        external_reply_id=external_reply_id,
    )
