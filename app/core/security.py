"""
Security utilities for encryption/decryption of sensitive data
Uses Fernet symmetric encryption from cryptography library
"""

import base64
import os

from cryptography.fernet import Fernet, InvalidToken

from app.core.logger import get_logger

logger = get_logger("security")


class EncryptionError(Exception):
    """Custom exception for encryption/decryption errors"""

    pass


class TokenEncryption:
    """
    Wrapper around Fernet for symmetric encryption of API tokens
    """

    def __init__(self, encryption_key: str | None = None):
        """
        Initialize TokenEncryption with encryption key

        Args:
            encryption_key: Base64-encoded 32-byte key. If None, reads from ENCRYPTION_KEY env var.

        Raises:
            EncryptionError: If key is not provided or invalid
        """
        key = encryption_key or os.getenv("ENCRYPTION_KEY")

        if not key:
            raise EncryptionError(
                "ENCRYPTION_KEY environment variable is not set. "
                "Please set a secure 32-byte key in base64 format."
            )

        try:
            # Ensure key is base64-encoded and valid for Fernet
            if not self._is_valid_fernet_key(key):
                # Try to encode if it's a raw string
                key_bytes = key.encode("utf-8")
                if len(key_bytes) != 32:
                    raise EncryptionError(
                        f"Encryption key must be 32 bytes. Got {len(key_bytes)} bytes."
                    )
                key = base64.urlsafe_b64encode(key_bytes).decode("utf-8")

            self._fernet = Fernet(key.encode("utf-8"))
            logger.info("TokenEncryption initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize TokenEncryption", error=str(e))
            raise EncryptionError(f"Invalid encryption key: {str(e)}") from e

    @staticmethod
    def _is_valid_fernet_key(key: str) -> bool:
        """Check if key is a valid base64-encoded Fernet key"""
        try:
            decoded = base64.urlsafe_b64decode(key.encode("utf-8"))
            return len(decoded) == 32
        except Exception:
            return False

    def encrypt_token(self, plain_token: str) -> str:
        """
        Encrypt a plain text API token

        Args:
            plain_token: Plain text token to encrypt

        Returns:
            Base64-encoded encrypted token

        Raises:
            EncryptionError: If encryption fails
        """
        if not plain_token:
            raise EncryptionError("Cannot encrypt empty token")

        try:
            encrypted = self._fernet.encrypt(plain_token.encode("utf-8"))
            return encrypted.decode("utf-8")
        except Exception as e:
            logger.error("Token encryption failed", error=str(e))
            raise EncryptionError(f"Failed to encrypt token: {str(e)}") from e

    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt an encrypted API token

        Args:
            encrypted_token: Base64-encoded encrypted token

        Returns:
            Plain text token

        Raises:
            EncryptionError: If decryption fails
        """
        if not encrypted_token:
            raise EncryptionError("Cannot decrypt empty token")

        try:
            decrypted = self._fernet.decrypt(encrypted_token.encode("utf-8"))
            return decrypted.decode("utf-8")
        except InvalidToken as e:
            logger.error("Token decryption failed - invalid token", error=str(e))
            raise EncryptionError(
                "Invalid encrypted token or wrong encryption key"
            ) from e
        except Exception as e:
            logger.error("Token decryption failed", error=str(e))
            raise EncryptionError(f"Failed to decrypt token: {str(e)}") from e


# Global instance for use across the application
_encryption_instance: TokenEncryption | None = None


def get_encryption() -> TokenEncryption:
    """
    Get or create the global TokenEncryption instance

    Returns:
        TokenEncryption instance

    Raises:
        EncryptionError: If ENCRYPTION_KEY is not set
    """
    global _encryption_instance

    if _encryption_instance is None:
        _encryption_instance = TokenEncryption()

    return _encryption_instance


def encrypt_token(plain_token: str) -> str:
    """
    Convenience function to encrypt a token using the global instance

    Args:
        plain_token: Plain text token to encrypt

    Returns:
        Base64-encoded encrypted token
    """
    return get_encryption().encrypt_token(plain_token)


def decrypt_token(encrypted_token: str) -> str:
    """
    Convenience function to decrypt a token using the global instance

    Args:
        encrypted_token: Base64-encoded encrypted token

    Returns:
        Plain text token
    """
    return get_encryption().decrypt_token(encrypted_token)
