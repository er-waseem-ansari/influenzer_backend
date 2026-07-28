"""Target-audience block (spec §3 step 4). Collected for both flows."""
from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator, model_validator

from app.schemas.campaign.common import CampaignBaseModel
from app.schemas.campaign.enums import AudienceGender


class AudienceTargeting(CampaignBaseModel):
    audience_age_min: Optional[int] = Field(None, ge=13, le=65)
    audience_age_max: Optional[int] = Field(None, ge=13, le=65)
    audience_gender: Optional[AudienceGender] = None
    audience_interests: list[str] = Field(default_factory=list)

    @field_validator("audience_interests")
    @classmethod
    def _tags(cls, v: Optional[list[str]]) -> list[str]:
        if not v:
            return []
        cleaned = [t.strip() for t in v if t and t.strip()]
        for t in cleaned:
            if len(t) > 100:
                raise ValueError("Each interest must be at most 100 characters.")
        return cleaned

    @model_validator(mode="after")
    def _age_order(self) -> "AudienceTargeting":
        if (
            self.audience_age_min is not None
            and self.audience_age_max is not None
            and self.audience_age_max < self.audience_age_min
        ):
            raise ValueError("audienceAgeMax must be ≥ audienceAgeMin.")
        return self