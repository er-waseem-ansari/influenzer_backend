"""Config-row tables that drive derived business logic (spec §5/§6/§8).

Keeping these as data (dicts keyed by enum) rather than branching code means a
new buy-point or integration is *a new row*, never an ``if`` edit.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.campaign.enums import BuyPoint, Integration


@dataclass(frozen=True)
class BuyPointMeta:
    """Capability metadata for a sales buy-point (spec SALES_BUY_POINTS)."""

    url_label: str
    integration: Integration | None  # None -> never verifiable (e.g. Marketplace)
    verifiable: bool


# A buy-point's verified-data capability. ``Marketplace`` is intentionally
# unverifiable (no integration); ``custom`` verifies via server postback.
BUY_POINT_CONFIG: dict[BuyPoint, BuyPointMeta] = {
    BuyPoint.SHOPIFY: BuyPointMeta("Store URL", Integration.SHOPIFY, True),
    BuyPoint.WOOCOMMERCE: BuyPointMeta("Store URL", Integration.WOOCOMMERCE, True),
    BuyPoint.CUSTOM: BuyPointMeta("Store URL", Integration.POSTBACK, True),
    BuyPoint.MARKETPLACE: BuyPointMeta("Listing URL", None, False),
}