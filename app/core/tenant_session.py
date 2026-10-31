"""Tenant-aware сессии с RLS для multi-tenant изоляции."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import JWTPayload
from app.core.auth import tenant_id_from_payload

# SQL для установки RLS контекста
SET_RLS_CONTEXT = text(
    "SELECT set_config('request.jwt.claims', :claims, true), "
    "set_config('app.company_id', :company_id, true), "
    "set_config('app.user_id', :user_id, true)"
)


def build_rls_claims(payload: JWTPayload) -> str:
    """Строит JWT claims для RLS политик в минимальном и безопасном формате."""
    claims = {
        "sub": str(payload.sub),
        "tenant_id": str(tenant_id_from_payload(payload)),
    }
    return json.dumps(claims)


async def set_rls_context(
    session: AsyncSession,
    payload: JWTPayload,
    *,
    user_id: str | None = None,
) -> None:
    """Устанавливает tenant claims в текущую транзакцию базы данных."""
    tenant_id = tenant_id_from_payload(payload)
    await session.execute(
        SET_RLS_CONTEXT,
        {
            "claims": build_rls_claims(payload),
            "company_id": str(tenant_id),
            "user_id": user_id if user_id is not None else str(payload.sub),
        },
    )


async def set_tenant_rls_context(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID | None = None,
) -> None:
    """Устанавливает tenant RLS-контекст, когда полный JWT недоступен."""
    payload = JWTPayload(sub=user_id or tenant_id, tenant_id=tenant_id)
    await set_rls_context(
        session,
        payload,
        user_id=str(user_id) if user_id else "",
    )


@asynccontextmanager
async def tenant_session(
    factory: Callable[[], AsyncSession],
    payload: JWTPayload,
) -> AsyncIterator[AsyncSession]:
    """Создает транзакцию с RLS контекстом для tenant изоляции.

    Устанавливает контекст в начале транзакции:
    - request.jwt.claims для Supabase RLS политик
    - app.company_id для custom RLS функций
    - app.user_id для аудита действий

    ВАЖНО: Не вызывать session.commit() внутри блока - контекст живет до конца транзакции.

    Args:
        factory: Фабрика для создания AsyncSession
        payload: JWT payload с tenant_id и user_id

    Yields:
        AsyncSession с установленным RLS контекстом
    """
    async with factory() as session, session.begin():
        # Устанавливаем RLS контекст первым statement в транзакции
        await set_rls_context(session, payload)
        yield session


async def get_tenant_session(
    factory: Callable[[], AsyncSession],
    tenant_id: UUID,
    user_id: UUID | None = None,
) -> AsyncSession:
    """Создает сессию с tenant контекстом для использования в dependency injection.

    Использует минимальный payload для создания RLS контекста.

    Args:
        factory: Фабрика для создания AsyncSession
        tenant_id: Company ID для RLS
        user_id: User ID для аудита (опционально)

    Returns:
        AsyncSession с установленным RLS контекстом
    """
    session = factory()

    # Устанавливаем RLS контекст
    await set_tenant_rls_context(session, tenant_id, user_id)

    return session
