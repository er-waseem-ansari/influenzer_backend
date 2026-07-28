"""Server-side derivation of campaign business logic (spec §8).

These are pure functions over a validated :class:`CampaignCreate`. Nothing here
is ever accepted from the client. Every ``match`` over a discriminated union ends
in :func:`typing.assert_never`, so adding a union variant fails type-checking
until it is handled here — the extensibility guarantee from the prompt.

Current scope note: ``affiliate_model`` is pinned to ``ONE_TIME`` (subscription/
both are reserved for later), so the subscription-commission-duration rule never
fires today.
"""
from __future__ import annotations

from typing import assert_never

from app.schemas.campaign.catalog import BUY_POINT_CONFIG
from app.schemas.campaign.compensation import AffiliateComp, FlatComp, HybridComp
from app.schemas.campaign.derived import AttributionProfile, CampaignDerived
from app.schemas.campaign.enums import AffiliateModel, PromotionType
from app.schemas.campaign.fulfillment import (
    NoProvisionFulfillment,
    ProductFulfillment,
    ServiceFulfillment,
    SubscriptionFulfillment,
)
from app.schemas.campaign.metrics import headline_metrics, measured_metric_ids
from app.schemas.campaign.promotion import (
    MobileAppPromotion,
    PhysicalProductPromotion,
    WebsiteSaasPromotion,
)
from app.schemas.campaign.requests import CampaignCreate
from app.schemas.campaign.track import AwarenessTrack, PerformanceTrack


# --- Individual derivations -------------------------------------------------


def derive_fixed_fee(comp: FlatComp | AffiliateComp | HybridComp) -> float:
    """§8: commission-only (affiliate) forces the flat fee to 0."""
    match comp:
        case FlatComp():
            return float(comp.fixed_fee_per_creator)
        case AffiliateComp():
            return 0.0
        case HybridComp():
            return float(comp.fixed_fee_per_creator)
        case _:
            assert_never(comp)


def derive_affiliate_enabled(comp: FlatComp | AffiliateComp | HybridComp) -> bool:
    return not isinstance(comp, FlatComp)


def derive_affiliate_model(promotion) -> AffiliateModel:
    """Current scope: always ONE_TIME.

    (Reserved future logic: SUBSCRIPTION when the promoted product is
    subscription-priced or an app/SaaS.)
    """
    return AffiliateModel.ONE_TIME


def is_mobile_app(track: AwarenessTrack | PerformanceTrack) -> bool:
    promotion = track.promotion
    return promotion is not None and promotion.promotion_type is PromotionType.MOBILE_APP


def derive_gifting_enabled(
    fulfillment: ProductFulfillment
    | SubscriptionFulfillment
    | ServiceFulfillment
    | NoProvisionFulfillment,
) -> bool:
    """§8: gifting is on for any provision type other than NONE."""
    match fulfillment:
        case ProductFulfillment() | SubscriptionFulfillment() | ServiceFulfillment():
            return True
        case NoProvisionFulfillment():
            return False
        case _:
            assert_never(fulfillment)


def derive_attribution_profile(track: AwarenessTrack | PerformanceTrack) -> AttributionProfile:
    """§8: can verified conversion data ever be unlocked, and by which
    integration. Marketplace buy-point is never verifiable; verified is always
    deferred (post-launch connect) for Sales."""
    match track:
        case AwarenessTrack():
            return AttributionProfile(
                verified_available=False,
                unlocking_integration=None,
                verified_at_launch=False,
                note="Awareness campaign — content metrics only; no verified conversions.",
            )
        case PerformanceTrack():
            match track.promotion:
                case MobileAppPromotion():
                    from app.schemas.campaign.enums import Integration

                    return AttributionProfile(
                        verified_available=True,
                        unlocking_integration=Integration.MMP,
                        verified_at_launch=False,
                        note="Connect a mobile measurement partner to verify installs & revenue.",
                    )
                case PhysicalProductPromotion() | WebsiteSaasPromotion():
                    meta = BUY_POINT_CONFIG[track.sales.buy_point]
                    if meta.verifiable:
                        return AttributionProfile(
                            verified_available=True,
                            unlocking_integration=meta.integration,
                            verified_at_launch=False,
                            note="Clicks tracked now; connect the integration to verify revenue.",
                        )
                    return AttributionProfile(
                        verified_available=False,
                        unlocking_integration=None,
                        verified_at_launch=False,
                        note="Clicks tracked; this buy-point can't be revenue-verified.",
                    )
                case _:
                    assert_never(track.promotion)
        case _:
            assert_never(track)


# --- Bundle -----------------------------------------------------------------


def derive_campaign(data: CampaignCreate) -> CampaignDerived:
    """Compute every §8 derived value for a validated create request."""
    comp = data.compensation
    affiliate_enabled = derive_affiliate_enabled(comp)
    mobile = is_mobile_app(data.track)
    performance = isinstance(data.track, PerformanceTrack)
    has_destination = bool(data.track.destination_url)

    affiliate_model = derive_affiliate_model(data.track.promotion) if affiliate_enabled else None

    return CampaignDerived(
        affiliate_enabled=affiliate_enabled,
        affiliate_model=affiliate_model,
        promo_code_enabled=affiliate_enabled,  # §8: forced true when affiliate
        gifting_enabled=derive_gifting_enabled(data.fulfillment),
        fixed_fee_per_creator=derive_fixed_fee(comp),
        attribution_profile=derive_attribution_profile(data.track),
        headline_kpis=list(headline_metrics(performance=performance, mobile_app=mobile)),
        measured_metrics=measured_metric_ids(
            performance=performance, mobile_app=mobile, has_destination=has_destination
        ),
    )