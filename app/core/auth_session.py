"""
Tenant Session для мультитенантности через RLS
"""

import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .database import AsyncSessionLocal
from .jwt_handler import AuthContext
from .tenant_session import set_tenant_rls_context

logger = logging.getLogger(__name__)


class TenantSession:
    """Обертка для сессии БД с установленным tenant context"""

    def __init__(self, session: AsyncSession, company_id: UUID, user_id: UUID):
        self.session = session
        self.company_id = company_id
        self.user_id = user_id
        self._context_set = False

    async def __aenter__(self) -> AsyncSession:
        """Вход в контекстный менеджер - устанавливаем tenant context"""

        if not self._context_set:
            await set_tenant_rls_context(
                self.session,
                self.company_id,
                self.user_id,
            )
            self._context_set = True
            logger.debug(f"Tenant context set: company_id={self.company_id}")

        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджера"""

        if exc_type is not None:
            # При ошибке откатываем транзакцию
            await self.session.rollback()
            logger.warning(
                f"Transaction rolled back due to {exc_type.__name__}: {exc_val}"
            )
        else:
            # При успехе коммитим
            try:
                await self.session.commit()
            except Exception as e:
                await self.session.rollback()
                logger.error(f"Commit failed, rolled back: {e}")
                raise

        # Закрываем сессию
        await self.session.close()
        logger.debug(f"Tenant session closed: company_id={self.company_id}")


async def get_tenant_session(auth_context: AuthContext) -> TenantSession:
    """
    Создание tenant-aware сессии БД

    Сессия устанавливает tenant RLS контекст и управляет транзакциями.
    """

    # Создаем новую сессию для tenant
    session = AsyncSessionLocal()

    return TenantSession(session, auth_context.company_id, auth_context.user_id)


# Альтернативная функция для совместимости с FastAPI Depends
async def get_db_with_tenant(
    auth_context: AuthContext,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для FastAPI с автоматической установкой tenant context

    ВАЖНО: Не используйте session.commit() внутри запроса!
    Используйте session.flush() для промежуточных операций.
    Коммит происходит автоматически в конце запроса.
    """

    async with await get_tenant_session(auth_context) as session:
        yield session
