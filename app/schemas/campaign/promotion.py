"""Promotion discriminated union (spec §5 PROMOTION_TYPES; prompt union #3).

``Promotion`` is tagged on ``promotion_type``:
    PHYSICAL_PRODUCT -> ``PhysicalProductPromotion`` (which nests a second
                        union on ``promotion_scope``: single-product vs store)
    MOBILE_APP       -> ``MobileAppPromotion``
    WEBSITE_SAAS     -> ``WebsiteSaasPromotion``

Every detail field is a real typed model — no ``dict[str, Any]`` bags.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import Field

from app.schemas.campaign.common import CampaignBaseModel, validate_http_url
from app.schemas.campaign.enums import (
    AppCategory,
    AppPricingModel,
    AppPrimaryAction,
    MobileAppPlatform,
    ProductCategory,
    PromotionScope,
    PromotionType,
    SaasAudience,
    SaasPricingModel,
    SaasPrimaryAction,
)
from pydantic import field_validator


# --- Detail records ---------------------------------------------------------


class PhysicalProductDetails(CampaignBaseModel):
    """One product in a single-product physical campaign (PHYSICAL_PRODUCT_FIELDS)."""

    name: str = Field(..., min_length=1, max_length=200)
    category: ProductCategory
    price: float = Field(..., ge=0)
    product_url: str = Field(..., max_length=500)
    key_features: Optional[str] = Field(None, max_length=1000)
    description: str = Field(..., min_length=1, max_length=5000)

    @field_validator("product_url")
    @classmethod
    def _url(cls, v: str) -> str:
        return validate_http_url(v)


class StoreCatalogDetails(CampaignBaseModel):
    """A whole-store / catalog promotion (STORE_CATALOG_FIELDS)."""

    store_name: str = Field(..., min_length=1, max_length=200)
    category: ProductCategory
    collections: Optional[str] = Field(None, max_length=1000)
    price_range: Optional[str] = Field(None, max_length=100)
    description: str = Field(..., min_length=1, max_length=5000)


class MobileAppDetails(CampaignBaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    platform: MobileAppPlatform
    app_category: Optional[AppCategory] = None
    app_store_url: Optional[str] = Field(None, max_length=500)
    play_store_url: Optional[str] = Field(None, max_length=500)
    pricing_model: AppPricingModel
    primary_action: AppPrimaryAction
    description: str = Field(..., min_length=1, max_length=5000)

    @field_validator("app_store_url", "play_store_url")
    @classmethod
    def _url(cls, v: Optional[str]) -> Optional[str]:
        return validate_http_url(v) if v else v


class WebsiteSaasDetails(CampaignBaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    audience: Optional[SaasAudience] = None
    pricing_model: SaasPricingModel
    starting_price: Optional[str] = Field(None, max_length=100)
    free_trial_days: Optional[int] = Field(None, ge=0, le=365)
    primary_action: SaasPrimaryAction
    description: str = Field(..., min_length=1, max_length=5000)


# --- Physical scope (nested union on promotion_scope) -----------------------


class PhysicalSingleProductScope(CampaignBaseModel):
    promotion_scope: Literal[PromotionScope.SINGLE_PRODUCT] = PromotionScope.SINGLE_PRODUCT
    products: list[PhysicalProductDetails] = Field(..., min_length=1, max_length=50)


class PhysicalStoreCatalogScope(CampaignBaseModel):
    promotion_scope: Literal[PromotionScope.STORE_CATALOG] = PromotionScope.STORE_CATALOG
    store: StoreCatalogDetails


PhysicalScope = Annotated[
    Union[PhysicalSingleProductScope, PhysicalStoreCatalogScope],
    Field(discriminator="promotion_scope"),
]


# --- Top-level promotion variants -------------------------------------------


class PhysicalProductPromotion(CampaignBaseModel):
    promotion_type: Literal[PromotionType.PHYSICAL_PRODUCT] = PromotionType.PHYSICAL_PRODUCT
    scope: PhysicalScope


class MobileAppPromotion(CampaignBaseModel):
    promotion_type: Literal[PromotionType.MOBILE_APP] = PromotionType.MOBILE_APP
    details: MobileAppDetails


class WebsiteSaasPromotion(CampaignBaseModel):
    promotion_type: Literal[PromotionType.WEBSITE_SAAS] = PromotionType.WEBSITE_SAAS
    details: WebsiteSaasDetails


Promotion = Annotated[
    Union[PhysicalProductPromotion, MobileAppPromotion, WebsiteSaasPromotion],
    Field(discriminator="promotion_type"),
]
