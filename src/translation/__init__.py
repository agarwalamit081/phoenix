"""Translation modules for multi-language support."""

from src.translation.engine import (
    TranslationEngine,
    TranslationRequest,
    TranslationResult,
    LanguageCode,
    TranslationQuality,
    get_translation_engine,
)
from src.translation.cache import (
    TranslationLRUCache,
    TranslationMemory,
    HybridTranslationCache,
    CacheEntry,
    get_translation_cache,
)
from src.translation.batch import (
    BatchTranslator,
    BatchTranslationJob,
    BatchTranslationItem,
    BatchStatus,
    ParallelTranslator,
    get_batch_translator,
    get_parallel_translator,
)
from src.services.translation_service import TranslationService

__all__ = [
    # Engine
    "TranslationEngine",
    "TranslationRequest",
    "TranslationResult",
    "LanguageCode",
    "TranslationQuality",
    "get_translation_engine",
    # Cache
    "TranslationLRUCache",
    "TranslationMemory",
    "HybridTranslationCache",
    "CacheEntry",
    "get_translation_cache",
    # Batch
    "BatchTranslator",
    "BatchTranslationJob",
    "BatchTranslationItem",
    "BatchStatus",
    "ParallelTranslator",
    "get_batch_translator",
    "get_parallel_translator",
    # Service
    "TranslationService",
]
