"""Brand campaign API.

Campaigns belong to the authenticated caller's brand. Cross-cutting concerns are
attached at the router level (mirroring brand profile):
  * ``read_router``  — any active brand member.
  * ``write_router`` — write-capable role (ADMIN/MANAGER) + write rate limit.

Controllers stay thin: resolve the request-cached ``BrandContext`` and delegate
to :class:`CampaignService`.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.dependencies import BrandContext, get_brand_context, require_brand_editor
from app.core.rate_limit import enforce_rate_limit
from app.database import get_db
from app.schemas.campaign import (
    CampaignCreate,
    CampaignCreatedResponse,
    CampaignListResponse,
    CampaignResponse,
)
from app.schemas.campaign.enums import CampaignStatus, Track
from app.schemas.campaign.responses import DraftResponse
from app.services.campaign_service import CampaignService

settings = get_settings()


def campaign_write_dependency(ctx: BrandContext = Depends(require_brand_editor)) -> BrandContext:
    """Router guard for campaign writes: write-capable role + per-user rate limit."""
    enforce_rate_limit(
        scope="campaign_write",
        identifier=str(ctx.user.id),
        limit=settings.CAMPAIGN_WRITE_RATE_LIMIT_MAX,
        window_seconds=settings.CAMPAIGN_WRITE_RATE_LIMIT_WINDOW_SECONDS,
    )
    return ctx


read_router = APIRouter(prefix="/brand/campaigns", tags=["Campaigns"])
write_router = APIRouter(
    prefix="/brand/campaigns",
    tags=["Campaigns"],
    dependencies=[Depends(campaign_write_dependency)],
)


# --- Writes -----------------------------------------------------------------


@write_router.post("", response_model=CampaignCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate,
    ctx: BrandContext = Depends(get_brand_context),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Create (launch) a campaign. Body is the validated request union; returns
    the created campaign, its derived attribution profile, and a flow-specific
    success message."""
    return CampaignService.create(db, ctx, payload, idempotency_key=idempotency_key)


@write_router.post("/draft", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign_draft(
    payload: dict = Body(...),
    ctx: BrandContext = Depends(get_brand_context),
    db: Session = Depends(get_db),
):
    """Persist a partial draft (relaxed validation; status DRAFT)."""
    return CampaignService.create_draft(db, ctx, payload)


# --- Reads ------------------------------------------------------------------


@read_router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    ctx: BrandContext = Depends(get_brand_context),
    db: Session = Depends(get_db),
    track: Optional[Track] = Query(default=None),
    status_filter: Optional[CampaignStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List the brand's campaigns with optional track/status filters + pagination."""
    return CampaignService.list(
        db, ctx, track=track, status=status_filter, limit=limit, offset=offset
    )


@read_router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    ctx: BrandContext = Depends(get_brand_context),
    db: Session = Depends(get_db),
):
    """Fetch one campaign by id (scoped to the caller's brand)."""
    return CampaignService.get(db, ctx, campaign_id)