from datetime import datetime, timedelta, timezone
from jose import jwt
from app.config import get_settings
import bcrypt
import hashlib
import secrets

settings = get_settings()

# bcrypt only considers the first 72 bytes of a password.
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt.

    Uses the `bcrypt` library directly (as `auth_service` does) to avoid a
    passlib/bcrypt-4.x backend incompatibility. bcrypt only uses the first 72
    bytes, so we truncate defensively; the API layer also rejects longer input.
    """
    pw = password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    pw = plain_password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(pw, password_hash.encode("utf-8"))
    except ValueError:
        return False


def generate_url_safe_token(num_bytes: int = 48) -> str:
    """Generate a cryptographically secure, URL-safe random token."""
    return secrets.token_urlsafe(num_bytes)


def hash_token(token: str) -> str:
    """Deterministically hash a high-entropy token for at-rest storage/lookup.

    SHA-256 is appropriate here (not bcrypt): the token is already random and
    high-entropy, and we need a deterministic digest to look the row up by.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": secrets.token_urlsafe(32)})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])