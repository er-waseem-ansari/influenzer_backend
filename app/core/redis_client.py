"""Process-wide Redis client (lazy singleton, connection-pooled).

The same client is intended for rate limiting now and metrics (clicks, installs)
later, so it lives in one place.
"""
import logging
from typing import Optional

import redis

from app.config import get_settings

LOGGER = logging.getLogger(__name__)
settings = get_settings()

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
        LOGGER.info("Initialized Redis client for %s", settings.REDIS_URL)
    return _client