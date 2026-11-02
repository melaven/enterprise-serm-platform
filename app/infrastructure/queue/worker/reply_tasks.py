"""ARQ tasks for publishing approved replies to review platforms."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from arq import Retry
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal
from app.core.logger import get_logger
from app.core.security import decrypt_token
from app.core.tenant_session import set_tenant_rls_context
from app.domain.reviews.publication import ReplyPublicationStatus
from app.infrastructure.integrations.review_platforms.base import (
    BasePlatformAdapter,
    PermanentAPIError,
    TransientAPIError,
)
from app.infrastructure.integrations.review_platforms.factory import (
    PlatformAdapterFactory,
)
from app.infrastructure.persistence.models.economics import (
    PlatformIntegration,
    Review,
)
from app.infrastructure.persistence.models.review_reply import ReviewReply

logger = get_logger(__name__)
DEFAULT_RETRY_DELAY_SECONDS = 5.0


@dataclass(frozen=True)
class ReplyPublication:
    integration_id: UUID
    review_external_id: str
    reply_text: str
    platform: str
    api_key: str
    encrypted_api_key: str
    refresh_token: str | None
    encrypted_refresh_token: str | None
    expires_at: datetime | None
    meta_config: dict[str, object]


@dataclass(frozen=True)
class RefreshedCredentials:
    api_key: str
    refresh_token: str | None
    expires_at: datetime | None


async def _load_reply_publication(
    tenant_id: UUID, review_id: UUID
) -> ReplyPublication | None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_rls_context(session, tenant_id)
            result = await session.execute(
                select(ReviewReply, Review, PlatformIntegration)
                .join(
                    Review,
                    (ReviewReply.review_id == Review.id)
                    & (ReviewReply.company_id == Review.company_id),
                )
                .join(
                    PlatformIntegration,
                    (PlatformIntegration.company_id == Review.company_id)
                    & (PlatformIntegration.platform == Review.platform),
                )
                .where(
                    Review.id == review_id,
                    Review.company_id == tenant_id,
                    PlatformIntegration.is_active.is_(True),
                )
                .with_for_update(of=ReviewReply)
            )
            row = result.one_or_none()
            if row is None:
                raise RuntimeError(
                    f"Reply, review, or active integration not found for {review_id}"
                )
            reply, review, integration = row
            if reply.status == ReplyPublicationStatus.PUBLISHED:
                return None
            if reply.status not in {
                ReplyPublicationStatus.QUEUED_OUTBOX,
                ReplyPublicationStatus.PUBLISHING,
            }:
                raise RuntimeError(f"Reply {review_id} is not queued for publication")
            if not isinstance(review.external_id, str) or not review.external_id:
                raise ValueError(f"Review {review_id} has no external platform ID")
            if not isinstance(review.platform, str) or not review.platform:
                raise ValueError(f"Review {review_id} has no platform")
            if not isinstance(reply.reply_text, str) or not reply.reply_text.strip():
                raise ValueError(f"Review {review_id} has no approved reply")
            if not isinstance(integration.meta_config, dict):
                raise ValueError("Platform integration metadata must be an object")

            reply.status = ReplyPublicationStatus.PUBLISHING
            reply.failure_reason = None
            await session.flush()
            return ReplyPublication(
                integration_id=integration.id,
                review_external_id=review.external_id,
                reply_text=reply.reply_text,
                platform=review.platform.strip().lower(),
                api_key=decrypt_token(integration.encrypted_api_key),
                encrypted_api_key=integration.encrypted_api_key,
                refresh_token=(
                    decrypt_token(integration.encrypted_refresh_token)
                    if integration.encrypted_refresh_token
                    else None
                ),
                encrypted_refresh_token=integration.encrypted_refresh_token,
                expires_at=integration.expires_at,
                meta_config=integration.meta_config,
            )


async def _record_publish_result(
    tenant_id: UUID,
    review_id: UUID,
    *,
    status: ReplyPublicationStatus,
    external_reply_id: str | None = None,
    failure_reason: str | None = None,
    integration_id: UUID | None = None,
    original_encrypted_api_key: str | None = None,
    original_encrypted_refresh_token: str | None = None,
    original_expires_at: datetime | None = None,
    refreshed_credentials: RefreshedCredentials | None = None,
) -> bool:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_rls_context(session, tenant_id)
            if refreshed_credentials is not None:
                integration_result = await session.execute(
                    select(PlatformIntegration)
                    .where(
                        PlatformIntegration.id == integration_id,
                        PlatformIntegration.company_id == tenant_id,
                    )
                    .with_for_update()
                )
                integration = integration_result.scalar_one_or_none()
                if integration is None:
                    raise RuntimeError(
                        f"Platform integration {integration_id} was not found"
                    )
                if (
                    integration.encrypted_api_key == original_encrypted_api_key
                    and integration.encrypted_refresh_token
                    == original_encrypted_refresh_token
                    and integration.expires_at == original_expires_at
                ):
                    integration.api_key = refreshed_credentials.api_key
                    integration.refresh_token = refreshed_credentials.refresh_token
                    integration.expires_at = refreshed_credentials.expires_at

            result = await session.execute(
                text(
                    "UPDATE public.review_replies SET status = :status, "
                    "external_reply_id = COALESCE(:external_reply_id, external_reply_id), "
                    "failure_reason = :failure_reason, updated_at = now() "
                    "WHERE review_id = :review_id AND company_id = :tenant_id "
                    "AND status IS DISTINCT FROM :published_status"
                ),
                {
                    "status": status.value,
                    "external_reply_id": external_reply_id,
                    "failure_reason": failure_reason,
                    "published_status": ReplyPublicationStatus.PUBLISHED.value,
                    "review_id": review_id,
                    "tenant_id": tenant_id,
                },
            )
            if result.rowcount == 1:
                return True

            current_status = await session.scalar(
                text(
                    "SELECT status FROM public.review_replies "
                    "WHERE review_id = :review_id AND company_id = :tenant_id"
                ),
                {"review_id": review_id, "tenant_id": tenant_id},
            )
            if current_status == ReplyPublicationStatus.PUBLISHED.value:
                return False
            raise RuntimeError(f"Reply record for review {review_id} was not updated")


def _get_refreshed_credentials(
    adapter: BasePlatformAdapter | None, publication: ReplyPublication
) -> RefreshedCredentials | None:
    if adapter is None:
        return None

    api_key = adapter.api_key
    refresh_token = adapter.refresh_token
    expires_at = adapter.expires_at
    if (
        api_key == publication.api_key
        and refresh_token == publication.refresh_token
        and expires_at == publication.expires_at
    ):
        return None
    return RefreshedCredentials(
        api_key=api_key,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )


async def publish_review_reply(
    ctx: dict[str, Any],
    event_id: str,
    tenant_id: str,
    payload: dict[str, Any],
) -> None:
    """Publish a moderated reply using separate DB and external-call phases."""
    event_uuid = UUID(event_id)
    tenant_uuid = UUID(tenant_id)
    payload_tenant = UUID(str(payload.get("tenant_id", "")))
    review_uuid = UUID(str(payload.get("review_id", "")))
    if payload_tenant != tenant_uuid:
        raise ValueError("Reply event tenant does not match job tenant")

    # Phase 1: load the reply and decrypt integration credentials in a short
    # tenant-scoped transaction. The session closes before any network request.
    publication = await _load_reply_publication(tenant_uuid, review_uuid)
    if publication is None:
        logger.info(
            "review_reply_already_published",
            event_id=str(event_uuid),
            tenant_id=str(tenant_uuid),
            review_id=str(review_uuid),
        )
        return
    # Phase 2: call the platform with no open database session or transaction.
    adapter = None
    try:
        adapter = PlatformAdapterFactory.get_adapter(
            publication.platform,
            publication.api_key,
            publication.meta_config,
            refresh_token=publication.refresh_token,
            expires_at=publication.expires_at,
        )
        external_reply_id = await adapter.publish_reply(
            publication.review_external_id,
            publication.reply_text,
        )
    except TransientAPIError as exc:
        updated = await _record_publish_result(
            tenant_uuid,
            review_uuid,
            status=ReplyPublicationStatus.QUEUED_OUTBOX,
            failure_reason=str(exc),
            integration_id=publication.integration_id,
            original_encrypted_api_key=publication.encrypted_api_key,
            original_encrypted_refresh_token=publication.encrypted_refresh_token,
            original_expires_at=publication.expires_at,
            refreshed_credentials=_get_refreshed_credentials(adapter, publication),
        )
        if not updated:
            return
        defer = (
            exc.retry_after
            if exc.retry_after is not None
            else DEFAULT_RETRY_DELAY_SECONDS
        )
        logger.warning(
            "review_reply_publish_transient_failure",
            event_id=str(event_uuid),
            tenant_id=str(tenant_uuid),
            review_id=str(review_uuid),
            platform=publication.platform,
            retry_after=defer,
            error=str(exc),
        )
        raise Retry(defer=defer) from exc
    except PermanentAPIError as exc:
        updated = await _record_publish_result(
            tenant_uuid,
            review_uuid,
            status=ReplyPublicationStatus.PUBLISH_FAILED,
            failure_reason=(
                "Токен доступа истёк или недействителен."
                if exc.status_code == 401
                else str(exc)
            ),
            integration_id=publication.integration_id,
            original_encrypted_api_key=publication.encrypted_api_key,
            original_encrypted_refresh_token=publication.encrypted_refresh_token,
            original_expires_at=publication.expires_at,
            refreshed_credentials=_get_refreshed_credentials(adapter, publication),
        )
        if not updated:
            return
        logger.error(
            "review_reply_publish_permanent_failure",
            event_id=str(event_uuid),
            tenant_id=str(tenant_uuid),
            review_id=str(review_uuid),
            platform=publication.platform,
            error=str(exc),
        )
        return
    except Exception as exc:
        await _record_publish_result(
            tenant_uuid,
            review_uuid,
            status=ReplyPublicationStatus.PUBLISH_FAILED,
            failure_reason=f"Неожиданная ошибка: {type(exc).__name__}",
            integration_id=publication.integration_id,
            original_encrypted_api_key=publication.encrypted_api_key,
            original_encrypted_refresh_token=publication.encrypted_refresh_token,
            original_expires_at=publication.expires_at,
            refreshed_credentials=_get_refreshed_credentials(adapter, publication),
        )
        logger.error(
            "review_reply_publish_unexpected_failure",
            event_id=str(event_uuid),
            tenant_id=str(tenant_uuid),
            review_id=str(review_uuid),
            platform=publication.platform,
            error_type=type(exc).__name__,
        )
        raise

    if not isinstance(external_reply_id, str) or not external_reply_id:
        error = "Platform adapter did not return an external reply ID"
        await _record_publish_result(
            tenant_uuid,
            review_uuid,
            status=ReplyPublicationStatus.PUBLISH_FAILED,
            failure_reason=error,
            integration_id=publication.integration_id,
            original_encrypted_api_key=publication.encrypted_api_key,
            original_encrypted_refresh_token=publication.encrypted_refresh_token,
            original_expires_at=publication.expires_at,
            refreshed_credentials=_get_refreshed_credentials(adapter, publication),
        )
        raise RuntimeError(error)

    # Phase 3: persist the external identifier after the HTTP call has finished.
    updated = await _record_publish_result(
        tenant_uuid,
        review_uuid,
        status=ReplyPublicationStatus.PUBLISHED,
        external_reply_id=external_reply_id,
        integration_id=publication.integration_id,
        original_encrypted_api_key=publication.encrypted_api_key,
        original_encrypted_refresh_token=publication.encrypted_refresh_token,
        original_expires_at=publication.expires_at,
        refreshed_credentials=_get_refreshed_credentials(adapter, publication),
    )
    if not updated:
        return
    logger.info(
        "review_reply_published",
        event_id=str(event_uuid),
        tenant_id=str(tenant_uuid),
        review_id=str(review_uuid),
        platform=publication.platform,
        external_reply_id=external_reply_id,
    )
