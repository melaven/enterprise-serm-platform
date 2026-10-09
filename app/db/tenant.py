"""
Tenant session factory для воркера ARQ
Обеспечивает RLS изоляцию в фоновых задачах
"""

import logging
from typing import AsyncGenerator, Callable
from uuid import UUID
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class TenantSessionFactory:
    """Фабрика tenant-aware сессий для воркера"""
    
    def __init__(self):
        self.session_local = AsyncSessionLocal
    
    @asynccontextmanager
    async def __call__(self, company_id: UUID) -> AsyncGenerator[AsyncSession, None]:
        """
        Создает session с установленным tenant context для RLS
        
        Args:
            company_id: ID компании для изоляции
        
        Yields:
            AsyncSession с установленным app.company_id
        """
        async with self.session_local() as session:
            try:
                # Устанавливаем tenant context для RLS
                await session.execute(
                    text("SELECT set_config('app.company_id', :company_id, true)"),
                    {"company_id": str(company_id)}
                )
                
                logger.debug(f"🔐 Tenant session created: company_id={company_id}")
                
                yield session
                
                # Коммит произойдет автоматически при выходе из контекста
                await session.commit()
                logger.debug(f"✅ Tenant session committed: company_id={company_id}")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Tenant session error: {e}")
                raise
            finally:
                await session.close()
                logger.debug(f"🔒 Tenant session closed: company_id={company_id}")


@asynccontextmanager
async def tenant_session_factory() -> AsyncGenerator[TenantSessionFactory, None]:
    """
    Контекстный менеджер для создания tenant session factory
    
    Usage:
        async with tenant_session_factory() as factory:
            async with factory(company_id) as session:
                # Работа с БД в tenant контексте
                pass
    """
    factory = TenantSessionFactory()
    try:
        yield factory
    finally:
        # Очистка ресурсов если необходимо
        pass