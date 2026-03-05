"""Voice service for speech-to-text, text-to-speech, and translation."""

import logging
import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import datetime, timezone
from typing import Any

import httpx

from src.config.settings import settings
from src.core.exceptions import ValidationError
from src.core.websocket import voice_manager
from src.services.chat_service import ChatService
from src.services.llm_service import LLMService
from src.voice.audio_processor import AudioBuffer, AudioProcessor, create_audio_stream
from src.voice.livekit_service import livekit_manager
from src.voice.speechmatics_client import SpeechmaticsClient, SpeechmaticsPool
from src.voice.translation_manager import (
    BiDirectionalTranslator,
    VoiceTranslationSession,
)

logger = logging.getLogger(__name__)


class VoiceService:
    """Service for handling voice interactions."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        chat_service: ChatService | None = None,
    ) -> None:
        """Initialize voice service.

        Args:
            llm_service: Optional LLM service
            chat_service: Optional chat service
        """
        self.llm_service = llm_service or LLMService()
        self.chat_service = chat_service
        self.speechmatics_pool = SpeechmaticsPool(
            max_clients=5,
        )
        self.active_sessions: dict[str, dict[str, Any]] = {}

        if not settings.enable_voice:
            logger.warning("Voice feature is disabled")

    def is_enabled(self) -> bool:
        """Check if voice service is enabled.

        Returns:
            True if enabled
        """
        return settings.enable_voice

    async def create_voice_session(
        self,
        user_id: uuid.UUID,
        language: str = "en",
        target_language: str = "en",
        tour_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new voice session.

        Args:
            user_id: User ID
            language: Source language code
            target_language: Target language code
            tour_id: Optional tour ID

        Returns:
            Session information
        """
        if not self.is_enabled():
            raise ValidationError("Voice feature is disabled")

        session_id = str(uuid.uuid4())

        # Create translation session
        translation_session = VoiceTranslationSession(
            session_id=session_id,
            source_language=language,
            target_language=target_language,
        )

        # Create LiveKit room if needed
        room_info = None
        if livekit_manager.service.is_configured():
            try:
                room_info = await livekit_manager.create_voice_room(user_id, tour_id)
            except Exception as e:
                logger.warning(f"Failed to create LiveKit room: {e}")

        self.active_sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "language": language,
            "target_language": target_language,
            "tour_id": tour_id,
            "translation_session": translation_session,
            "room_info": room_info,
            "audio_buffer": AudioBuffer(max_size_seconds=30),
            "processor": AudioProcessor(sample_rate=16000),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "transcripts": [],
            "responses": [],
        }

        logger.info(f"Created voice session: {session_id} for user {user_id}")

        return {
            "session_id": session_id,
            "user_id": user_id,
            "language": language,
            "target_language": target_language,
            "room_info": room_info,
        }

    async def process_audio_stream(
        self,
        session_id: str,
        audio_stream: AsyncGenerator[bytes, None],
        on_transcript: Callable[..., Any] | None = None,
        on_response: Callable[..., Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Process audio stream and generate responses.

        Args:
            session_id: Session ID
            audio_stream: Audio data stream
            on_transcript: Optional callback for transcripts
            on_response: Optional callback for responses

        Yields:
            Processing events
        """
        if session_id not in self.active_sessions:
            raise ValidationError(f"Invalid session: {session_id}")

        session = self.active_sessions[session_id]
        processor = session["processor"]
        translation_session = session["translation_session"]
        language = session["language"]

        # Get Speechmatics client
        client = await self.speechmatics_pool.get_client(session_id, language)

        try:
            final_transcript = ""

            async for transcript in client.start_listening(audio_stream):
                text = transcript["text"]
                is_final = transcript["is_final"]

                if on_transcript:
                    await on_transcript(transcript)

                if is_final:
                    # Add to translation session
                    translation_result = await translation_session.add_transcript(text, is_final)
                    final_transcript = text

                    session["transcripts"].append(transcript)

                    yield {
                        "type": "transcript",
                        "data": {
                            "text": text,
                            "is_final": is_final,
                            "translation": translation_result.get("translated", text),
                        },
                    }

                    # Generate response for final transcript
                    if text.strip():
                        async for response in self._generate_response(session_id, text):
                            if on_response:
                                await on_response(response)

                            yield {
                                "type": "response",
                                "data": response,
                            }

        finally:
            await self.speechmatics_pool.release_client(session_id)

    async def _generate_response(
        self,
        session_id: str,
        text: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Generate AI response to user input.

        Args:
            session_id: Session ID
            text: User input text

        Yields:
            Response chunks
        """
        if session_id not in self.active_sessions:
            return

        session = self.active_sessions[session_id]

        # Translate if needed
        translation_session = session["translation_session"]
        target_language = session["target_language"]

        translated_text = await translation_session.manager.translate(
            text,
            target_language=target_language,
        )

        # Generate AI response using LLM
        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful AI travel assistant for Phoenix Travel Companion.",
                    },
                    {
                        "role": "user",
                        "content": translated_text,
                    },
                ],
                temperature=0.7,
            )

            response_text = response.get("content", "")

            # Translate response back to user language if needed
            if target_language != session["language"]:
                response_text = await translation_session.manager.translate(
                    response_text,
                    target_language=session["language"],
                )

            session["responses"].append({
                "user_input": text,
                "assistant_response": response_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            yield {
                "text": response_text,
                "session_id": session_id,
            }

        except Exception as e:
            logger.error(f"Failed to generate response: {e}")

            yield {
                "text": "I apologize, but I couldn't generate a response. Please try again.",
                "error": str(e),
                "session_id": session_id,
            }

    async def text_to_speech(
        self,
        text: str,
        voice: str | None = None,
        language: str = "en",
    ) -> bytes:
        """Convert text to speech audio.

        Args:
            text: Text to synthesize
            voice: Voice name (defaults to settings)
            language: Language code

        Returns:
            Audio bytes
        """
        if not settings.elevenlabs_api_key:
            raise ValidationError("ElevenLabs API key not configured")

        if not text.strip():
            raise ValidationError("Text cannot be empty")

        async def resolve_voice_id(client: httpx.AsyncClient, selected_voice: str) -> str:
            """Resolve configured voice name to ElevenLabs voice ID when necessary."""
            if len(selected_voice) > 20 and "-" in selected_voice:
                return selected_voice

            try:
                response = await client.get(
                    "https://api.elevenlabs.io/v1/voices",
                    headers={"xi-api-key": settings.elevenlabs_api_key},
                )
                response.raise_for_status()
                voices = response.json().get("voices", [])
                for item in voices:
                    if item.get("name", "").lower() == selected_voice.lower():
                        return item.get("voice_id", selected_voice)
            except Exception:
                logger.warning("Failed to resolve ElevenLabs voice name, using raw voice value")

            return selected_voice

        selected_voice = (voice or settings.elevenlabs_voice).strip()

        async with httpx.AsyncClient(timeout=30.0) as client:
            voice_id = await resolve_voice_id(client, selected_voice)
            tts_response = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": settings.elevenlabs_api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": settings.elevenlabs_model,
                    "voice_settings": {
                        "stability": 0.45,
                        "similarity_boost": 0.8,
                        "style": 0.2,
                        "use_speaker_boost": True,
                    },
                },
            )
            tts_response.raise_for_status()
            return tts_response.content

    async def get_session_info(self, session_id: str) -> dict[str, Any] | None:
        """Get session information.

        Args:
            session_id: Session ID

        Returns:
            Session information or None
        """
        return self.active_sessions.get(session_id)

    async def end_session(self, session_id: str) -> dict[str, Any]:
        """End a voice session.

        Args:
            session_id: Session ID

        Returns:
            Session summary
        """
        if session_id not in self.active_sessions:
            raise ValidationError(f"Invalid session: {session_id}")

        session = self.active_sessions[session_id]

        # Close LiveKit room if exists
        if session.get("room_info"):
            room_name = session["room_info"].get("room_name")
            if room_name:
                await livekit_manager.leave_voice_room(
                    room_name,
                    session["user_id"],
                )

        # Get summary
        translation_session = session["translation_session"]
        summary = {
            "session_id": session_id,
            "user_id": str(session["user_id"]),
            "duration_seconds": (
                datetime.now(timezone.utc) - datetime.fromisoformat(session["created_at"])
            ).total_seconds(),
            "transcript_count": len(session["transcripts"]),
            "response_count": len(session["responses"]),
            "final_transcript": translation_session.get_final_text(),
            "translations": translation_session.get_translations(),
            "session_stats": translation_session.get_session_stats(),
        }

        # Clean up
        del self.active_sessions[session_id]

        logger.info(f"Ended voice session: {session_id}")

        return summary

    async def cleanup_expired_sessions(self, max_age_seconds: int = 3600) -> int:
        """Clean up expired sessions.

        Args:
            max_age_seconds: Maximum session age

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now(timezone.utc)
        expired = []

        for session_id, session in self.active_sessions.items():
            created_at = datetime.fromisoformat(session["created_at"])
            age = (now - created_at).total_seconds()

            if age > max_age_seconds:
                expired.append(session_id)

        for session_id in expired:
            await self.end_session(session_id)

        return len(expired)

    def get_supported_languages(self) -> list[dict[str, Any]]:
        """Get supported languages for voice.

        Returns:
            List of supported languages
        """
        languages = [
            {"code": "en", "name": "English"},
            {"code": "zh", "name": "Chinese"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
            {"code": "hi", "name": "Hindi"},
            {"code": "fr", "name": "French"},
            {"code": "es", "name": "Spanish"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "ru", "name": "Russian"},
            {"code": "ar", "name": "Arabic"},
        ]

        # Filter by settings
        supported = settings.supported_languages_list

        return [
            lang for lang in languages
            if lang["code"] in supported
        ]

    def get_supported_voices(self) -> list[dict[str, Any]]:
        """Get supported TTS voices.

        Returns:
            List of supported voices
        """
        # ElevenLabs voices
        return [
            {"id": "Rachel", "name": "Rachel", "language": "en", "gender": "F"},
            {"id": "Drew", "name": "Drew", "language": "en", "gender": "M"},
            {"id": "Clyde", "name": "Clyde", "language": "en", "gender": "M"},
            {"id": "Mimi", "name": "Mimi", "language": "en", "gender": "F"},
            {"id": "Fin", "name": "Fin", "language": "en", "gender": "M"},
        ]


class VoiceSessionManager:
    """Manage active voice sessions."""

    def __init__(self) -> None:
        """Initialize session manager."""
        self.voice_service = VoiceService()

    async def create_session(
        self,
        user_id: uuid.UUID,
        language: str = "en",
        target_language: str = "en",
        tour_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new voice session.

        Args:
            user_id: User ID
            language: Source language
            target_language: Target language
            tour_id: Optional tour ID

        Returns:
            Session information
        """
        return await self.voice_service.create_voice_session(
            user_id=user_id,
            language=language,
            target_language=target_language,
            tour_id=tour_id,
        )

    async def process_audio(
        self,
        session_id: str,
        audio_data: bytes,
    ) -> list[dict[str, Any]]:
        """Process audio data and return results.

        Args:
            session_id: Session ID
            audio_data: Audio bytes

        Returns:
            List of processing results
        """
        results = []

        audio_stream = create_audio_stream(audio_data)

        async for event in self.voice_service.process_audio_stream(session_id, audio_stream):
            results.append(event)

        return results

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session information.

        Args:
            session_id: Session ID

        Returns:
            Session information or None
        """
        return await self.voice_service.get_session_info(session_id)

    async def close_session(self, session_id: str) -> dict[str, Any]:
        """Close a voice session.

        Args:
            session_id: Session ID

        Returns:
            Session summary
        """
        return await self.voice_service.end_session(session_id)


# Global instance
voice_session_manager = VoiceSessionManager()
