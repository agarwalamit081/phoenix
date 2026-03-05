"""LiveKit Agents worker for voice AI using Speechmatics plugin.

This worker runs as a separate process and joins LiveKit rooms to provide
real-time voice interaction with Speechmatics STT and OpenAI LLM.

Run with:
    python src/voice/voice_agent_worker.py
"""

import asyncio
import json
import logging
import os
import time
from typing import Callable, Any

# Load environment variables from .env file first
# This populates os.environ for the current process and child processes
from dotenv import load_dotenv
load_dotenv()

# Ensure critical environment variables are set for child processes
# Import settings to get the values (which loads from .env via Pydantic)
from src.config.settings import settings

# Set environment variables explicitly so child processes inherit them
# This is required for LiveKit's spawned worker processes
if settings.openai_api_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
if settings.speechmatics_api_key:
    os.environ["SPEECHMATICS_API_KEY"] = settings.speechmatics_api_key
if settings.livekit_url:
    os.environ["LIVEKIT_URL"] = settings.livekit_url
if settings.livekit_api_key:
    os.environ["LIVEKIT_API_KEY"] = settings.livekit_api_key
if settings.livekit_api_secret:
    os.environ["LIVEKIT_API_SECRET"] = settings.livekit_api_secret

from livekit import rtc
from livekit.agents import stt, tts, vad, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.agents.worker import WorkerOptions, JobContext, JobRequest
from livekit.plugins import openai

# Try to import speechmatics plugin
try:
    from livekit.plugins import speechmatics
    SPEECHMATICS_AVAILABLE = True
except ImportError:
    speechmatics = None
    SPEECHMATICS_AVAILABLE = False
    logging.warning("livekit-plugins-speechmatics not available, using fallback")

logger = logging.getLogger(__name__)
ALLOWED_ROOM_PREFIXES = ("voice-", "tour-")


def _get_speechmatics_ws_url() -> str:
    """Get Speechmatics websocket URL with backward-compatible env fallback."""
    return os.environ.get(
        "SPEECHMATICS_WS_URL",
        os.environ.get("SPEECHMATICS_RT_URL", "wss://eu2.rt.speechmatics.com/v2"),
    )


def _build_stt_config(language: str = "en") -> stt.STT:
    """Build STT provider config with Speechmatics-first fallback to OpenAI."""
    speechmatics_key = os.environ.get("SPEECHMATICS_API_KEY", "")
    if SPEECHMATICS_AVAILABLE and speechmatics_key:
        logger.info("Using Speechmatics STT plugin")
        return speechmatics.STT(
            api_key=speechmatics_key,
            base_url=_get_speechmatics_ws_url(),
            language=language,
            include_partials=True,
        )

    if not SPEECHMATICS_AVAILABLE:
        logger.warning("Speechmatics plugin unavailable. Falling back to OpenAI STT.")
    elif not speechmatics_key:
        logger.warning("SPEECHMATICS_API_KEY missing. Falling back to OpenAI STT.")

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        logger.info("Using OpenAI STT fallback")
        return openai.stt.STT(
            api_key=openai_key,
            language=language,
            model=os.environ.get("OPENAI_MODEL_STT", "gpt-4o-mini-transcribe"),
        )

    raise RuntimeError(
        "No STT provider configured: Speechmatics unavailable/misconfigured and OPENAI_API_KEY missing"
    )


class TravelVoiceAgent(Agent):
    """Voice agent for travel assistance.

    Handles:
    - Speech-to-Text using Speechmatics
    - LLM processing using OpenAI
    - Text-to-Speech for responses
    """

    def __init__(self, publish_event: Callable[[dict[str, Any]], None] | None = None) -> None:
        """Initialize the voice agent."""
        self._publish_event = publish_event
        super().__init__(
            instructions="You are Hugo, a helpful AI travel assistant for Phoenix. "
            "You help travelers discover hidden gems, local experiences, and personalized recommendations. "
            "Be friendly, concise, and enthusiastic about travel. "
            "Keep your responses brief and conversational.",
        )
        logger.info("TravelVoiceAgent initialized")

    async def on_enter(self) -> None:
        """Called when agent enters room."""
        logger.info("[AGENT ENTER] Agent has entered the room")

    async def on_exit(self) -> None:
        """Called when agent exits room."""
        logger.info("[AGENT EXIT] Agent is leaving the room")

    async def on_user_turn_completed(
        self, turn_ctx: "llm.ChatContext", new_message: "llm.ChatMessage"
    ) -> None:
        """Called when the user has finished speaking, and the LLM is about to respond.

        This is called with the transcribed user speech and provides an opportunity to
        log or modify the message before it's sent to the LLM.

        Args:
            turn_ctx: The chat context with the conversation history
            new_message: The new message from the user (transcribed speech)
        """
        # Log the user's transcribed speech
        user_content = ""
        if new_message.content:
            if isinstance(new_message.content, str):
                user_content = new_message.content
            elif isinstance(new_message.content, list):
                # Handle multipart content (text + images, etc.)
                for part in new_message.content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        user_content += part.get("text", "")

        if user_content:
            logger.info(f"[USER SPEECH] Transcribed: {user_content}")
            if self._publish_event:
                self._publish_event(
                    {
                        "type": "transcript",
                        "data": {
                            "text": user_content,
                            "is_final": True,
                            "timestamp": int(time.time() * 1000),
                        },
                    }
                )
        else:
            logger.warning("[USER SPEECH] No content in transcribed message")

        # Log the full chat context for debugging
        logger.debug(f"[CHAT CONTEXT] Current context has {len(turn_ctx.messages)} messages")


async def entrypoint(ctx: JobContext) -> None:
    """Main entry point for the voice agent worker.

    This function is called for each room that the worker joins.
    Runs in a spawned process, so needs to load environment variables.

    Args:
        ctx: The job context with room and participant info
    """
    # Reload environment variables in this spawned process
    # This is required because spawned processes don't inherit os.environ changes
    load_dotenv()

    logger.info(f"Voice agent worker starting for room: {ctx.room.name}")

    # Log room participants for debugging
    participants = ctx.room.remote_participants
    logger.info(f"Room has {len(participants)} remote participants: {[p.identity for p in participants]}")

    def publish_room_event(payload: dict) -> None:
        """Publish structured event payload to room data channel for frontend UI."""
        try:
            ctx.room.local_participant.publish_data(
                json.dumps(payload),
                reliable=True,
                topic="voice-events",
            )
        except Exception as e:
            logger.warning(f"Failed to publish room event: {e}")

    # Configure STT provider with Speechmatics-first fallback to OpenAI
    stt_config = _build_stt_config(language=os.environ.get("SPEECHMATICS_LANGUAGE", "en"))

    # Configure LLM with OpenAI
    llm_config = openai.llm.LLM(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        model=os.environ.get("OPENAI_MODEL_CHAT", "gpt-4o-mini"),
    )

    # Configure TTS with OpenAI
    tts_config = openai.tts.TTS(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        voice="alloy",
    )

    # Create the agent (without STT/LLM/TTS - those are configured in the session)
    agent = TravelVoiceAgent(publish_event=publish_room_event)

    # Create an AgentSession with STT/LLM/TTS configurations
    # The session handles audio transcription, LLM processing, and TTS
    session = AgentSession(
        turn_detection="stt",
        stt=stt_config,
        llm=llm_config,
        tts=tts_config,
        user_away_timeout=600,  # Increase timeout to 10 minutes
        min_endpointing_delay=0.5,
        max_endpointing_delay=3.0,
        allow_interruptions=True,
        min_consecutive_speech_delay=0.2,
    )

    # Start the session with the agent and room
    logger.info("Starting agent session...")
    await session.start(agent, room=ctx.room)

    logger.info(f"Voice agent started in room: {ctx.room.name}")

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev):
        logger.info(f"[USER INPUT TRANSCRIBED] {ev}")

    @session.on("conversation_item_added")
    def on_conversation_item_added(item):
        try:
            role = getattr(item, "role", None)
            content = getattr(item, "content", "")
            text = ""
            if isinstance(content, str):
                text = content.strip()
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text += part.get("text", "")
            if role == "assistant" and text:
                logger.info(f"[ASSISTANT RESPONSE] {text}")
                publish_room_event(
                    {
                        "type": "response",
                        "text": text,
                        "timestamp": int(time.time() * 1000),
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to process conversation item: {e}")

    # Add room event listeners for debugging
    @ctx.room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        logger.info(f"[PARTICIPANT CONNECTED] {participant.identity} ({participant.name})")

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        logger.info(f"[PARTICIPANT DISCONNECTED] {participant.identity}")

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        logger.info(f"[TRACK SUBSCRIBED] kind={track.kind} name={publication.name} from {participant.identity}")

        # Log track details for debugging
        logger.info(f"[TRACK DETAILS] sid={publication.sid} mime_type={publication.mime_type if hasattr(publication, 'mime_type') else 'N/A'}")

        # Check if this is an audio track
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"[TRACK SUBSCRIBED] Audio track detected - should forward to STT")
        else:
            logger.warning(f"[TRACK SUBSCRIBED] Non-audio track detected: {track.kind}")

    @ctx.room.on("track_unsubscribed")
    def on_track_unsubscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        logger.info(f"[TRACK UNSUBSCRIBED] {track.kind} from {participant.identity}")

    # Monitor participants for debugging
    async def monitor_participants():
        """Periodically log participant status for debugging."""
        while True:
            participants = ctx.room.remote_participants
            if participants:
                # remote_participants is a dict-like object, iterate values
                participant_list = [(p.identity, p.name) for p in participants.values()]
                logger.info(f"Current participants: {participant_list}")
            await asyncio.sleep(5)

    # Start monitoring in background
    asyncio.create_task(monitor_participants())


async def request_fnc(req: JobRequest) -> None:
    """Accept jobs for supported voice room prefixes.

    This function is called for each job request and decides whether
    to accept or reject based on the room name.
    """
    room_name = req.room.name
    logger.info(f"Received job request for room: {room_name}")
    if room_name.startswith(ALLOWED_ROOM_PREFIXES):
        logger.info(f"Accepting job for room: {room_name}")
        await req.accept()
    else:
        logger.info(
            f"Declining job for room: {room_name} (allowed prefixes: {ALLOWED_ROOM_PREFIXES})"
        )
        await req.reject()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Import after loading environment variables
    from livekit.agents.worker import AgentServer

    # Create WorkerOptions - settings will provide credentials from environment
    worker_options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        request_fnc=request_fnc,
        port=8082,  # Use port 8082 to avoid conflicts
    )

    # Create and run the agent server directly
    server = AgentServer.from_server_options(worker_options)

    # Run the server (this blocks)
    asyncio.run(server.run())
