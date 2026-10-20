import pytest
from sqlalchemy.engine import make_url

from app.core.database import _postgresql_url


def test_database_urls_must_use_postgresql() -> None:
    with pytest.raises(RuntimeError, match="SQLite.*disabled"):
        _postgresql_url("sqlite+aiosqlite:///:memory:", "DATABASE_URL")


def test_database_url_is_normalized_to_asyncpg() -> None:
    url = _postgresql_url(
        "postgresql://user:password@db.example.test:5432/app",
        "DATABASE_URL",
    )

    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "db.example.test"


def test_database_url_rejects_unsupported_postgresql_driver() -> None:
    with pytest.raises(RuntimeError, match="asyncpg"):
        _postgresql_url(
            "postgresql+psycopg://user:password@db.example.test:5432/app",
            "DATABASE_URL",
        )


def test_runtime_database_engine_uses_a_postgresql_url() -> None:
    from app.core.database import database_url

    assert make_url(str(database_url)).get_backend_name() == "postgresql"
