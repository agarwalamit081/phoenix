"""Voice API endpoints for real-time voice interactions using LiveKit."""

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DBSession
from src.services.voice_service import voice_session_manager
from src.services.llm_service import LLMService

router = APIRouter()
logger = logging.getLogger(__name__)


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

        # Transcription task
        async def run_transcription():
            """Run Speechmatics transcription and send results."""
            nonlocal speechmatics_client
            from src.voice.speechmatics_client import SpeechmaticsClient

            speechmatics_client = SpeechmaticsClient(language=language)

            try:
                await speechmatics_client.connect()
                logger.info(f"Speechmatics connected for session: {session_id}")

                async for transcript in speechmatics_client.start_listening(
                    audio_stream_generator(),
                ):
                    logger.info(f"[TRANSCRIPT] {'FINAL' if transcript['is_final'] else 'partial'}: {transcript['text']!r}")
                    # Send transcript to frontend immediately — never block this loop
                    await websocket.send_json({
                        "type": "transcript",
                        "data": {
                            "text": transcript["text"],
                            "is_final": transcript["is_final"],
                            "timestamp": transcript["timestamp"],
                            "speaker": transcript.get("speaker"),  # e.g. "S1", "S2"
                        },
                    })

                    # Fire LLM response as a background task so it never blocks
                    # the Speechmatics receive loop (LLM calls take 2-5 s).
                    if transcript["is_final"] and transcript["text"].strip():
                        async def _send_llm_response(text: str) -> None:
                            try:
                                llm_service = LLMService()
                                response = await llm_service.chat_completion(
                                    messages=[
                                        {
                                            "role": "system",
                                            "content": "You are a helpful AI travel assistant.",
                                        },
                                        {"role": "user", "content": text},
                                    ],
                                )
                                await websocket.send_json({
                                    "type": "response",
                                    "text": response.get("content", ""),
                                })
                            except Exception as _e:
                                logger.warning(f"LLM response failed: {_e}")

                        asyncio.create_task(_send_llm_response(transcript["text"]))

            except Exception as e:
                logger.error(f"Transcription error: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                })
            finally:
                if speechmatics_client:
                    await speechmatics_client.disconnect()
                    speechmatics_client = None

        # Main message loop
        while True:
            message = await websocket.receive()

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
                                        "content": "You are a helpful AI travel assistant.",
                                    },
                                    {
                                        "role": "user",
                                        "content": text,
                                    },
                                ],
                            )
                            await websocket.send_json({
                                "type": "response",
                                "text": response.get("content", ""),
                            })

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON message: {e}")

            # Handle binary audio data
            elif "bytes" in message:
                audio_data = message["bytes"]
                # Compute RMS to detect silence vs real audio
                import struct as _struct
                samples = _struct.unpack_from(f"<{len(audio_data)//2}h", audio_data)
                rms = (sum(s*s for s in samples) / len(samples)) ** 0.5 if samples else 0
                max_amp = max(abs(s) for s in samples) if samples else 0
                logger.info(f"[AUDIO] {len(audio_data)}B rms={rms:.0f} max={max_amp} silence={'YES' if rms < 100 else 'NO'} session={session_id[:8]}")
                if is_listening:
                    try:
                        audio_queue.put_nowait(audio_data)
                    except asyncio.QueueFull:
                        logger.warning("Audio queue full, dropping chunk")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
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
    text: str,
    voice: str | None = None,
    language: str = "en",
) -> dict[str, Any]:
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
    from fastapi import Response
    from src.services.voice_service import VoiceService

    voice_service = VoiceService()

    try:
        audio = await voice_service.text_to_speech(
            text=text,
            voice=voice,
            language=language,
        )

        return {
            "audio_size": len(audio),
            "format": "mp3",
        }

    except Exception as e:
        return {
            "error": str(e),
            "audio_size": 0,
        }


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
