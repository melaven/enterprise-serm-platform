"""Разбор DSN базы данных. Без зависимости от SQLAlchemy: используется и приложением, и Alembic."""

import os
from pathlib import Path

try:  # python-dotenv опционален: в проде переменные задаёт окружение
    from dotenv import load_dotenv

    # override=False: переменные окружения ОС приоритетнее файла .env
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:  # pragma: no cover
    pass

_ASYNC_SCHEME = "postgresql+asyncpg://"


def normalize_database_url(raw: str) -> str:
    """postgres:// и postgresql:// -> postgresql+asyncpg://; другие драйверы отклоняются."""
    url = raw.strip()
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return _ASYNC_SCHEME + url[len(prefix) :]
    if url.startswith(_ASYNC_SCHEME):
        return url
    scheme = url.split("://", 1)[0] if "://" in url else "<нет схемы>"
    raise RuntimeError(
        f"Неподдерживаемая схема DSN '{scheme}': нужен postgresql+asyncpg:// (асинхронный драйвер asyncpg)."
    )


def get_database_url(*env_names: str) -> str:
    """Первый непустой DSN из перечисленных переменных (по умолчанию DATABASE_URL), в формате asyncpg."""
    names = env_names or ("DATABASE_URL",)
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return normalize_database_url(value)
    raise RuntimeError(
        f"Не задана переменная окружения {' / '.join(names)} (см. .env.example)."
    )
