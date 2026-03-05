"""Translation cache for storing and retrieving translations."""

import asyncio
import hashlib
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from src.translation.engine import LanguageCode, TranslationResult

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry for translations."""

    key: str
    translation: str
    source_lang: LanguageCode
    target_lang: LanguageCode
    confidence: float
    cached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    hits: int = 0
    ttl_seconds: int = 86400  # 24 hours default

    def is_expired(self) -> bool:
        """Check if entry is expired.

        Returns:
            True if expired
        """
        return (datetime.now(timezone.utc) - self.cached_at).total_seconds() >= self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "key": self.key,
            "translation": self.translation,
            "source_lang": self.source_lang.value,
            "target_lang": self.target_lang.value,
            "confidence": self.confidence,
            "cached_at": self.cached_at.isoformat(),
            "hits": self.hits,
            "ttl_seconds": self.ttl_seconds,
        }


class TranslationLRUCache:
    """LRU cache for translations."""

    def __init__(
        self,
        max_size: int = 10000,
        default_ttl_seconds: int = 86400,
    ) -> None:
        """Initialize LRU cache.

        Args:
            max_size: Maximum cache size
            default_ttl_seconds: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl_seconds = default_ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
        }

    def _generate_key(
        self,
        text: str,
        target_lang: LanguageCode,
        source_lang: LanguageCode | None = None,
    ) -> str:
        """Generate cache key.

        Args:
            text: Source text
            target_lang: Target language
            source_lang: Optional source language

        Returns:
            Cache key
        """
        # Create hash of text + languages
        data = {
            "text": text,
            "target": target_lang.value,
            "source": source_lang.value if source_lang else "auto",
        }
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()[:32]

    async def get(
        self,
        text: str,
        target_lang: LanguageCode,
        source_lang: LanguageCode | None = None,
    ) -> CacheEntry | None:
        """Get translation from cache.

        Args:
            text: Source text
            target_lang: Target language
            source_lang: Optional source language

        Returns:
            Cache entry or None
        """
        key = self._generate_key(text, target_lang, source_lang)

        if key not in self._cache:
            self._stats["misses"] += 1
            return None

        entry = self._cache[key]

        # Check if expired
        if entry.is_expired():
            del self._cache[key]
            self._stats["expirations"] += 1
            self._stats["misses"] += 1
            return None

        # Update access (move to end for LRU)
        self._cache.move_to_end(key)
        entry.hits += 1
        self._stats["hits"] += 1

        return entry

    async def set(
        self,
        text: str,
        translation: str,
        target_lang: LanguageCode,
        source_lang: LanguageCode,
        confidence: float,
        ttl_seconds: int | None = None,
    ) -> CacheEntry:
        """Set translation in cache.

        Args:
            text: Source text
            translation: Translated text
            target_lang: Target language
            source_lang: Source language
            confidence: Translation confidence
            ttl_seconds: Optional TTL

        Returns:
            Cache entry
        """
        key = self._generate_key(text, target_lang, source_lang)
        ttl = ttl_seconds or self.default_ttl_seconds

        # Evict if at capacity
        if key not in self._cache and len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)
            self._stats["evictions"] += 1

        entry = CacheEntry(
            key=key,
            translation=translation,
            source_lang=source_lang,
            target_lang=target_lang,
            confidence=confidence,
            ttl_seconds=ttl,
        )

        self._cache[key] = entry
        self._cache.move_to_end(key)

        return entry

    async def delete(
        self,
        text: str,
        target_lang: LanguageCode,
        source_lang: LanguageCode | None = None,
    ) -> bool:
        """Delete translation from cache.

        Args:
            text: Source text
            target_lang: Target language
            source_lang: Optional source language

        Returns:
            True if deleted
        """
        key = self._generate_key(text, target_lang, source_lang)

        if key in self._cache:
            del self._cache[key]
            return True

        return False

    async def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
        }

    async def cleanup_expired(self) -> int:
        """Remove expired entries.

        Returns:
            Number of entries removed
        """
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]

        for key in expired_keys:
            del self._cache[key]
            self._stats["expirations"] += 1

        return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Statistics dictionary
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate,
            "evictions": self._stats["evictions"],
            "expirations": self._stats["expirations"],
        }

    def get_entries(self) -> list[CacheEntry]:
        """Get all cache entries.

        Returns:
            List of entries
        """
        return list(self._cache.values())


class TranslationMemory:
    """Translation memory for storing high-quality translations."""

    def __init__(
        self,
        min_confidence: float = 0.9,
    ) -> None:
        """Initialize translation memory.

        Args:
            min_confidence: Minimum confidence to store
        """
        self.min_confidence = min_confidence
        self._memory: dict[str, CacheEntry] = {}
        self._segment_index: dict[str, list[str]] = {}  # segment -> list of keys

    def _generate_segment_key(
        self,
        source_lang: LanguageCode,
        target_lang: LanguageCode,
    ) -> str:
        """Generate segment key.

        Args:
            source_lang: Source language
            target_lang: Target language

        Returns:
            Segment key
        """
        return f"{source_lang.value}->{target_lang.value}"

    async def add(
        self,
        text: str,
        translation: str,
        source_lang: LanguageCode,
        target_lang: LanguageCode,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Add translation to memory.

        Args:
            text: Source text
            translation: Translated text
            source_lang: Source language
            target_lang: Target language
            confidence: Translation confidence
            metadata: Optional metadata

        Returns:
            True if added
        """
        if confidence < self.min_confidence:
            return False

        segment_key = self._generate_segment_key(source_lang, target_lang)
        entry_key = hashlib.sha256(
            f"{text}:{translation}".encode()
        ).hexdigest()[:32]

        entry = CacheEntry(
            key=entry_key,
            translation=translation,
            source_lang=source_lang,
            target_lang=target_lang,
            confidence=confidence,
            ttl_seconds=31536000,  # 1 year
        )

        self._memory[entry_key] = entry

        if segment_key not in self._segment_index:
            self._segment_index[segment_key] = []

        self._segment_index[segment_key].append(entry_key)

        return True

    async def find_similar(
        self,
        text: str,
        source_lang: LanguageCode,
        target_lang: LanguageCode,
        threshold: float = 0.8,
        limit: int = 5,
    ) -> list[tuple[str, float]]:
        """Find similar translations in memory.

        Args:
            text: Source text
            source_lang: Source language
            target_lang: Target language
            threshold: Similarity threshold
            limit: Max results

        Returns:
            List of (translation, similarity) tuples
        """
        segment_key = self._generate_segment_key(source_lang, target_lang)
        keys = self._segment_index.get(segment_key, [])

        # Simple similarity check (would use embeddings in production)
        results = []

        for key in keys:
            entry = self._memory.get(key)
            if not entry:
                continue

            # Calculate word overlap similarity
            similarity = self._calculate_similarity(text, entry.translation)

            if similarity >= threshold:
                results.append((entry.translation, similarity))

        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:limit]

    def _calculate_similarity(
        self,
        text1: str,
        text2: str,
    ) -> float:
        """Calculate text similarity.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_entries": len(self._memory),
            "segments": len(self._segment_index),
            "min_confidence": self.min_confidence,
        }


class HybridTranslationCache:
    """Hybrid cache combining LRU cache and translation memory."""

    def __init__(
        self,
        lru_max_size: int = 10000,
        lru_ttl_seconds: int = 86400,
        memory_min_confidence: float = 0.9,
    ) -> None:
        """Initialize hybrid cache.

        Args:
            lru_max_size: LRU cache max size
            lru_ttl_seconds: LRU cache TTL
            memory_min_confidence: Translation memory min confidence
        """
        self.lru_cache = TranslationLRUCache(
            max_size=lru_max_size,
            default_ttl_seconds=lru_ttl_seconds,
        )
        self.translation_memory = TranslationMemory(
            min_confidence=memory_min_confidence,
        )

    async def get(
        self,
        text: str,
        target_lang: LanguageCode,
        source_lang: LanguageCode | None = None,
    ) -> CacheEntry | None:
        """Get from LRU cache.

        Args:
            text: Source text
            target_lang: Target language
            source_lang: Optional source language

        Returns:
            Cache entry or None
        """
        return await self.lru_cache.get(text, target_lang, source_lang)

    async def set(
        self,
        text: str,
        translation: str,
        target_lang: LanguageCode,
        source_lang: LanguageCode,
        confidence: float,
        ttl_seconds: int | None = None,
    ) -> CacheEntry:
        """Set in both caches.

        Args:
            text: Source text
            translation: Translated text
            target_lang: Target language
            source_lang: Source language
            confidence: Translation confidence
            ttl_seconds: Optional TTL for LRU

        Returns:
            Cache entry from LRU
        """
        # Add to LRU cache
        entry = await self.lru_cache.set(
            text, translation, target_lang, source_lang, confidence, ttl_seconds
        )

        # Add to translation memory if high confidence
        if confidence >= self.translation_memory.min_confidence:
            await self.translation_memory.add(
                text, translation, source_lang, target_lang, confidence
            )

        return entry

    async def find_similar(
        self,
        text: str,
        source_lang: LanguageCode,
        target_lang: LanguageCode,
        threshold: float = 0.8,
        limit: int = 5,
    ) -> list[tuple[str, float]]:
        """Find similar translations in memory.

        Args:
            text: Source text
            source_lang: Source language
            target_lang: Target language
            threshold: Similarity threshold
            limit: Max results

        Returns:
            List of (translation, similarity) tuples
        """
        return await self.translation_memory.find_similar(
            text, source_lang, target_lang, threshold, limit
        )

    async def cleanup(self) -> dict[str, int]:
        """Cleanup expired entries.

        Returns:
            Cleanup statistics
        """
        lru_cleaned = await self.lru_cache.cleanup_expired()

        return {
            "lru_expired": lru_cleaned,
            "memory_entries": len(self.translation_memory._memory),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get combined statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "lru_cache": self.lru_cache.get_stats(),
            "translation_memory": self.translation_memory.get_stats(),
        }


# Global instance
translation_cache = HybridTranslationCache()


def get_translation_cache() -> HybridTranslationCache:
    """Get global translation cache instance.

    Returns:
        Translation cache instance
    """
    return translation_cache
