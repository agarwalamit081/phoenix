"""Social data cache for caching social media results."""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class CacheEntry:
    """Cache entry with expiration."""

    def __init__(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 3600,
    ) -> None:
        """Initialize cache entry.

        Args:
            key: Cache key
            value: Cached value
            ttl_seconds: Time to live in seconds
        """
        self.key = key
        self.value = value
        self.created_at = datetime.now(timezone.utc)
        self.expires_at = self.created_at + timedelta(seconds=ttl_seconds)
        self.hits = 0
        self.last_accessed = None

    def is_expired(self) -> bool:
        """Check if entry is expired.

        Returns:
            True if expired
        """
        return datetime.now(timezone.utc) >= self.expires_at

    def touch(self) -> None:
        """Update access time."""
        self.last_accessed = datetime.now(timezone.utc)
        self.hits += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "key": self.key,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "hits": self.hits,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "is_expired": self.is_expired(),
        }


class SocialCache:
    """Cache for social media data."""

    def __init__(
        self,
        default_ttl_seconds: int = 3600,
        max_entries: int = 1000,
    ) -> None:
        """Initialize social cache.

        Args:
            default_ttl_seconds: Default TTL in seconds
            max_entries: Maximum cache entries
        """
        self.default_ttl_seconds = default_ttl_seconds
        self.max_entries = max_entries
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    def _generate_key(
        self,
        prefix: str,
        **kwargs: Any,
    ) -> str:
        """Generate cache key from parameters.

        Args:
            prefix: Key prefix
            **kwargs: Key parameters

        Returns:
            Cache key
        """
        # Sort kwargs for consistent key generation
        sorted_items = sorted(kwargs.items())

        # Create key string
        key_parts = [prefix]
        for k, v in sorted_items:
            if v is not None:
                key_parts.append(f"{k}={v}")

        key_string = ":".join(key_parts)

        # Hash for shorter keys
        return hashlib.md5(key_string.encode()).hexdigest()

    async def get(
        self,
        key: str,
    ) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        async with self._lock:
            entry = self._cache.get(key)

            if not entry:
                return None

            if entry.is_expired():
                # Remove expired entry
                del self._cache[key]
                return None

            entry.touch()
            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional TTL override
        """
        async with self._lock:
            ttl = ttl_seconds or self.default_ttl_seconds

            # Check cache size
            if len(self._cache) >= self.max_entries:
                await self._evict_lru()

            self._cache[key] = CacheEntry(key, value, ttl)

    async def delete(
        self,
        key: str,
    ) -> bool:
        """Delete entry from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    async def cleanup_expired(self) -> int:
        """Remove expired entries.

        Returns:
            Number of entries removed
        """
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    async def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find LRU entry
        lru_key = None
        lru_time = None

        for key, entry in self._cache.items():
            accessed = entry.last_accessed or entry.created_at

            if lru_time is None or accessed < lru_time:
                lru_time = accessed
                lru_key = key

        if lru_key:
            del self._cache[lru_key]

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        async with self._lock:
            total_hits = sum(e.hits for e in self._cache.values())

            return {
                "total_entries": len(self._cache),
                "max_entries": self.max_entries,
                "total_hits": total_hits,
                "expired_entries": sum(
                    1 for e in self._cache.values()
                    if e.is_expired()
                ),
                "default_ttl_seconds": self.default_ttl_seconds,
            }

    async def get_entries(self) -> list[dict[str, Any]]:
        """Get all cache entries.

        Returns:
            List of cache entries
        """
        async with self._lock:
            return [entry.to_dict() for entry in self._cache.values()]


class SocialSearchCache(SocialCache):
    """Cache specifically for social search results."""

    def key_for_search(
        self,
        query: str,
        location: str | None = None,
        platform: str | None = None,
    ) -> str:
        """Generate cache key for search.

        Args:
            query: Search query
            location: Optional location
            platform: Optional platform

        Returns:
            Cache key
        """
        return self._generate_key(
            "search",
            query=query,
            location=location,
            platform=platform,
        )

    async def get_search_results(
        self,
        query: str,
        location: str | None = None,
        platform: str | None = None,
    ) -> Any | None:
        """Get cached search results.

        Args:
            query: Search query
            location: Optional location
            platform: Optional platform

        Returns:
            Cached results or None
        """
        key = self.key_for_search(query, location, platform)
        return await self.get(key)

    async def set_search_results(
        self,
        query: str,
        results: Any,
        location: str | None = None,
        platform: str | None = None,
        ttl_seconds: int = 1800,  # 30 minutes default
    ) -> None:
        """Cache search results.

        Args:
            query: Search query
            results: Results to cache
            location: Optional location
            platform: Optional platform
            ttl_seconds: TTL in seconds
        """
        key = self.key_for_search(query, location, platform)
        await self.set(key, results, ttl_seconds)


class SentimentCache(SocialCache):
    """Cache for sentiment analysis results."""

    def key_for_sentiment(
        self,
        text: str,
    ) -> str:
        """Generate cache key for sentiment analysis.

        Args:
            text: Text to analyze

        Returns:
            Cache key
        """
        # Use text hash for key
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return self._generate_key("sentiment", text_hash=text_hash)

    async def get_sentiment(
        self,
        text: str,
    ) -> Any | None:
        """Get cached sentiment analysis.

        Args:
            text: Text

        Returns:
            Cached sentiment or None
        """
        key = self.key_for_sentiment(text)
        return await self.get(key)

    async def set_sentiment(
        self,
        text: str,
        sentiment: Any,
        ttl_seconds: int = 86400,  # 24 hours
    ) -> None:
        """Cache sentiment analysis.

        Args:
            text: Text
            sentiment: Sentiment analysis result
            ttl_seconds: TTL in seconds
        """
        key = self.key_for_sentiment(text)
        await self.set(key, sentiment, ttl_seconds)


class InsightsCache(SocialCache):
    """Cache for extracted insights."""

    def key_for_insights(
        self,
        location: str | None = None,
        days: int = 7,
    ) -> str:
        """Generate cache key for insights.

        Args:
            location: Optional location
            days: Number of days

        Returns:
            Cache key
        """
        return self._generate_key(
            "insights",
            location=location,
            days=days,
        )

    async def get_insights(
        self,
        location: str | None = None,
        days: int = 7,
    ) -> Any | None:
        """Get cached insights.

        Args:
            location: Optional location
            days: Number of days

        Returns:
            Cached insights or None
        """
        key = self.key_for_insights(location, days)
        return await self.get(key)

    async def set_insights(
        self,
        insights: Any,
        location: str | None = None,
        days: int = 7,
        ttl_seconds: int = 3600,  # 1 hour
    ) -> None:
        """Cache insights.

        Args:
            insights: Insights to cache
            location: Optional location
            days: Number of days
            ttl_seconds: TTL in seconds
        """
        key = self.key_for_insights(location, days)
        await self.set(key, insights, ttl_seconds)


# Global instances
social_cache = SocialCache()
search_cache = SocialSearchCache()
sentiment_cache = SentimentCache()
insights_cache = InsightsCache()


def get_social_cache() -> SocialCache:
    """Get social cache instance.

    Returns:
        Social cache instance
    """
    return social_cache


def get_search_cache() -> SocialSearchCache:
    """Get search cache instance.

    Returns:
        Search cache instance
    """
    return search_cache


def get_sentiment_cache() -> SentimentCache:
    """Get sentiment cache instance.

    Returns:
        Sentiment cache instance
    """
    return sentiment_cache


def get_insights_cache() -> InsightsCache:
    """Get insights cache instance.

    Returns:
        Insights cache instance
    """
    return insights_cache
