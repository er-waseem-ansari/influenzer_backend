"""Compensation discriminated union (spec §3 step 11; prompt union #4).

Tagged on ``compensation_model``:
    FLAT      -> just ``fixed_fee_per_creator``.
    AFFILIATE -> commission config only; ``fixed_fee_per_creator`` is forced to
                 0 server-side (commission-only).
    HYBRID    -> flat fee + commission config.

Derived/forced values are NOT accepted from the client:
    ``affiliate_enabled``, ``affiliate_model`` (pinned ONE_TIME for now),
    ``promo_code_enabled`` (forced true when affiliate). See
    :mod:`app.services.campaign_derivation`.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import Field

from app.schemas.campaign.common import CampaignBaseModel
from app.schemas.campaign.enums import (
    CommissionType,
    CompensationModel,
    CookieWindow,
    SubscriptionCommissionDuration,
)


class CommissionConfig(CampaignBaseModel):
    """Affiliate/hybrid commission config. Promo code is mandatory when
    affiliate is active (``promo_code_enabled`` is forced true server-side), so
    the buyer discount is required here."""

    commission_type: CommissionType
    commission_value: float = Field(..., ge=0)
    cookie_window: CookieWindow
    promo_code_discount: int = Field(..., ge=0, le=100)
    promo_code_prefix: Optional[str] = Field(None, max_length=30)
    # Reserved: only required once affiliate_model is subscription/both. Pinned
    # ONE_TIME for now, so this stays optional and unused.
    subscription_commission_duration: Optional[SubscriptionCommissionDuration] = None


class FlatComp(CampaignBaseModel):
    compensation_model: Literal[CompensationModel.FLAT] = CompensationModel.FLAT
    fixed_fee_per_creator: float = Field(..., ge=0)


class AffiliateComp(CampaignBaseModel):
    compensation_model: Literal[CompensationModel.AFFILIATE] = CompensationModel.AFFILIATE
    commission: CommissionConfig
    # fixed_fee_per_creator intentionally absent — forced to 0 (commission-only).


class HybridComp(CampaignBaseModel):
    compensation_model: Literal[CompensationModel.HYBRID] = CompensationModel.HYBRID
    fixed_fee_per_creator: float = Field(..., ge=0)
    commission: CommissionConfig


CompensationConfig = Annotated[
    Union[FlatComp, AffiliateComp, HybridComp],
    Field(discriminator="compensation_model"),
]