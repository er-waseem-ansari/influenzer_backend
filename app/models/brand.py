from sqlalchemy import Column, String, Text, SmallInteger, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func, text
from sqlalchemy.orm import relationship
from app.database import Base, uuid_pk, uuid_fk


class BrandProfile(Base):
    """A brand. This row *is* the brand identity that every other brand table
    (members, social links, OAuth connections, billing) references by id."""

    __tablename__ = "brand_profiles"

    id = uuid_pk()
    # The user who first created this brand (the founding ADMIN).
    created_by = uuid_fk("users.id", nullable=False, index=True, ondelete="CASCADE")

    # --- Identity ---
    # Nullable: the brand row is created at signup and named later via the
    # profile-update API (see ProfileStatus on the user).
    display_name = Column(String(100), nullable=True)
    legal_entity_name = Column(String(200), nullable=True)
    tagline = Column(String(300), nullable=True)
    about = Column(Text, nullable=True)

    # --- Business ---
    industry = Column(String(50), nullable=True)        # enum enforced at app layer
    company_size = Column(String(50), nullable=True)    # e.g. "1-10", "11-50"
    founded_year = Column(SmallInteger, nullable=True)
    website_url = Column(String(500), nullable=True)

    # --- Address ---
    headquarters_country = Column(String(100), nullable=True)
    address_line_1 = Column(String(255), nullable=True)
    address_line_2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state_region = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)

    # --- Primary Contact ---
    contact_name = Column(String(150), nullable=True)
    contact_title = Column(String(100), nullable=True)
    contact_email = Column(String(255), nullable=True)
    support_email = Column(String(255), nullable=True)
    phone_number = Column(String(30), nullable=True)

    # --- Target Audience ---
    target_regions = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    min_age = Column(SmallInteger, nullable=True)
    max_age = Column(SmallInteger, nullable=True)
    audience_interests = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))

    # --- Meta ---
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    creator = relationship("User", backref="created_brands")
    social_links = relationship(
        "BrandSocialLink", back_populates="brand", cascade="all, delete-orphan"
    )
    oauth_connections = relationship(
        "BrandOAuthConnection", back_populates="brand", cascade="all, delete-orphan"
    )
    billing_details = relationship(
        "BrandBillingDetail",
        back_populates="brand",
        uselist=False,
        cascade="all, delete-orphan",
    )