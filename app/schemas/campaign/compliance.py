"""Compliance / usage-rights block (spec §3 step 8).

Optional on the campaign as a whole: it is skipped when BYOC + contract bypass
(enforced at the top-level model). When present, the disclosure acknowledgement
must be true and at least one usage-rights scope must be chosen.
"""
from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from app.schemas.campaign.common import CampaignBaseModel
from app.schemas.campaign.enums import (
    EXCLUSIVITY_WINDOW_DAYS,
    UsageDuration,
    UsageRight,
)


class ComplianceConfig(CampaignBaseModel):
    usage_rights_scope: list[UsageRight] = Field(..., min_length=1)
    usage_rights_duration: UsageDuration
    exclusivity_window_days: int = Field(0, ge=0)
    compliance_acknowledged: bool

    @field_validator("usage_rights_scope")
    @classmethod
    def _unique(cls, v: list[UsageRight]) -> list[UsageRight]:
        if len(set(v)) != len(v):
            raise ValueError("Duplicate usage-rights scopes are not allowed.")
        return v

    @field_validator("exclusivity_window_days")
    @classmethod
    def _window(cls, v: int) -> int:
        if v not in EXCLUSIVITY_WINDOW_DAYS:
            allowed = ", ".join(str(x) for x in sorted(EXCLUSIVITY_WINDOW_DAYS))
            raise ValueError(f"exclusivityWindowDays must be one of: {allowed}.")
        return v

    @model_validator(mode="after")
    def _ack(self) -> "ComplianceConfig":
        if not self.compliance_acknowledged:
            raise ValueError("complianceAcknowledged must be true.")
        return self