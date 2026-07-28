"""Schemas for brand-facing postback integration management.

The plaintext signing ``secret`` is returned **only** at create/rotate time
(``IntegrationSecretResponse``) — it is never persisted in plaintext and never
echoed by any read endpoint (``IntegrationResponse`` omits it).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntegrationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    label: Optional[str] = Field(None, max_length=120)


class IntegrationResponse(BaseModel):
    """Safe representation — no secret."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str               # the X-Inflz-Integration header value
    brand_id: UUID
    status: str
    label: Optional[str] = None
    rotated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class IntegrationSecretResponse(BaseModel):
    """Returned once, at create/rotate. Persist the secret on your side now — it
    cannot be retrieved again."""

    integration: IntegrationResponse
    secret: str
    message: str = (
        "Store this signing secret securely now. It is shown only once and cannot "
        "be retrieved later; rotate to obtain a new one."
    )