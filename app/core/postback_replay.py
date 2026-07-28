"""Replay protection via a Redis nonce store (optional hardening).

The timestamp window already bounds how long a captured signed request *could* be
replayed; this closes the remaining gap by rejecting reuse of the same signature
**within** that window, giving full replay immunity.

Mechanism: ``SET key value NX EX ttl`` — atomic "claim if absent". The first time
we see a signature we claim it with TTL = the timestamp window; a replay finds the
key already set and is rejected. TTL = window means the key can't outlive the
period in which the signature is even valid, so the store stays small and
self-cleaning.

**Graceful degradation:** this is defence-in-depth, not the primary auth. If Redis
is unreachable we fail **open on this check only** (log + allow) — the HMAC,
timestamp window, and ``order_id`` idempotency still protect the request. A Redis
outage must never block a brand's legitimate conversions.
"""
from __future__ import annotations

import logging

from redis.exceptions import RedisError

from app.config import get_settings
from app.core.redis_client import get_redis

LOGGER = logging.getLogger(__name__)
settings = get_settings()

_KEY_PREFIX = "postback:nonce:"


def claim_nonce(integration_public_id: str, signature: str, ttl_seconds: int) -> bool:
    """Atomically claim a one-time nonce for this request.

    Returns ``True`` if the nonce was unused (request may proceed), ``False`` if
    it was already seen (replay → reject). Scoped per integration so two
    integrations can't collide. On Redis error, returns ``True`` (fail-open;
    see module docstring).
    """
    if not settings.POSTBACK_REPLAY_PROTECTION_ENABLED:
        return True

    key = f"{_KEY_PREFIX}{integration_public_id}:{signature}"
    try:
        # nx=True -> only set if absent; returns True on first claim, None on reuse.
        claimed = get_redis().set(key, "1", nx=True, ex=ttl_seconds)
        return bool(claimed)
    except RedisError as exc:
        LOGGER.error("Replay nonce store unavailable; failing open: %s", exc)
        return True