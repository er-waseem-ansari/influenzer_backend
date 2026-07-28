"""Campaign persistence (hybrid relational + JSONB).

Always-present scalars are real, queryable columns (filter by track/status/date
without a 15-table join). Polymorphic/variant data lives in typed JSONB blobs,
each validated by its Pydantic model before write and re-validated on read. A
blob can be promoted to a column later when query patterns demand it.

Enum-valued scalars are stored as VARCHAR validated at the app layer (matching
``brand_profiles.industry``), which keeps the drop+recreate workflow free of
Postgres ENUM-type churn. The enum *values* (UPPERCASE) are what's written.
"""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text

from app.database import Base, uuid_fk, uuid_pk


class Campaign(Base):
    """A single creator campaign owned by a brand."""

    __tablename__ = "campaigns"

    id = uuid_pk()
    brand_id = uuid_fk("brand_profiles.id", nullable=False, index=True, ondelete="CASCADE")
    # Kept on creator deletion (campaign outlives the member who created it).
    created_by = uuid_fk("users.id", nullable=True, index=True, ondelete="SET NULL")

    # --- Queryable scalars (UPPERCASE enum values; validated at app layer) ---
    status = Column(String(20), nullable=False, default="DRAFT", index=True)
    title = Column(String(200), nullable=True)
    track = Column(String(20), nullable=True, index=True)            # AWARENESS | PERFORMANCE
    visibility = Column(String(30), nullable=True, index=True)       # MARKETPLACE | INVITE_EXISTING
    compensation_model = Column(String(20), nullable=True)           # FLAT | AFFILIATE | HYBRID

    fixed_fee_per_creator = Column(Numeric(12, 2), nullable=True)    # derived (0 for commission-only)
    max_influencers = Column(Integer, nullable=True)

    describe_product = Column(Boolean, nullable=True)                # awareness opt-out
    destination_url = Column(String(500), nullable=True)
    join_type = Column(String(20), nullable=True)                   # marketplace only

    niches = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))

    # Timeline (queryable)
    content_submission_deadline = Column(Date, nullable=True)
    live_start = Column(Date, nullable=True, index=True)
    live_end = Column(Date, nullable=True)
    application_start = Column(Date, nullable=True)                 # marketplace only
    application_end = Column(Date, nullable=True)                   # marketplace only

    # --- Typed JSONB blobs (each validated by its Pydantic model) ------------
    promotion = Column(JSONB, nullable=True)            # Promotion union
    sales = Column(JSONB, nullable=True)                # SalesConfig (buy-point + coupon)
    targeting_or_roster = Column(JSONB, nullable=True)  # SourcingConfig (targeting | roster)
    audience = Column(JSONB, nullable=True)             # AudienceTargeting
    creative = Column(JSONB, nullable=True)             # CreativeBrief
    fulfillment = Column(JSONB, nullable=True)          # FulfillmentConfig
    compliance = Column(JSONB, nullable=True)           # ComplianceConfig | null (bypass)
    affiliate = Column(JSONB, nullable=True)            # CommissionConfig | null (flat)
    kpi_targets = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    attribution_profile = Column(JSONB, nullable=True)  # derived AttributionProfile
    derived = Column(JSONB, nullable=True)              # other derived flags/metric sets
    cover_image = Column(JSONB, nullable=True)          # FileAsset metadata

    # Relaxed-validation partial (POST /campaigns/draft); null for full campaigns.
    draft_payload = Column(JSONB, nullable=True)

    # Idempotent create: a key is unique per brand (safe retries).
    idempotency_key = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    brand = relationship("BrandProfile", backref="campaigns")

    __table_args__ = (
        UniqueConstraint("brand_id", "idempotency_key", name="uq_campaign_idempotency"),
    )