"""Attribution resolution — a pure function over already-fetched lookups.

The service does the DB I/O (find the click row, find the coupon assignment, read
the campaign's cookie window) and hands the results here as plain dataclasses.
Keeping the decision logic free of I/O means every branch in the spec's
attribution rules is unit-testable without a database.

Rules (spec §"Attribution logic"):

1. ``click_id`` resolving to a click **within the cookie window** earns credit.
2. else a ``coupon_code`` mapping to an assigned creator earns credit
   (tag ``CODE_ONLY`` — attribution rests on the code alone).
3. else → UNATTRIBUTED (credit no one); the caller still stores the event.

Conflict: if a valid click and a coupon resolve to **different** creators, the
coupon is the source of truth for coupon-driven sales, but we set
``flagged_for_review`` rather than silently choosing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from app.models.postback import AttributionConfidence, AttributionKey


@dataclass(frozen=True)
class ClickMatch:
    """A resolved click row (``click_id`` -> creator/campaign)."""

    campaign_id: UUID
    influencer_id: UUID
    brand_id: UUID          # owner of the campaign (for authorization)
    occurred_at: datetime   # when the click happened (window anchor)


@dataclass(frozen=True)
class CouponMatch:
    """A resolved coupon assignment (``coupon_code`` -> creator/campaign)."""

    campaign_id: UUID
    influencer_id: UUID
    brand_id: UUID


@dataclass(frozen=True)
class AttributionResult:
    attributed: bool
    key: Optional[str] = None              # AttributionKey.* or None
    value: Optional[str] = None            # the click_id / coupon code that won
    campaign_id: Optional[UUID] = None
    influencer_id: Optional[UUID] = None
    brand_id: Optional[UUID] = None        # owner of the credited campaign (authz)
    confidence: Optional[str] = None       # AttributionConfidence.* or None
    flagged_for_review: bool = False


UNATTRIBUTED = AttributionResult(attributed=False)


def _click_in_window(
    click: ClickMatch, conversion_at: datetime, cookie_window_days: int
) -> bool:
    """True iff the conversion falls within ``cookie_window_days`` after the click
    (and not before it)."""
    delta = conversion_at - click.occurred_at
    return timedelta(0) <= delta <= timedelta(days=cookie_window_days)


def resolve(
    *,
    click_id: Optional[str],
    coupon_code: Optional[str],
    click: Optional[ClickMatch],
    coupon: Optional[CouponMatch],
    conversion_at: datetime,
    cookie_window_days: int,
) -> AttributionResult:
    """Decide how a conversion is credited. See module docstring for the rules."""
    click_valid = click is not None and _click_in_window(
        click, conversion_at, cookie_window_days
    )

    # Both resolve: coupon is source of truth; flag if creators disagree.
    if click_valid and coupon is not None:
        flagged = click.influencer_id != coupon.influencer_id
        return AttributionResult(
            attributed=True,
            key=AttributionKey.COUPON,
            value=coupon_code,
            campaign_id=coupon.campaign_id,
            influencer_id=coupon.influencer_id,
            brand_id=coupon.brand_id,
            flagged_for_review=flagged,
        )

    # Valid click only.
    if click_valid:
        return AttributionResult(
            attributed=True,
            key=AttributionKey.CLICK_ID,
            value=click_id,
            campaign_id=click.campaign_id,
            influencer_id=click.influencer_id,
            brand_id=click.brand_id,
        )

    # Coupon only (covers: no click_id, or a click_id that didn't resolve / was
    # stale). Attribution rests on the code alone -> CODE_ONLY.
    if coupon is not None:
        return AttributionResult(
            attributed=True,
            key=AttributionKey.COUPON,
            value=coupon_code,
            campaign_id=coupon.campaign_id,
            influencer_id=coupon.influencer_id,
            brand_id=coupon.brand_id,
            confidence=AttributionConfidence.CODE_ONLY,
        )

    return UNATTRIBUTED