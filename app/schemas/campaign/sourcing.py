"""Sourcing discriminated union (spec §2/§3; prompt union #2).

``SourcingConfig`` is tagged on ``visibility``:
    MARKETPLACE     -> creator targeting + application window + join type.
    INVITE_EXISTING -> BYOC roster + welcome message + contract-bypass ack.

The application window / join type live on the marketplace variant (they are
marketplace-only in the spec), keeping each variant self-contained.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Optional, Union

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.campaign.common import CampaignBaseModel
from app.schemas.campaign.enums import (
    CreatorGender,
    InfluencerTier,
    JoinType,
    Platform,
    Visibility,
)

_MAX_TAG_LEN = 100


def _clean_tags(v: Optional[list[str]]) -> list[str]:
    if not v:
        return []
    cleaned = [t.strip() for t in v if t and t.strip()]
    for t in cleaned:
        if len(t) > _MAX_TAG_LEN:
            raise ValueError(f"Each entry must be at most {_MAX_TAG_LEN} characters.")
    return cleaned


class MarketplaceSourcing(CampaignBaseModel):
    visibility: Literal[Visibility.MARKETPLACE] = Visibility.MARKETPLACE

    # Targeting
    platforms: list[Platform] = Field(..., min_length=1)
    tiers: list[InfluencerTier] = Field(..., min_length=1)
    min_engagement: Optional[float] = Field(None, ge=0, le=20)
    creator_gender: Optional[CreatorGender] = None
    creator_age_min: Optional[int] = Field(None, ge=13, le=80)
    creator_age_max: Optional[int] = Field(None, ge=13, le=80)
    creator_niches: list[str] = Field(default_factory=list)
    creator_locations: list[str] = Field(default_factory=list)

    # Application window + access (marketplace-only)
    application_start: date
    application_end: date
    join_type: JoinType

    @field_validator("platforms", "tiers")
    @classmethod
    def _unique(cls, v: list) -> list:
        if len(set(v)) != len(v):
            raise ValueError("Duplicate values are not allowed.")
        return v

    @field_validator("creator_niches", "creator_locations")
    @classmethod
    def _tags(cls, v: Optional[list[str]]) -> list[str]:
        return _clean_tags(v)

    @model_validator(mode="after")
    def _checks(self) -> "MarketplaceSourcing":
        if (
            self.creator_age_min is not None
            and self.creator_age_max is not None
            and self.creator_age_max < self.creator_age_min
        ):
            raise ValueError("creatorAgeMax must be ≥ creatorAgeMin.")
        if self.application_end < self.application_start:
            raise ValueError("applicationEnd must be on or after applicationStart.")
        return self


class RosterEntry(CampaignBaseModel):
    """One invited creator (BYOC). Per-creator rate overrides are optional."""

    email: EmailStr
    custom_rate: Optional[float] = Field(None, ge=0)
    custom_commission_pct: Optional[float] = Field(None, ge=0, le=100)
    welcome_note: Optional[str] = Field(None, max_length=2000)


class ByocSourcing(CampaignBaseModel):
    visibility: Literal[Visibility.INVITE_EXISTING] = Visibility.INVITE_EXISTING
    invite_roster: list[RosterEntry] = Field(..., min_length=1, max_length=500)
    welcome_message: Optional[str] = Field(None, max_length=2000)
    contract_bypass_acknowledged: bool = False

    @model_validator(mode="after")
    def _unique_emails(self) -> "ByocSourcing":
        emails = [r.email.lower() for r in self.invite_roster]
        if len(set(emails)) != len(emails):
            raise ValueError("Duplicate creator emails in the invite roster.")
        return self


SourcingConfig = Annotated[
    Union[MarketplaceSourcing, ByocSourcing],
    Field(discriminator="visibility"),
]