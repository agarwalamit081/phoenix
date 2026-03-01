"""LiveKit Agents worker for voice AI using Speechmatics plugin.

This worker runs as a separate process and joins LiveKit rooms to provide
real-time voice interaction with Speechmatics STT and OpenAI LLM.

Run with:
    python src/voice/voice_agent_worker.py
"""

import asyncio
import logging
import os

# Load environment variables from .env file first
from dotenv import load_dotenv
load_dotenv()

from livekit import rtc
from livekit.agents import stt, tts, vad, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai

# Try to import speechmatics plugin
try:
    from livekit.plugins import speechmatics
    SPEECHMATICS_AVAILABLE = True
except ImportError:
    SPEECHMATICS_AVAILABLE = False
    logging.warning("livekit-plugins-speechmatics not available, using fallback")

from src.config.settings import settings

logger = logging.getLogger(__name__)


class TravelVoiceAgent(Agent):
    """Voice agent for travel assistance.

    Handles:
    - Speech-to-Text using Speechmatics
    - LLM processing using OpenAI
    - Text-to-Speech for responses
    """

    def __init__(self) -> None:
        """Initialize the voice agent."""
        super().__init__(
            instructions="You are Hugo, a helpful AI travel assistant for Phoenix. "
            "You help travelers discover hidden gems, local experiences, and personalized recommendations. "
            "Be friendly, concise, and enthusiastic about travel.",
        )
        logger.info("TravelVoiceAgent initialized")


def prewarm(proc: cli.JobProcess) -> None:
    """Prewarm the agent process with loaded models."""
    proc.userdata["stt"] = openai.stt.STT(
        api_key=settings.openai_api_key,
        model="whisper-1",
        language="en",
    )
    logger.info("Agent process prewarmed with STT model")


async def entrypoint(ctx: cli.JobContext) -> None:
    """Main entry point for the voice agent worker.

    This function is called for each room that the worker joins.

    Args:
        ctx: The job context with room and participant info
    """
    logger.info(f"Voice agent worker starting for room: {ctx.room.name}")

    # Configure STT with Speechmatics or fallback to OpenAI
    if SPEECHMATICS_AVAILABLE:
        stt_config = speechmatics.STT(
            api_key=settings.speechmatics_api_key,
            language="en",
            model="2.0",
            enable_partials=True,
        )
        logger.info("Using Speechmatics STT plugin")
    else:
        # Use prewarmed STT if available
        stt_config = ctx.proc.userdata().get("stt") or openai.stt.STT(
            api_key=settings.openai_api_key,
            model="whisper-1",
            language="en",
        )
        logger.info("Using OpenAI Whisper STT (fallback)")

    # Configure LLM with OpenAI
    llm_config = openai.llm.LLM(
        api_key=settings.openai_api_key,
        model=settings.openai_model_chat,
    )

    # Configure TTS with OpenAI
    tts_config = openai.tts.TTS(
        api_key=settings.openai_api_key,
        voice="alloy",
    )

    # Create and start the agent
    agent = TravelVoiceAgent()

    # Start the agent in the room
    await agent.start(
        ctx.room,
        stt=stt_config,
        llm=llm_config,
        tts=tts_config,
        vad=vad.VAD(
            min_speech_duration=0.5,
            min_silence_duration=0.8,
            padding_duration=0.1,
            prefix_padding_duration=0.1,
        ),
    )

    logger.info(f"Voice agent started in room: {ctx.room.name}")


async def request_fnc(req: cli.JobRequest) -> None:
    """Accept jobs for rooms starting with 'voice-'.

    This function is called for each job request and decides whether
    to accept or reject based on the room name.
    """
    room_name = req.room.name
    logger.info(f"Received job request for room: {room_name}")
    # Only accept rooms that start with "voice-"
    if room_name.startswith("voice-"):
        logger.info(f"Accepting job for room: {room_name}")
        await req.accept()
    else:
        logger.info(f"Declining job for room: {room_name} (doesn't match 'voice-' prefix)")
        await req.reject()


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set environment variables for the CLI
    os.environ["LIVEKIT_URL"] = settings.livekit_url
    os.environ["LIVEKIT_API_KEY"] = settings.livekit_api_key
    os.environ["LIVEKIT_API_SECRET"] = settings.livekit_api_secret

    # Use the CLI to run the agent
    # This automatically handles worker registration, job dispatch, and lifecycle
    cli.run_app(
        cli.AppEntry(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            request_fnc=request_fnc,
        )
    )
