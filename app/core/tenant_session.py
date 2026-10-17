"""Tenant-aware сессии с RLS для multi-tenant изоляции."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.auth import JWTPayload

# SQL для установки RLS контекста
SET_RLS_CONTEXT = text(
    "SELECT set_config('request.jwt.claims', :claims, true), "
    "set_config('app.company_id', :company_id, true), "
    "set_config('app.user_id', :user_id, true)"
)


def build_rls_claims(payload: JWTPayload) -> str:
    """Строит JWT claims для RLS политик в минимальном и безопасном формате."""
    claims = {"sub": str(payload.sub), "tenant_id": str(payload.tenant_id)}
    return json.dumps(claims)


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
        await session.execute(
            SET_RLS_CONTEXT,
            {
                "claims": build_rls_claims(payload),
                "company_id": str(payload.tenant_id),
                "user_id": str(payload.sub),
            },
        )
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
    # Создаем минимальный payload для RLS
    payload = JWTPayload(
        sub=user_id or tenant_id,  # Если user_id нет, используем tenant_id
        tenant_id=tenant_id,
    )

    session = factory()

    # Устанавливаем RLS контекст
    await session.execute(
        SET_RLS_CONTEXT,
        {
            "claims": build_rls_claims(payload),
            "company_id": str(tenant_id),
            "user_id": str(user_id) if user_id else "",
        },
    )

    return session
