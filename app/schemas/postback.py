"""Public wire contract for ``POST /collect/event``.

The brand sends **snake_case** JSON (matching the spec example), so unlike the
campaign schemas there is no camelCase aliasing here. The body is a discriminated
union on ``event_type`` so new event kinds (e.g. ``signup``) are a new variant,
not a new route.

Note on attribution keys: ``click_id`` and ``coupon_code`` are each optional and
we deliberately do **not** require at least one at the schema layer — a payload
with neither is still accepted and stored UNATTRIBUTED (the domain layer decides
credit, never the parser). What we reject here (``400``) is genuinely malformed
data: missing ``order_id``/``occurred_at``, or a purchase without ``value`` /
``currency``.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator


class PostbackEventType(str, Enum):
    PURCHASE = "purchase"
    REFUND = "refund"


class _PostbackBase(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",          # reject unknown top-level keys (catch integrator typos)
        use_enum_values=False,
    )

    order_id: str = Field(..., min_length=1, max_length=128)
    click_id: Optional[str] = Field(None, max_length=128)
    coupon_code: Optional[str] = Field(None, max_length=64)
    status: Optional[str] = Field(None, max_length=30)
    occurred_at: datetime
    meta: dict[str, Any] = Field(default_factory=dict)


class PurchaseEvent(_PostbackBase):
    event_type: Literal[PostbackEventType.PURCHASE] = PostbackEventType.PURCHASE
    value: float = Field(..., gt=0)        # required + positive for a purchase
    currency: str = Field(..., min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        v = v.upper()
        if not v.isalpha():
            raise ValueError("currency must be a 3-letter ISO code.")
        return v


class RefundEvent(_PostbackBase):
    event_type: Literal[PostbackEventType.REFUND] = PostbackEventType.REFUND
    # Partial refunds carry a value; a full refund may omit it (reverse in full).
    value: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.upper()
        if not v.isalpha():
            raise ValueError("currency must be a 3-letter ISO code.")
        return v


PostbackEvent = Annotated[
    Union[PurchaseEvent, RefundEvent],
    Field(discriminator="event_type"),
]

# Validate raw bytes directly (raw-body signing requires we parse the verified
# bytes ourselves rather than let FastAPI bind the body before signature check).
POSTBACK_EVENT_ADAPTER: TypeAdapter[PostbackEvent] = TypeAdapter(PostbackEvent)


class PostbackAccepted(BaseModel):
    """Response for an accepted event (also returned for duplicates)."""

    status: str = "accepted"
    order_id: str
    event_type: PostbackEventType
    duplicate: bool = False
    attributed: bool = False
    attribution_key: Optional[str] = None        # CLICK_ID | COUPON | null
    confidence: Optional[str] = None             # CODE_ONLY | null
    flagged_for_review: bool = False
    campaign_id: Optional[UUID] = None
    influencer_id: Optional[UUID] = None