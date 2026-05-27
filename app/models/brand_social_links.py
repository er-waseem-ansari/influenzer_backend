from sqlalchemy import Column, String, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base, uuid_pk, uuid_fk


class BrandSocialLink(Base):
    """A brand's public profile URL on a social platform. One URL per platform
    per brand (enforced by the composite unique constraint)."""

    __tablename__ = "brand_social_links"

    id = uuid_pk()
    brand_id = uuid_fk("brand_profiles.id", nullable=False, index=True, ondelete="CASCADE")

    platform = Column(String(30), nullable=False)  # enum enforced at app layer
    url = Column(String(500), nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    brand = relationship("BrandProfile", back_populates="social_links")

    __table_args__ = (
        UniqueConstraint("brand_id", "platform", name="uq_brand_social_platform"),
    )