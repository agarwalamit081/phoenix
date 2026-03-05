"""Batch translation processing for high-volume translation tasks."""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.translation.engine import (
    TranslationEngine,
    LanguageCode,
    TranslationResult,
    TranslationQuality,
)
from src.translation.cache import HybridTranslationCache

logger = logging.getLogger(__name__)


class BatchStatus(str, Enum):
    """Batch translation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchTranslationItem:
    """Single item in a batch translation."""

    id: str
    text: str
    source_lang: LanguageCode
    target_lang: LanguageCode
    status: BatchStatus = BatchStatus.PENDING
    result: TranslationResult | None = None
    error: str | None = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


@dataclass
class BatchTranslationJob:
    """Batch translation job."""

    id: str
    items: list[BatchTranslationItem] = field(default_factory=list)
    status: BatchStatus = BatchStatus.PENDING
    progress: float = 0.0  # 0.0 to 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_items(self) -> int:
        """Get total number of items."""
        return len(self.items)

    @property
    def completed_items(self) -> int:
        """Get number of completed items."""
        return sum(
            1 for item in self.items
            if item.status == BatchStatus.COMPLETED
        )

    @property
    def failed_items(self) -> int:
        """Get number of failed items."""
        return sum(
            1 for item in self.items
            if item.status == BatchStatus.FAILED
        )

    @property
    def success_rate(self) -> float:
        """Get success rate (0.0 to 1.0)."""
        if self.total_items == 0:
            return 1.0
        return self.completed_items / self.total_items


class BatchTranslator:
    """Batch translation processor."""

    def __init__(
        self,
        engine: TranslationEngine | None = None,
        cache: HybridTranslationCache | None = None,
        max_concurrent: int = 10,
        max_retries: int = 3,
    ) -> None:
        """Initialize batch translator.

        Args:
            engine: Optional translation engine
            cache: Optional translation cache
            max_concurrent: Maximum concurrent translations
            max_retries: Maximum retry attempts
        """
        self.engine = engine or TranslationEngine()
        self.cache = cache
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self._jobs: dict[str, BatchTranslationJob] = {}
        self._active_tasks: dict[str, asyncio.Task] = {}

    async def create_job(
        self,
        texts: list[str],
        target_lang: LanguageCode,
        source_lang: LanguageCode | None = None,
        quality: TranslationQuality = TranslationQuality.STANDARD,
        metadata: dict[str, Any] | None = None,
    ) -> BatchTranslationJob:
        """Create a batch translation job.

        Args:
            texts: List of texts to translate
            target_lang: Target language
            source_lang: Optional source language
            quality: Translation quality
            metadata: Optional metadata

        Returns:
            Batch translation job
        """
        import uuid

        job_id = str(uuid.uuid4())

        items = []
        for i, text in enumerate(texts):
            items.append(BatchTranslationItem(
                id=f"{job_id}_{i}",
                text=text,
                source_lang=source_lang or LanguageCode.ENGLISH,
                target_lang=target_lang,
            ))

        job = BatchTranslationJob(
            id=job_id,
            items=items,
            metadata=metadata or {},
        )

        self._jobs[job_id] = job

        logger.info(f"Created batch translation job {job_id} with {len(texts)} items")

        return job

    async def start_job(
        self,
        job_id: str,
    ) -> BatchTranslationJob:
        """Start processing a batch job.

        Args:
            job_id: Job ID

        Returns:
            Updated job

        Raises:
            ValueError: If job not found
        """
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.status != BatchStatus.PENDING:
            raise ValueError(f"Job {job_id} is not pending")

        job.status = BatchStatus.IN_PROGRESS
        job.started_at = datetime.now(timezone.utc)

        # Create background task for processing
        task = asyncio.create_task(self._process_job(job_id))
        self._active_tasks[job_id] = task

        return job

    async def get_job(
        self,
        job_id: str,
    ) -> BatchTranslationJob | None:
        """Get job details.

        Args:
            job_id: Job ID

        Returns:
            Job or None
        """
        return self._jobs.get(job_id)

    async def cancel_job(
        self,
        job_id: str,
    ) -> BatchTranslationJob | None:
        """Cancel a batch job.

        Args:
            job_id: Job ID

        Returns:
            Cancelled job or None
        """
        job = self._jobs.get(job_id)
        if not job:
            return None

        job.status = BatchStatus.CANCELLED

        # Cancel active task
        task = self._active_tasks.get(job_id)
        if task and not task.done():
            task.cancel()

        return job

    async def get_job_results(
        self,
        job_id: str,
    ) -> list[TranslationResult] | None:
        """Get results from a completed job.

        Args:
            job_id: Job ID

        Returns:
            List of translation results or None
        """
        job = self._jobs.get(job_id)
        if not job:
            return None

        results = []
        for item in job.items:
            if item.result:
                results.append(item.result)

        return results

    async def _process_job(
        self,
        job_id: str,
    ) -> None:
        """Process a batch translation job.

        Args:
            job_id: Job ID
        """
        job = self._jobs.get(job_id)
        if not job:
            return

        logger.info(f"Processing batch translation job {job_id}")

        try:
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(self.max_concurrent)

            # Create tasks for each item
            tasks = [
                self._process_item(job_id, item.id, semaphore)
                for item in job.items
            ]

            # Wait for all tasks
            await asyncio.gather(*tasks, return_exceptions=True)

            # Update job status
            job.status = BatchStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 1.0

            logger.info(
                f"Completed batch translation job {job_id}: "
                f"{job.completed_items}/{job.total_items} successful"
            )

        except asyncio.CancelledError:
            job.status = BatchStatus.CANCELLED
            logger.info(f"Cancelled batch translation job {job_id}")

        except Exception as e:
            job.status = BatchStatus.FAILED
            job.error = str(e)
            logger.error(f"Failed batch translation job {job_id}: {e}")

        finally:
            # Clean up task
            if job_id in self._active_tasks:
                del self._active_tasks[job_id]

    async def _process_item(
        self,
        job_id: str,
        item_id: str,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """Process a single batch item.

        Args:
            job_id: Job ID
            item_id: Item ID
            semaphore: Semaphore for concurrency control
        """
        job = self._jobs.get(job_id)
        if not job:
            return

        item = next((i for i in job.items if i.id == item_id), None)
        if not item:
            return

        async with semaphore:
            # Check cache first
            if self.cache:
                cached = await self.cache.get(
                    item.text,
                    item.target_lang,
                    item.source_lang,
                )
                if cached:
                    item.status = BatchStatus.COMPLETED
                    item.result = TranslationResult(
                        request_id=item.id,
                        translated_text=cached.translation,
                        source_lang=cached.source_lang,
                        target_lang=cached.target_lang,
                        confidence=cached.confidence,
                    )
                    item.completed_at = datetime.now(timezone.utc)
                    self._update_job_progress(job)
                    return

            # Translate with retry
            for attempt in range(self.max_retries):
                try:
                    result = await self.engine.translate(
                        text=item.text,
                        target_lang=item.target_lang,
                        source_lang=item.source_lang,
                    )

                    item.status = BatchStatus.COMPLETED
                    item.result = result
                    item.completed_at = datetime.now(timezone.utc)

                    # Cache result
                    if self.cache:
                        await self.cache.set(
                            text=item.text,
                            translation=result.translated_text,
                            target_lang=item.target_lang,
                            source_lang=item.source_lang,
                            confidence=result.confidence,
                        )

                    break

                except Exception as e:
                    item.retry_count = attempt + 1
                    if attempt == self.max_retries - 1:
                        item.status = BatchStatus.FAILED
                        item.error = str(e)
                        logger.error(f"Failed to translate item {item_id}: {e}")
                    else:
                        # Wait before retry
                        await asyncio.sleep(1 * (attempt + 1))

            self._update_job_progress(job)

    def _update_job_progress(
        self,
        job: BatchTranslationJob,
    ) -> None:
        """Update job progress.

        Args:
            job: Job to update
        """
        total = job.total_items
        if total > 0:
            job.progress = job.completed_items / total


class ParallelTranslator:
    """Translate to multiple languages in parallel."""

    def __init__(
        self,
        engine: TranslationEngine | None = None,
        cache: HybridTranslationCache | None = None,
    ) -> None:
        """Initialize parallel translator.

        Args:
            engine: Optional translation engine
            cache: Optional translation cache
        """
        self.engine = engine or TranslationEngine()
        self.cache = cache

    async def translate_to_languages(
        self,
        text: str,
        target_langs: list[LanguageCode],
        source_lang: LanguageCode | None = None,
    ) -> dict[LanguageCode, TranslationResult]:
        """Translate text to multiple languages.

        Args:
            text: Text to translate
            target_langs: List of target languages
            source_lang: Optional source language

        Returns:
            Dictionary mapping language to result
        """
        tasks = {
            lang: self.engine.translate(text, lang, source_lang)
            for lang in target_langs
        }

        results = await asyncio.gather(*tasks.values())

        return dict(zip(target_langs, results))

    async def translate_batch_to_languages(
        self,
        texts: list[str],
        target_langs: list[LanguageCode],
        source_lang: LanguageCode | None = None,
    ) -> dict[str, dict[LanguageCode, str]]:
        """Translate multiple texts to multiple languages.

        Args:
            texts: List of texts
            target_langs: List of target languages
            source_lang: Optional source language

        Returns:
            Nested dictionary {text_index: {language: translation}}
        """
        results = {}

        for i, text in enumerate(texts):
            lang_results = await self.translate_to_languages(
                text, target_langs, source_lang
            )
            results[str(i)] = {
                lang: result.translated_text
                for lang, result in lang_results.items()
            }

        return results


# Global instances
batch_translator = BatchTranslator()
parallel_translator = ParallelTranslator()


def get_batch_translator() -> BatchTranslator:
    """Get global batch translator instance.

    Returns:
        Batch translator instance
    """
    return batch_translator


def get_parallel_translator() -> ParallelTranslator:
    """Get global parallel translator instance.

    Returns:
        Parallel translator instance
    """
    return parallel_translator
