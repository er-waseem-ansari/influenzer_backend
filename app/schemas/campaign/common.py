"""Shared base model & helpers for campaign schemas.

Mirrors the brand-profile convention: camelCase on the wire, snake_case in
Python, enums kept as enum objects (serialised to their UPPERCASE value with
``model_dump(mode="json")``).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, TypeAdapter, HttpUrl
from pydantic.alias_generators import to_camel

URL_MAX_LENGTH = 500
_URL_ADAPTER = TypeAdapter(HttpUrl)


def validate_http_url(value: str) -> str:
    """Validate an http(s) URL, returning the original string (no normalisation)."""
    value = value.strip()
    if not value:
        raise ValueError("URL must not be empty.")
    if len(value) > URL_MAX_LENGTH:
        raise ValueError(f"URL must be at most {URL_MAX_LENGTH} characters.")
    _URL_ADAPTER.validate_python(value)  # raises on bad scheme/host
    return value


class CampaignBaseModel(BaseModel):
    """camelCase aliases on the wire, snake_case in Python."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,    # also accept snake_case keys on input
        from_attributes=True,
        str_strip_whitespace=True,
        use_enum_values=False,
        extra="forbid",           # reject unknown keys (catches frontend cruft)
    )