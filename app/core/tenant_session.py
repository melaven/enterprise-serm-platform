"""Tenant-aware сессии с RLS для multi-tenant изоляции."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.schemas.auth import JWTPayload
from app.core.auth import tenant_id_from_payload

# SQL для установки RLS контекста
SET_RLS_CONTEXT = text(
    "SELECT set_config('request.jwt.claims', :claims, true), "
    "set_config('app.company_id', :company_id, true), "
    "set_config('app.user_id', :user_id, true)"
)
RLS_CONTEXT_INFO_KEY = "tenant_rls_context"
RLS_CONTEXT_LISTENER_INFO_KEY = "tenant_rls_context_listener"
RLS_CONTEXT_APPLIED_INFO_KEY = "tenant_rls_context_applied"
SESSION_WRITE_LISTENER_INFO_KEY = "session_write_listener"
SESSION_HAS_WRITES_INFO_KEY = "has_writes"


def _restore_rls_context(
    session: Session,
    transaction: Any,
    connection: Any,
) -> None:
    """Reapply tenant-local settings whenever this session starts a transaction."""
    params = session.info.get(RLS_CONTEXT_INFO_KEY)
    if params is not None and not session.info.get(RLS_CONTEXT_APPLIED_INFO_KEY):
        connection.execute(SET_RLS_CONTEXT, params)
        session.info[RLS_CONTEXT_APPLIED_INFO_KEY] = True


def _mark_session_writes(execute_state: Any) -> None:
    if execute_state.is_insert or execute_state.is_update or execute_state.is_delete:
        execute_state.session.info[SESSION_HAS_WRITES_INFO_KEY] = True


def _reset_transaction_state(session: Session) -> None:
    session.info.pop(SESSION_HAS_WRITES_INFO_KEY, None)
    session.info.pop(RLS_CONTEXT_APPLIED_INFO_KEY, None)


def track_session_writes(session: AsyncSession) -> None:
    """Track ORM DML statements so dependency cleanup can commit Core writes."""
    sync_session = session.sync_session
    if sync_session.info.get(SESSION_WRITE_LISTENER_INFO_KEY):
        return

    event.listen(sync_session, "do_orm_execute", _mark_session_writes)
    event.listen(sync_session, "after_commit", _reset_transaction_state)
    event.listen(sync_session, "after_rollback", _reset_transaction_state)
    sync_session.info[SESSION_WRITE_LISTENER_INFO_KEY] = True


def _remember_rls_context(
    session: AsyncSession,
    payload: JWTPayload,
    *,
    user_id: str | None = None,
) -> None:
    tenant_id = tenant_id_from_payload(payload)
    session.sync_session.info[RLS_CONTEXT_INFO_KEY] = {
        "claims": build_rls_claims(payload),
        "company_id": str(tenant_id),
        "user_id": user_id if user_id is not None else str(payload.sub),
    }
    sync_session = session.sync_session
    if not sync_session.info.get(RLS_CONTEXT_LISTENER_INFO_KEY):
        event.listen(sync_session, "after_begin", _restore_rls_context)
        event.listen(sync_session, "after_commit", _reset_transaction_state)
        event.listen(sync_session, "after_rollback", _reset_transaction_state)
        sync_session.info[RLS_CONTEXT_LISTENER_INFO_KEY] = True


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
    """Запоминает tenant claims и устанавливает их, если транзакция уже активна."""
    _remember_rls_context(session, payload, user_id=user_id)
    sync_session = session.sync_session
    if session.in_transaction() and not sync_session.info.get(
        RLS_CONTEXT_APPLIED_INFO_KEY
    ):
        params = sync_session.info[RLS_CONTEXT_INFO_KEY]
        await session.execute(SET_RLS_CONTEXT, params)
        sync_session.info[RLS_CONTEXT_APPLIED_INFO_KEY] = True


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
    async with factory() as session:
        _remember_rls_context(session, payload)
        async with session.begin():
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
