"""Track discriminated union (spec §1/§3; prompt union #1).

``TrackConfig`` is tagged on ``track``:
    AWARENESS    -> optional destination, optional product (``describe_product``
                    gate), never a buy-point. Always flat compensation.
    PERFORMANCE  -> required destination, required promotion, required sales
                    config. Sales is implicit (Leads is descoped — see prompt
                    correction #1); ``SalesConfig`` stays a struct so a future
                    conversion type is a new field, not a rewrite.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import Field, field_validator, model_validator

from app.schemas.campaign.common import CampaignBaseModel, validate_http_url
from app.schemas.campaign.enums import BuyPoint, PromotionType, Track
from app.schemas.campaign.promotion import Promotion


class CouponTracking(CampaignBaseModel):
    """Brand's coupon-tracking choice (per-creator codes are minted on
    assignment, not here). Discount is one typed int percent + optional label
    (prompt correction #4)."""

    enabled: bool = False
    discount_percent: Optional[int] = Field(None, ge=0, le=100)
    discount_label: Optional[str] = Field(None, max_length=50)

    @model_validator(mode="after")
    def _require_discount_when_enabled(self) -> "CouponTracking":
        if self.enabled and self.discount_percent is None:
            raise ValueError("discountPercent is required when coupon tracking is enabled.")
        return self


class SalesConfig(CampaignBaseModel):
    """Performance conversion config. UTM tracking links are always-on (minted
    per creator on assignment) so they need no field; only the optional coupon
    choice and the buy-point are captured here."""

    buy_point: Optional[BuyPoint] = None
    coupon: CouponTracking = Field(default_factory=CouponTracking)


class AwarenessTrack(CampaignBaseModel):
    track: Literal[Track.AWARENESS] = Track.AWARENESS
    describe_product: bool = True
    destination_url: Optional[str] = Field(None, max_length=500)
    promotion: Optional[Promotion] = None

    @field_validator("destination_url")
    @classmethod
    def _url(cls, v: Optional[str]) -> Optional[str]:
        return validate_http_url(v) if v else v

    @model_validator(mode="after")
    def _product_gate(self) -> "AwarenessTrack":
        if not self.describe_product and self.promotion is not None:
            raise ValueError("promotion must be omitted when describeProduct is false.")
        return self


class PerformanceTrack(CampaignBaseModel):
    track: Literal[Track.PERFORMANCE] = Track.PERFORMANCE
    destination_url: str = Field(..., max_length=500)
    promotion: Promotion
    sales: SalesConfig = Field(default_factory=SalesConfig)

    @field_validator("destination_url")
    @classmethod
    def _url(cls, v: str) -> str:
        return validate_http_url(v)

    @model_validator(mode="after")
    def _buy_point_rule(self) -> "PerformanceTrack":
        # Buy-point is collected for everything except mobile apps (spec §3 basics).
        is_mobile = self.promotion.promotion_type is PromotionType.MOBILE_APP
        if is_mobile:
            if self.sales.buy_point is not None:
                raise ValueError("buyPoint is not applicable to a mobile_app promotion.")
        elif self.sales.buy_point is None:
            raise ValueError("buyPoint is required for a Performance campaign.")
        return self


TrackConfig = Annotated[
    Union[AwarenessTrack, PerformanceTrack],
    Field(discriminator="track"),
]