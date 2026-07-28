"""Campaign create-campaign use case + reads.

Route handlers stay thin: they hand a validated request schema and the
authorized :class:`BrandContext` to this service. The service:
    1. derives all §8 business logic (``campaign_derivation``),
    2. decomposes the normalized request into queryable columns + typed JSONB
       blobs,
    3. persists, and
    4. rebuilds a typed response (no ORM object leaks past this layer).

Idempotency: a create carrying an ``Idempotency-Key`` that was already used by
this brand returns the existing campaign instead of inserting a duplicate.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import BrandContext
from app.core.exceptions import ConflictException, NotFoundException
from app.models.campaign import Campaign
from app.schemas.campaign.audience import AudienceTargeting
from app.schemas.campaign.compliance import ComplianceConfig
from app.schemas.campaign.creative import CreativeBrief
from app.schemas.campaign.derived import CampaignDerived
from app.schemas.campaign.enums import CampaignStatus, Track, Visibility
from app.schemas.campaign.requests import CampaignCreate
from app.schemas.campaign.responses import (
    COMPENSATION_ADAPTER,
    FULFILLMENT_ADAPTER,
    SOURCING_ADAPTER,
    TRACK_ADAPTER,
    CampaignCreatedResponse,
    CampaignInfluencers,
    CampaignListItem,
    CampaignListResponse,
    CampaignResults,
    CampaignResponse,
    CampaignSpend,
    DraftResponse,
)
from app.schemas.campaign.sourcing import MarketplaceSourcing
from app.schemas.campaign.timeline import Timeline
from app.schemas.campaign.track import AwarenessTrack, PerformanceTrack
from app.services.campaign_derivation import derive_campaign

LOGGER = logging.getLogger(__name__)

_SUCCESS_MESSAGES = {
    Visibility.MARKETPLACE: "Creators can now apply.",
    Visibility.INVITE_EXISTING: "Invites are being sent to your roster.",
}


def _dump(model) -> dict:
    """Serialise a sub-model to a snake_case, JSON-safe blob for JSONB storage."""
    return model.model_dump(mode="json", by_alias=False)


class CampaignService:

    # --- Create -------------------------------------------------------------

    @staticmethod
    def create(
        db: Session,
        ctx: BrandContext,
        payload: CampaignCreate,
        idempotency_key: Optional[str] = None,
    ) -> CampaignCreatedResponse:
        if idempotency_key:
            existing = (
                db.query(Campaign)
                .filter(
                    Campaign.brand_id == ctx.brand.id,
                    Campaign.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing is not None:
                LOGGER.info(
                    "Idempotent campaign replay: brand_id=%s key=%s", ctx.brand.id, idempotency_key
                )
                return CampaignService._created_response(existing)

        derived = derive_campaign(payload)
        campaign = CampaignService._to_orm(ctx, payload, derived, idempotency_key)

        db.add(campaign)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Lost the race on the idempotency key — return the winning row.
            if idempotency_key:
                existing = (
                    db.query(Campaign)
                    .filter(
                        Campaign.brand_id == ctx.brand.id,
                        Campaign.idempotency_key == idempotency_key,
                    )
                    .first()
                )
                if existing is not None:
                    return CampaignService._created_response(existing)
            raise ConflictException("Could not create the campaign due to a conflict.")

        db.refresh(campaign)
        LOGGER.info("Campaign created: id=%s brand_id=%s", campaign.id, ctx.brand.id)
        return CampaignService._created_response(campaign)

    # --- Draft (relaxed validation) -----------------------------------------

    @staticmethod
    def create_draft(db: Session, ctx: BrandContext, raw: dict) -> DraftResponse:
        # Best-effort title for the drafts list — top-level or nested in creative.
        title = raw.get("title")
        creative = raw.get("creative")
        if not title and isinstance(creative, dict):
            title = creative.get("title")
        campaign = Campaign(
            brand_id=ctx.brand.id,
            created_by=ctx.user.id,
            status=CampaignStatus.DRAFT.value,
            title=title if isinstance(title, str) else None,
            draft_payload=raw,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        LOGGER.info("Campaign draft saved: id=%s brand_id=%s", campaign.id, ctx.brand.id)
        return DraftResponse(
            id=campaign.id,
            brand_id=campaign.brand_id,
            status=CampaignStatus(campaign.status),
            title=campaign.title,
            data=campaign.draft_payload or {},
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )

    # --- Reads --------------------------------------------------------------

    @staticmethod
    def get(db: Session, ctx: BrandContext, campaign_id: UUID) -> CampaignResponse:
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id, Campaign.brand_id == ctx.brand.id)
            .first()
        )
        if campaign is None:
            raise NotFoundException("Campaign not found.")
        if campaign.status == CampaignStatus.DRAFT.value and campaign.track is None:
            # A bare draft has no normalized blobs to rebuild a full response from.
            raise NotFoundException(
                "Campaign is still a draft; fetch it via the drafts endpoint."
            )
        return CampaignService._to_response(campaign)

    @staticmethod
    def list(
        db: Session,
        ctx: BrandContext,
        *,
        track: Optional[Track] = None,
        status: Optional[CampaignStatus] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> CampaignListResponse:
        q = db.query(Campaign).filter(Campaign.brand_id == ctx.brand.id)
        if track is not None:
            q = q.filter(Campaign.track == track.value)
        if status is not None:
            q = q.filter(Campaign.status == status.value)
        total = q.count()
        rows = (
            q.order_by(Campaign.created_at.desc()).limit(limit).offset(offset).all()
        )
        items = [CampaignService._to_list_item(r) for r in rows]
        return CampaignListResponse(items=items, total=total, limit=limit, offset=offset)

    @staticmethod
    def _to_list_item(c: Campaign) -> CampaignListItem:
        """Project an ORM row onto the campaign-list row shape (spec: list page).

        Spend/results/influencer-joined have no actuals source yet, so they are
        structurally-correct placeholders: spend 0, results shaped per track
        (the two relevant fields zeroed, the other two ``None``), joined 0.
        """
        track = Track(c.track) if c.track else None

        # Results: populate the two fields the frontend renders for this track.
        if track == Track.PERFORMANCE:
            results = CampaignResults(revenue=0.0, roas=0.0)
        elif track == Track.AWARENESS:
            results = CampaignResults(clicks=0, cvr=0.0)
        else:
            results = CampaignResults()

        # Subheading: the creative's key message (short tagline-style line).
        subheading = None
        if isinstance(c.creative, dict):
            km = c.creative.get("key_messaging")
            if isinstance(km, str) and km.strip():
                subheading = km.strip()

        return CampaignListItem(
            id=c.id,
            title=c.title,
            subheading=subheading,
            track=track,
            visibility=Visibility(c.visibility) if c.visibility else None,
            status=CampaignStatus(c.status),
            spend=CampaignSpend(amount=0.0),
            results=results,
            influencers=CampaignInfluencers(joined=0, target=c.max_influencers),
            live_start=c.live_start,
            live_end=c.live_end,
            created_at=c.created_at,
        )

    # --- Mapping: request -> ORM -------------------------------------------

    @staticmethod
    def _to_orm(
        ctx: BrandContext,
        data: CampaignCreate,
        derived: CampaignDerived,
        idempotency_key: Optional[str],
    ) -> Campaign:
        track = data.track
        sourcing = data.sourcing
        comp = data.compensation

        # Track / promotion / sales projection
        promotion_blob = _dump(track.promotion) if track.promotion is not None else None
        sales_blob = _dump(track.sales) if isinstance(track, PerformanceTrack) else None
        describe_product = track.describe_product if isinstance(track, AwarenessTrack) else None

        # Sourcing projection (marketplace-only scalars)
        if isinstance(sourcing, MarketplaceSourcing):
            application_start = sourcing.application_start
            application_end = sourcing.application_end
            join_type = sourcing.join_type.value
        else:
            application_start = application_end = None
            join_type = None

        # Compensation projection
        affiliate_blob = (
            _dump(comp.commission) if getattr(comp, "commission", None) is not None else None
        )

        derived_blob = derived.model_dump(
            mode="json", by_alias=False, exclude={"attribution_profile"}
        )

        return Campaign(
            brand_id=ctx.brand.id,
            created_by=ctx.user.id,
            status=CampaignStatus.ACTIVE.value,
            title=data.creative.title,
            track=track.track.value,
            visibility=sourcing.visibility.value,
            compensation_model=comp.compensation_model.value,
            fixed_fee_per_creator=derived.fixed_fee_per_creator,
            max_influencers=data.max_influencers,
            describe_product=describe_product,
            destination_url=track.destination_url,
            join_type=join_type,
            niches=data.niches,
            content_submission_deadline=data.timeline.content_submission_deadline,
            live_start=data.timeline.live_start,
            live_end=data.timeline.live_end,
            application_start=application_start,
            application_end=application_end,
            promotion=promotion_blob,
            sales=sales_blob,
            targeting_or_roster=_dump(sourcing),
            audience=_dump(data.audience),
            creative=_dump(data.creative),
            fulfillment=_dump(data.fulfillment),
            compliance=_dump(data.compliance) if data.compliance is not None else None,
            affiliate=affiliate_blob,
            kpi_targets=data.kpi_targets,
            attribution_profile=_dump(derived.attribution_profile),
            derived=derived_blob,
            cover_image=_dump(data.cover_image) if data.cover_image is not None else None,
            idempotency_key=idempotency_key,
        )

    # --- Mapping: ORM -> response ------------------------------------------

    @staticmethod
    def _to_response(c: Campaign) -> CampaignResponse:
        # Track (rebuild from columns + promotion/sales blobs)
        if c.track == Track.AWARENESS.value:
            track_dict = {
                "track": Track.AWARENESS.value,
                "describe_product": c.describe_product,
                "destination_url": c.destination_url,
                "promotion": c.promotion,
            }
        else:
            track_dict = {
                "track": Track.PERFORMANCE.value,
                "destination_url": c.destination_url,
                "promotion": c.promotion,
                "sales": c.sales,
            }
        track_obj = TRACK_ADAPTER.validate_python(track_dict)

        sourcing_obj = SOURCING_ADAPTER.validate_python(c.targeting_or_roster)

        # Compensation (rebuild from columns + affiliate blob)
        cm = c.compensation_model
        fee = float(c.fixed_fee_per_creator) if c.fixed_fee_per_creator is not None else 0.0
        if cm == "FLAT":
            comp_dict = {"compensation_model": "FLAT", "fixed_fee_per_creator": fee}
        elif cm == "AFFILIATE":
            comp_dict = {"compensation_model": "AFFILIATE", "commission": c.affiliate}
        else:  # HYBRID
            comp_dict = {
                "compensation_model": "HYBRID",
                "fixed_fee_per_creator": fee,
                "commission": c.affiliate,
            }
        comp_obj = COMPENSATION_ADAPTER.validate_python(comp_dict)

        fulfillment_obj = FULFILLMENT_ADAPTER.validate_python(c.fulfillment)
        derived_obj = CampaignDerived.model_validate(
            {**(c.derived or {}), "attribution_profile": c.attribution_profile}
        )

        return CampaignResponse(
            id=c.id,
            brand_id=c.brand_id,
            status=CampaignStatus(c.status),
            title=c.title,
            niches=c.niches or [],
            max_influencers=c.max_influencers,
            cover_image=c.cover_image,
            track=track_obj,
            sourcing=sourcing_obj,
            compensation=comp_obj,
            fulfillment=fulfillment_obj,
            audience=AudienceTargeting.model_validate(c.audience or {}),
            creative=CreativeBrief.model_validate(c.creative),
            timeline=Timeline(
                content_submission_deadline=c.content_submission_deadline,
                live_start=c.live_start,
                live_end=c.live_end,
            ),
            compliance=ComplianceConfig.model_validate(c.compliance) if c.compliance else None,
            kpi_targets=c.kpi_targets or {},
            derived=derived_obj,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )

    @staticmethod
    def _created_response(c: Campaign) -> CampaignCreatedResponse:
        response = CampaignService._to_response(c)
        message = _SUCCESS_MESSAGES.get(
            Visibility(c.visibility), "Your campaign has been created."
        )
        return CampaignCreatedResponse(campaign=response, message=message)