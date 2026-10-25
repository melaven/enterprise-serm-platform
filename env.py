"""Async-окружение Alembic (шаблон `alembic init -t async`), подключённое к Base проекта."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.url import get_database_url
from app.models.base import Base
from app.models.review import Review  # noqa: F401  (импорт регистрирует таблицу reviews в Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Миграции выполняются под владельцем схемы: ALEMBIC_DATABASE_URL, иначе DATABASE_URL.
DATABASE_URL = get_database_url("ALEMBIC_DATABASE_URL", "DATABASE_URL")


def include_object(obj: object, name: str | None, type_: str, reflected: bool, compare_to: object | None) -> bool:
    """Таблицы, которые есть в БД, но не описаны моделями, не трогаем (autogenerate не предложит DROP)."""
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    """Генерация SQL без подключения: `alembic upgrade head --sql`."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # NullPool: миграция — одноразовый процесс, пул не нужен.
    connectable = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
