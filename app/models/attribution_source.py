"""Upstream attribution lookup tables.

A conversion is credited by resolving its ``click_id`` or ``coupon_code`` back to
the creator (influencer) and campaign that earned it. Those mappings are produced
*before* a conversion arrives:

* **clicks** — written by the click/redirect tracker when a creator's tracking
  link is followed.
* **coupon_assignments** — written when a per-creator coupon code is minted on
  campaign assignment.

This module only defines the tables so the attribution resolver has something to
read; the producers live elsewhere (and may not exist yet). The influencer is the
creator's ``users.id``.
"""
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base, uuid_fk, uuid_pk


class Click(Base):
    """A recorded click on a creator's tracking link for a campaign.

    Attribution only needs the ``click_id -> (campaign, influencer, created_at)``
    mapping. The extra columns serve click *metrics* and fraud signalling, kept
    deliberately light: ``platform`` (validated against the campaign ``Platform``
    enum at the app layer) plus a freeform ``context`` JSONB for IP / user-agent /
    UTM / referrer / geo. We resist rigid columns for those because the click
    tracker (a separate feature) owns that schema; a field can be promoted to a
    real column later when query patterns demand it.
    """

    __tablename__ = "clicks"

    id = uuid_pk()
    # The opaque click handle echoed back in a conversion's ``click_id``.
    click_id = Column(String(128), nullable=False, unique=True, index=True)
    campaign_id = uuid_fk("campaigns.id", nullable=False, index=True, ondelete="CASCADE")
    influencer_id = uuid_fk("users.id", nullable=False, index=True, ondelete="CASCADE")
    platform = Column(String(20), nullable=True, index=True)  # IG_REELS | TIKTOK | ... (app-validated)
    context = Column(JSONB, nullable=True)                    # ip / user_agent / utm / referrer / geo
    # When the click happened — the anchor for the cookie/attribution window.
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CouponAssignment(Base):
    """A per-creator coupon code minted for a campaign."""

    __tablename__ = "coupon_assignments"

    id = uuid_pk()
    # Stored uppercased for case-insensitive matching against a conversion's code.
    coupon_code = Column(String(64), nullable=False, unique=True, index=True)
    campaign_id = uuid_fk("campaigns.id", nullable=False, index=True, ondelete="CASCADE")
    influencer_id = uuid_fk("users.id", nullable=False, index=True, ondelete="CASCADE")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
