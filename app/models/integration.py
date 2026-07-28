"""Per-brand postback integration: the signing secret and its public handle.

Each integration owns one HMAC signing secret used to authenticate conversion
postbacks. The secret is stored **encrypted at rest** (Fernet via
``EncryptedString``) — not hashed — because we must recompute the HMAC on every
request. It is shown to the brand exactly once (at create / rotate); thereafter
only the ciphertext lives in the DB.

The brand identifies itself on each request with ``public_id`` (the opaque
``intg_<random>`` handle sent in the ``X-Inflz-Integration`` header). It carries
no brand information and is non-enumerable; it maps to a brand only via this
table.
"""
from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.encryption import EncryptedString
from app.database import Base, uuid_fk, uuid_pk


class IntegrationStatus:
    """Lifecycle states (UPPERCASE wire/DB values, validated at the app layer)."""

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class PostbackIntegration(Base):
    """A brand's conversion-postback integration + its signing secret."""

    __tablename__ = "postback_integrations"

    id = uuid_pk()
    # Opaque public handle (intg_<hex>) sent in X-Inflz-Integration. Unique +
    # indexed for the per-request lookup; reveals nothing about the brand.
    public_id = Column(String(64), nullable=False, unique=True, index=True)
    brand_id = uuid_fk("brand_profiles.id", nullable=False, index=True, ondelete="CASCADE")

    # Encrypted at rest; decrypted in-process only to recompute the HMAC.
    secret = Column(EncryptedString, nullable=False)

    status = Column(String(20), nullable=False, default=IntegrationStatus.ACTIVE, index=True)
    label = Column(String(120), nullable=True)  # human label, e.g. "Production Shopify"

    rotated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    brand = relationship("BrandProfile", backref="postback_integrations")