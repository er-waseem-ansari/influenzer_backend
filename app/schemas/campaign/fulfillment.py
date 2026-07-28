"""Fulfillment discriminated union (spec §3 step 7), tagged on ``provision_type``.

``gifting_enabled`` (= provision ≠ NONE) is derived server-side, not accepted
here. A new provisioning style is a new variant + enum row.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import Field, field_validator

from app.schemas.campaign.common import CampaignBaseModel
from app.schemas.campaign.enums import (
    ProvisionType,
    ShippingScope,
    SubscriptionAccessMethod,
    SubscriptionDuration,
)


class ProductFulfillment(CampaignBaseModel):
    provision_type: Literal[ProvisionType.PRODUCT] = ProvisionType.PRODUCT
    product_variants: list[str] = Field(default_factory=list)
    shipping_scope: Optional[ShippingScope] = None
    shipping_countries: list[str] = Field(default_factory=list)
    estimated_delivery_days: Optional[int] = Field(None, ge=0, le=60)

    @field_validator("product_variants", "shipping_countries")
    @classmethod
    def _tags(cls, v: Optional[list[str]]) -> list[str]:
        return [t.strip() for t in (v or []) if t and t.strip()]


class SubscriptionFulfillment(CampaignBaseModel):
    provision_type: Literal[ProvisionType.SUBSCRIPTION] = ProvisionType.SUBSCRIPTION
    subscription_plan: Optional[str] = Field(None, max_length=200)
    subscription_duration: Optional[SubscriptionDuration] = None
    subscription_seats: int = Field(1, ge=1, le=100)
    subscription_access_method: SubscriptionAccessMethod  # required (spec §7.11)


class ServiceFulfillment(CampaignBaseModel):
    provision_type: Literal[ProvisionType.SERVICE] = ProvisionType.SERVICE
    service_provision_note: Optional[str] = Field(None, max_length=2000)


class NoProvisionFulfillment(CampaignBaseModel):
    provision_type: Literal[ProvisionType.NONE] = ProvisionType.NONE


FulfillmentConfig = Annotated[
    Union[
        ProductFulfillment,
        SubscriptionFulfillment,
        ServiceFulfillment,
        NoProvisionFulfillment,
    ],
    Field(discriminator="provision_type"),
]