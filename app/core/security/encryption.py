"""SQLAlchemy types for encrypting sensitive values at rest."""

from cryptography.fernet import Fernet
from sqlalchemy.engine import Dialect
from sqlalchemy.types import Text, TypeDecorator

from app.core.config import get_settings


def _get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_secret_key
    if key is None or not key.get_secret_value():
        key = settings.encryption_key
    if key is None or not key.get_secret_value():
        raise RuntimeError(
            "ENCRYPTION_SECRET_KEY must be configured before storing OAuth tokens"
        )
    return Fernet(key.get_secret_value().encode("utf-8"))


class EncryptedString(TypeDecorator[str]):
    """Encrypt string values for storage and decrypt them when loaded."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
