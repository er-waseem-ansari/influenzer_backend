"""Redis-backed rate limiting.

Uses the *sliding-window-counter* algorithm. Each identifier keeps two adjacent
fixed-window tallies (current + previous) in a single Redis hash; the rate is
estimated by weighting the previous window by how much of it still overlaps the
trailing `window_seconds`:

    estimate = previous_count * (1 - elapsed/window) + current_count

This smooths the burst-at-the-boundary problem of a plain fixed window (which
can admit up to 2x the limit across a boundary) while staying O(1) in memory —
two counters per key, no per-request log. The read-decide-write step is one
atomic Lua script, and Redis server time (`TIME`) is the single clock, so app
servers can't disagree about window boundaries. On a Redis outage, behavior
follows `RATE_LIMIT_FAIL_OPEN`.
"""
import logging
from typing import Callable

from fastapi import Request
from redis.exceptions import RedisError

from app.config import get_settings
from app.core.exceptions import ServiceUnavailableException, TooManyRequestsException
from app.core.redis_client import get_redis

LOGGER = logging.getLogger(__name__)
settings = get_settings()

# Sliding-window-counter limiter, evaluated atomically server-side.
#   KEYS[1] = state key (hash: w=window index, cc=current count, pc=previous count)
#   ARGV[1] = window length (seconds)   ARGV[2] = max requests per window
# Returns {allowed (1|0), retry_after_seconds, weighted_count}. A denied request
# is NOT counted, so hammering a blocked key cannot extend the block.
_SLIDING_WINDOW_LUA = """
local window = tonumber(ARGV[1])
local limit  = tonumber(ARGV[2])

local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
local idx = math.floor(now / window)
local elapsed = now - idx * window
local weight = (window - elapsed) / window

local state = redis.call('HMGET', KEYS[1], 'w', 'cc', 'pc')
local sw = tonumber(state[1])
local cc = tonumber(state[2]) or 0
local pc = tonumber(state[3]) or 0

if sw == nil then
    cc = 0; pc = 0
elseif idx == sw then
    -- same window: counts stand
elseif idx == sw + 1 then
    pc = cc; cc = 0          -- rolled forward exactly one window
else
    pc = 0; cc = 0           -- idle for >= 2 windows: state is stale
end

local estimated = pc * weight + cc
local ttl_ms = (window * 2 + 1) * 1000

if estimated + 1 > limit then
    -- Denied: estimate when decay drops the weighted count back under the limit.
    local retry
    if pc > 0 then
        local target_weight = (limit - 1 - cc) / pc
        if target_weight > 0 then
            retry = math.ceil(window * (1 - target_weight) - elapsed)
        else
            retry = math.ceil(window - elapsed)   -- current count alone is too high
        end
    else
        retry = math.ceil(window - elapsed)
    end
    if retry < 1 then retry = 1 end
    redis.call('PEXPIRE', KEYS[1], ttl_ms)
    return {0, retry, math.floor(estimated)}
end

cc = cc + 1
redis.call('HSET', KEYS[1], 'w', idx, 'cc', cc, 'pc', pc)
redis.call('PEXPIRE', KEYS[1], ttl_ms)
return {1, 0, math.floor(estimated + 1)}
"""

_script = None


def get_client_ip(request: Request) -> str:
    """Best-effort client IP. Uses the first X-Forwarded-For hop when trusted
    (i.e. behind a known reverse proxy); otherwise the socket peer address."""
    if settings.TRUST_FORWARDED_FOR:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def enforce_rate_limit(*, scope: str, identifier: str, limit: int, window_seconds: int) -> None:
    """Count one attempt for (scope, identifier); raise if over `limit`.

    Raises:
        TooManyRequestsException (429) when the window limit is exceeded, with
            `retryAfterSeconds` reported in the response body.
        ServiceUnavailableException (503) when Redis is unreachable and
            RATE_LIMIT_FAIL_OPEN is False.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    key = f"ratelimit:{scope}:{identifier}"
    try:
        client = get_redis()
        global _script
        if _script is None:
            _script = client.register_script(_SLIDING_WINDOW_LUA)
        allowed, retry_after, count = _script(keys=[key], args=[window_seconds, limit])
    except RedisError as exc:
        LOGGER.error("Rate limiter unavailable (scope=%s): %s", scope, exc)
        if settings.RATE_LIMIT_FAIL_OPEN:
            return  # availability-first: allow the request through
        raise ServiceUnavailableException(
            detail="Rate limiting is temporarily unavailable. Please try again shortly."
        )

    if not allowed:
        retry_after = retry_after if isinstance(retry_after, int) and retry_after > 0 else window_seconds
        LOGGER.warning(
            "Rate limit exceeded: scope=%s id=%s ~count=%s/%s", scope, identifier, count, limit
        )
        raise TooManyRequestsException(
            detail=f"Rate limit exceeded. Try again in {retry_after} second(s).",
            errors={"retryAfterSeconds": retry_after},
        )


def rate_limit_by_ip(
    scope: str, *, limit: int, window_seconds: int
) -> Callable[[Request], None]:
    """Build a FastAPI dependency that rate-limits a route by client IP.

    Declare it at the route/router level so throttling stays a declarative,
    cross-cutting concern instead of leaking into controllers or services:

        @router.post("/login", dependencies=[Depends(
            rate_limit_by_ip("brand_login", limit=10, window_seconds=300))])

    Counting runs against the same Redis sliding-window counter as everything else.
    """
    def _dependency(request: Request) -> None:
        enforce_rate_limit(
            scope=scope,
            identifier=get_client_ip(request),
            limit=limit,
            window_seconds=window_seconds,
        )

    return _dependency