"""Translation service for multi-language support."""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ValidationError
from src.translation.engine import (
    TranslationEngine,
    LanguageCode,
    TranslationResult,
    TranslationQuality,
)
from src.translation.cache import HybridTranslationCache, get_translation_cache
from src.translation.batch import (
    BatchTranslator,
    BatchTranslationJob,
    get_batch_translator,
)

logger = logging.getLogger(__name__)


class TranslationService:
    """Service for handling translation operations."""

    def __init__(
        self,
        db: AsyncSession,
        engine: TranslationEngine | None = None,
        cache: HybridTranslationCache | None = None,
        batch_translator: BatchTranslator | None = None,
    ) -> None:
        """Initialize translation service.

        Args:
            db: Database session
            engine: Optional translation engine
            cache: Optional translation cache
            batch_translator: Optional batch translator
        """
        self.db = db
        self.engine = engine or TranslationEngine()
        self.cache = cache or get_translation_cache()
        self.batch_translator = batch_translator or get_batch_translator()

    async def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str | None = None,
        quality: str = "standard",
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Translate text to target language.

        Args:
            text: Text to translate
            target_lang: Target language code
            source_lang: Optional source language code
            quality: Translation quality (draft, standard, professional)
            use_cache: Whether to use cache

        Returns:
            Translation result
        """
        # Validate language codes
        try:
            target = LanguageCode(target_lang)
            source = LanguageCode(source_lang) if source_lang else None
        except ValueError as e:
            raise ValidationError(
                message=f"Invalid language code: {e}",
                details={
                    "target_lang": target_lang,
                    "source_lang": source_lang,
                    "valid_codes": [l.value for l in LanguageCode],
                },
            )

        # Validate quality
        try:
            qual = TranslationQuality(quality)
        except ValueError:
            qual = TranslationQuality.STANDARD

        # Check cache first
        if use_cache and self.cache:
            cached = await self.cache.get(text, target, source)
            if cached:
                logger.debug(f"Cache hit for translation: {text[:50]}...")
                return {
                    "translated_text": cached.translation,
                    "source_lang": cached.source_lang.value,
                    "target_lang": cached.target_lang.value,
                    "confidence": cached.confidence,
                    "from_cache": True,
                }

        # Perform translation
        result = await self.engine.translate(
            text=text,
            target_lang=target,
            source_lang=source,
            quality=qual,
        )

        # Cache result
        if use_cache and self.cache:
            await self.cache.set(
                text=text,
                translation=result.translated_text,
                target_lang=target,
                source_lang=result.source_lang,
                confidence=result.confidence,
            )

        return {
            "translated_text": result.translated_text,
            "source_lang": result.source_lang.value,
            "target_lang": result.target_lang.value,
            "confidence": result.confidence,
            "from_cache": False,
            "word_count": result.word_count,
            "character_count": result.character_count,
            "processing_time_ms": result.processing_time_ms,
        }

    async def translate_batch(
        self,
        texts: list[str],
        target_lang: str,
        source_lang: str | None = None,
        quality: str = "standard",
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Translate multiple texts.

        Args:
            texts: List of texts to translate
            target_lang: Target language code
            source_lang: Optional source language code
            quality: Translation quality
            use_cache: Whether to use cache

        Returns:
            List of translation results
        """
        # Validate language codes
        try:
            target = LanguageCode(target_lang)
            source = LanguageCode(source_lang) if source_lang else None
        except ValueError as e:
            raise ValidationError(
                message=f"Invalid language code: {e}",
                details={"valid_codes": [l.value for l in LanguageCode]},
            )

        # Validate quality
        try:
            qual = TranslationQuality(quality)
        except ValueError:
            qual = TranslationQuality.STANDARD

        # Translate batch
        results = await self.engine.translate_batch(
            texts=texts,
            target_lang=target,
            source_lang=source,
            quality=qual,
        )

        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "translated_text": result.translated_text,
                "source_lang": result.source_lang.value,
                "target_lang": result.target_lang.value,
                "confidence": result.confidence,
                "word_count": result.word_count,
                "character_count": result.character_count,
            })

            # Cache if enabled
            if use_cache and self.cache:
                await self.cache.set(
                    text=texts[results.index(result)],
                    translation=result.translated_text,
                    target_lang=target,
                    source_lang=result.source_lang,
                    confidence=result.confidence,
                )

        return formatted_results

    async def create_batch_job(
        self,
        texts: list[str],
        target_lang: str,
        source_lang: str | None = None,
        quality: str = "standard",
    ) -> dict[str, Any]:
        """Create a batch translation job.

        Args:
            texts: List of texts to translate
            target_lang: Target language code
            source_lang: Optional source language code
            quality: Translation quality

        Returns:
            Job details
        """
        # Validate language codes
        try:
            target = LanguageCode(target_lang)
            source = LanguageCode(source_lang) if source_lang else None
        except ValueError as e:
            raise ValidationError(
                message=f"Invalid language code: {e}",
                details={"valid_codes": [l.value for l in LanguageCode]},
            )

        # Validate quality
        try:
            qual = TranslationQuality(quality)
        except ValueError:
            qual = TranslationQuality.STANDARD

        # Create job
        job = await self.batch_translator.create_job(
            texts=texts,
            target_lang=target,
            source_lang=source,
            quality=qual,
        )

        return {
            "job_id": job.id,
            "total_items": job.total_items,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
        }

    async def start_batch_job(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        """Start processing a batch job.

        Args:
            job_id: Job ID

        Returns:
            Updated job details
        """
        job = await self.batch_translator.start_job(job_id)

        return {
            "job_id": job.id,
            "total_items": job.total_items,
            "status": job.status.value,
            "started_at": job.started_at.isoformat() if job.started_at else None,
        }

    async def get_batch_job_status(
        self,
        job_id: str,
    ) -> dict[str, Any] | None:
        """Get batch job status.

        Args:
            job_id: Job ID

        Returns:
            Job status or None
        """
        job = await self.batch_translator.get_job(job_id)

        if not job:
            return None

        return {
            "job_id": job.id,
            "total_items": job.total_items,
            "completed_items": job.completed_items,
            "failed_items": job.failed_items,
            "progress": job.progress,
            "status": job.status.value,
            "success_rate": job.success_rate,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error": job.error,
        }

    async def get_batch_job_results(
        self,
        job_id: str,
    ) -> list[dict[str, Any]] | None:
        """Get results from a completed batch job.

        Args:
            job_id: Job ID

        Returns:
            List of translation results or None
        """
        results = await self.batch_translator.get_job_results(job_id)

        if not results:
            return None

        return [
            {
                "translated_text": r.translated_text,
                "source_lang": r.source_lang.value,
                "target_lang": r.target_lang.value,
                "confidence": r.confidence,
                "word_count": r.word_count,
            }
            for r in results
        ]

    async def detect_language(
        self,
        text: str,
    ) -> dict[str, Any]:
        """Detect the language of text.

        Args:
            text: Text to analyze

        Returns:
            Detection result
        """
        lang, confidence = await self.engine.detect_language(text)

        return {
            "language": lang.value,
            "language_name": TranslationEngine.LANGUAGE_NAMES[lang],
            "confidence": confidence,
        }

    async def translate_to_multiple_languages(
        self,
        text: str,
        target_langs: list[str],
        source_lang: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Translate text to multiple languages.

        Args:
            text: Text to translate
            target_langs: List of target language codes
            source_lang: Optional source language code

        Returns:
            Dictionary mapping language to translation result
        """
        from src.translation.batch import ParallelTranslator

        # Validate language codes
        try:
            targets = [LanguageCode(lang) for lang in target_langs]
            source = LanguageCode(source_lang) if source_lang else None
        except ValueError as e:
            raise ValidationError(
                message=f"Invalid language code: {e}",
                details={"valid_codes": [l.value for l in LanguageCode]},
            )

        parallel_translator = ParallelTranslator(self.engine, self.cache)

        results = await parallel_translator.translate_to_languages(
            text=text,
            target_langs=targets,
            source_lang=source,
        )

        return {
            lang.value: {
                "translated_text": result.translated_text,
                "confidence": result.confidence,
            }
            for lang, result in results.items()
        }

    async def get_supported_languages(
        self,
    ) -> list[dict[str, str]]:
        """Get list of supported languages.

        Returns:
            List of language info
        """
        return [
            {
                "code": lang.value,
                "name": name,
            }
            for lang, name in TranslationEngine.LANGUAGE_NAMES.items()
        ]

    async def get_cache_stats(
        self,
    ) -> dict[str, Any] | None:
        """Get translation cache statistics.

        Returns:
            Cache statistics or None
        """
        if not self.cache:
            return None

        return self.cache.get_stats()

    async def clear_cache(
        self,
    ) -> dict[str, Any]:
        """Clear translation cache.

        Returns:
            Result of cache clear
        """
        if not self.cache:
            return {"cleared": False, "reason": "No cache configured"}

        await self.cache.lru_cache.clear()

        return {"cleared": True}
