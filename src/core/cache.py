"""Redis-based caching layer for expensive operations."""

import json
import hashlib
import functools
from typing import Any, Callable, TypeVar, ParamSpec

from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from src.config.logging import logger
from src.config.settings import settings

# Type variables for generic decorator
P = ParamSpec("P")
R = TypeVar("R")

# Redis connection pool (shared with session.py)
_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    """Get or create Redis connection pool.

    Returns:
        Redis connection pool
    """
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=settings.redis_pool_size,
        )
    return _pool


async def get(key: str) -> Any | None:
    """Get value from cache.

    Args:
        key: Cache key

    Returns:
        Cached value or None if not found
    """
    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            data = await redis.get(key)
            if data:
                return json.loads(data)
            return None
    except Exception as e:
        logger.error(f"Cache get failed for key {key}: {e}")
        return None


async def set(key: str, value: Any, ttl: int = 3600) -> None:
    """Set value in cache.

    Args:
        key: Cache key
        value: Value to cache (must be JSON-serializable)
        ttl: Time to live in seconds (default: 1 hour)
    """
    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            await redis.setex(key, ttl, json.dumps(value))
            logger.debug(f"Cached key {key} with TTL {ttl}s")
    except Exception as e:
        logger.error(f"Cache set failed for key {key}: {e}")


async def delete(key: str) -> None:
    """Delete value from cache.

    Args:
        key: Cache key
    """
    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            await redis.delete(key)
            logger.debug(f"Deleted cache key {key}")
    except Exception as e:
        logger.error(f"Cache delete failed for key {key}: {e}")


async def delete_pattern(pattern: str) -> int:
    """Delete all keys matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "poi:*")

    Returns:
        Number of keys deleted
    """
    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            keys = await redis.keys(pattern)
            if keys:
                return await redis.delete(*keys)
            return 0
    except Exception as e:
        logger.error(f"Cache delete pattern failed for {pattern}: {e}")
        return 0


async def exists(key: str) -> bool:
    """Check if key exists in cache.

    Args:
        key: Cache key

    Returns:
        True if key exists
    """
    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            return await redis.exists(key) > 0
    except Exception as e:
        logger.error(f"Cache exists check failed for key {key}: {e}")
        return False


def cache_result(
    ttl: int = 3600,
    key_prefix: str = "",
    key_parts: list[str] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to cache function results in Redis.

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache keys
        key_parts: List of argument names to include in cache key (default: all args)

    Returns:
        Decorated function with caching

    Example:
        ```python
        @cache_result(ttl=1800, key_prefix="poi", key_parts=["latitude", "longitude"])
        async def get_nearby_pois(latitude: float, longitude: float, radius: float = 5.0):
            ... expensive operation ...
        ```
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Generate cache key
            key_parts_to_use = key_parts or list(kwargs.keys()) if kwargs else []
            key_data = []

            if key_parts_to_use:
                # Use specified key parts
                for part in key_parts_to_use:
                    if part in kwargs:
                        key_data.append(str(kwargs[part]))
            else:
                # Use all arguments
                key_data = [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]

            # Create hash of key data for consistent length
            key_hash = hashlib.md5(":".join(key_data).encode()).hexdigest()[:12]
            cache_key = f"{key_prefix}:{func.__name__}:{key_hash}" if key_prefix else f"{func.__name__}:{key_hash}"

            # Try to get from cache
            cached = await get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for key {cache_key}")
                return cached

            # Call function and cache result
            result = await func(*args, **kwargs)
            await set(cache_key, result, ttl)
            logger.debug(f"Cached result for key {cache_key}")

            return result

        return wrapper

    return decorator


def cache_invalidate(*patterns: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that invalidates cache patterns after function execution.

    Args:
        *patterns: Cache key patterns to invalidate

    Returns:
        Decorated function

    Example:
        ```python
        @cache_invalidate("poi:*", "user:*")
        async def update_poi_data(poi_id: str, data: dict):
            ... update operation ...
        ```
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            result = await func(*args, **kwargs)

            # Invalidate patterns
            for pattern in patterns:
                await delete_pattern(pattern)
                logger.debug(f"Invalidated cache pattern {pattern}")

            return result

        return wrapper

    return decorator


async def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics from Redis.

    Returns:
        Dictionary with cache stats
    """
    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            info = await redis.info("stats")
            keyspace = await redis.info("keyspace")
            return {
                "total_keys": sum(int(v.split("=")[1] if "=" in v else 0) for v in keyspace.values()),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": info.get("keyspace_hits", 0) / max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0)),
            }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {
            "total_keys": 0,
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
        }


async def clear_cache() -> int:
    """Clear all cache keys (excluding sessions).

    Returns:
        Number of keys deleted
    """
    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            # Get all keys
            all_keys = await redis.keys("*")

            # Exclude session-related keys
            excluded_patterns = ["session:", "checkpoint:", "user_state:"]
            cache_keys = [
                key for key in all_keys
                if not any(pattern in key for pattern in excluded_patterns)
            ]

            if cache_keys:
                return await redis.delete(*cache_keys)
            return 0
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return 0


class CacheLock:
    """Distributed lock using Redis."""

    def __init__(self, key: str, ttl: int = 30):
        """Initialize cache lock.

        Args:
            key: Lock key
            ttl: Lock TTL in seconds
        """
        self.key = f"lock:{key}"
        self.ttl = ttl
        self._redis: Redis | None = None
        self._acquired = False

    async def __aenter__(self) -> "CacheLock":
        """Acquire lock."""
        self._redis = Redis(connection_pool=get_redis_pool())
        acquired = await self._redis.set(
            self.key,
            "locked",
            nx=True,
            ex=self.ttl,
        )
        self._acquired = bool(acquired)
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Release lock."""
        if self._acquired and self._redis:
            await self._redis.delete(self.key)
            await self._redis.close()
        self._acquired = False

    @property
    def acquired(self) -> bool:
        """Check if lock was acquired."""
        return self._acquired
