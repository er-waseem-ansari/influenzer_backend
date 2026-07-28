"""Attribution resolver rules (pure; no DB)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.postback import AttributionConfidence, AttributionKey
from app.services import attribution as attr

BRAND = uuid4()
CAMPAIGN = uuid4()
CREATOR_A = uuid4()
CREATOR_B = uuid4()
NOW = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)


def _click(creator=CREATOR_A, *, days_ago=1):
    return attr.ClickMatch(
        campaign_id=CAMPAIGN,
        influencer_id=creator,
        brand_id=BRAND,
        occurred_at=NOW - timedelta(days=days_ago),
    )


def _coupon(creator=CREATOR_A):
    return attr.CouponMatch(campaign_id=CAMPAIGN, influencer_id=creator, brand_id=BRAND)


def test_click_within_window_attributes_by_click():
    res = attr.resolve(
        click_id="clk_1", coupon_code=None, click=_click(days_ago=5), coupon=None,
        conversion_at=NOW, cookie_window_days=30,
    )
    assert res.attributed and res.key == AttributionKey.CLICK_ID
    assert res.influencer_id == CREATOR_A and res.confidence is None


def test_click_outside_window_falls_through_to_unattributed():
    res = attr.resolve(
        click_id="clk_1", coupon_code=None, click=_click(days_ago=45), coupon=None,
        conversion_at=NOW, cookie_window_days=30,
    )
    assert res.attributed is False


def test_stale_click_falls_through_to_coupon():
    res = attr.resolve(
        click_id="clk_1", coupon_code="MAYA10", click=_click(days_ago=45), coupon=_coupon(),
        conversion_at=NOW, cookie_window_days=30,
    )
    assert res.attributed and res.key == AttributionKey.COUPON
    # No valid click -> rests on the code alone.
    assert res.confidence == AttributionConfidence.CODE_ONLY


def test_coupon_only_is_code_only():
    res = attr.resolve(
        click_id=None, coupon_code="MAYA10", click=None, coupon=_coupon(),
        conversion_at=NOW, cookie_window_days=30,
    )
    assert res.attributed and res.key == AttributionKey.COUPON
    assert res.confidence == AttributionConfidence.CODE_ONLY
    assert res.flagged_for_review is False


def test_both_same_creator_prefers_coupon_not_flagged():
    res = attr.resolve(
        click_id="clk_1", coupon_code="MAYA10",
        click=_click(CREATOR_A), coupon=_coupon(CREATOR_A),
        conversion_at=NOW, cookie_window_days=30,
    )
    assert res.key == AttributionKey.COUPON
    assert res.flagged_for_review is False
    # A valid click existed, so this is not "code only".
    assert res.confidence is None


def test_both_different_creator_flags_for_review():
    res = attr.resolve(
        click_id="clk_1", coupon_code="MAYA10",
        click=_click(CREATOR_A), coupon=_coupon(CREATOR_B),
        conversion_at=NOW, cookie_window_days=30,
    )
    assert res.key == AttributionKey.COUPON
    assert res.influencer_id == CREATOR_B          # coupon is source of truth
    assert res.flagged_for_review is True


def test_neither_key_resolves_is_unattributed():
    res = attr.resolve(
        click_id=None, coupon_code=None, click=None, coupon=None,
        conversion_at=NOW, cookie_window_days=30,
    )
    assert res.attributed is False
    assert res.campaign_id is None and res.influencer_id is None
