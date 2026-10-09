"""
ARQ Worker настройки для SERM
"""

import logging
import os
from typing import Optional

from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Function

from .tasks import fetch_reviews_task

logger = logging.getLogger(__name__)


def get_redis_settings() -> RedisSettings:
    """Настройки Redis для ARQ"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Парсим URL для RedisSettings
    if redis_url.startswith("redis://"):
        # Простая реализация для redis://host:port/db
        url_parts = redis_url.replace("redis://", "").split("/")
        host_port = url_parts[0].split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 6379
        database = int(url_parts[1]) if len(url_parts) > 1 else 0
        
        return RedisSettings(
            host=host,
            port=port,
            database=database
        )
    else:
        # Fallback для других форматов
        return RedisSettings.from_dsn(redis_url)


class WorkerSettings:
    """Конфигурация ARQ Worker"""
    
    # Настройки Redis
    redis_settings = get_redis_settings()
    
    # Задачи для выполнения
    functions = [
        fetch_reviews_task
    ]
    
    # Настройки воркера
    max_jobs = 10
    job_timeout = 300  # 5 минут на задачу
    keep_result = 120  # Держим результаты 2 минуты
    
    # Логирование
    log_results = True
    
    # Обработка ошибок
    allow_abort_jobs = True


async def startup(ctx):
    """Инициализация воркера"""
    logger.info("=" * 60)
    logger.info("🚀 ARQ Worker starting up...")
    logger.info("=" * 60)
    
    try:
        # Загружаем переменные окружения
        from dotenv import load_dotenv
        load_dotenv()
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: Если подключение не удалось с app_tenant ролью - 
        # это может означать что используется fallback на суперюзера
        # В этом случае ЖЁСТКО падаем
        
        # Проверяем подключение через app_tenant URL
        tenant_url = os.getenv("TENANT_DATABASE_URL")
        if not tenant_url:
            logger.error("❌ FATAL: TENANT_DATABASE_URL not configured!")
            raise ValueError("TENANT_DATABASE_URL is required for secure worker operation")
        
        # Конвертируем URL для asyncpg (убираем +asyncpg)
        asyncpg_url = tenant_url.replace('postgresql+asyncpg://', 'postgresql://')
        
        import asyncpg
        logger.info("🔒 SECURITY CHECK: Testing app_tenant role connection...")
        
        try:
            # КРИТИЧЕСКАЯ ПРОВЕРКА: Подключение ДОЛЖНО быть только через app_tenant
            # Подключаемся с отключенным кэшем prepared statements для Supabase
            conn = await asyncpg.connect(asyncpg_url, statement_cache_size=0)
        except Exception as db_error:
            logger.error("❌ CRITICAL FAILURE: Cannot connect with app_tenant role!")
            logger.error(f"❌ Database error: {db_error}")
            logger.error("❌ This indicates app_tenant role is not properly configured in Supabase")
            logger.error("❌ Worker CANNOT start without proper non-privileged role!")
            logger.error("❌ SECURITY HALT: Risk of using privileged role detected")
            raise ValueError(f"SECURITY FAILURE: app_tenant connection failed - {db_error}")
        
        # Проверяем роль на предмет нарушения безопасности RLS
        role_info = await conn.fetchrow('''
            SELECT rolname, rolsuper, rolbypassrls 
            FROM pg_roles WHERE rolname = current_user
        ''')
        
        current_role = role_info['rolname']
        is_superuser = role_info['rolsuper']
        bypass_rls = role_info['rolbypassrls']
        
        logger.info(f"🔒 Current database role: {current_role}")
        logger.info(f"🔒 Superuser: {is_superuser}")  
        logger.info(f"🔒 Bypass RLS: {bypass_rls}")
        
        # ЖЁСТКАЯ ПРОВЕРКА БЕЗОПАСНОСТИ - НИ ОДНОГО ИСКЛЮЧЕНИЯ
        if is_superuser:
            logger.error("❌ CRITICAL SECURITY VIOLATION: Database role is SUPERUSER!")
            logger.error("❌ Superuser roles CANNOT be used in multi-tenant systems!")
            logger.error("❌ Worker startup TERMINATED to prevent data leakage!")
            raise ValueError(f"SECURITY VIOLATION: Role '{current_role}' is SUPERUSER - multi-tenant isolation COMPROMISED")
        
        if bypass_rls:
            logger.error("❌ CRITICAL SECURITY VIOLATION: Database role has BYPASSRLS privilege!")
            logger.error("❌ BYPASSRLS completely destroys Row Level Security isolation!")
            logger.error("❌ Worker startup TERMINATED to prevent tenant data exposure!")
            raise ValueError(f"SECURITY VIOLATION: Role '{current_role}' has BYPASSRLS - multi-tenant isolation DESTROYED")
        
        # Проверяем что это именно app_tenant роль
        if current_role != 'app_tenant':
            logger.error(f"❌ SECURITY ERROR: Expected 'app_tenant' role, got '{current_role}'")
            logger.error("❌ Only app_tenant role is authorized for worker operations!")
            raise ValueError(f"UNAUTHORIZED ROLE: Expected 'app_tenant', got '{current_role}'")
        
        logger.info("✅ SECURITY VERIFIED: app_tenant role with proper RLS restrictions")
        
        await conn.close()
        
        logger.info("✅ Database connection verified - RLS security maintained")
        
        # Проверяем Redis подключение
        redis_settings = get_redis_settings()
        logger.info(f"🔗 Testing Redis connection at {redis_settings.host}:{redis_settings.port}")
        
        pool = await create_pool(redis_settings)
        await pool.close()
        
        logger.info("✅ Redis connection verified")
        
    except Exception as e:
        logger.error(f"❌ Worker startup failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    logger.info("=" * 60)
    logger.info("✅ ARQ Worker startup completed successfully!")
    logger.info("=" * 60)


async def shutdown(ctx):
    """Завершение работы воркера"""
    logger.info("🛑 ARQ Worker shutting down...")
    logger.info("✅ Worker shutdown completed")


# Добавляем хуки в настройки
WorkerSettings.on_startup = startup
WorkerSettings.on_shutdown = shutdown


async def create_arq_pool():
    """Создание пула подключений к Redis для ARQ"""
    return await create_pool(get_redis_settings())