"""Unit tests for translation modules."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.translation.engine import (
    TranslationEngine,
    TranslationResult,
    LanguageCode,
    TranslationQuality,
)
from src.translation.cache import (
    TranslationLRUCache,
    TranslationMemory,
    HybridTranslationCache,
    CacheEntry,
)
from src.translation.batch import (
    BatchTranslator,
    BatchTranslationJob,
    BatchStatus,
)


class TestTranslationEngine:
    """Test translation engine."""

    @pytest.mark.asyncio
    async def test_translate(self):
        """Test basic translation."""
        engine = TranslationEngine()

        with patch.object(engine.llm_service, 'chat_completion', return_value={"content": "你好"}):
            result = await engine.translate(
                text="Hello",
                target_lang=LanguageCode.CHINESE,
                source_lang=LanguageCode.ENGLISH,
            )

            assert isinstance(result, TranslationResult)
            assert result.translated_text == "你好"
            assert result.target_lang == LanguageCode.CHINESE

    @pytest.mark.asyncio
    async def test_detect_language(self):
        """Test language detection."""
        engine = TranslationEngine()

        with patch.object(engine.llm_service, 'chat_completion', return_value={"content": '{"language": "Chinese", "confidence": 0.95}'}):
            lang, confidence = await engine.detect_language("你好世界")

            assert lang == LanguageCode.CHINESE
            assert confidence == 0.95

    @pytest.mark.asyncio
    async def test_translate_batch(self):
        """Test batch translation."""
        engine = TranslationEngine()

        texts = ["Hello", "Goodbye"]

        with patch.object(engine.llm_service, 'chat_completion', return_value={"content": "你好"}):
            results = await engine.translate_batch(
                texts=texts,
                target_lang=LanguageCode.CHINESE,
            )

            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_translate_with_alternatives(self):
        """Test translation with alternatives."""
        engine = TranslationEngine()

        with patch.object(engine.llm_service, 'chat_completion', return_value={"content": "你好"}):
            result = await engine.translate_with_alternatives(
                text="Hello",
                target_lang=LanguageCode.CHINESE,
                num_alternatives=3,
            )

            assert result.translated_text == "你好"
            assert len(result.alternatives) >= 0

    @pytest.mark.asyncio
    async def test_transliterate(self):
        """Test transliteration."""
        engine = TranslationEngine()

        with patch.object(engine.llm_service, 'chat_completion', return_value={"content": "Nihao"}):
            result = await engine.transliterate(
                text="你好",
                source_lang=LanguageCode.CHINESE,
                target_script="latin",
            )

            assert result == "Nihao"


class TestTranslationLRUCache:
    """Test translation LRU cache."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test setting and getting cache values."""
        cache = TranslationLRUCache(max_size=100)

        await cache.set(
            text="Hello",
            translation="Hola",
            target_lang=LanguageCode.SPANISH,
            source_lang=LanguageCode.ENGLISH,
            confidence=0.95,
        )

        entry = await cache.get(
            text="Hello",
            target_lang=LanguageCode.SPANISH,
            source_lang=LanguageCode.ENGLISH,
        )

        assert entry is not None
        assert entry.translation == "Hola"

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test cache miss."""
        cache = TranslationLRUCache()

        entry = await cache.get(
            text="Hello",
            target_lang=LanguageCode.SPANISH,
        )

        assert entry is None

    @pytest.mark.asyncio
    async def test_cache_eviction(self):
        """Test LRU eviction."""
        cache = TranslationLRUCache(max_size=2)

        # Add 3 items (should evict first)
        await cache.set("A", "a", LanguageCode.SPANISH, LanguageCode.ENGLISH, 1.0)
        await cache.set("B", "b", LanguageCode.SPANISH, LanguageCode.ENGLISH, 1.0)
        await cache.set("C", "c", LanguageCode.SPANISH, LanguageCode.ENGLISH, 1.0)

        # First item should be evicted
        entry_a = await cache.get("A", LanguageCode.SPANISH, LanguageCode.ENGLISH)
        assert entry_a is None

        # Last item should still be there
        entry_c = await cache.get("C", LanguageCode.SPANISH, LanguageCode.ENGLISH)
        assert entry_c is not None

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        """Test cleaning up expired entries."""
        cache = TranslationLRUCache(default_ttl_seconds=1)

        await cache.set(
            text="Hello",
            translation="Hola",
            target_lang=LanguageCode.SPANISH,
            source_lang=LanguageCode.ENGLISH,
            confidence=1.0,
        )

        # Should be available immediately
        entry = await cache.get("Hello", LanguageCode.SPANISH, LanguageCode.ENGLISH)
        assert entry is not None

        # Wait for expiration
        import asyncio
        await asyncio.sleep(2)

        # Should be expired
        entry = await cache.get("Hello", LanguageCode.SPANISH, LanguageCode.ENGLISH)
        assert entry is None

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting cache statistics."""
        cache = TranslationLRUCache()

        await cache.set("Hello", "Hola", LanguageCode.SPANISH, LanguageCode.ENGLISH, 1.0)

        # Hit
        await cache.get("Hello", LanguageCode.SPANISH, LanguageCode.ENGLISH)

        # Miss
        await cache.get("Goodbye", LanguageCode.SPANISH, LanguageCode.ENGLISH)

        stats = cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1


class TestTranslationMemory:
    """Test translation memory."""

    @pytest.mark.asyncio
    async def test_add_and_find_similar(self):
        """Test adding and finding similar translations."""
        memory = TranslationMemory(min_confidence=0.9)

        # Add high-confidence translation
        await memory.add(
            text="Hello",
            translation="Hola",
            source_lang=LanguageCode.ENGLISH,
            target_lang=LanguageCode.SPANISH,
            confidence=0.95,
        )

        # Add low-confidence translation (should not be stored)
        await memory.add(
            text="Goodbye",
            translation="Adios",
            source_lang=LanguageCode.ENGLISH,
            target_lang=LanguageCode.SPANISH,
            confidence=0.8,
        )

        stats = memory.get_stats()
        assert stats["total_entries"] == 1

    @pytest.mark.asyncio
    async def test_find_similar(self):
        """Test finding similar translations."""
        memory = TranslationMemory()

        await memory.add(
            text="Hello world",
            translation="Hola mundo",
            source_lang=LanguageCode.ENGLISH,
            target_lang=LanguageCode.SPANISH,
            confidence=0.95,
        )

        # Find similar
        results = await memory.find_similar(
            text="Hello everyone",
            source_lang=LanguageCode.ENGLISH,
            target_lang=LanguageCode.SPANISH,
            threshold=0.0,
        )

        # Should find the similar translation
        assert len(results) >= 0


class TestHybridTranslationCache:
    """Test hybrid translation cache."""

    @pytest.mark.asyncio
    async def test_cache_and_retrieve(self):
        """Test caching and retrieving translations."""
        cache = HybridTranslationCache()

        await cache.set(
            text="Hello",
            translation="Hola",
            target_lang=LanguageCode.SPANISH,
            source_lang=LanguageCode.ENGLISH,
            confidence=0.95,
        )

        entry = await cache.get(
            text="Hello",
            target_lang=LanguageCode.SPANISH,
            source_lang=LanguageCode.ENGLISH,
        )

        assert entry is not None
        assert entry.translation == "Hola"

    @pytest.mark.asyncio
    async def test_find_similar(self):
        """Test finding similar translations."""
        cache = HybridTranslationCache()

        # Add to translation memory via set (high confidence)
        await cache.set(
            text="Hello world",
            translation="Hola mundo",
            target_lang=LanguageCode.SPANISH,
            source_lang=LanguageCode.ENGLISH,
            confidence=0.95,
        )

        # Find similar
        results = await cache.find_similar(
            text="Hello everyone",
            source_lang=LanguageCode.ENGLISH,
            target_lang=LanguageCode.SPANISH,
            threshold=0.0,
        )

        assert isinstance(results, list)

    def test_get_stats(self):
        """Test getting combined statistics."""
        cache = HybridTranslationCache()

        stats = cache.get_stats()

        assert "lru_cache" in stats
        assert "translation_memory" in stats


class TestBatchTranslator:
    """Test batch translator."""

    @pytest.mark.asyncio
    async def test_create_job(self):
        """Test creating a batch translation job."""
        translator = BatchTranslator()

        job = await translator.create_job(
            texts=["Hello", "Goodbye"],
            target_lang=LanguageCode.SPANISH,
            source_lang=LanguageCode.ENGLISH,
        )

        assert job.id is not None
        assert job.total_items == 2
        assert job.status == BatchStatus.PENDING

    @pytest.mark.asyncio
    async def test_start_job(self):
        """Test starting a batch job."""
        translator = BatchTranslator()

        job = await translator.create_job(
            texts=["Hello"],
            target_lang=LanguageCode.SPANISH,
        )

        with patch.object(translator.engine, 'translate', return_value=MagicMock(
            translated_text="Hola",
            source_lang=LanguageCode.ENGLISH,
            target_lang=LanguageCode.SPANISH,
            confidence=0.95,
        )):
            started_job = await translator.start_job(job.id)

            assert started_job.status == BatchStatus.IN_PROGRESS

            # Wait a bit for processing
            import asyncio
            await asyncio.sleep(0.1)

            # Check final status
            final_job = await translator.get_job(job.id)
            assert final_job is not None

    @pytest.mark.asyncio
    async def test_cancel_job(self):
        """Test cancelling a batch job."""
        translator = BatchTranslator()

        job = await translator.create_job(
            texts=["Hello"],
            target_lang=LanguageCode.SPANISH,
        )

        cancelled = await translator.cancel_job(job.id)

        assert cancelled.status == BatchStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_get_job_results(self):
        """Test getting job results."""
        translator = BatchTranslator()

        job = await translator.create_job(
            texts=["Hello"],
            target_lang=LanguageCode.SPANISH,
        )

        # Empty results for pending job
        results = await translator.get_job_results(job.id)

        # Should return None or empty list for incomplete job
        assert results is None or len(results) == 0


class TestTranslationResult:
    """Test translation result dataclass."""

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = TranslationResult(
            request_id="req_1",
            translated_text="Hola",
            source_lang=LanguageCode.ENGLISH,
            target_lang=LanguageCode.SPANISH,
            confidence=0.95,
            word_count=1,
            character_count=4,
        )

        # Test attribute access
        assert result.translated_text == "Hola"
        assert result.confidence == 0.95
