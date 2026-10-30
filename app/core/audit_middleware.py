"""Persist audit events for sensitive tenant actions."""

import re
from collections.abc import Callable
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import AsyncSessionLocal
from app.core.logger import get_logger
from app.core.tenant_session import get_tenant_session
from app.infrastructure.persistence.models.economics import AuditLog

logger = get_logger(__name__)
_WEBHOOK_ID = re.compile(r"^/api/v1/webhooks/(?P<endpoint_id>[0-9a-fA-F-]{36})/?$")


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """Audit successful webhook deletions after tenant authentication."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        match = _WEBHOOK_ID.fullmatch(request.url.path)
        if request.method != "DELETE" or match is None:
            return response
        if not 200 <= response.status_code < 300:
            return response

        tenant_id = getattr(request.state, "tenant_id", None)
        user_id = getattr(request.state, "user_id", None)
        if not isinstance(tenant_id, UUID) or not isinstance(user_id, UUID):
            raise RuntimeError(
                "Authenticated tenant and user are required to audit webhook deletion"
            )

        client_ip = request.client.host if request.client is not None else None
        session = await get_tenant_session(
            factory=AsyncSessionLocal,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        try:
            session.add(
                AuditLog(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="webhook.delete",
                    ip_address=client_ip,
                )
            )
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                "security_audit_write_failed",
                action="webhook.delete",
                tenant_id=str(tenant_id),
                endpoint_id=match.group("endpoint_id"),
            )
            raise
        finally:
            await session.close()

        return response
