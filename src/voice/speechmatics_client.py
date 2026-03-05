"""Speechmatics WebSocket client for speech-to-text transcription."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Callable
from datetime import datetime, timezone
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

from src.config.settings import settings

logger = logging.getLogger(__name__)


class SpeechmaticsClient:
    """Async WebSocket client for Speechmatics transcription API."""

    def __init__(
        self,
        api_key: str | None = None,
        language: str = "en",
        ws_url: str | None = None,
    ) -> None:
        """Initialize Speechmatics client.

        Args:
            api_key: Speechmatics API key (defaults to settings)
            language: Language code for transcription
            ws_url: WebSocket URL (defaults to settings)
        """
        self.api_key = api_key or settings.speechmatics_api_key
        self.language = language
        self.ws_url = ws_url or settings.speechmatics_ws_url
        logger.info(f"[SpeechmaticsClient] Initialized with URL: {self.ws_url}")

        if not self.api_key:
            raise ValueError("Speechmatics API key is required")

        self._websocket: websockets.WebSocketClientProtocol | None = None
        self._is_connected = False
        self._transcript_handlers: list[Callable] = []
        self._error_handlers: list[Callable] = []

    async def connect(self) -> None:
        """Connect to Speechmatics WebSocket server."""
        if self._is_connected:
            logger.warning("Already connected to Speechmatics")
            return

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }

            logger.info(f"[SpeechmaticsClient] Attempting to connect to: {self.ws_url}")
            self._websocket = await websockets.connect(
                self.ws_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=90,
            )

            self._is_connected = True
            logger.info(f"Connected to Speechmatics at {self.ws_url}")

            # Send configuration message
            config_message = {
                "message": "StartRecognition",
                "transcription_config": {
                    "language": self.language,
                    "enable_partials": True,
                    "max_delay": 2,
                },
                "audio_format": {
                    "type": "raw",
                    "encoding": "pcm_s16le",
                    "sample_rate": 16000,
                },
            }

            await self._send_message(config_message)
            logger.debug("Sent StartRecognition configuration")

        except Exception as e:
            logger.error(f"Failed to connect to Speechmatics: {e}")
            self._is_connected = False
            raise

    async def disconnect(self) -> None:
        """Disconnect from Speechmatics WebSocket server."""
        if not self._is_connected:
            return

        try:
            if self._websocket:
                await self._websocket.close()
                self._websocket = None

            self._is_connected = False
            logger.info("Disconnected from Speechmatics")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    async def send_audio(self, audio_data: bytes) -> None:
        """Send audio data for transcription.

        Args:
            audio_data: Raw audio bytes (PCM 16-bit, 16kHz)
        """
        if not self._is_connected or not self._websocket:
            raise RuntimeError("Not connected to Speechmatics")

        try:
            # Speechmatics Realtime v2 expects raw binary audio frames after StartRecognition.
            await self._websocket.send(audio_data)

        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            raise

    async def start_listening(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        on_transcript: Callable[[str, bool], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Start listening to audio stream and yield transcripts.

        Args:
            audio_stream: Async generator of audio chunks
            on_transcript: Callback for transcript updates (text, is_final)
            on_error: Callback for errors

        Yields:
            Transcript messages
        """
        if not self._is_connected:
            await self.connect()

        try:
            # Start audio task and message task concurrently
            audio_task = asyncio.create_task(self._send_audio_stream(audio_stream))

            # Process incoming messages
            async for message in self._receive_messages():
                msg_type = message.get("message")
                if msg_type in {"RecognitionResult", "AddPartialTranscript", "AddTranscript"}:
                    transcript_data = self._extract_transcript(message)
                    if not transcript_data["text"].strip():
                        continue

                    if on_transcript:
                        on_transcript(transcript_data["text"], transcript_data["is_final"])

                    yield transcript_data

        except ConnectionClosedError:
            logger.warning("Speechmatics connection closed")
            raise

        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            if on_error:
                on_error(e)
            raise

        finally:
            audio_task.cancel()
            await self.disconnect()

    async def _send_audio_stream(self, audio_stream: AsyncGenerator[bytes, None]) -> None:
        """Send audio data from stream to Speechmatics.

        Args:
            audio_stream: Async generator of audio chunks
        """
        try:
            async for audio_chunk in audio_stream:
                await self.send_audio(audio_chunk)

        except Exception as e:
            logger.error(f"Error in audio stream: {e}")
            raise

    async def _receive_messages(self) -> AsyncGenerator[dict[str, Any], None]:
        """Receive and parse messages from Speechmatics.

        Yields:
            Parsed message dictionaries
        """
        if not self._websocket:
            return

        try:
            async for raw_message in self._websocket:
                try:
                    message = json.loads(raw_message)

                    # Handle different message types
                    msg_type = message.get("message")

                    if msg_type in {"RecognitionResult", "AddPartialTranscript", "AddTranscript"}:
                        yield message

                    elif msg_type == "Warning":
                        logger.warning(f"Speechmatics warning: {message.get('description')}")

                    elif msg_type == "Error":
                        error_desc = message.get("description", "Unknown error")
                        logger.error(f"Speechmatics error: {error_desc}, full message: {message}")
                        raise RuntimeError(f"Speechmatics error: {error_desc}")

                    elif msg_type == "Info":
                        logger.debug(f"Speechmatics info: {message}")
                    elif msg_type in {"RecognitionStarted", "AudioAdded"}:
                        logger.debug(f"Speechmatics event: {msg_type}")
                    else:
                        # Log unknown message types for debugging
                        logger.warning(
                            f"Unknown Speechmatics message type: {msg_type}, full message: {message}"
                        )

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")

        except ConnectionClosed:
            logger.warning("Connection closed while receiving messages")
            raise

    async def _send_message(self, message: dict[str, Any]) -> None:
        """Send a message to Speechmatics.

        Args:
            message: Message dictionary
        """
        if not self._websocket:
            raise RuntimeError("Not connected to Speechmatics")

        try:
            await self._websocket.send(json.dumps(message))

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise

    def _extract_transcript(self, message: dict[str, Any]) -> dict[str, Any]:
        """Normalize transcript payloads across Speechmatics realtime message variants."""
        msg_type = message.get("message")
        metadata = message.get("metadata", {}) if isinstance(message.get("metadata"), dict) else {}
        results = message.get("results", []) if isinstance(message.get("results"), list) else []

        # Realtime v2 AddPartialTranscript/AddTranscript provide full segment text in metadata.transcript.
        text = str(metadata.get("transcript", "")).strip()
        if not text and results:
            # Fallback for older message shapes.
            parts: list[str] = []
            for result in results:
                alternatives = result.get("alternatives", []) if isinstance(result, dict) else []
                if alternatives and isinstance(alternatives[0], dict):
                    content = str(alternatives[0].get("content", ""))
                    if content:
                        parts.append(content)
            text = " ".join(parts).strip()

        confidences: list[float] = []
        for result in results:
            alternatives = result.get("alternatives", []) if isinstance(result, dict) else []
            if alternatives and isinstance(alternatives[0], dict):
                confidence = alternatives[0].get("confidence")
                if isinstance(confidence, (int, float)):
                    confidences.append(float(confidence))

        return {
            "text": text,
            "is_final": msg_type in {"AddTranscript", "RecognitionResult"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": max(confidences) if confidences else 0.0,
        }

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._is_connected

    def add_transcript_handler(self, handler: Callable) -> None:
        """Add a transcript event handler.

        Args:
            handler: Callback function for transcript events
        """
        self._transcript_handlers.append(handler)

    def add_error_handler(self, handler: Callable) -> None:
        """Add an error event handler.

        Args:
            handler: Callback function for error events
        """
        self._error_handlers.append(handler)


class SpeechmaticsSession:
    """Context manager for Speechmatics transcription sessions."""

    def __init__(
        self,
        api_key: str | None = None,
        language: str = "en",
    ) -> None:
        """Initialize session.

        Args:
            api_key: Speechmatics API key
            language: Language code
        """
        self.client = SpeechmaticsClient(api_key=api_key, language=language)
        self._transcripts: list[dict[str, Any]] = []

    async def __aenter__(self) -> "SpeechmaticsSession":
        """Enter session context."""
        await self.client.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit session context."""
        await self.client.disconnect()

    async def transcribe(
        self,
        audio_stream: AsyncGenerator[bytes, None],
    ) -> list[dict[str, Any]]:
        """Transcribe audio stream.

        Args:
            audio_stream: Async generator of audio chunks

        Returns:
            List of transcript dictionaries
        """
        self._transcripts.clear()

        async for transcript in self.client.start_listening(audio_stream):
            self._transcripts.append(transcript)

        return self._transcripts

    def get_final_transcript(self) -> str:
        """Get concatenated final transcript text.

        Returns:
            Complete transcript text
        """
        return " ".join(
            t["text"] for t in self._transcripts if t["is_final"]
        )

    def get_all_transcripts(self) -> list[dict[str, Any]]:
        """Get all transcripts received.

        Returns:
            List of transcript dictionaries
        """
        return self._transcripts.copy()


async def create_audio_stream(
    audio_data: bytes,
    chunk_size: int = 3200,
) -> AsyncGenerator[bytes, None]:
    """Create an async audio stream from bytes.

    Args:
        audio_data: Complete audio data
        chunk_size: Size of each chunk (default: 3200 = 100ms at 16kHz)

    Yields:
        Audio chunks
    """
    for i in range(0, len(audio_data), chunk_size):
        yield audio_data[i : i + chunk_size]
        await asyncio.sleep(0.01)  # Simulate real-time streaming


class SpeechmaticsPool:
    """Pool of Speechmatics clients for concurrent transcription."""

    def __init__(
        self,
        max_clients: int = 5,
        api_key: str | None = None,
    ) -> None:
        """Initialize pool.

        Args:
            max_clients: Maximum number of concurrent clients
            api_key: Speechmatics API key
        """
        self.max_clients = max_clients
        self.api_key = api_key or settings.speechmatics_api_key
        self._clients: dict[str, SpeechmaticsClient] = {}
        self._semaphore = asyncio.Semaphore(max_clients)

    async def get_client(
        self,
        session_id: str,
        language: str = "en",
    ) -> SpeechmaticsClient:
        """Get a client from the pool.

        Args:
            session_id: Unique session identifier
            language: Language code

        Returns:
            Speechmatics client
        """
        await self._semaphore.acquire()

        if session_id not in self._clients:
            self._clients[session_id] = SpeechmaticsClient(
                api_key=self.api_key,
                language=language,
            )

        return self._clients[session_id]

    async def release_client(self, session_id: str) -> None:
        """Release a client back to the pool.

        Args:
            session_id: Session identifier
        """
        if session_id in self._clients:
            client = self._clients[session_id]
            await client.disconnect()
            del self._clients[session_id]

        self._semaphore.release()

    async def cleanup_all(self) -> None:
        """Clean up all clients in the pool."""
        for session_id in list(self._clients.keys()):
            await self.release_client(session_id)
