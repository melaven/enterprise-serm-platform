"""Зависимости внешнего B2B API: аутентификация по X-API-Key и RLS-сессия тенанта."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.apikey_db import ApiKeysNotConfigured, resolve_api_key_in_db
from app.db.context import SET_TENANT_CONTEXT, tenant_context_params
from app.db.session import SessionFactory
from app.services.api_keys import hash_api_key, is_well_formed, resolve_tenant

_UNAUTHORIZED = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    "Invalid API key",
    headers={"WWW-Authenticate": "ApiKey"},
)


@dataclass(frozen=True, slots=True)
class ApiKeyPrincipal:
    tenant_id: UUID


async def verify_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiKeyPrincipal:
    if not x_api_key or not is_well_formed(x_api_key):
        raise _UNAUTHORIZED  # единый ответ: не различаем «нет», «битый», «отозван»
    try:
        tenant = await resolve_tenant(
            request.app.state.redis_pool, hash_api_key(x_api_key), resolve_api_key_in_db
        )
    except ApiKeysNotConfigured as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "API access not configured"
        ) from exc
    if tenant is None:
        raise _UNAUTHORIZED
    return ApiKeyPrincipal(tenant_id=tenant)


ApiPrincipal = Annotated[ApiKeyPrincipal, Depends(verify_api_key)]


async def get_api_tenant_session(
    principal: ApiPrincipal,
) -> AsyncIterator[AsyncSession]:
    """Та же RLS-транзакция, что и для JWT, но без user_id (действие от имени ключа, не человека)."""
    async with SessionFactory() as session, session.begin():
        await session.execute(
            SET_TENANT_CONTEXT, tenant_context_params(principal.tenant_id)
        )
        yield session


ApiTenantSession = Annotated[AsyncSession, Depends(get_api_tenant_session)]
