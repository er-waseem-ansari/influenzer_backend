"""Postback persistence: the append-only audit trail and the conversion fact.

Two tables, two jobs:

* **raw_postback_events** — every *verified* request, stored raw and immediately,
  before attribution runs. Append-only audit + replay source: if attribution
  logic changes we can reprocess from here. Never carries the secret/signature.
* **conversions** — the resolved, immutable business fact (one per
  ``(integration, order_id)``). Refunds mutate the matching row (``reversed`` +
  commission reversal) rather than inserting a duplicate, so verified revenue
  stays net of refunds.
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base, uuid_fk, uuid_pk


class AttributionKey:
    """How a conversion was credited (UPPERCASE; validated at the app layer)."""

    CLICK_ID = "CLICK_ID"
    COUPON = "COUPON"


class AttributionConfidence:
    """Optional confidence tag. ``CODE_ONLY`` = attributed via coupon with no
    click present (code-leakage awareness) — still fully counted."""

    CODE_ONLY = "CODE_ONLY"


class RawPostbackEvent(Base):
    """An accepted, signature-verified postback, stored verbatim (audit/replay)."""

    __tablename__ = "raw_postback_events"

    id = uuid_pk()
    integration_id = uuid_fk(
        "postback_integrations.id", nullable=False, index=True, ondelete="CASCADE"
    )
    event_type = Column(String(20), nullable=True, index=True)   # purchase | refund (best-effort)
    order_id = Column(String(128), nullable=True, index=True)
    raw_body = Column(String, nullable=False)                    # exact bytes we verified (text)
    headers = Column(JSONB, nullable=True)                       # sanitized: no signature/secret
    verification_result = Column(String(20), nullable=False, default="VERIFIED")
    processed = Column(Boolean, nullable=False, default=False)   # did we write a conversion?
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Conversion(Base):
    """The immutable conversion fact (one per integration + order_id)."""

    __tablename__ = "conversions"

    id = uuid_pk()
    integration_id = uuid_fk(
        "postback_integrations.id", nullable=False, index=True, ondelete="CASCADE"
    )
    brand_id = uuid_fk("brand_profiles.id", nullable=False, index=True, ondelete="CASCADE")
    # Null when unattributed (no resolvable click/coupon) — we still store it.
    campaign_id = uuid_fk("campaigns.id", nullable=True, index=True, ondelete="SET NULL")

    order_id = Column(String(128), nullable=False, index=True)
    event_type = Column(String(20), nullable=False)             # purchase | refund

    attributed_influencer_id = uuid_fk("users.id", nullable=True, index=True, ondelete="SET NULL")
    attribution_key = Column(String(20), nullable=True)         # CLICK_ID | COUPON | null
    attribution_value = Column(String(128), nullable=True)      # the click_id / coupon code matched
    confidence = Column(String(20), nullable=True)              # CODE_ONLY | null
    flagged_for_review = Column(Boolean, nullable=False, default=False)

    value = Column(Numeric(14, 2), nullable=True)               # purchase amount (gross)
    currency = Column(String(3), nullable=True)
    status = Column(String(30), nullable=True)                  # brand-supplied (e.g. confirmed)
    commission_amount = Column(Numeric(14, 2), nullable=True)   # earned commission (derived)

    occurred_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Refund handling: set when a refund reverses this conversion.
    reversed = Column(Boolean, nullable=False, default=False, index=True)
    reversed_value = Column(Numeric(14, 2), nullable=True)      # amount refunded (partial-aware)
    reversed_at = Column(DateTime(timezone=True), nullable=True)

    meta = Column(JSONB, nullable=True)                         # freeform brand payload `meta`
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Idempotency: one conversion per order per integration. A repeated
        # purchase order_id is deduped; a refund mutates the matched row.
        UniqueConstraint("integration_id", "order_id", name="uq_conversion_order"),
    )