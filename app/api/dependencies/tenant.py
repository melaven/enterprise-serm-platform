"""Tenant authorization dependencies."""

from uuid import UUID

from fastapi import Depends, HTTPException, Query, status

from app.api.schemas.auth import AuthContext, JWTPayload
from app.core.auth import get_jwt_payload, tenant_id_from_payload


async def get_current_user(
    payload: JWTPayload = Depends(get_jwt_payload),
) -> AuthContext:
    """Build the authenticated user context from the verified JWT claims."""
    return AuthContext(
        user_id=payload.sub,
        company_id=tenant_id_from_payload(payload),
        company_role=payload.company_role,
    )


async def verify_tenant_access(
    company_id: UUID | None = Query(default=None),
    current_user: AuthContext = Depends(get_current_user),
) -> UUID:
    """Reject requested tenant IDs that differ from the authenticated user's tenant."""
    if company_id is not None and company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this tenant",
        )
    return current_user.company_id
