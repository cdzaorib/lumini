"""Fixed-window counters in Redis for public endpoints.

Keys hold a hash of the identifier, never the identifier itself. When Redis is missing or fails
the request is allowed: limits protect provider quotas, while link tokens are unguessable.
"""

import hashlib
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


async def allow(
    redis: Redis | None, scope: str, identifier: str, *, limit: int, window_seconds: int
) -> bool:
    if redis is None:
        return True
    key = f"lumini:rl:{scope}:{hashlib.sha256(identifier.encode()).hexdigest()[:32]}"
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            count, _ = await pipe.execute()
    except RedisError:
        logger.warning("rate limit unavailable for %s", scope)
        return True
    return int(count) <= limit
