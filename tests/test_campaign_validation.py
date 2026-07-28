"""Server-side validation matrix (spec §7) — each rule's pass and fail case."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.campaign.requests import CampaignCreate
from tests.campaign_factory import (
    mobile_app_promotion,
    patched,
    valid_awareness_byoc,
    valid_performance_marketplace,
)


# --- Happy paths ------------------------------------------------------------


def test_valid_performance_marketplace_passes():
    CampaignCreate.model_validate(valid_performance_marketplace())


def test_valid_awareness_byoc_passes():
    CampaignCreate.model_validate(valid_awareness_byoc())


# --- §7 rules: each should raise --------------------------------------------


def _assert_rejected(payload):
    with pytest.raises(ValidationError):
        CampaignCreate.model_validate(payload)


def test_performance_requires_destination_url():
    track = {"track": "PERFORMANCE", "promotion": mobile_app_promotion(), "sales": {}}
    _assert_rejected(patched(valid_performance_marketplace(), track=track))


def test_performance_invalid_destination_url():
    base = valid_performance_marketplace()
    base["track"]["destinationUrl"] = "not-a-url"
    _assert_rejected(base)


def test_performance_non_mobile_requires_buy_point():
    base = valid_performance_marketplace()
    base["track"]["sales"] = {}  # drop buyPoint on a physical promotion
    _assert_rejected(base)


def test_mobile_app_rejects_buy_point():
    track = {
        "track": "PERFORMANCE",
        "destinationUrl": "https://x.com",
        "promotion": mobile_app_promotion(),
        "sales": {"buyPoint": "SHOPIFY"},
    }
    _assert_rejected(patched(valid_performance_marketplace(), track=track))


def test_description_min_length():
    base = valid_performance_marketplace()
    base["creative"]["campaignDescription"] = "too short"
    _assert_rejected(base)


def test_niches_at_least_one():
    _assert_rejected(patched(valid_performance_marketplace(), niches=[]))


def test_marketplace_requires_platforms_and_tiers():
    base = valid_performance_marketplace()
    base["sourcing"]["platforms"] = []
    _assert_rejected(base)


def test_creator_age_order():
    base = valid_performance_marketplace()
    base["sourcing"]["creatorAgeMin"] = 40
    base["sourcing"]["creatorAgeMax"] = 20
    _assert_rejected(base)


def test_audience_age_order():
    base = valid_performance_marketplace()
    base["audience"]["audienceAgeMin"] = 40
    base["audience"]["audienceAgeMax"] = 20
    _assert_rejected(base)


def test_deliverables_at_least_one():
    base = valid_performance_marketplace()
    base["creative"]["deliverables"] = []
    _assert_rejected(base)


def test_key_messaging_min_length():
    base = valid_performance_marketplace()
    base["creative"]["keyMessaging"] = "short"
    _assert_rejected(base)


def test_cta_min_length():
    base = valid_performance_marketplace()
    base["creative"]["cta"] = "x"
    _assert_rejected(base)


def test_compliance_required_unless_bypass():
    _assert_rejected(patched(valid_performance_marketplace(), compliance=None))


def test_compliance_acknowledged_must_be_true():
    base = valid_performance_marketplace()
    base["compliance"]["complianceAcknowledged"] = False
    _assert_rejected(base)


def test_subscription_requires_access_method():
    base = valid_performance_marketplace()
    base["fulfillment"] = {"provisionType": "SUBSCRIPTION"}  # missing access method
    _assert_rejected(base)


def test_timeline_submission_before_live_start():
    base = valid_performance_marketplace()
    base["timeline"]["contentSubmissionDeadline"] = "2026-07-25"  # after liveStart
    _assert_rejected(base)


def test_timeline_live_end_after_start():
    base = valid_performance_marketplace()
    base["timeline"]["liveEnd"] = "2026-07-19"  # before liveStart
    _assert_rejected(base)


def test_marketplace_application_window_order():
    base = valid_performance_marketplace()
    base["sourcing"]["applicationEnd"] = "2026-06-30"  # before applicationStart
    _assert_rejected(base)


def test_max_influencers_at_least_one():
    _assert_rejected(patched(valid_performance_marketplace(), maxInfluencers=0))


def test_byoc_roster_at_least_one():
    base = valid_awareness_byoc()
    base["sourcing"]["inviteRoster"] = []
    _assert_rejected(base)


def test_awareness_must_be_flat_compensation():
    base = valid_awareness_byoc()
    base["compensation"] = {
        "compensationModel": "AFFILIATE",
        "commission": {
            "commissionType": "FLAT",
            "commissionValue": 50,
            "cookieWindow": "7D",
            "promoCodeDiscount": 10,
        },
    }
    _assert_rejected(base)


def test_coupon_enabled_requires_discount():
    base = valid_performance_marketplace()
    base["track"]["sales"]["coupon"] = {"enabled": True}  # missing discountPercent
    _assert_rejected(base)


def test_unknown_kpi_rejected():
    _assert_rejected(patched(valid_performance_marketplace(), kpiTargets={"madeUpMetric": 5}))


def test_unknown_field_rejected():
    """extra='forbid' catches frontend cruft (e.g. the no-UI schema-only fields)."""
    _assert_rejected(patched(valid_performance_marketplace(), totalBudgetCap=5000))