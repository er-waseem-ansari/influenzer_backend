"""FastAPI dependency that authenticates a conversion postback.

This is the gate in front of ``POST /collect/event``. It ties the pieces together
in a strict, fail-closed order and hands the route a verified, raw body to parse:

    raw body  →  integration lookup  →  status active  →  rate limit
              →  timestamp window  →  HMAC signature  →  replay nonce

Security posture:
* **Raw-body first** — we read ``await request.body()`` *before* any JSON parsing
  so the signature is checked against the exact bytes the brand signed.
* **Generic failure** — every authentication/integrity/freshness failure raises
  the *same* generic ``401`` (``UnauthorizedException``). We never reveal which
  check failed or whether the integration exists (no enumeration oracle).
* **Fail-closed** — any unexpected error → reject. The only deliberate fail-open
  is the Redis nonce check (defence-in-depth; see ``postback_replay``).
* **429** for the per-integration rate limit (distinct from auth failures, since
  the brand's retry logic treats it differently).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import UnauthorizedException
from app.core.postback_replay import claim_nonce
from app.core.postback_signing import (
    HEADER_INTEGRATION,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    timestamp_within_tolerance,
    verify_signature,
)
from app.core.rate_limit import enforce_rate_limit
from app.database import get_db
from app.models.integration import IntegrationStatus, PostbackIntegration

LOGGER = logging.getLogger(__name__)
settings = get_settings()

# One generic message for every auth/integrity/freshness failure — never leaks
# which check failed or whether the integration exists.
_GENERIC_AUTH_ERROR = "Postback authentication failed."

# Headers we persist for audit (never the signature; never any secret).
_AUDIT_HEADERS = (HEADER_INTEGRATION, HEADER_TIMESTAMP, "content-type", "user-agent")


@dataclass
class VerifiedPostback:
    """Result of a passed authentication: the owning integration + verified bytes."""

    integration: PostbackIntegration
    raw_body: bytes
    audit_headers: dict[str, str]


def _reject() -> UnauthorizedException:
    return UnauthorizedException(_GENERIC_AUTH_ERROR)


async def verify_postback(
    request: Request,
    db: Session = Depends(get_db),
) -> VerifiedPostback:
    """Authenticate the request; return a ``VerifiedPostback`` or raise 401/429."""
    # 1. Raw body BEFORE any parsing — this is what the signature covers.
    raw_body = await request.body()

    integration_id = request.headers.get(HEADER_INTEGRATION)
    timestamp = request.headers.get(HEADER_TIMESTAMP)
    signature = request.headers.get(HEADER_SIGNATURE)
    if not integration_id or not timestamp or not signature:
        raise _reject()

    # 2. Resolve the integration (must exist + be active).
    integration = (
        db.query(PostbackIntegration)
        .filter(PostbackIntegration.public_id == integration_id)
        .first()
    )
    if integration is None or integration.status != IntegrationStatus.ACTIVE:
        raise _reject()

    # 3. Per-integration flood protection (429, not 401).
    enforce_rate_limit(
        scope="postback",
        identifier=integration.public_id,
        limit=settings.POSTBACK_RATE_LIMIT_MAX,
        window_seconds=settings.POSTBACK_RATE_LIMIT_WINDOW_SECONDS,
    )

    # 4. Freshness: bounded clock skew (rejects stale and future timestamps).
    if not timestamp_within_tolerance(timestamp, settings.POSTBACK_TIMESTAMP_TOLERANCE_SECONDS):
        raise _reject()

    # 5. Integrity + authenticity: constant-time HMAC over the raw bytes.
    secret = integration.secret  # decrypted in-process by EncryptedString
    if not secret or not verify_signature(secret, timestamp, raw_body, signature):
        raise _reject()

    # 6. Replay immunity: claim a one-time nonce (Redis; fail-open on outage).
    if not claim_nonce(
        integration.public_id, signature, settings.POSTBACK_TIMESTAMP_TOLERANCE_SECONDS
    ):
        raise _reject()

    audit_headers = {
        k: v for k, v in request.headers.items() if k.lower() in _AUDIT_HEADERS
    }
    return VerifiedPostback(
        integration=integration, raw_body=raw_body, audit_headers=audit_headers
    )