"""Server-derived values (spec §8) — never accepted from the client.

Kept as schemas (not just service locals) so they round-trip into the response
and into the persisted ``attribution_profile`` JSONB blob.
"""
from __future__ import annotations

from typing import Optional

from pydantic import Field

from app.schemas.campaign.common import CampaignBaseModel
from app.schemas.campaign.enums import AffiliateModel, Integration


class AttributionProfile(CampaignBaseModel):
    """Whether/how verified conversion data can be unlocked for this campaign.

    At creation everything is merely "tracked"; Sales flips to "verified" only
    after the brand connects ``unlocking_integration`` post-launch — hence
    ``verified_at_launch`` is always False for sales. A marketplace buy-point is
    never verifiable (no integration)."""

    verified_available: bool
    unlocking_integration: Optional[Integration] = None
    verified_at_launch: bool = False
    note: str


class CampaignDerived(CampaignBaseModel):
    """All §8 derivations bundled — persisted/echoed alongside the campaign."""

    affiliate_enabled: bool
    affiliate_model: Optional[AffiliateModel] = None
    promo_code_enabled: bool
    gifting_enabled: bool
    fixed_fee_per_creator: float
    attribution_profile: AttributionProfile
    headline_kpis: list[str] = Field(default_factory=list)
    measured_metrics: list[str] = Field(default_factory=list)