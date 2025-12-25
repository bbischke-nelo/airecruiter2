"""Fernet encryption for sensitive data like credentials."""

import base64

from cryptography.fernet import Fernet, InvalidToken
import structlog

from api.config.settings import settings

logger = structlog.get_logger()

# Cache fernet instance
_fernet: Fernet | None = None


class EncryptionKeyError(Exception):
    """Raised when encryption key is missing or invalid in production."""
    pass


def get_fernet() -> Fernet:
    """Get or create Fernet instance.

    Raises:
        EncryptionKeyError: If ENCRYPTION_KEY is missing in production
    """
    global _fernet
    if _fernet is None:
        key = settings.ENCRYPTION_KEY
        if not key:
            if settings.ENVIRONMENT == "production":
                # CRITICAL: Never allow missing key in production
                raise EncryptionKeyError(
                    "ENCRYPTION_KEY is required in production. "
                    "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )
            # Generate a key for development only (not secure!)
            logger.warning(
                "No ENCRYPTION_KEY set, generating temporary key. "
                "This is ONLY acceptable in development!"
            )
            key = Fernet.generate_key().decode()

        # Ensure key is valid Fernet key (32 bytes, base64-encoded)
        try:
            _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            # Key might not be properly formatted, try to pad/fix it
            key_bytes = key.encode() if isinstance(key, str) else key
            if len(key_bytes) < 32:
                key_bytes = key_bytes.ljust(32, b"=")
            key_b64 = base64.urlsafe_b64encode(key_bytes[:32])
            _fernet = Fernet(key_b64)

    return _fernet


def validate_encryption_key() -> None:
    """Validate encryption key at startup.

    Call this during application startup to fail fast if key is missing.

    Raises:
        EncryptionKeyError: If key validation fails
    """
    get_fernet()  # Will raise if invalid in production


def encrypt_value(value: str) -> str:
    """
    Encrypt a string value using Fernet.

    Args:
        value: Plain text to encrypt

    Returns:
        Base64-encoded encrypted value
    """
    if not value:
        return value

    fernet = get_fernet()
    encrypted = fernet.encrypt(value.encode())
    return encrypted.decode()


def decrypt_value(encrypted_value: str) -> str:
    """
    Decrypt a Fernet-encrypted value.

    Args:
        encrypted_value: Base64-encoded encrypted value

    Returns:
        Decrypted plain text

    Raises:
        InvalidToken: If decryption fails
    """
    if not encrypted_value:
        return encrypted_value

    fernet = get_fernet()
    try:
        decrypted = fernet.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except InvalidToken:
        logger.error("Failed to decrypt value - invalid token")
        raise
