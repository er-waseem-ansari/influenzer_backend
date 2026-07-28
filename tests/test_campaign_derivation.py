"""Derived business logic (spec §8) tests."""
from __future__ import annotations

from app.schemas.campaign.enums import AffiliateModel, Integration
from app.schemas.campaign.requests import CampaignCreate
from app.services.campaign_derivation import derive_campaign
from tests.campaign_factory import (
    mobile_app_promotion,
    patched,
    valid_awareness_byoc,
    valid_performance_marketplace,
)


def _derive(payload):
    return derive_campaign(CampaignCreate.model_validate(payload))


def test_affiliate_forces_fixed_fee_zero_and_promo_enabled():
    d = _derive(valid_performance_marketplace())  # AFFILIATE
    assert d.affiliate_enabled is True
    assert d.fixed_fee_per_creator == 0.0
    assert d.promo_code_enabled is True
    assert d.affiliate_model is AffiliateModel.ONE_TIME  # pinned per current scope


def test_flat_is_not_affiliate():
    d = _derive(valid_awareness_byoc())  # FLAT
    assert d.affiliate_enabled is False
    assert d.promo_code_enabled is False
    assert d.affiliate_model is None
    assert d.fixed_fee_per_creator == 2000.0


def test_hybrid_keeps_fixed_fee():
    base = valid_performance_marketplace()
    base["compensation"] = {
        "compensationModel": "HYBRID",
        "fixedFeePerCreator": 1500,
        "commission": {
            "commissionType": "PERCENTAGE",
            "commissionValue": 8,
            "cookieWindow": "30D",
            "promoCodeDiscount": 10,
        },
    }
    d = _derive(base)
    assert d.affiliate_enabled is True
    assert d.fixed_fee_per_creator == 1500.0


def test_gifting_enabled_tracks_provision_type():
    # PRODUCT provisioning -> gifting on
    assert _derive(valid_performance_marketplace()).gifting_enabled is True
    # NONE provisioning -> gifting off
    assert _derive(valid_awareness_byoc()).gifting_enabled is False


def test_attribution_shopify_verifiable():
    d = _derive(valid_performance_marketplace())  # SHOPIFY buy-point
    ap = d.attribution_profile
    assert ap.verified_available is True
    assert ap.unlocking_integration is Integration.SHOPIFY
    assert ap.verified_at_launch is False  # deferred to post-launch connect


def test_attribution_marketplace_never_verifiable():
    base = valid_performance_marketplace()
    base["track"]["sales"]["buyPoint"] = "MARKETPLACE"
    ap = _derive(base).attribution_profile
    assert ap.verified_available is False
    assert ap.unlocking_integration is None


def test_attribution_mobile_app_uses_mmp():
    base = valid_performance_marketplace()
    base["track"] = {
        "track": "PERFORMANCE",
        "destinationUrl": "https://x.com",
        "promotion": mobile_app_promotion(),
        "sales": {},
    }
    ap = _derive(base).attribution_profile
    assert ap.unlocking_integration is Integration.MMP


def test_awareness_attribution_not_available():
    ap = _derive(valid_awareness_byoc()).attribution_profile
    assert ap.verified_available is False


def test_headline_kpis_by_track():
    # sales (web/physical) -> roas/revenue
    assert _derive(valid_performance_marketplace()).headline_kpis == ["roas", "revenue"]
    # awareness -> reach/impressions
    assert _derive(valid_awareness_byoc()).headline_kpis == ["reach", "impressions"]


def test_mobile_app_headline_installs():
    base = valid_performance_marketplace()
    base["track"] = {
        "track": "PERFORMANCE",
        "destinationUrl": "https://x.com",
        "promotion": mobile_app_promotion(),
        "sales": {},
    }
    assert _derive(base).headline_kpis == ["installs", "cpi"]