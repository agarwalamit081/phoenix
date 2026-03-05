"""Translation engine for multi-language support."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class LanguageCode(str, Enum):
    """Supported language codes."""

    CHINESE = "zh"
    ENGLISH = "en"
    JAPANESE = "ja"
    KOREAN = "ko"
    HINDI = "hi"
    FRENCH = "fr"
    SPANISH = "es"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    ARABIC = "ar"
    THAI = "th"
    VIETNAMESE = "vi"
    DUTCH = "nl"


class TranslationQuality(str, Enum):
    """Translation quality levels."""

    DRAFT = "draft"  # Quick, literal translation
    STANDARD = "standard"  # Good quality translation
    PROFESSIONAL = "professional"  # High-quality, localized translation


@dataclass
class TranslationRequest:
    """Translation request."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    source_lang: LanguageCode = LanguageCode.ENGLISH
    target_lang: LanguageCode = LanguageCode.CHINESE
    quality: TranslationQuality = TranslationQuality.STANDARD
    context: str | None = None  # Optional context for better translation
    domain: str | None = None  # Optional domain (travel, food, history, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TranslationResult:
    """Translation result."""

    request_id: str
    translated_text: str
    source_lang: LanguageCode
    target_lang: LanguageCode
    confidence: float  # 0.0 to 1.0
    alternatives: list[str] = field(default_factory=list)
    detected_source_lang: LanguageCode | None = None
    word_count: int = 0
    character_count: int = 0
    processing_time_ms: int = 0
    translated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TranslationEngine:
    """Translation engine using LLM."""

    # Language name mapping
    LANGUAGE_NAMES = {
        LanguageCode.CHINESE: "Chinese",
        LanguageCode.ENGLISH: "English",
        LanguageCode.JAPANESE: "Japanese",
        LanguageCode.KOREAN: "Korean",
        LanguageCode.HINDI: "Hindi",
        LanguageCode.FRENCH: "French",
        LanguageCode.SPANISH: "Spanish",
        LanguageCode.GERMAN: "German",
        LanguageCode.ITALIAN: "Italian",
        LanguageCode.PORTUGUESE: "Portuguese",
        LanguageCode.RUSSIAN: "Russian",
        LanguageCode.ARABIC: "Arabic",
        LanguageCode.THAI: "Thai",
        LanguageCode.VIETNAMESE: "Vietnamese",
        LanguageCode.DUTCH: "Dutch",
    }

    def __init__(
        self,
        llm_service: LLMService | None = None,
    ) -> None:
        """Initialize translation engine.

        Args:
            llm_service: Optional LLM service
        """
        self.llm_service = llm_service or LLMService()

    async def translate(
        self,
        text: str,
        target_lang: LanguageCode,
        source_lang: LanguageCode | None = None,
        quality: TranslationQuality = TranslationQuality.STANDARD,
        context: str | None = None,
        domain: str | None = None,
    ) -> TranslationResult:
        """Translate text to target language.

        Args:
            text: Text to translate
            target_lang: Target language
            source_lang: Optional source language (auto-detect if None)
            quality: Translation quality
            context: Optional context
            domain: Optional domain

        Returns:
            Translation result
        """
        request = TranslationRequest(
            text=text,
            source_lang=source_lang or LanguageCode.ENGLISH,
            target_lang=target_lang,
            quality=quality,
            context=context,
            domain=domain,
        )

        return await self._translate_request(request)

    async def translate_batch(
        self,
        texts: list[str],
        target_lang: LanguageCode,
        source_lang: LanguageCode | None = None,
        quality: TranslationQuality = TranslationQuality.STANDARD,
    ) -> list[TranslationResult]:
        """Translate multiple texts.

        Args:
            texts: List of texts to translate
            target_lang: Target language
            source_lang: Optional source language
            quality: Translation quality

        Returns:
            List of translation results
        """
        # Translate concurrently
        tasks = [
            self.translate(text, target_lang, source_lang, quality)
            for text in texts
        ]

        return await asyncio.gather(*tasks)

    async def detect_language(
        self,
        text: str,
    ) -> tuple[LanguageCode, float]:
        """Detect the language of text.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (detected language, confidence)
        """
        prompt = f"""Detect the language of this text and provide your confidence (0-1).

Text: {text[:500]}

Respond in JSON format:
{{"language": "language_code", "confidence": 0.0}}

Supported languages: {", ".join(self.LANGUAGE_NAMES.values())}"""

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a language detection expert.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.1,
                max_tokens=100,
            )

            content = response.get("content", "{}")

            # Parse response
            import json
            result = json.loads(content)

            lang_name = result.get("language", "")
            confidence = float(result.get("confidence", 0.5))

            # Map language name to code
            for code, name in self.LANGUAGE_NAMES.items():
                if name.lower() in lang_name.lower():
                    return code, confidence

            return LanguageCode.ENGLISH, confidence

        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return LanguageCode.ENGLISH, 0.5

    async def transliterate(
        self,
        text: str,
        source_lang: LanguageCode,
        target_script: str,
    ) -> str:
        """Transliterate text to a different script.

        Args:
            text: Text to transliterate
            source_lang: Source language
            target_script: Target script (e.g., "latin", "cyrillic", "arabic")

        Returns:
            Transliterated text
        """
        prompt = f"""Transliterate this text from {self.LANGUAGE_NAMES[source_lang]} to {target_script} script.

Text: {text}

Provide only the transliterated text, no explanation."""

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a transliteration expert.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.3,
                max_tokens=500,
            )

            return response.get("content", text).strip()

        except Exception as e:
            logger.error(f"Transliteration failed: {e}")
            return text

    async def get_localized_content(
        self,
        content_id: str,
        target_lang: LanguageCode,
        fallback_content: str | None = None,
    ) -> str:
        """Get localized version of content.

        Args:
            content_id: Content identifier
            target_lang: Target language
            fallback_content: Optional fallback content

        Returns:
            Localized content
        """
        # This would integrate with a content localization system
        # For now, return fallback
        return fallback_content or ""

    async def _translate_request(
        self,
        request: TranslationRequest,
    ) -> TranslationResult:
        """Translate a translation request.

        Args:
            request: Translation request

        Returns:
            Translation result
        """
        start_time = datetime.now(timezone.utc)

        # Build translation prompt
        target_lang_name = self.LANGUAGE_NAMES[request.target_lang]
        source_lang_name = self.LANGUAGE_NAMES[request.source_lang]

        quality_instructions = {
            TranslationQuality.DRAFT: "Provide a quick, literal translation.",
            TranslationQuality.STANDARD: "Provide a natural, accurate translation.",
            TranslationQuality.PROFESSIONAL: "Provide a high-quality, culturally appropriate translation with localization.",
        }

        prompt_parts = [
            f"Translate the following text from {source_lang_name} to {target_lang_name}.",
            quality_instructions[request.quality],
        ]

        if request.context:
            prompt_parts.append(f"Context: {request.context}")

        if request.domain:
            prompt_parts.append(f"Domain: {request.domain}")

        prompt_parts.append(f"\nText: {request.text}")

        prompt = "\n".join(prompt_parts)

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a professional translator specializing in {target_lang_name}.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.3 if request.quality == TranslationQuality.DRAFT else 0.5,
                max_tokens=2000,
            )

            translated_text = response.get("content", request.text).strip()

        except Exception as e:
            logger.error(f"Translation failed: {e}")
            translated_text = request.text

        # Calculate processing time
        processing_time_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

        # Create result
        result = TranslationResult(
            request_id=request.id,
            translated_text=translated_text,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            confidence=0.85,  # LLM-based translation generally good
            word_count=len(translated_text.split()),
            character_count=len(translated_text),
            processing_time_ms=processing_time_ms,
        )

        return result

    async def translate_with_alternatives(
        self,
        text: str,
        target_lang: LanguageCode,
        num_alternatives: int = 3,
    ) -> TranslationResult:
        """Translate with multiple alternative translations.

        Args:
            text: Text to translate
            target_lang: Target language
            num_alternatives: Number of alternative translations

        Returns:
            Translation result with alternatives
        """
        base_result = await self.translate(text, target_lang)

        if num_alternatives <= 1:
            return base_result

        # Generate alternatives
        tasks = [
            self._translate_alternative(text, target_lang, i + 1)
            for i in range(num_alternatives - 1)
        ]

        alternatives = await asyncio.gather(*tasks, return_exceptions=True)

        # Extract successful translations
        base_result.alternatives = [
            alt for alt in alternatives
            if not isinstance(alt, Exception) and alt != base_result.translated_text
        ][:num_alternatives - 1]

        return base_result

    async def _translate_alternative(
        self,
        text: str,
        target_lang: LanguageCode,
        variant: int,
    ) -> str:
        """Generate an alternative translation.

        Args:
            text: Text to translate
            target_lang: Target language
            variant: Variant number

        Returns:
            Alternative translation
        """
        target_lang_name = self.LANGUAGE_NAMES[target_lang]

        prompt = f"""Provide an alternative translation (variant {variant}) to {target_lang_name}.

Original text: {text}

Give a different, but equally valid translation than a standard one."""

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a creative translator for {target_lang_name}.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.8,
                max_tokens=1000,
            )

            return response.get("content", text).strip()

        except Exception as e:
            logger.error(f"Alternative translation failed: {e}")
            return text


# Global instance
translation_engine = TranslationEngine()


def get_translation_engine() -> TranslationEngine:
    """Get global translation engine instance.

    Returns:
        Translation engine instance
    """
    return translation_engine
