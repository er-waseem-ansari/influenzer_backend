"""Centralised enums & option lists for the campaign domain (spec §5).

Every closed option set the wizard collects lives here — no magic strings
anywhere else. Wire/DB values are UPPERCASE ("block letters"), matching the
rest of the brand API; the frontend's slugified lowercase values map 1:1 to
these (e.g. ``ig_reels`` -> ``IG_REELS``, ``invite_existing`` -> ``INVITE_EXISTING``).

Adding a new option (a new platform, buy-point, provision type, …) is a single
entry here plus, where relevant, one row in :mod:`app.schemas.campaign.catalog`.
"""
from __future__ import annotations

from enum import Enum


# --- Track / sourcing / status ---------------------------------------------


class Track(str, Enum):
    AWARENESS = "AWARENESS"        # pure content play; destination optional
    PERFORMANCE = "PERFORMANCE"    # destination required; always Sales


class Visibility(str, Enum):
    MARKETPLACE = "MARKETPLACE"            # publish brief; creators apply
    INVITE_EXISTING = "INVITE_EXISTING"    # BYOC — invite by email


class CampaignStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


# --- Targeting (marketplace) -----------------------------------------------


class Platform(str, Enum):
    IG_REELS = "IG_REELS"
    IG_STORIES = "IG_STORIES"
    IG_POSTS = "IG_POSTS"
    TIKTOK = "TIKTOK"
    YT_DEDICATED = "YT_DEDICATED"
    YT_SHORTS = "YT_SHORTS"
    LINKEDIN = "LINKEDIN"


class InfluencerTier(str, Enum):
    NANO = "NANO"        # 1K – 10K
    MICRO = "MICRO"      # 10K – 50K
    MIDTIER = "MIDTIER"  # 50K – 500K
    MACRO = "MACRO"      # 500K+


class CreatorGender(str, Enum):
    ANY = "ANY"
    FEMALE = "FEMALE"
    MALE = "MALE"
    NON_BINARY = "NON_BINARY"


class JoinType(str, Enum):
    OPEN = "OPEN"
    APPROVAL = "APPROVAL"


# --- Audience ---------------------------------------------------------------


class AudienceGender(str, Enum):
    ANY = "ANY"
    FEMALE = "FEMALE"
    MALE = "MALE"
    BALANCED = "BALANCED"


# --- Creative ---------------------------------------------------------------


class DeliverableType(str, Enum):
    IG_REEL = "IG_REEL"
    IG_STORY = "IG_STORY"
    IG_POST = "IG_POST"
    TIKTOK_VIDEO = "TIKTOK_VIDEO"
    YT_DEDICATED = "YT_DEDICATED"
    YT_SHORTS = "YT_SHORTS"
    LINKEDIN_POST = "LINKEDIN_POST"


# --- Compliance -------------------------------------------------------------


class UsageRight(str, Enum):
    ORGANIC_REPOST = "ORGANIC_REPOST"
    PAID_WHITELIST = "PAID_WHITELIST"
    SPARK_ADS = "SPARK_ADS"
    WEBSITE = "WEBSITE"


class UsageDuration(str, Enum):
    DAYS_30 = "30D"
    DAYS_90 = "90D"
    YEAR_1 = "1Y"
    PERPETUAL = "PERPETUAL"


# Exclusivity window is a free int constrained to this set (spec EXCLUSIVITY_WINDOWS).
EXCLUSIVITY_WINDOW_DAYS = frozenset({0, 15, 30, 60, 90})


# --- Promotion --------------------------------------------------------------


class PromotionType(str, Enum):
    PHYSICAL_PRODUCT = "PHYSICAL_PRODUCT"
    MOBILE_APP = "MOBILE_APP"
    WEBSITE_SAAS = "WEBSITE_SAAS"


class PromotionScope(str, Enum):
    SINGLE_PRODUCT = "SINGLE_PRODUCT"
    STORE_CATALOG = "STORE_CATALOG"


class ProductCategory(str, Enum):
    APPAREL_FASHION = "APPAREL_FASHION"
    BEAUTY_SKINCARE = "BEAUTY_SKINCARE"
    ELECTRONICS_GADGETS = "ELECTRONICS_GADGETS"
    FOOD_BEVERAGE = "FOOD_BEVERAGE"
    HOME_LIVING = "HOME_LIVING"
    HEALTH_SUPPLEMENTS = "HEALTH_SUPPLEMENTS"
    TOYS_BABY = "TOYS_BABY"
    JEWELLERY_ACCESSORIES = "JEWELLERY_ACCESSORIES"
    OTHER = "OTHER"


class MobileAppPlatform(str, Enum):
    IOS = "IOS"
    ANDROID = "ANDROID"
    BOTH = "BOTH"


class AppCategory(str, Enum):
    HEALTH_FITNESS = "HEALTH_FITNESS"
    FINANCE = "FINANCE"
    PRODUCTIVITY = "PRODUCTIVITY"
    SOCIAL = "SOCIAL"
    GAMING = "GAMING"
    EDUCATION = "EDUCATION"
    SHOPPING = "SHOPPING"
    FOOD_DRINK = "FOOD_DRINK"
    TRAVEL = "TRAVEL"
    OTHER = "OTHER"


class AppPricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    SUBSCRIPTION = "SUBSCRIPTION"
    IN_APP_PURCHASES = "IN_APP_PURCHASES"


class AppPrimaryAction(str, Enum):
    INSTALL = "INSTALL"
    SIGN_UP = "SIGN_UP"
    PURCHASE = "PURCHASE"


class SaasAudience(str, Enum):
    B2B = "B2B"
    B2C = "B2C"
    BOTH = "BOTH"


class SaasPricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    FREE_TRIAL = "FREE_TRIAL"
    SUBSCRIPTION = "SUBSCRIPTION"
    ONE_TIME = "ONE_TIME"


class SaasPrimaryAction(str, Enum):
    SIGN_UP = "SIGN_UP"
    START_FREE_TRIAL = "START_FREE_TRIAL"
    BOOK_A_DEMO = "BOOK_A_DEMO"
    PURCHASE = "PURCHASE"


# --- Sales / attribution ----------------------------------------------------


class BuyPoint(str, Enum):
    SHOPIFY = "SHOPIFY"
    WOOCOMMERCE = "WOOCOMMERCE"
    CUSTOM = "CUSTOM"
    MARKETPLACE = "MARKETPLACE"


class Integration(str, Enum):
    """Backend integration that unlocks verified conversion data (spec §5)."""

    SHOPIFY = "SHOPIFY"
    WOOCOMMERCE = "WOOCOMMERCE"
    PIXEL = "PIXEL"
    POSTBACK = "POSTBACK"
    MMP = "MMP"
    CRM = "CRM"


# --- Compensation / affiliate ----------------------------------------------


class CompensationModel(str, Enum):
    FLAT = "FLAT"
    AFFILIATE = "AFFILIATE"
    HYBRID = "HYBRID"


class CommissionType(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    FLAT = "FLAT"


class CookieWindow(str, Enum):
    HOURS_24 = "24H"
    DAYS_7 = "7D"
    DAYS_30 = "30D"
    DAYS_60 = "60D"


class AffiliateModel(str, Enum):
    ONE_TIME = "ONE_TIME"
    SUBSCRIPTION = "SUBSCRIPTION"
    BOTH = "BOTH"


class SubscriptionCommissionDuration(str, Enum):
    FIRST_ONLY = "FIRST_ONLY"
    MONTHS_3 = "3M"
    MONTHS_6 = "6M"
    MONTHS_12 = "12M"
    LIFETIME = "LIFETIME"


# --- Fulfillment ------------------------------------------------------------


class ProvisionType(str, Enum):
    PRODUCT = "PRODUCT"
    SUBSCRIPTION = "SUBSCRIPTION"
    SERVICE = "SERVICE"
    NONE = "NONE"


class ShippingScope(str, Enum):
    DOMESTIC = "DOMESTIC"
    INTERNATIONAL = "INTERNATIONAL"
    BOTH = "BOTH"


class SubscriptionAccessMethod(str, Enum):
    PROMO_CODE = "PROMO_CODE"
    MANUAL_INVITE = "MANUAL_INVITE"
    LICENSE_KEY = "LICENSE_KEY"


class SubscriptionDuration(str, Enum):
    MONTHS_1 = "1M"
    MONTHS_3 = "3M"
    MONTHS_6 = "6M"
    MONTHS_12 = "12M"
    LIFETIME = "LIFETIME"


# --- Free-tag suggestion lists (not closed enums; spec §5) ------------------
# These are *suggestions* surfaced in the UI; the fields accept arbitrary
# strings, so they live as plain constants rather than enums.

NICHE_SUGGESTIONS: tuple[str, ...] = (
    "Skincare", "Beauty", "Fashion", "Fitness", "Wellness", "Food", "Tech",
    "Gaming", "Edtech", "Lifestyle", "Parenting", "Travel", "Finance",
    "B2B SaaS", "Other",
)
