"""Discriminated-union discrimination + round-trip + exhaustiveness tests.

Each variant must (a) discriminate to the right type from its tag, and (b)
round-trip through a model_dump -> TypeAdapter.validate cycle (the exact path the
persistence layer uses to store and rebuild JSONB blobs).
"""
from __future__ import annotations

import pytest

from app.schemas.campaign import enums
from app.schemas.campaign.compensation import (
    AffiliateComp,
    CompensationConfig,
    FlatComp,
    HybridComp,
)
from app.schemas.campaign.fulfillment import (
    FulfillmentConfig,
    NoProvisionFulfillment,
    ProductFulfillment,
    ServiceFulfillment,
    SubscriptionFulfillment,
)
from app.schemas.campaign.promotion import (
    MobileAppPromotion,
    PhysicalProductPromotion,
    PhysicalSingleProductScope,
    PhysicalStoreCatalogScope,
    WebsiteSaasPromotion,
)
from app.schemas.campaign.requests import CampaignCreate
from app.schemas.campaign.responses import (
    COMPENSATION_ADAPTER,
    FULFILLMENT_ADAPTER,
    PROMOTION_ADAPTER,
)
from app.schemas.campaign.sourcing import ByocSourcing, MarketplaceSourcing
from app.schemas.campaign.track import AwarenessTrack, PerformanceTrack
from tests.campaign_factory import (
    mobile_app_promotion,
    physical_single_product,
    valid_awareness_byoc,
    valid_performance_marketplace,
)


def _roundtrip(adapter, obj):
    return adapter.validate_python(obj.model_dump(mode="json", by_alias=False))


# --- Track ------------------------------------------------------------------


def test_track_discriminates_performance():
    m = CampaignCreate.model_validate(valid_performance_marketplace())
    assert isinstance(m.track, PerformanceTrack)


def test_track_discriminates_awareness():
    m = CampaignCreate.model_validate(valid_awareness_byoc())
    assert isinstance(m.track, AwarenessTrack)


# --- Sourcing ---------------------------------------------------------------


def test_sourcing_discriminates_marketplace():
    m = CampaignCreate.model_validate(valid_performance_marketplace())
    assert isinstance(m.sourcing, MarketplaceSourcing)


def test_sourcing_discriminates_byoc():
    m = CampaignCreate.model_validate(valid_awareness_byoc())
    assert isinstance(m.sourcing, ByocSourcing)


# --- Promotion (incl. nested scope union) -----------------------------------


@pytest.mark.parametrize(
    "blob,top_type,inner",
    [
        (physical_single_product(), PhysicalProductPromotion, PhysicalSingleProductScope),
        (mobile_app_promotion(), MobileAppPromotion, None),
        (
            {
                "promotionType": "PHYSICAL_PRODUCT",
                "scope": {
                    "promotionScope": "STORE_CATALOG",
                    "store": {
                        "storeName": "My Store",
                        "category": "APPAREL_FASHION",
                        "description": "A lovely store of clothes.",
                    },
                },
            },
            PhysicalProductPromotion,
            PhysicalStoreCatalogScope,
        ),
        (
            {
                "promotionType": "WEBSITE_SAAS",
                "details": {
                    "name": "Tool",
                    "pricingModel": "SUBSCRIPTION",
                    "primaryAction": "SIGN_UP",
                    "description": "A useful SaaS tool.",
                },
            },
            WebsiteSaasPromotion,
            None,
        ),
    ],
)
def test_promotion_variants_discriminate_and_roundtrip(blob, top_type, inner):
    obj = PROMOTION_ADAPTER.validate_python(blob)
    assert isinstance(obj, top_type)
    if inner is not None:
        assert isinstance(obj.scope, inner)
    assert isinstance(_roundtrip(PROMOTION_ADAPTER, obj), top_type)


# --- Compensation -----------------------------------------------------------


@pytest.mark.parametrize(
    "blob,expected",
    [
        ({"compensationModel": "FLAT", "fixedFeePerCreator": 100}, FlatComp),
        (
            {
                "compensationModel": "AFFILIATE",
                "commission": {
                    "commissionType": "FLAT",
                    "commissionValue": 50,
                    "cookieWindow": "7D",
                    "promoCodeDiscount": 10,
                },
            },
            AffiliateComp,
        ),
        (
            {
                "compensationModel": "HYBRID",
                "fixedFeePerCreator": 100,
                "commission": {
                    "commissionType": "PERCENTAGE",
                    "commissionValue": 5,
                    "cookieWindow": "30D",
                    "promoCodeDiscount": 10,
                },
            },
            HybridComp,
        ),
    ],
)
def test_compensation_variants(blob, expected):
    obj = COMPENSATION_ADAPTER.validate_python(blob)
    assert isinstance(obj, expected)
    assert isinstance(_roundtrip(COMPENSATION_ADAPTER, obj), expected)


# --- Fulfillment ------------------------------------------------------------


@pytest.mark.parametrize(
    "blob,expected",
    [
        ({"provisionType": "NONE"}, NoProvisionFulfillment),
        ({"provisionType": "PRODUCT", "shippingScope": "BOTH"}, ProductFulfillment),
        (
            {"provisionType": "SUBSCRIPTION", "subscriptionAccessMethod": "PROMO_CODE"},
            SubscriptionFulfillment,
        ),
        ({"provisionType": "SERVICE", "serviceProvisionNote": "Free session"}, ServiceFulfillment),
    ],
)
def test_fulfillment_variants(blob, expected):
    obj = FULFILLMENT_ADAPTER.validate_python(blob)
    assert isinstance(obj, expected)
    assert isinstance(_roundtrip(FULFILLMENT_ADAPTER, obj), expected)


# --- Exhaustiveness ---------------------------------------------------------


def test_compensation_union_membership_matches_enum():
    """If a CompensationModel enum value is added, a matching variant must exist
    (and the derivation match must handle it) — this guards the union."""
    from typing import get_args

    variants = get_args(get_args(CompensationConfig)[0])  # unwrap Annotated[Union[...]]
    tags = {v.model_fields["compensation_model"].default for v in variants}
    assert tags == set(enums.CompensationModel)


def test_provision_union_membership_matches_enum():
    from typing import get_args

    variants = get_args(get_args(FulfillmentConfig)[0])
    tags = {v.model_fields["provision_type"].default for v in variants}
    assert tags == set(enums.ProvisionType)