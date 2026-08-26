from typing import AsyncGenerator
from datetime import datetime

import os
from asyncio import current_task
from supabase import Client, create_client
from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String, Text, DateTime
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


class LNRReviewLog(Base):
    __tablename__ = "lnr_reviews_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False)
    platform_id = Column(Integer, nullable=False)
    external_review_id = Column(String(255), unique=True, nullable=False)
    author_name = Column(String(255))
    rating = Column(Integer, nullable=False)
    review_text = Column(Text)
    sentiment = Column(String(50))  # "negative" if rating <= 3 else "positive"
    processing_status = Column(String(50), default="new")  # new, processed, alert_sent
    created_at = Column(DateTime, default=datetime.utcnow)


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
