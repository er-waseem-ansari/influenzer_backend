from sqlalchemy import Column, String, DateTime, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func, text
from sqlalchemy.orm import relationship
from app.database import Base, uuid_pk, uuid_fk
from app.core.encryption import EncryptedString


class BrandOAuthConnection(Base):
    """A brand's linked third-party account (Google, Meta). Access/refresh
    tokens are encrypted at rest via `EncryptedString`. The (provider,
    provider_account_id) pair is globally unique so the same external account
    cannot be connected to two brands."""

    __tablename__ = "brand_oauth_connections"

    id = uuid_pk()
    brand_id = uuid_fk("brand_profiles.id", nullable=False, index=True, ondelete="CASCADE")

    provider = Column(String(30), nullable=False)            # enum enforced at app layer: google, meta
    provider_account_id = Column(String(255), nullable=False)  # their id on that platform

    access_token = Column(EncryptedString, nullable=False)   # encrypted at rest
    refresh_token = Column(EncryptedString, nullable=True)   # encrypted at rest
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    scopes = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))

    connected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_refreshed_at = Column(DateTime(timezone=True), nullable=True)

    brand = relationship("BrandProfile", back_populates="oauth_connections")

    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
    )