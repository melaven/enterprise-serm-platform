import pytest
from sqlalchemy.engine import make_url

from app.core.database import _postgresql_url, _runtime_database_url


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


def test_runtime_rejects_missing_tenant_database_url() -> None:
    with pytest.raises(RuntimeError, match="TENANT_DATABASE_URL"):
        _runtime_database_url(
            None,
            "postgresql://postgres:secret@db.example.test/app",
            use_tenant_role=True,
            allow_admin_runtime=False,
        )


@pytest.mark.parametrize("role", ["postgres", "service_role"])
def test_runtime_rejects_privileged_tenant_database_role(role: str) -> None:
    with pytest.raises(RuntimeError, match="non-privileged"):
        _runtime_database_url(
            f"postgresql://{role}:secret@db.example.test/app",
            "postgresql://postgres:secret@db.example.test/app",
            use_tenant_role=True,
            allow_admin_runtime=False,
        )


def test_runtime_rejects_disabled_tenant_role_outside_test_context() -> None:
    with pytest.raises(RuntimeError, match="USE_TENANT_ROLE"):
        _runtime_database_url(
            "postgresql://app_tenant:secret@db.example.test/app",
            "postgresql://postgres:secret@db.example.test/app",
            use_tenant_role=False,
            allow_admin_runtime=False,
        )


def test_runtime_admin_role_requires_explicit_test_context() -> None:
    url = _runtime_database_url(
        "postgresql://app_tenant:secret@db.example.test/app",
        "postgresql://postgres:secret@db.example.test/app",
        use_tenant_role=False,
        allow_admin_runtime=True,
    )

    assert url.username == "postgres"


def test_runtime_database_engine_uses_a_postgresql_url() -> None:
    from app.core.database import database_url

    assert make_url(str(database_url)).get_backend_name() == "postgresql"
