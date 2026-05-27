from sqlalchemy import Column, String, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base, uuid_pk, uuid_fk
from app.core.encryption import EncryptedString


class BrandBillingDetail(Base):
    """A brand's billing/invoicing details. One record per brand. Tax
    identifiers are encrypted at rest via `EncryptedString`."""

    __tablename__ = "brand_billing_details"

    id = uuid_pk()
    brand_id = uuid_fk("brand_profiles.id", nullable=False, ondelete="CASCADE")

    billing_contact_name = Column(String(150), nullable=True)
    billing_email = Column(String(255), nullable=True)
    billing_phone = Column(String(30), nullable=True)

    address_line_1 = Column(String(255), nullable=True)
    address_line_2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state_region = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)

    tax_id = Column(EncryptedString, nullable=True)     # encrypted at rest
    gst_number = Column(EncryptedString, nullable=True)  # encrypted at rest

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    brand = relationship("BrandProfile", back_populates="billing_details")

    __table_args__ = (
        UniqueConstraint("brand_id", name="uq_brand_billing"),
    )