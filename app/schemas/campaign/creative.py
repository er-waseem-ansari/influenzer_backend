"""Creative brief block (spec §3 step 6) + shared file-asset metadata.

File uploads arrive as metadata only (``{name,size,type}``); the actual binary
pipeline is out of scope (prompt) — the reference is stored as-is.
"""
from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from app.schemas.campaign.common import CampaignBaseModel
from app.schemas.campaign.enums import DeliverableType


class FileAsset(CampaignBaseModel):
    """Uploaded-file metadata. Wire to the upload pipeline separately."""

    name: str = Field(..., max_length=255)
    size: int = Field(..., ge=0)
    type: str = Field(..., max_length=100)


class Deliverable(CampaignBaseModel):
    type: DeliverableType
    quantity: int = Field(..., ge=1, le=20)


class CreativeBrief(CampaignBaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    campaign_description: str = Field(..., min_length=20, max_length=5000)
    deliverables: list[Deliverable] = Field(..., min_length=1)
    key_messaging: str = Field(..., min_length=10, max_length=5000)
    dos: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)
    cta: str = Field(..., min_length=2, max_length=300)
    media_assets: list[FileAsset] = Field(default_factory=list, max_length=20)
    pre_approval_required: bool = False

    @field_validator("deliverables")
    @classmethod
    def _unique_types(cls, v: list[Deliverable]) -> list[Deliverable]:
        types = [d.type for d in v]
        if len(set(types)) != len(types):
            raise ValueError("Each deliverable type may appear only once.")
        return v

    @field_validator("dos", "donts")
    @classmethod
    def _tags(cls, v: Optional[list[str]]) -> list[str]:
        if not v:
            return []
        return [t.strip() for t in v if t and t.strip()]