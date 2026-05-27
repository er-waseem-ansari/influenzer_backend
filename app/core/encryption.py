"""Application-level encryption for data that must be encrypted at rest.

OAuth tokens and tax identifiers are stored encrypted so a database leak does
not expose usable secrets. We use Fernet (AES-128-CBC + HMAC-SHA256, authenticated)
keyed by `settings.ENCRYPTION_KEY`.

`EncryptedString` is a SQLAlchemy type that transparently encrypts on write and
decrypts on read, so models declare it like any other column type.
"""
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import Text, TypeDecorator

from app.config import get_settings

LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = get_settings().ENCRYPTION_KEY
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string, returning URL-safe base64 ciphertext."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    """Decrypt ciphertext produced by `encrypt_value`. Raises on tampering."""
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


class EncryptedString(TypeDecorator):
    """A Text column whose value is encrypted at rest with Fernet.

    Plaintext is exchanged with application code; ciphertext is what hits the
    database. The output is non-deterministic (random IV per write), so these
    columns cannot be used in WHERE clauses or unique constraints.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return decrypt_value(value)
        except InvalidToken:
            # Wrong/rotated key or corrupted data: never crash a read path on it.
            LOGGER.error("Failed to decrypt an EncryptedString column value.")
            return None