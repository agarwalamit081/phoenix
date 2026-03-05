"""Audio processing utilities for voice interactions."""

import asyncio
import io
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Process audio data for speech recognition and synthesis."""

    # Supported audio configurations
    SAMPLE_RATES = [8000, 12000, 16000, 24000, 44100, 48000]
    CHANNELS = [1, 2]
    BIT_DEPTHS = [16, 24, 32]

    # Default configuration
    DEFAULT_SAMPLE_RATE = 16000
    DEFAULT_CHANNELS = 1
    DEFAULT_BIT_DEPTH = 16

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        bit_depth: int = DEFAULT_BIT_DEPTH,
    ) -> None:
        """Initialize audio processor.

        Args:
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels
            bit_depth: Bit depth per sample
        """
        if sample_rate not in self.SAMPLE_RATES:
            raise ValueError(f"Invalid sample rate: {sample_rate}")

        if channels not in self.CHANNELS:
            raise ValueError(f"Invalid channel count: {channels}")

        if bit_depth not in self.BIT_DEPTHS:
            raise ValueError(f"Invalid bit depth: {bit_depth}")

        self.sample_rate = sample_rate
        self.channels = channels
        self.bit_depth = bit_depth
        self.bytes_per_sample = bit_depth // 8
        self.frame_size = channels * self.bytes_per_sample

    def validate_audio(self, audio_data: bytes) -> bool:
        """Validate audio data format.

        Args:
            audio_data: Raw audio bytes

        Returns:
            True if valid
        """
        if not audio_data:
            return False

        # Check if data length is a multiple of frame size
        return len(audio_data) % self.frame_size == 0

    def convert_to_pcm16(
        self,
        audio_data: bytes,
        source_sample_rate: int | None = None,
        source_channels: int | None = None,
    ) -> bytes:
        """Convert audio to PCM 16-bit, 16kHz, mono format.

        Args:
            audio_data: Input audio bytes
            source_sample_rate: Original sample rate (if different)
            source_channels: Original channel count (if different)

        Returns:
            Converted audio bytes
        """
        try:
            # Convert to numpy array for processing
            dtype = np.int16 if self.bit_depth == 16 else np.int32
            audio_array = np.frombuffer(audio_data, dtype=dtype)

            # Resample if needed
            if source_sample_rate and source_sample_rate != self.sample_rate:
                audio_array = self._resample(
                    audio_array,
                    source_sample_rate,
                    self.sample_rate,
                )

            # Convert to mono if needed
            if source_channels and source_channels > 1:
                audio_array = self._to_mono(audio_array, source_channels)

            # Convert to 16-bit if needed
            if self.bit_depth != 16:
                audio_array = self._to_16bit(audio_array, self.bit_depth)

            return audio_array.tobytes()

        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            raise

    def _resample(
        self,
        audio_array: np.ndarray,
        from_rate: int,
        to_rate: int,
    ) -> np.ndarray:
        """Resample audio array.

        Args:
            audio_array: Input audio array
            from_rate: Source sample rate
            to_rate: Target sample rate

        Returns:
            Resampled audio array
        """
        # Simple linear interpolation resampling
        ratio = from_rate / to_rate
        new_length = int(len(audio_array) / ratio)

        indices = np.linspace(0, len(audio_array) - 1, new_length)
        return np.interp(indices, np.arange(len(audio_array)), audio_array).astype(audio_array.dtype)

    def _to_mono(
        self,
        audio_array: np.ndarray,
        channels: int,
    ) -> np.ndarray:
        """Convert multi-channel audio to mono.

        Args:
            audio_array: Input audio array
            channels: Number of channels

        Returns:
            Mono audio array
        """
        # Reshape and average channels
        reshaped = audio_array.reshape(-1, channels)
        return np.mean(reshaped, axis=1).astype(audio_array.dtype)

    def _to_16bit(
        self,
        audio_array: np.ndarray,
        source_bit_depth: int,
    ) -> np.ndarray:
        """Convert audio to 16-bit.

        Args:
            audio_array: Input audio array
            source_bit_depth: Source bit depth

        Returns:
            16-bit audio array
        """
        # Normalize to 16-bit range
        max_val = 2 ** (source_bit_depth - 1) - 1
        target_max = 2 ** 15 - 1

        normalized = audio_array.astype(np.float32) / max_val
        return (normalized * target_max).astype(np.int16)

    def split_audio(
        self,
        audio_data: bytes,
        chunk_duration_ms: int = 100,
    ) -> list[bytes]:
        """Split audio into chunks.

        Args:
            audio_data: Input audio bytes
            chunk_duration_ms: Chunk duration in milliseconds

        Returns:
            List of audio chunks
        """
        if not self.validate_audio(audio_data):
            raise ValueError("Invalid audio data")

        samples_per_chunk = (self.sample_rate * chunk_duration_ms) // 1000
        bytes_per_chunk = samples_per_chunk * self.frame_size

        chunks = []
        for i in range(0, len(audio_data), bytes_per_chunk):
            chunk = audio_data[i : i + bytes_per_chunk]

            # Pad last chunk if needed
            if len(chunk) < bytes_per_chunk:
                chunk += b"\x00" * (bytes_per_chunk - len(chunk))

            chunks.append(chunk)

        return chunks

    def calculate_duration(self, audio_data: bytes) -> float:
        """Calculate audio duration in seconds.

        Args:
            audio_data: Audio bytes

        Returns:
            Duration in seconds
        """
        total_samples = len(audio_data) // self.frame_size
        return total_samples / self.sample_rate

    def detect_silence(
        self,
        audio_data: bytes,
        threshold: float = 0.01,
        window_ms: int = 100,
    ) -> list[dict[str, Any]]:
        """Detect silence regions in audio.

        Args:
            audio_data: Audio bytes
            threshold: Silence threshold (0-1)
            window_ms: Analysis window size in milliseconds

        Returns:
            List of silence regions with start/end times
        """
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        audio_float = audio_array.astype(np.float32) / np.iinfo(np.int16).max

        window_size = (self.sample_rate * window_ms) // 1000
        silences = []

        in_silence = False
        silence_start = 0

        for i in range(0, len(audio_float), window_size):
            window = audio_float[i : i + window_size]
            rms = np.sqrt(np.mean(window**2))

            if rms < threshold:
                if not in_silence:
                    silence_start = i / self.sample_rate
                    in_silence = True
            else:
                if in_silence:
                    silence_end = i / self.sample_rate
                    silences.append({
                        "start": silence_start,
                        "end": silence_end,
                        "duration": silence_end - silence_start,
                    })
                    in_silence = False

        return silences

    def normalize_volume(
        self,
        audio_data: bytes,
        target_level: float = 0.9,
    ) -> bytes:
        """Normalize audio volume.

        Args:
            audio_data: Input audio bytes
            target_level: Target RMS level (0-1)

        Returns:
            Normalized audio bytes
        """
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        audio_float = audio_array.astype(np.float32)

        # Calculate current RMS
        rms = np.sqrt(np.mean(audio_float**2))

        if rms == 0:
            return audio_data

        # Calculate gain factor
        gain = target_level / rms

        # Apply gain with clipping protection
        normalized = np.clip(audio_float * gain, -32768, 32767).astype(np.int16)

        return normalized.tobytes()

    def apply_highpass_filter(
        self,
        audio_data: bytes,
        cutoff_freq: int = 80,
    ) -> bytes:
        """Apply high-pass filter to remove low-frequency noise.

        Args:
            audio_data: Input audio bytes
            cutoff_freq: Cutoff frequency in Hz

        Returns:
            Filtered audio bytes
        """
        # Simple RC high-pass filter
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        audio_float = audio_array.astype(np.float32)

        # Calculate filter coefficient
        rc = 1.0 / (cutoff_freq * 2 * np.pi)
        dt = 1.0 / self.sample_rate
        alpha = rc / (rc + dt)

        # Apply filter
        filtered = np.zeros_like(audio_float)
        filtered[0] = audio_float[0]

        for i in range(1, len(audio_float)):
            filtered[i] = alpha * (filtered[i - 1] + audio_float[i] - audio_float[i - 1])

        return filtered.astype(np.int16).tobytes()


class AudioBuffer:
    """Buffer for streaming audio data."""

    def __init__(
        self,
        max_size_seconds: float = 30.0,
        sample_rate: int = 16000,
        channels: int = 1,
        bit_depth: int = 16,
    ) -> None:
        """Initialize audio buffer.

        Args:
            max_size_seconds: Maximum buffer size in seconds
            sample_rate: Sample rate
            channels: Number of channels
            bit_depth: Bit depth
        """
        self.max_size = int(max_size_seconds * sample_rate * channels * (bit_depth // 8))
        self.buffer = bytearray()
        self.sample_rate = sample_rate
        self.channels = channels
        self.bit_depth = bit_depth

    def write(self, data: bytes) -> int:
        """Write data to buffer.

        Args:
            data: Audio data

        Returns:
            Number of bytes written
        """
        self.buffer.extend(data)

        # Trim if exceeding max size
        if len(self.buffer) > self.max_size:
            overflow = len(self.buffer) - self.max_size
            del self.buffer[:overflow]

        return len(data)

    def read(self, size: int) -> bytes:
        """Read data from buffer.

        Args:
            size: Number of bytes to read

        Returns:
            Audio data
        """
        if size >= len(self.buffer):
            data = bytes(self.buffer)
            self.buffer.clear()
            return data

        data = bytes(self.buffer[:size])
        del self.buffer[:size]
        return data

    def peek(self, size: int) -> bytes:
        """Peek at buffer without consuming.

        Args:
            size: Number of bytes to peek

        Returns:
            Audio data
        """
        if size >= len(self.buffer):
            return bytes(self.buffer)

        return bytes(self.buffer[:size])

    def clear(self) -> None:
        """Clear buffer."""
        self.buffer.clear()

    def get_duration(self) -> float:
        """Get buffered audio duration.

        Returns:
            Duration in seconds
        """
        bytes_per_sample = self.channels * (self.bit_depth // 8)
        total_samples = len(self.buffer) // bytes_per_sample
        return total_samples / self.sample_rate

    def is_empty(self) -> bool:
        """Check if buffer is empty.

        Returns:
            True if empty
        """
        return len(self.buffer) == 0

    def size(self) -> int:
        """Get buffer size.

        Returns:
            Number of bytes
        """
        return len(self.buffer)


async def create_audio_stream(
    audio_data: bytes,
    chunk_duration_ms: int = 100,
    sample_rate: int = 16000,
) -> AsyncGenerator[bytes, None]:
    """Create async audio stream from bytes.

    Args:
        audio_data: Complete audio data
        chunk_duration_ms: Duration of each chunk
        sample_rate: Sample rate

    Yields:
        Audio chunks
    """
    processor = AudioProcessor(sample_rate=sample_rate)
    chunks = processor.split_audio(audio_data, chunk_duration_ms)

    for chunk in chunks:
        yield chunk
        await asyncio.sleep(chunk_duration_ms / 1000.0)


class AudioMetrics:
    """Track audio processing metrics."""

    def __init__(self) -> None:
        """Initialize metrics tracker."""
        self.total_samples = 0
        self.total_duration = 0.0
        self.processing_times: list[float] = []
        self.error_count = 0
        self.start_time = datetime.now(timezone.utc)

    def record_processing(self, duration: float, samples: int) -> None:
        """Record processing metrics.

        Args:
            duration: Processing time in seconds
            samples: Number of samples processed
        """
        self.processing_times.append(duration)
        self.total_samples += samples
        self.total_duration += samples / 16000  # Assuming 16kHz

    def record_error(self) -> None:
        """Record an error."""
        self.error_count += 1

    def get_stats(self) -> dict[str, Any]:
        """Get statistics.

        Returns:
            Statistics dictionary
        """
        avg_time = np.mean(self.processing_times) if self.processing_times else 0

        return {
            "total_samples": self.total_samples,
            "total_duration_seconds": self.total_duration,
            "average_processing_time": avg_time,
            "error_count": self.error_count,
            "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds(),
        }
