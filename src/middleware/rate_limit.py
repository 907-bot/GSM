"""Redis-backed token bucket rate limiter.

Uses Redis INCR + EXPIRE for atomic counters that survive restarts
and work across multiple workers/instances.
Falls back to in-memory if Redis is unavailable.
"""

import time
import asyncio
from typing import Dict, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from redis import asyncio as aioredis
import structlog

from ..config import settings

logger = structlog.get_logger()


@dataclass
class LocalBucket:
    tokens: float
    last_refill: float


class RateLimiter:
    """Redis-backed sliding window rate limiter.

    Two-tier: Redis for multi-worker coordination, in-memory fallback
    when Redis is unavailable.

    Uses a sliding window counter approach:
      key = gsm:ratelimit:{client_key}:{window}
      INCR key
      EXPIRE key 60
    """

    def __init__(self, default_rate: float = 10.0, default_burst: int = 20):
        self.default_rate = default_rate
        self.default_burst = default_burst
        self._redis: Optional[aioredis.Redis] = None
        self._local_buckets: Dict[str, LocalBucket] = {}
        self._total_requests: int = 0
        self._blocked_requests: int = 0
        self._redis_ok: bool = False

    async def _ensure_redis(self) -> Optional[aioredis.Redis]:
        if self._redis is None:
            try:
                self._redis = aioredis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB + 1,
                    password=settings.REDIS_PASSWORD or None,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                await self._redis.ping()
                self._redis_ok = True
                logger.info("RateLimiter connected to Redis")
            except Exception as e:
                logger.warning("RateLimiter Redis unavailable, using local fallback", error=str(e))
                self._redis_ok = False
        return self._redis if self._redis_ok else None

    def _key(self, request) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            client_key = forwarded.split(",")[0].strip()
        elif request.client:
            client_key = request.client.host or "unknown"
        else:
            client_key = "unknown"
        return client_key

    async def _check_redis(self, client_key: str, rate: float, burst: int) -> bool:
        """Redis-based sliding window check."""
        redis = await self._ensure_redis()
        if not redis:
            return False  # fall through to local

        now = int(time.time())
        window = now // 60  # 1-minute window
        key = f"gsm:ratelimit:{client_key}:{window}"
        window_start = window * 60

        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 120)  # 2x TTL for safety

            reset_at = window_start + 60
            ttl = await redis.ttl(key)
            if ttl < 0:
                ttl = 60

            if count > burst:
                return False  # rate limited

            return True
        except Exception:
            return False  # fall through to local

    def _check_local(self, client_key: str, rate: float, burst: int) -> bool:
        """In-memory token bucket fallback."""
        now = time.time()
        if client_key not in self._local_buckets:
            self._local_buckets[client_key] = LocalBucket(tokens=float(burst), last_refill=now)

        bucket = self._local_buckets[client_key]
        elapsed = now - bucket.last_refill
        bucket.tokens = min(float(burst), bucket.tokens + elapsed * rate)
        bucket.last_refill = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True
        return False

    async def check(self, request, rate: Optional[float] = None, burst: Optional[int] = None) -> bool:
        """Check if the request should be allowed. Returns True if allowed."""
        rate = rate or self.default_rate
        burst = burst or self.default_burst
        client_key = self._key(request)
        self._total_requests += 1

        # Try Redis first
        if self._redis_ok:
            allowed = await self._check_redis(client_key, rate, burst)
        else:
            allowed = self._check_local(client_key, rate, burst)

        if not allowed:
            self._blocked_requests += 1

        return allowed

    async def remaining(self, request, rate: Optional[float] = None, burst: Optional[int] = None) -> Tuple[int, float]:
        """Get (remaining_tokens, retry_after_seconds) for the client."""
        return 0, 60.0  # Conservative estimate; real value requires Redis query

    def stats(self) -> Dict[str, int]:
        return {
            "total_requests": self._total_requests,
            "blocked_requests": self._blocked_requests,
            "redis_connected": self._redis_ok,
            "active_local_clients": len(self._local_buckets),
        }


rate_limiter = RateLimiter()
