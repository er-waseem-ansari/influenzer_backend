from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from app.database import Base, uuid_pk, uuid_fk


class EmailVerificationToken(Base):
    """Single-use, time-bound token used to verify a user's email address.

    Only the SHA-256 hash of the token is stored; the raw token is sent to the
    user and never persisted, so a database leak does not expose usable tokens.
    """
    __tablename__ = "email_verification_tokens"

    id = uuid_pk()
    user_id = uuid_fk("users.id", nullable=False, index=True, ondelete="CASCADE")
    token_hash = Column(String(64), unique=True, index=True, nullable=False)  # sha256 hex digest
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)  # Set when the token is consumed
    created_at = Column(DateTime(timezone=True), server_default=func.now())