"""Voice API endpoints for real-time voice interactions using LiveKit."""

import asyncio
import logging
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.websockets import WebSocketState
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DBSession
from src.services.voice_service import voice_session_manager
from src.services.llm_service import LLMService

router = APIRouter()
logger = logging.getLogger(__name__)


class TTSRequest(BaseModel):
    """Request body for text-to-speech generation."""

    text: str = Field(..., min_length=1)
    voice: str | None = None
    language: str = "en"


SPOKEN_RESPONSE_SYSTEM_PROMPT = (
    "You are Hugo, a concise and helpful travel assistant. "
    "Answer only the user's latest request naturally, in plain spoken English. "
    "Do not use markdown, bullets, numbered lists, asterisks, emojis, or special formatting. "
    "Keep responses brief and conversational with no repeated sentences."
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def _clean_spoken_text(text: str) -> str:
    cleaned = re.sub(r"```[\s\S]*?```", " ", text)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"[*_~`#>|\[\]]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _has_meaningful_content(text: str) -> bool:
    return any(char.isalnum() for char in text)


def _is_repetitive_response(normalized_response: str, recent_responses: list[str]) -> bool:
    if not normalized_response:
        return True
    return any(
        normalized_response == previous
        or normalized_response in previous
        or previous in normalized_response
        for previous in recent_responses
    )


@router.post("/session", status_code=201)
async def create_voice_session(
    language: str = "en",
    target_language: str = "en",
    tour_id: str | None = None,
) -> dict[str, Any]:
    """Create a new voice session with LiveKit room (public endpoint).

    Creates a LiveKit room for real-time voice interaction using WebRTC.
    The frontend can connect to the room using the returned URL and token.

    This endpoint is public and creates anonymous sessions for demo purposes.

    Args:
        language: Source language code
        target_language: Target language code for responses
        tour_id: Optional tour ID

    Returns:
        LiveKit room information with access token
    """
    from src.voice.livekit_service import livekit_manager

    # Generate anonymous user ID for demo
    anonymous_user_id = uuid.uuid4()

    # Create LiveKit room for voice session
    room_info = await livekit_manager.create_voice_room(
        user_id=anonymous_user_id,
        tour_id=tour_id,
    )

    # Add language info to response
    room_info["language"] = language
    room_info["target_language"] = target_language

    logger.info(f"Created LiveKit voice room: {room_info['room_name']} for anonymous user: {anonymous_user_id}")

    return room_info


@router.get("/session/{session_id}")
async def get_voice_session(
    session_id: str,
    user: CurrentUser,
    session: DBSession,
) -> dict[str, Any]:
    """Get voice session information.

    Args:
        session_id: Session ID
        user: Current user
        session: Database session

    Returns:
        Session information

    Raises:
        HTTPException: If session not found
    """
    session_info = await voice_session_manager.get_session(session_id)

    if not session_info:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Verify user owns this session
    if session_info.get("user_id") != user.id:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session",
        )

    return session_info


@router.delete("/session/{session_id}")
async def close_voice_session(
    session_id: str,
    user: CurrentUser,
    session: DBSession,
) -> dict[str, Any]:
    """Close a voice session.

    Args:
        session_id: Session ID
        user: Current user
        session: Database session

    Returns:
        Session summary

    Raises:
        HTTPException: If session not found
    """
    try:
        summary = await voice_session_manager.close_session(session_id)
        return summary
    except Exception as e:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.websocket("/ws")
async def voice_websocket(
    websocket: WebSocket,
    session_id: str | None = None,
) -> None:
    """WebSocket endpoint for real-time voice interaction with Speechmatics transcription.

    This endpoint:
    1. Creates or retrieves a voice session
    2. Sends session ready message to frontend
    3. Receives binary audio data from frontend
    4. Streams audio to Speechmatics for transcription
    5. Sends transcripts back to frontend

    Args:
        websocket: WebSocket connection
        session_id: Voice session ID (optional, will create anonymous session if not provided)
    """
    await websocket.accept()

    # Speechmatics client and state
    speechmatics_client = None
    is_listening = False
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
    transcription_task = None

    try:
        from src.config.settings import settings

        # Verify or create session
        session_info = None
        if session_id:
            session_info = await voice_session_manager.get_session(session_id)

        # Create anonymous session if not exists
        if not session_info:
            anonymous_user_id = uuid.uuid4()
            if not session_id:
                session_id = str(uuid.uuid4())

            session_info = await voice_session_manager.create_session(
                user_id=anonymous_user_id,
                language="en",
                target_language="en",
                tour_id=None,
            )
            logger.info(f"Created anonymous voice session: {session_id}")

        language = session_info.get("language", "en")

        # Send session ready message to frontend
        await websocket.send_json({
            "type": "session_ready",
            "session_id": session_id,
            "language": language,
        })

        logger.info(f"Session ready for voice: {session_id}")

        # Audio stream generator for Speechmatics
        async def audio_stream_generator() -> Any:
            """Generate audio stream from queue."""
            while is_listening:
                try:
                    audio_chunk = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
                    yield audio_chunk
                except asyncio.TimeoutError:
                    # Continue waiting for audio
                    continue

        def _merge_transcript(existing: str, incoming: str) -> str:
            """Merge overlapping transcript chunks to avoid word/phrase duplication."""
            existing = existing.strip()
            incoming = incoming.strip()
            if not incoming:
                return existing
            if not existing:
                return incoming
            if incoming in existing:
                return existing
            if existing in incoming:
                return incoming

            max_overlap = min(len(existing), len(incoming))
            for overlap in range(max_overlap, 0, -1):
                if existing.endswith(incoming[:overlap]):
                    return (existing + incoming[overlap:]).strip()
            return f"{existing} {incoming}".strip()

        # Transcription task
        async def run_transcription():
            """Run Speechmatics transcription and send results."""
            nonlocal speechmatics_client
            from src.voice.speechmatics_client import SpeechmaticsClient

            speechmatics_client = SpeechmaticsClient(language=language)
            llm_service = LLMService()
            pending_user_text = ""
            pending_response_task: asyncio.Task[None] | None = None
            recent_responses: list[str] = []

            async def respond_after_silence(text_snapshot: str) -> None:
                """Debounce LLM response until user pauses speaking."""
                nonlocal pending_user_text
                await asyncio.sleep(0.9)
                text_snapshot = text_snapshot.strip()
                if not text_snapshot or not is_listening:
                    return

                response = await llm_service.chat_completion(
                    messages=[
                        {
                            "role": "system",
                            "content": SPOKEN_RESPONSE_SYSTEM_PROMPT,
                        },
                        {
                            "role": "user",
                            "content": text_snapshot,
                        },
                    ],
                )
                response_text = _clean_spoken_text(response.get("content", ""))
                if not response_text:
                    return
                normalized_response = _normalize_text(response_text)
                if _is_repetitive_response(normalized_response, recent_responses):
                    return

                await websocket.send_json({
                    "type": "response",
                    "text": response_text,
                })
                recent_responses.append(normalized_response)
                recent_responses[:] = recent_responses[-5:]

                if pending_user_text.strip() == text_snapshot:
                    pending_user_text = ""

            try:
                await speechmatics_client.connect()
                logger.info(f"Speechmatics connected for session: {session_id}")

                async for transcript in speechmatics_client.start_listening(
                    audio_stream_generator(),
                ):
                    # Send transcript to frontend
                    await websocket.send_json({
                        "type": "transcript",
                        "data": {
                            "text": transcript["text"],
                            "is_final": transcript["is_final"],
                            "timestamp": transcript["timestamp"],
                        },
                    })

                    # Accumulate finalized transcript chunks and debounce response generation.
                    if transcript["is_final"] and _has_meaningful_content(transcript["text"]):
                        pending_user_text = _merge_transcript(
                            pending_user_text,
                            transcript["text"],
                        )
                        if pending_response_task and not pending_response_task.done():
                            pending_response_task.cancel()
                            try:
                                await pending_response_task
                            except asyncio.CancelledError:
                                pass
                        pending_response_task = asyncio.create_task(
                            respond_after_silence(pending_user_text)
                        )

            except Exception as e:
                logger.error(f"Transcription error: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                })
            finally:
                if pending_response_task and not pending_response_task.done():
                    pending_response_task.cancel()
                    try:
                        await pending_response_task
                    except asyncio.CancelledError:
                        pass
                if speechmatics_client:
                    await speechmatics_client.disconnect()
                    speechmatics_client = None

        # Main message loop
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                logger.info(f"WebSocket disconnect frame received for session: {session_id}")
                break

            # Handle text messages (control messages)
            if "text" in message:
                import json
                try:
                    data = json.loads(message["text"])
                    message_type = data.get("type")

                    if message_type == "ping":
                        await websocket.send_json({"type": "pong"})

                    elif message_type == "start_listening":
                        # Start listening - initialize Speechmatics
                        if not is_listening:
                            is_listening = True
                            # Start transcription task
                            transcription_task = asyncio.create_task(run_transcription())
                            await websocket.send_json({"type": "listening_started"})
                            logger.info(f"Started listening for session: {session_id}")

                    elif message_type == "stop_listening":
                        # Stop listening
                        is_listening = False
                        if transcription_task and not transcription_task.done():
                            transcription_task.cancel()
                            try:
                                await transcription_task
                            except asyncio.CancelledError:
                                pass
                        await websocket.send_json({"type": "listening_stopped"})
                        logger.info(f"Stopped listening for session: {session_id}")

                    elif message_type == "text":
                        # Handle text input as alternative to voice
                        text = data.get("text", "")
                        if text:
                            llm_service = LLMService()
                            response = await llm_service.chat_completion(
                                messages=[
                                    {
                                        "role": "system",
                                        "content": SPOKEN_RESPONSE_SYSTEM_PROMPT,
                                    },
                                    {
                                        "role": "user",
                                        "content": text,
                                    },
                                ],
                            )
                            await websocket.send_json({
                                "type": "response",
                                "text": _clean_spoken_text(response.get("content", "")),
                            })

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON message: {e}")

            # Handle binary audio data
            elif "bytes" in message:
                audio_data = message["bytes"]
                if is_listening:
                    # Queue audio for transcription
                    try:
                        audio_queue.put_nowait(audio_data)
                    except asyncio.QueueFull:
                        logger.warning("Audio queue full, dropping chunk")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)

    finally:
        # Cleanup
        is_listening = False
        if transcription_task and not transcription_task.done():
            transcription_task.cancel()
            try:
                await transcription_task
            except asyncio.CancelledError:
                pass
        if speechmatics_client:
            await speechmatics_client.disconnect()


@router.get("/languages")
async def get_supported_languages() -> dict[str, Any]:
    """Get supported languages for voice interaction.

    Returns:
        List of supported languages
    """
    from src.services.voice_service import VoiceService

    voice_service = VoiceService()
    languages = voice_service.get_supported_languages()

    return {
        "languages": languages,
        "total": len(languages),
    }


@router.get("/voices")
async def get_supported_voices() -> dict[str, Any]:
    """Get supported TTS voices.

    Returns:
        List of supported voices
    """
    from src.services.voice_service import VoiceService

    voice_service = VoiceService()
    voices = voice_service.get_supported_voices()

    return {
        "voices": voices,
        "total": len(voices),
    }


@router.post("/tts")
async def text_to_speech(
    payload: TTSRequest | None = None,
    text: str | None = Query(default=None),
    voice: str | None = Query(default=None),
    language: str = Query(default="en"),
) -> Response:
    """Convert text to speech.

    Args:
        text: Text to synthesize
        voice: Optional voice name
        language: Language code

    Returns:
        Audio data or error

    Note:
        This endpoint returns audio bytes directly.
        In production, consider returning a URL to stored audio.
    """
    from src.services.voice_service import VoiceService

    voice_service = VoiceService()

    try:
        resolved_text = payload.text if payload else text
        resolved_voice = payload.voice if payload else voice
        resolved_language = payload.language if payload else language
        if not resolved_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="`text` is required for TTS",
            )

        audio = await voice_service.text_to_speech(
            text=resolved_text,
            voice=resolved_voice,
            language=resolved_language,
        )
        return Response(content=audio, media_type="audio/mpeg")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS generation failed: {e}",
        ) from e


@router.get("/health")
async def voice_health_check() -> dict[str, Any]:
    """Health check for voice services.

    Returns:
        Health status
    """
    from src.config.settings import settings
    from src.voice.livekit_service import livekit_manager

    livekit_configured = livekit_manager.service.is_configured()

    return {
        "voice_enabled": settings.enable_voice,
        "speechmatics_configured": bool(settings.speechmatics_api_key),
        "elevenlabs_configured": bool(settings.elevenlabs_api_key),
        "livekit_configured": livekit_configured,
        "supported_languages": settings.supported_languages_list,
    }
