"""HMAC request signing — the pure cryptographic primitive.

No I/O, no DB, no framework: just the signing/verification maths, so it can be
unit-tested exhaustively and reasoned about in isolation. Everything stateful
(integration lookup, replay store, rate limit) lives in ``postback_security``.

Scheme (must match what the brand computes):

    signature = hex( HMAC_SHA256(secret, f"{timestamp}.{raw_body}") )

* ``raw_body`` is the **exact request body bytes** — never re-serialized JSON.
* the secret is the shared per-integration secret string, used as UTF-8 key bytes.
* comparison is **constant-time** (``hmac.compare_digest``) to defeat timing
  attacks — we never early-return on the first differing byte.
"""
from __future__ import annotations

import hashlib
import hmac
import time

# Canonical header names (single source of truth; no magic strings elsewhere).
HEADER_INTEGRATION = "X-Inflz-Integration"
HEADER_TIMESTAMP = "X-Inflz-Timestamp"
HEADER_SIGNATURE = "X-Inflz-Signature"

_SEPARATOR = b"."


def _signing_input(timestamp: str, raw_body: bytes) -> bytes:
    """The exact byte string that gets HMAC'd: ``f"{timestamp}.{raw_body}"``."""
    return timestamp.encode("utf-8") + _SEPARATOR + raw_body


def compute_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    """Return the hex HMAC-SHA256 for ``(timestamp, raw_body)`` under ``secret``."""
    return hmac.new(
        secret.encode("utf-8"),
        _signing_input(timestamp, raw_body),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(secret: str, timestamp: str, raw_body: bytes, provided: str) -> bool:
    """Constant-time check of a provided hex signature. Never raises; any bad
    input (including a malformed ``provided``) returns ``False`` — fail-closed."""
    if not provided:
        return False
    expected = compute_signature(secret, timestamp, raw_body)
    # compare_digest is constant-time over equal-length inputs and safe for
    # unequal lengths; it does not early-return on the first mismatching byte.
    return hmac.compare_digest(expected, provided.strip())


def timestamp_within_tolerance(timestamp: str, tolerance_seconds: int, *, now: float | None = None) -> bool:
    """True iff ``timestamp`` (unix seconds) is within ±tolerance of now.

    Rejects stale *and* future timestamps (clock-skew bounded both ways), which
    caps how long a captured signed request stays replayable. Non-numeric input
    returns ``False``.
    """
    try:
        ts = float(timestamp)
    except (TypeError, ValueError):
        return False
    current = time.time() if now is None else now
    return abs(current - ts) <= tolerance_seconds