import pytest

from app.db.url import get_database_url, normalize_database_url


def test_normalize_adds_asyncpg_driver() -> None:
    assert normalize_database_url("postgresql://u:p@h:5432/db") == "postgresql+asyncpg://u:p@h:5432/db"
    assert normalize_database_url("postgres://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    assert normalize_database_url("postgresql+asyncpg://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"


def test_normalize_rejects_sync_driver() -> None:
    with pytest.raises(RuntimeError, match="psycopg2"):
        normalize_database_url("postgresql+psycopg2://u:p@h/db")


def test_alembic_url_has_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://app@h/db")
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", "postgresql://owner@h/db")
    assert get_database_url("ALEMBIC_DATABASE_URL", "DATABASE_URL").startswith("postgresql+asyncpg://owner@")
    monkeypatch.delenv("ALEMBIC_DATABASE_URL")
    assert get_database_url("ALEMBIC_DATABASE_URL", "DATABASE_URL").startswith("postgresql+asyncpg://app@")


def test_missing_url_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_database_url()
