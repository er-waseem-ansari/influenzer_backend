"""Postback orchestration: idempotency, raw-first durability, attribution,
authorization, conversion write, and refund reversal.

Flow per accepted (already signature-verified) event:

    store raw event (durable, append-only)
      ├── purchase → dedupe on order_id → resolve attribution → authorize
      │              → compute commission → insert conversion
      └── refund   → find original conversion → reverse (net of refunds)

The HMAC/timestamp/replay gate lives in ``core.postback_security``; by the time we
get here the request is authentic. The one authorization check that remains is
*ownership*: a verified integration must not credit a conversion to a campaign
belonging to a different brand (cross-tenant) — that raises 403.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException
from app.core.postback_security import VerifiedPostback
from app.models.attribution_source import Click, CouponAssignment
from app.models.campaign import Campaign
from app.models.integration import PostbackIntegration
from app.models.postback import Conversion, RawPostbackEvent
from app.schemas.campaign.enums import CookieWindow
from app.schemas.postback import (
    PostbackAccepted,
    PostbackEvent,
    PostbackEventType,
    PurchaseEvent,
    RefundEvent,
)
from app.services import attribution as attr
from app.services.commission import compute_commission

LOGGER = logging.getLogger(__name__)

# CookieWindow enum value -> attribution window length in days.
_COOKIE_WINDOW_DAYS: dict[str, int] = {
    CookieWindow.HOURS_24.value: 1,
    CookieWindow.DAYS_7.value: 7,
    CookieWindow.DAYS_30.value: 30,
    CookieWindow.DAYS_60.value: 60,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PostbackService:

    @staticmethod
    def process(db: Session, verified: VerifiedPostback, event: PostbackEvent) -> PostbackAccepted:
        """Persist and process a verified postback. Returns an accepted response
        (also for duplicates, so the brand stops retrying)."""
        integration = verified.integration
        raw_event = RawPostbackEvent(
            integration_id=integration.id,
            event_type=event.event_type.value,
            order_id=event.order_id,
            raw_body=verified.raw_body.decode("utf-8", errors="replace"),
            headers=verified.audit_headers,
            verification_result="VERIFIED",
            processed=False,
        )
        db.add(raw_event)
        db.flush()  # durable insert before processing; same transaction

        if isinstance(event, RefundEvent):
            result = PostbackService._process_refund(db, integration, event)
        else:
            result = PostbackService._process_purchase(db, integration, event)

        raw_event.processed = True
        db.commit()
        return result

    # --- Purchase -----------------------------------------------------------

    @staticmethod
    def _process_purchase(
        db: Session, integration: PostbackIntegration, event: PurchaseEvent
    ) -> PostbackAccepted:
        # Idempotency: a repeat order_id is accepted but not re-counted.
        existing = PostbackService._find_conversion(db, integration.id, event.order_id)
        if existing is not None:
            LOGGER.info(
                "Duplicate purchase order_id=%s integration_id=%s — deduped",
                event.order_id, integration.id,
            )
            return PostbackService._accepted(event, existing, duplicate=True)

        result = PostbackService._resolve_attribution(db, integration, event)

        # Authorization: never credit another brand's campaign (cross-tenant).
        if (
            result.attributed
            and result.brand_id is not None
            and result.brand_id != integration.brand_id
        ):
            LOGGER.warning(
                "Cross-tenant postback blocked: integration brand=%s campaign brand=%s",
                integration.brand_id, result.brand_id,
            )
            raise ForbiddenException("This integration cannot post for that campaign.")

        commission = None
        if result.attributed and result.campaign_id is not None:
            campaign = db.query(Campaign).filter(Campaign.id == result.campaign_id).first()
            if campaign is not None:
                commission = compute_commission(campaign.affiliate, event.value)

        conversion = Conversion(
            integration_id=integration.id,
            brand_id=integration.brand_id,
            campaign_id=result.campaign_id,
            order_id=event.order_id,
            event_type=event.event_type.value,
            attributed_influencer_id=result.influencer_id,
            attribution_key=result.key,
            attribution_value=result.value,
            confidence=result.confidence,
            flagged_for_review=result.flagged_for_review,
            value=event.value,
            currency=event.currency,
            status=event.status,
            commission_amount=commission,
            occurred_at=event.occurred_at,
            meta=event.meta or None,
        )
        db.add(conversion)
        try:
            db.flush()
        except IntegrityError:
            # Lost the race on (integration_id, order_id) — treat as duplicate.
            db.rollback()
            existing = PostbackService._find_conversion(db, integration.id, event.order_id)
            if existing is not None:
                return PostbackService._accepted(event, existing, duplicate=True)
            raise

        if not result.attributed:
            LOGGER.info("Unattributed conversion stored: order_id=%s", event.order_id)
        return PostbackService._accepted(event, conversion, duplicate=False)

    # --- Refund -------------------------------------------------------------

    @staticmethod
    def _process_refund(
        db: Session, integration: PostbackIntegration, event: RefundEvent
    ) -> PostbackAccepted:
        original = PostbackService._find_conversion(db, integration.id, event.order_id)

        # Nothing to reverse (refund arrived for an unknown order) — accept so the
        # brand stops retrying; the raw event is still recorded for audit.
        if original is None:
            LOGGER.info("Refund for unknown order_id=%s — recorded, nothing to reverse", event.order_id)
            return PostbackAccepted(
                status="accepted", order_id=event.order_id, event_type=event.event_type
            )

        # Idempotent: a refund already applied to this order is a no-op. (Multiple
        # distinct partial refunds per order aren't modelled yet — see doc §8.)
        if original.reversed_at is not None:
            return PostbackService._accepted(event, original, duplicate=True)

        original_value = float(original.value) if original.value is not None else 0.0
        refund_value = float(event.value) if event.value is not None else original_value
        reversed_value = min(refund_value, original_value) if original_value else refund_value

        original.reversed_value = reversed_value
        original.reversed = original_value > 0 and reversed_value >= original_value
        original.reversed_at = _utcnow()
        db.flush()
        LOGGER.info(
            "Refund applied: order_id=%s reversed_value=%s full=%s",
            event.order_id, reversed_value, original.reversed,
        )
        return PostbackService._accepted(event, original, duplicate=False)

    # --- Attribution wiring (DB lookups -> pure resolver) -------------------

    @staticmethod
    def _resolve_attribution(
        db: Session, integration: PostbackIntegration, event: PurchaseEvent
    ) -> attr.AttributionResult:
        click_match: Optional[attr.ClickMatch] = None
        cookie_window_days = _settings_default_window()

        if event.click_id:
            click = db.query(Click).filter(Click.click_id == event.click_id).first()
            if click is not None:
                campaign = db.query(Campaign).filter(Campaign.id == click.campaign_id).first()
                if campaign is not None:
                    cookie_window_days = _campaign_cookie_window_days(campaign)
                    click_match = attr.ClickMatch(
                        campaign_id=click.campaign_id,
                        influencer_id=click.influencer_id,
                        brand_id=campaign.brand_id,
                        occurred_at=click.created_at,
                    )

        coupon_match: Optional[attr.CouponMatch] = None
        if event.coupon_code:
            coupon = (
                db.query(CouponAssignment)
                .filter(CouponAssignment.coupon_code == event.coupon_code.upper())
                .first()
            )
            if coupon is not None:
                campaign = db.query(Campaign).filter(Campaign.id == coupon.campaign_id).first()
                if campaign is not None:
                    coupon_match = attr.CouponMatch(
                        campaign_id=coupon.campaign_id,
                        influencer_id=coupon.influencer_id,
                        brand_id=campaign.brand_id,
                    )

        return attr.resolve(
            click_id=event.click_id,
            coupon_code=event.coupon_code,
            click=click_match,
            coupon=coupon_match,
            conversion_at=event.occurred_at,
            cookie_window_days=cookie_window_days,
        )

    # --- Helpers ------------------------------------------------------------

    @staticmethod
    def _find_conversion(db: Session, integration_id, order_id: str) -> Optional[Conversion]:
        return (
            db.query(Conversion)
            .filter(
                Conversion.integration_id == integration_id,
                Conversion.order_id == order_id,
            )
            .first()
        )

    @staticmethod
    def _accepted(
        event: PostbackEvent, conversion: Conversion, *, duplicate: bool
    ) -> PostbackAccepted:
        return PostbackAccepted(
            status="accepted",
            order_id=event.order_id,
            event_type=event.event_type,
            duplicate=duplicate,
            attributed=conversion.attributed_influencer_id is not None,
            attribution_key=conversion.attribution_key,
            confidence=conversion.confidence,
            flagged_for_review=conversion.flagged_for_review,
            campaign_id=conversion.campaign_id,
            influencer_id=conversion.attributed_influencer_id,
        )


def _settings_default_window() -> int:
    from app.config import get_settings

    return get_settings().POSTBACK_DEFAULT_COOKIE_WINDOW_DAYS


def _campaign_cookie_window_days(campaign: Campaign) -> int:
    """Cookie window from the campaign's affiliate config, else the default."""
    affiliate = campaign.affiliate if isinstance(campaign.affiliate, dict) else None
    if affiliate:
        cw = affiliate.get("cookie_window")
        if cw in _COOKIE_WINDOW_DAYS:
            return _COOKIE_WINDOW_DAYS[cw]
    return _settings_default_window()
