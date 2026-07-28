"""Response schemas for the campaign API.

Responses are rebuilt from the persisted columns + typed JSONB blobs and
re-serialised to camelCase. The ``*_ADAPTER`` ``TypeAdapter``s re-validate each
stored blob back into its discriminated-union model on read, so a corrupted or
stale blob fails loudly rather than leaking an untyped dict.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import Field, TypeAdapter

from app.schemas.campaign.audience import AudienceTargeting
from app.schemas.campaign.common import CampaignBaseModel
from app.schemas.campaign.compensation import CompensationConfig
from app.schemas.campaign.compliance import ComplianceConfig
from app.schemas.campaign.creative import CreativeBrief, FileAsset
from app.schemas.campaign.derived import CampaignDerived
from app.schemas.campaign.enums import CampaignStatus, Track, Visibility
from app.schemas.campaign.fulfillment import FulfillmentConfig
from app.schemas.campaign.promotion import Promotion
from app.schemas.campaign.sourcing import SourcingConfig
from app.schemas.campaign.timeline import Timeline
from app.schemas.campaign.track import TrackConfig

# Re-validate stored blobs back into typed models on read.
TRACK_ADAPTER: TypeAdapter[TrackConfig] = TypeAdapter(TrackConfig)
SOURCING_ADAPTER: TypeAdapter[SourcingConfig] = TypeAdapter(SourcingConfig)
COMPENSATION_ADAPTER: TypeAdapter[CompensationConfig] = TypeAdapter(CompensationConfig)
FULFILLMENT_ADAPTER: TypeAdapter[FulfillmentConfig] = TypeAdapter(FulfillmentConfig)
PROMOTION_ADAPTER: TypeAdapter[Promotion] = TypeAdapter(Promotion)


class CampaignResponse(CampaignBaseModel):
    id: UUID
    brand_id: UUID
    status: CampaignStatus

    title: str
    niches: list[str]
    max_influencers: int
    cover_image: Optional[FileAsset] = None

    track: TrackConfig
    sourcing: SourcingConfig
    compensation: CompensationConfig
    fulfillment: FulfillmentConfig

    audience: AudienceTargeting
    creative: CreativeBrief
    timeline: Timeline
    compliance: Optional[ComplianceConfig] = None
    kpi_targets: dict[str, float] = Field(default_factory=dict)

    derived: CampaignDerived

    created_at: datetime
    updated_at: Optional[datetime] = None


class CampaignCreatedResponse(CampaignBaseModel):
    """POST /campaigns result: the campaign + the surfaced attribution profile
    and the flow-specific success message (spec §9)."""

    campaign: CampaignResponse
    message: str


class CampaignSpend(CampaignBaseModel):
    """Money actually spent on a campaign so far.

    Sourced from the (future) billing/metrics actuals pipeline; ``amount`` is 0
    until that lands. ``currency`` is a placeholder default until per-brand
    currency settings exist.
    """

    amount: float = 0.0
    currency: str = "USD"


class CampaignResults(CampaignBaseModel):
    """Headline results for the list row.

    All four fields are always present; only two are populated per campaign:
      * PERFORMANCE track -> ``revenue`` + ``roas``
      * AWARENESS track   -> ``clicks`` + ``cvr`` (conversion rate, percent)

    The unpopulated pair is ``None``. Values are 0 placeholders until the
    metrics-actuals pipeline lands.
    """

    revenue: Optional[float] = None
    roas: Optional[float] = None
    clicks: Optional[int] = None
    cvr: Optional[float] = None


class CampaignInfluencers(CampaignBaseModel):
    """Roster progress, rendered as ``joined/target`` (e.g. 18/17).

    ``joined`` is 0 until the participation/roster model lands; ``target`` is
    the campaign's ``max_influencers``.
    """

    joined: int = 0
    target: Optional[int] = None


class CampaignListItem(CampaignBaseModel):
    id: UUID
    # heading + subheading for the list cell
    title: Optional[str] = None
    subheading: Optional[str] = None
    track: Optional[Track] = None
    visibility: Optional[Visibility] = None
    status: CampaignStatus
    spend: CampaignSpend = Field(default_factory=CampaignSpend)
    results: CampaignResults = Field(default_factory=CampaignResults)
    influencers: CampaignInfluencers = Field(default_factory=CampaignInfluencers)
    live_start: Optional[date] = None
    live_end: Optional[date] = None  # "Ends" column
    created_at: datetime


class CampaignListResponse(CampaignBaseModel):
    items: list[CampaignListItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class DraftResponse(CampaignBaseModel):
    """A persisted partial draft (relaxed validation)."""

    id: UUID
    brand_id: UUID
    status: CampaignStatus
    title: Optional[str] = None
    data: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None