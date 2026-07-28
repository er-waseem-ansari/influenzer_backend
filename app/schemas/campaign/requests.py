"""Top-level campaign create request — assembles the four discriminated unions
plus the simple blocks, and enforces the cross-block rules from spec §7 that no
single sub-model can see on its own.

Everything here is server-authoritative: derived fields (§8) are never accepted
from the client — they are computed in :mod:`app.services.campaign_derivation`.
"""
from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator, model_validator

from app.schemas.campaign.audience import AudienceTargeting
from app.schemas.campaign.common import CampaignBaseModel
from app.schemas.campaign.compensation import CompensationConfig, FlatComp
from app.schemas.campaign.compliance import ComplianceConfig
from app.schemas.campaign.creative import CreativeBrief, FileAsset
from app.schemas.campaign.fulfillment import FulfillmentConfig
from app.schemas.campaign.metrics import KNOWN_METRIC_IDS
from app.schemas.campaign.sourcing import ByocSourcing, SourcingConfig
from app.schemas.campaign.timeline import Timeline
from app.schemas.campaign.track import AwarenessTrack, TrackConfig


def _is_contract_bypassed(sourcing: SourcingConfig) -> bool:
    return isinstance(sourcing, ByocSourcing) and sourcing.contract_bypass_acknowledged


class CampaignCreate(CampaignBaseModel):
    # Core
    niches: list[str] = Field(..., min_length=1)
    cover_image: Optional[FileAsset] = None
    max_influencers: int = Field(..., ge=1)

    # Discriminated unions (prompt #1–#4) + fulfillment union
    track: TrackConfig
    sourcing: SourcingConfig
    compensation: CompensationConfig
    fulfillment: FulfillmentConfig

    # Simple blocks
    audience: AudienceTargeting
    creative: CreativeBrief
    timeline: Timeline
    compliance: Optional[ComplianceConfig] = None
    kpi_targets: dict[str, float] = Field(default_factory=dict)

    @field_validator("niches")
    @classmethod
    def _niches(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip() for t in v if t and t.strip()]
        if not cleaned:
            raise ValueError("At least one niche is required.")
        for t in cleaned:
            if len(t) > 100:
                raise ValueError("Each niche must be at most 100 characters.")
        return cleaned

    @field_validator("kpi_targets")
    @classmethod
    def _kpis(cls, v: dict[str, float]) -> dict[str, float]:
        for metric_id, target in v.items():
            if metric_id not in KNOWN_METRIC_IDS:
                raise ValueError(f"Unknown KPI metric '{metric_id}'.")
            if target < 0:
                raise ValueError(f"KPI target for '{metric_id}' must be ≥ 0.")
        return v

    @model_validator(mode="after")
    def _cross_block(self) -> "CampaignCreate":
        # §1/§8: commission models are only offered when a conversion target
        # exists (Performance). Awareness is always flat.
        if isinstance(self.track, AwarenessTrack) and not isinstance(self.compensation, FlatComp):
            raise ValueError(
                "Awareness campaigns must use flat compensation (no conversion target)."
            )

        # §7.15: compliance is required unless BYOC + contract bypass.
        if not _is_contract_bypassed(self.sourcing) and self.compliance is None:
            raise ValueError("Compliance details are required for this campaign.")

        # §7.16: submission deadline must fall on/before go-live (cross-block);
        # the marketplace application window is validated on its own variant.
        return self