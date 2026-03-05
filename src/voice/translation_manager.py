"""Translation manager for voice interactions."""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from src.config.settings import settings

logger = logging.getLogger(__name__)


class TranslationManager:
    """Manage translation tasks for voice conversations."""

    def __init__(
        self,
        source_language: str = "en",
        target_language: str = "en",
        cache_ttl: int = 86400,
    ) -> None:
        """Initialize translation manager.

        Args:
            source_language: Source language code
            target_language: Target language code
            cache_ttl: Cache time-to-live in seconds
        """
        self.source_language = source_language
        self.target_language = target_language
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[str, float]] = {}
        self._pending_translations: dict[str, asyncio.Task] = {}

    async def translate(
        self,
        text: str,
        target_language: str | None = None,
    ) -> str:
        """Translate text to target language.

        Args:
            text: Text to translate
            target_language: Target language (defaults to instance target)

        Returns:
            Translated text
        """
        if not text or not text.strip():
            return text

        target = target_language or self.target_language

        # Skip if same language
        if self.source_language == target:
            return text

        # Check cache
        cache_key = f"{self.source_language}:{target}:{text}"
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.debug(f"Cache hit for translation: {cache_key[:50]}...")
            return cached

        # Check if already pending
        if cache_key in self._pending_translations:
            task = self._pending_translations[cache_key]
            return await task

        # Create translation task
        task = asyncio.create_task(self._translate_text(text, target))
        self._pending_translations[cache_key] = task

        try:
            result = await task
            self._add_to_cache(cache_key, result)
            return result

        finally:
            del self._pending_translations[cache_key]

    async def translate_batch(
        self,
        texts: list[str],
        target_language: str | None = None,
    ) -> list[str]:
        """Translate multiple texts.

        Args:
            texts: List of texts to translate
            target_language: Target language

        Returns:
            List of translated texts
        """
        target = target_language or self.target_language

        # Process in batches for efficiency
        batch_size = settings.translation_batch_size
        results: list[str] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            tasks = [
                self.translate(text, target)
                for text in batch
            ]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

        return results

    async def _translate_text(
        self,
        text: str,
        target_language: str,
    ) -> str:
        """Perform actual translation.

        Args:
            text: Text to translate
            target_language: Target language code

        Returns:
            Translated text
        """
        # This is a placeholder implementation
        # In production, integrate with OpenAI, Google Translate, or DeepL
        try:
            # For now, return original text
            # TODO: Integrate with translation service
            logger.warning("Translation not implemented, returning original text")
            return text

        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return text

    def _add_to_cache(self, key: str, value: str) -> None:
        """Add translation to cache.

        Args:
            key: Cache key
            value: Translated text
        """
        self._cache[key] = (value, asyncio.get_event_loop().time())

    def _get_from_cache(self, key: str) -> str | None:
        """Get translation from cache.

        Args:
            key: Cache key

        Returns:
            Cached translation or None
        """
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        current_time = asyncio.get_event_loop().time()

        # Check if expired
        if current_time - timestamp > self.cache_ttl:
            del self._cache[key]
            return None

        return value

    def clear_cache(self) -> None:
        """Clear translation cache."""
        self._cache.clear()
        logger.info("Translation cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        return {
            "size": len(self._cache),
            "ttl": self.cache_ttl,
        }


class BiDirectionalTranslator:
    """Handle bidirectional translation for conversations."""

    def __init__(
        self,
        primary_language: str = "en",
        secondary_language: str = "en",
    ) -> None:
        """Initialize bidirectional translator.

        Args:
            primary_language: Primary language
            secondary_language: Secondary language
        """
        self.primary = primary_language
        self.secondary = secondary_language

        self._to_primary = TranslationManager(
            source_language=secondary_language,
            target_language=primary_language,
        )

        self._to_secondary = TranslationManager(
            source_language=primary_language,
            target_language=secondary_language,
        )

    async def to_primary(self, text: str) -> str:
        """Translate to primary language.

        Args:
            text: Text to translate

        Returns:
            Translated text
        """
        return await self._to_primary.translate(text)

    async def to_secondary(self, text: str) -> str:
        """Translate to secondary language.

        Args:
            text: Text to translate

        Returns:
            Translated text
        """
        return await self._to_secondary.translate(text)

    async def detect_and_translate(
        self,
        text: str,
        target_language: str | None = None,
    ) -> tuple[str, str, str]:
        """Detect language and translate to target.

        Args:
            text: Text to process
            target_language: Optional target language

        Returns:
            Tuple of (detected_language, original_text, translated_text)
        """
        # Simple language detection based on first character
        detected = self._detect_language(text)

        if target_language:
            if detected == target_language:
                return detected, text, text

            # Translate to target
            if target_language == self.primary:
                translated = await self._to_primary.translate(text)
            else:
                translated = await self._to_secondary.translate(text)

            return detected, text, translated

        # Auto-detect target (translate to other language)
        if detected == self.primary:
            translated = await self._to_secondary.translate(text)
            return detected, text, translated
        else:
            translated = await self._to_primary.translate(text)
            return detected, text, translated

    def _detect_language(self, text: str) -> str:
        """Detect text language.

        Args:
            text: Text to analyze

        Returns:
            Detected language code
        """
        # Simple heuristic detection
        # In production, use proper language detection library
        if not text:
            return self.primary

        # Check for common non-Latin scripts
        if any(ord(c) > 0x4E00 and ord(c) < 0x9FFF for c in text):
            return "zh"  # Chinese

        if any(ord(c) > 0x0400 and ord(c) < 0x052F for c in text):
            return "ru"  # Russian

        if any(ord(c) > 0x0600 and ord(c) < 0x06FF for c in text):
            return "ar"  # Arabic

        # Default to primary
        return self.primary

    def clear_caches(self) -> None:
        """Clear all translation caches."""
        self._to_primary.clear_cache()
        self._to_secondary.clear_cache()


class ConversationTranslator:
    """Manage translation for entire conversations."""

    def __init__(
        self,
        user_language: str = "en",
        assistant_language: str = "en",
    ) -> None:
        """Initialize conversation translator.

        Args:
            user_language: User's preferred language
            assistant_language: Assistant's language
        """
        self.user_language = user_language
        self.assistant_language = assistant_language
        self.translator = BiDirectionalTranslator(
            primary_language=assistant_language,
            secondary_language=user_language,
        )

        self._conversation_history: list[dict[str, Any]] = []

    async def process_user_message(
        self,
        message: str,
    ) -> dict[str, Any]:
        """Process user message with translation.

        Args:
            message: User's message

        Returns:
            Processing result with translations
        """
        detected, original, translated = await self.translator.detect_and_translate(
            message,
            target_language=self.assistant_language,
        )

        result = {
            "original": original,
            "translated": translated,
            "original_language": detected,
            "target_language": self.assistant_language,
            "direction": "user_to_assistant",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._conversation_history.append(result)
        return result

    async def process_assistant_message(
        self,
        message: str,
    ) -> dict[str, Any]:
        """Process assistant message with translation.

        Args:
            message: Assistant's message

        Returns:
            Processing result with translations
        """
        translated = await self.translator.to_secondary(message)

        result = {
            "original": message,
            "translated": translated,
            "original_language": self.assistant_language,
            "target_language": self.user_language,
            "direction": "assistant_to_user",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._conversation_history.append(result)
        return result

    def get_conversation_summary(self) -> dict[str, Any]:
        """Get summary of conversation translations.

        Returns:
            Conversation summary
        """
        user_messages = [
            m for m in self._conversation_history
            if m["direction"] == "user_to_assistant"
        ]

        assistant_messages = [
            m for m in self._conversation_history
            if m["direction"] == "assistant_to_user"
        ]

        return {
            "total_messages": len(self._conversation_history),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "user_language": self.user_language,
            "assistant_language": self.assistant_language,
            "languages_detected": set(
                m["original_language"]
                for m in self._conversation_history
            ),
        }

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()

    def get_history(self) -> list[dict[str, Any]]:
        """Get conversation history.

        Returns:
            List of translation events
        """
        return self._conversation_history.copy()


class VoiceTranslationSession:
    """Session for managing voice translation."""

    def __init__(
        self,
        session_id: str,
        source_language: str = "en",
        target_language: str = "en",
    ) -> None:
        """Initialize translation session.

        Args:
            session_id: Unique session identifier
            source_language: Source language
            target_language: Target language
        """
        self.session_id = session_id
        self.source_language = source_language
        self.target_language = target_language
        self.manager = TranslationManager(
            source_language=source_language,
            target_language=target_language,
        )

        self._transcripts: list[dict[str, Any]] = []
        self._translations: list[dict[str, Any]] = []
        self.created_at = datetime.now(timezone.utc)

    async def add_transcript(
        self,
        text: str,
        is_final: bool = False,
    ) -> dict[str, Any]:
        """Add transcript and translate.

        Args:
            text: Transcript text
            is_final: Whether transcript is final

        Returns:
            Translation result
        """
        transcript = {
            "text": text,
            "is_final": is_final,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._transcripts.append(transcript)

        if is_final:
            translated = await self.manager.translate(text)

            translation = {
                "original": text,
                "translated": translated,
                "source_language": self.source_language,
                "target_language": self.target_language,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self._translations.append(translation)
            return translation

        return {"text": text, "is_final": False}

    def get_final_text(self) -> str:
        """Get concatenated final transcript.

        Returns:
            Final transcript text
        """
        return " ".join(
            t["text"]
            for t in self._transcripts
            if t["is_final"]
        )

    def get_translations(self) -> list[dict[str, Any]]:
        """Get all translations.

        Returns:
            List of translations
        """
        return self._translations.copy()

    def get_session_stats(self) -> dict[str, Any]:
        """Get session statistics.

        Returns:
            Session statistics
        """
        return {
            "session_id": self.session_id,
            "duration_seconds": (datetime.now(timezone.utc) - self.created_at).total_seconds(),
            "transcript_count": len(self._transcripts),
            "translation_count": len(self._translations),
            "cache_stats": self.manager.get_cache_stats(),
        }
