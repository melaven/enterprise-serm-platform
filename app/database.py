from typing import AsyncGenerator

import os
from asyncio import current_task
from supabase import Client, create_client
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    create_async_engine, 
    async_sessionmaker,
    async_scoped_session
)
from sqlalchemy.orm import declarative_base

# Жестко грузим переменные из .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("CRITICAL: DATABASE_URL variable is missing in .env file.")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("CRITICAL: Supabase variables are missing in .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Настраиваем асинхронный движок под микро-инстанс Supabase (t4g.nano в Ирландии)
engine = create_async_engine(
    DATABASE_URL,
    echo=False,               # Отключаем тяжелый дебаг-логгинг в продакшене
    pool_size=5,              # Для t4g.nano держим небольшой пул, чтобы не выжрать RAM
    max_overflow=10,          # Оверфлоу для кратковременных пиков B2B-нагрузки
    pool_timeout=30,          # Время ожидания свободного коннекта
    pool_pre_ping=True        # Авто-проверка живого коннекта (защита от разрывов AWS)
)

# Асинхронная фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Потокобезопасная скоупед-сессия
ScopedSession = async_scoped_session(AsyncSessionLocal, scopefunc=current_task)

Base = declarative_base()

# Наш главный мост — Dependency Injection для FastAPI роутеров
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception as error:
            await session.rollback()
            raise error
        finally:
            await session.close()
