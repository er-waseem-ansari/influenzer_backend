"""Payload builders for campaign tests.

These produce *valid* base payloads for each flow; individual tests mutate a copy
to exercise a single rule. No DB or app config is touched — these import only the
pure schema/derivation layers.
"""
from __future__ import annotations

import copy
from typing import Any


def physical_single_product() -> dict[str, Any]:
    return {
        "promotionType": "PHYSICAL_PRODUCT",
        "scope": {
            "promotionScope": "SINGLE_PRODUCT",
            "products": [
                {
                    "name": "Vitamin C Serum",
                    "category": "BEAUTY_SKINCARE",
                    "price": 1899,
                    "productUrl": "https://brand.com/serum",
                    "description": "A great serum for glowing skin.",
                }
            ],
        },
    }


def mobile_app_promotion() -> dict[str, Any]:
    return {
        "promotionType": "MOBILE_APP",
        "details": {
            "name": "FitApp",
            "platform": "IOS",
            "pricingModel": "FREEMIUM",
            "primaryAction": "INSTALL",
            "description": "A fitness tracking app.",
        },
    }


def valid_performance_marketplace() -> dict[str, Any]:
    """Performance + Marketplace + Physical single-product + Affiliate."""
    return {
        "niches": ["Beauty", "Skincare"],
        "maxInfluencers": 10,
        "track": {
            "track": "PERFORMANCE",
            "destinationUrl": "https://brand.com/serum",
            "promotion": physical_single_product(),
            "sales": {
                "buyPoint": "SHOPIFY",
                "coupon": {"enabled": True, "discountPercent": 15, "discountLabel": "15% OFF"},
            },
        },
        "sourcing": {
            "visibility": "MARKETPLACE",
            "platforms": ["IG_REELS", "TIKTOK"],
            "tiers": ["NANO", "MICRO"],
            "applicationStart": "2026-07-01",
            "applicationEnd": "2026-07-10",
            "joinType": "APPROVAL",
        },
        "compensation": {
            "compensationModel": "AFFILIATE",
            "commission": {
                "commissionType": "PERCENTAGE",
                "commissionValue": 12,
                "cookieWindow": "30D",
                "promoCodeDiscount": 15,
                "promoCodePrefix": "CREATOR",
            },
        },
        "fulfillment": {
            "provisionType": "PRODUCT",
            "shippingScope": "DOMESTIC",
            "estimatedDeliveryDays": 5,
        },
        "audience": {
            "audienceAgeMin": 18,
            "audienceAgeMax": 35,
            "audienceGender": "FEMALE",
            "audienceInterests": ["skincare"],
        },
        "creative": {
            "title": "Glow Serum Launch",
            "campaignDescription": "Drive trial of our new vitamin C serum with honest reviews.",
            "deliverables": [{"type": "IG_REEL", "quantity": 2}],
            "keyMessaging": "Hook in the first 3 seconds with the glow result.",
            "cta": "Shop now",
            "preApprovalRequired": True,
        },
        "timeline": {
            "contentSubmissionDeadline": "2026-07-15",
            "liveStart": "2026-07-20",
            "liveEnd": "2026-07-30",
        },
        "compliance": {
            "usageRightsScope": ["ORGANIC_REPOST", "SPARK_ADS"],
            "usageRightsDuration": "90D",
            "exclusivityWindowDays": 30,
            "complianceAcknowledged": True,
        },
        "kpiTargets": {"roas": 3.5, "revenue": 100000},
    }


def valid_awareness_byoc() -> dict[str, Any]:
    """Awareness + BYOC + contract bypass (compliance skipped) + Flat."""
    return {
        "niches": ["Lifestyle"],
        "maxInfluencers": 5,
        "track": {"track": "AWARENESS", "describeProduct": False},
        "sourcing": {
            "visibility": "INVITE_EXISTING",
            "inviteRoster": [{"email": "a@b.com"}, {"email": "c@d.com", "customRate": 500}],
            "welcomeMessage": "Hi there!",
            "contractBypassAcknowledged": True,
        },
        "compensation": {"compensationModel": "FLAT", "fixedFeePerCreator": 2000},
        "fulfillment": {"provisionType": "NONE"},
        "audience": {},
        "creative": {
            "title": "Brand Buzz",
            "campaignDescription": "Pure awareness content play for our brand.",
            "deliverables": [{"type": "IG_STORY", "quantity": 1}],
            "keyMessaging": "Talk about the vibe.",
            "cta": "Follow us",
        },
        "timeline": {
            "contentSubmissionDeadline": "2026-08-01",
            "liveStart": "2026-08-05",
            "liveEnd": "2026-08-15",
        },
    }


def patched(base: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Deep-copy ``base`` and replace top-level keys from ``overrides``."""
    out = copy.deepcopy(base)
    out.update(overrides)
    return out