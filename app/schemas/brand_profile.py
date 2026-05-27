"""Schemas for brand profile management (profile, social links, billing, OAuth).

Wire format is camelCase: requests are parsed from camelCase aliases and
responses are serialized back to camelCase (FastAPI serializes response models
`by_alias` by default). Python attributes stay snake_case.

Update schemas use PATCH semantics: only fields actually present in the request
body are applied (`exclude_unset` in the service), so an omitted field is left
unchanged while an explicit `null` clears it.

Enum values are UPPERCASE ("block letters") on the wire and in the database;
the frontend is expected to send them in that exact form.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

# ---------------------------------------------------------------------------
# Enums (validated at the app layer; stored as UPPERCASE VARCHAR — block letters)
# ---------------------------------------------------------------------------


class Industry(str, Enum):
    FASHION = "FASHION"
    BEAUTY = "BEAUTY"
    TECHNOLOGY = "TECHNOLOGY"
    FOOD_BEVERAGE = "FOOD_BEVERAGE"
    TRAVEL = "TRAVEL"
    FITNESS = "FITNESS"
    GAMING = "GAMING"
    FINANCE = "FINANCE"
    EDUCATION = "EDUCATION"
    ENTERTAINMENT = "ENTERTAINMENT"
    HEALTH = "HEALTH"
    AUTOMOTIVE = "AUTOMOTIVE"
    HOME_LIVING = "HOME_LIVING"
    LIFESTYLE = "LIFESTYLE"
    OTHER = "OTHER"


class CompanySize(str, Enum):
    SIZE_1_10 = "1-10"
    SIZE_11_50 = "11-50"
    SIZE_51_200 = "51-200"
    SIZE_201_500 = "201-500"
    SIZE_501_1000 = "501-1000"
    SIZE_1000_PLUS = "1000+"


class SocialPlatform(str, Enum):
    INSTAGRAM = "INSTAGRAM"
    YOUTUBE = "YOUTUBE"
    TIKTOK = "TIKTOK"
    LINKEDIN = "LINKEDIN"
    FACEBOOK = "FACEBOOK"
    X = "X"


class OAuthProvider(str, Enum):
    GOOGLE = "GOOGLE"
    META = "META"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_URL_ADAPTER = TypeAdapter(HttpUrl)
URL_MAX_LENGTH = 500


def validate_http_url(value: str) -> str:
    """Validate an http(s) URL but return the original string (no normalization)."""
    value = value.strip()
    if len(value) > URL_MAX_LENGTH:
        raise ValueError(f"URL must be at most {URL_MAX_LENGTH} characters.")
    _URL_ADAPTER.validate_python(value)  # raises ValueError on bad scheme/host
    return value


class _CamelModel(BaseModel):
    """Base model: camelCase aliases on the wire, snake_case in Python."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,   # also accept snake_case keys on input
        from_attributes=True,    # build responses straight from ORM objects
        str_strip_whitespace=True,
        use_enum_values=False,
    )


# ---------------------------------------------------------------------------
# Brand profile
# ---------------------------------------------------------------------------


class BrandProfileUpdate(_CamelModel):
    """Partial update of the brand's core profile. All fields optional."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    legal_entity_name: Optional[str] = Field(None, max_length=200)
    tagline: Optional[str] = Field(None, max_length=300)
    about: Optional[str] = Field(None, max_length=5000)

    industry: Optional[Industry] = None
    company_size: Optional[CompanySize] = None
    founded_year: Optional[int] = None
    website_url: Optional[str] = Field(None, max_length=URL_MAX_LENGTH)

    headquarters_country: Optional[str] = Field(None, max_length=100)
    address_line_1: Optional[str] = Field(None, max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state_region: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)

    contact_name: Optional[str] = Field(None, max_length=150)
    contact_title: Optional[str] = Field(None, max_length=100)
    contact_email: Optional[EmailStr] = None
    support_email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=30)

    target_regions: Optional[List[str]] = Field(None, max_length=100)
    min_age: Optional[int] = Field(None, ge=0, le=120)
    max_age: Optional[int] = Field(None, ge=0, le=120)
    audience_interests: Optional[List[str]] = Field(None, max_length=100)

    @field_validator("website_url")
    @classmethod
    def _check_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_http_url(v) if v else v

    @field_validator("founded_year")
    @classmethod
    def _check_year(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        current_year = datetime.now(timezone.utc).year
        if not (1800 <= v <= current_year):
            raise ValueError(f"foundedYear must be between 1800 and {current_year}.")
        return v

    @field_validator("phone_number")
    @classmethod
    def _check_phone(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        digit_count = sum(c.isdigit() for c in v)
        if not (7 <= digit_count <= 15):
            raise ValueError("Phone number must contain between 7 and 15 digits.")
        return v

    @field_validator("target_regions", "audience_interests")
    @classmethod
    def _clean_string_list(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        cleaned = [item.strip() for item in v if item and item.strip()]
        for item in cleaned:
            if len(item) > 100:
                raise ValueError("Each entry must be at most 100 characters.")
        return cleaned

    @model_validator(mode="after")
    def _check_age_range(self) -> "BrandProfileUpdate":
        if self.min_age is not None and self.max_age is not None and self.min_age > self.max_age:
            raise ValueError("minAge cannot be greater than maxAge.")
        return self


class BrandProfileResponse(_CamelModel):
    id: UUID
    display_name: Optional[str] = None
    legal_entity_name: Optional[str] = None
    tagline: Optional[str] = None
    about: Optional[str] = None

    industry: Optional[str] = None
    company_size: Optional[str] = None
    founded_year: Optional[int] = None
    website_url: Optional[str] = None

    headquarters_country: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state_region: Optional[str] = None
    postal_code: Optional[str] = None

    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    support_email: Optional[str] = None
    phone_number: Optional[str] = None

    target_regions: List[str] = Field(default_factory=list)
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    audience_interests: List[str] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Social links
# ---------------------------------------------------------------------------


class SocialLinkUpsert(_CamelModel):
    url: str = Field(..., max_length=URL_MAX_LENGTH)

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        return validate_http_url(v)


class SocialLinkResponse(_CamelModel):
    id: UUID
    platform: SocialPlatform
    url: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------


class BillingDetailsUpdate(_CamelModel):
    billing_contact_name: Optional[str] = Field(None, max_length=150)
    billing_email: Optional[EmailStr] = None
    billing_phone: Optional[str] = Field(None, max_length=30)

    address_line_1: Optional[str] = Field(None, max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state_region: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)

    tax_id: Optional[str] = Field(None, max_length=100)
    gst_number: Optional[str] = Field(None, max_length=100)


class BillingDetailsResponse(_CamelModel):
    """Sensitive identifiers are returned masked (last 4 chars only)."""

    billing_contact_name: Optional[str] = None
    billing_email: Optional[str] = None
    billing_phone: Optional[str] = None

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state_region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

    tax_id: Optional[str] = None       # masked, e.g. "••••1234"
    gst_number: Optional[str] = None   # masked

    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# OAuth connections (read-only here; tokens are never exposed)
# ---------------------------------------------------------------------------


class OAuthConnectionResponse(_CamelModel):
    id: UUID
    provider: OAuthProvider
    provider_account_id: str
    scopes: List[str] = Field(default_factory=list)
    is_active: bool
    token_expires_at: Optional[datetime] = None
    connected_at: datetime
    last_refreshed_at: Optional[datetime] = None


class BrandOverviewResponse(_CamelModel):
    """Everything the brand-settings screen needs in one round-trip."""

    profile: BrandProfileResponse
    social_links: List[SocialLinkResponse] = Field(default_factory=list)
    billing: Optional[BillingDetailsResponse] = None
    oauth_connections: List[OAuthConnectionResponse] = Field(default_factory=list)
