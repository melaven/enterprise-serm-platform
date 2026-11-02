import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.types import Integer

from app.core.config import Settings
from app.core.security import encryption
from app.core.security.encryption import EncryptedString
from app.infrastructure.persistence.models.economics import PlatformIntegration


class EncryptionTestBase(DeclarativeBase):
    pass


class EncryptedValue(EncryptionTestBase):
    __tablename__ = "encrypted_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)


def _settings(key: str) -> Settings:
    return Settings(
        database_url="postgresql://test:test@localhost/test",
        supabase_url="https://example.supabase.co",
        encryption_secret_key=key,
    )


def test_platform_oauth_columns_use_encrypted_string() -> None:
    assert isinstance(
        PlatformIntegration.__table__.c.encrypted_api_key.type, EncryptedString
    )
    assert isinstance(
        PlatformIntegration.__table__.c.encrypted_refresh_token.type, EncryptedString
    )


def test_encrypted_string_round_trips_without_storing_plaintext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(encryption, "get_settings", lambda: _settings(key))
    engine = create_engine("sqlite://")
    try:
        EncryptionTestBase.metadata.create_all(engine)
        with Session(engine) as session:
            record = EncryptedValue(value="oauth-secret-token")
            session.add(record)
            session.flush()
            record_id = record.id

            stored_value = session.scalar(
                text("SELECT value FROM encrypted_values WHERE id = :id"),
                {"id": record_id},
            )
            assert isinstance(stored_value, str)
            assert stored_value != "oauth-secret-token"
            assert (
                Fernet(key.encode("ascii"))
                .decrypt(stored_value.encode("ascii"))
                .decode("ascii")
                == "oauth-secret-token"
            )
            session.commit()

        with Session(engine) as session:
            loaded_record = session.get(EncryptedValue, record_id)
            assert loaded_record is not None
            assert loaded_record.value == "oauth-secret-token"
    finally:
        engine.dispose()


def test_encrypted_string_preserves_none(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(encryption, "get_settings", lambda: _settings(key))
    encrypted_type = EncryptedString()
    dialect = DefaultDialect()

    assert encrypted_type.process_bind_param(None, dialect) is None
    assert encrypted_type.process_result_value(None, dialect) is None


def test_encrypted_string_accepts_legacy_encryption_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = Fernet.generate_key().decode("ascii")
    settings = Settings(
        database_url="postgresql://test:test@localhost/test",
        supabase_url="https://example.supabase.co",
        encryption_key=key,
    )
    monkeypatch.setattr(encryption, "get_settings", lambda: settings)

    encrypted_value = EncryptedString().process_bind_param(
        "legacy-oauth-token", DefaultDialect()
    )

    assert encrypted_value is not None
    assert (
        Fernet(key.encode("ascii"))
        .decrypt(encrypted_value.encode("ascii"))
        .decode("ascii")
        == "legacy-oauth-token"
    )
