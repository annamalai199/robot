"""Speech-to-Text using faster-whisper for local transcription.

Provides streaming transcription from audio generator with VAD-based
silence detection for automatic stopping.
"""

import logging
from typing import Generator, Optional
import numpy as np
from faster_whisper import WhisperModel
from robot_assistant.config import config

logger = logging.getLogger(__name__)

# Global model instance (loaded once on first use)
_model: Optional[WhisperModel] = None


def _get_model() -> WhisperModel:
    """Get or initialize the Whisper model (lazy loading).
    
    Returns:
        Initialized WhisperModel instance.
    """
    global _model
    
    if _model is None:
        logger.info(f"Loading faster-whisper model: {config.STT_MODEL}")
        _model = WhisperModel(
            config.STT_MODEL,
            device=config.STT_DEVICE,
            compute_type="int8"  # Quantized for faster CPU inference
        )
        logger.info("Whisper model loaded successfully")
    
    return _model


def transcribe_stream(audio_generator: Generator[bytes, None, None], 
                     language: str = None,
                     vad_threshold: float = 0.5,
                     silence_duration_ms: int = 2000) -> str:
    """Transcribe audio from a stream generator with VAD-based stopping.
    
    Processes audio chunks from generator, accumulating until silence is
    detected via Voice Activity Detection (VAD). Returns final transcript.
    
    Args:
        audio_generator: Generator yielding audio chunks (bytes, 16kHz mono PCM)
        language: Optional language code (e.g., 'en'). If None, auto-detect.
        vad_threshold: VAD sensitivity (0.0-1.0, higher = more aggressive)
        silence_duration_ms: Silence duration to trigger stop (milliseconds)
    
    Returns:
        str: Final transcription text
    
    Example:
        >>> from robot_assistant.voice.audio_io import capture_audio
        >>> audio_gen = capture_audio(duration_seconds=10)
        >>> transcript = transcribe_stream(audio_gen)
        >>> print(transcript)
        "Hello, how can I help you?"
    """
    model = _get_model()
    
    # Accumulate audio chunks
    audio_chunks = []
    total_frames = 0
    
    logger.info("Starting streaming transcription...")
    
    try:
        for chunk in audio_generator:
            audio_chunks.append(chunk)
            total_frames += len(chunk) // 2  # 2 bytes per sample (int16)
            
            # Check if we have enough audio (at least 1 second before attempting transcription)
            duration_seconds = total_frames / config.AUDIO_SAMPLE_RATE
            
            if duration_seconds >= 1.0:
                # Simple silence detection: check recent chunk energy
                # Convert last chunk to numpy array for analysis
                recent_audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                energy = np.sqrt(np.mean(recent_audio ** 2))
                
                # If energy is very low, consider it silence
                if energy < vad_threshold and duration_seconds >= 2.0:
                    logger.debug(f"Silence detected (energy={energy:.4f}), stopping capture")
                    break
            
            # Safety limit: stop after 30 seconds to prevent infinite capture
            if duration_seconds >= 30.0:
                logger.warning("Reached 30-second capture limit, stopping")
                break
    
    except StopIteration:
        pass  # Generator exhausted normally
    
    # Combine all chunks into single audio buffer
    audio_data = b''.join(audio_chunks)
    
    if len(audio_data) == 0:
        logger.warning("No audio data captured")
        return ""
    
    # Convert bytes to numpy array (float32 normalized to [-1, 1])
    audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    
    duration = len(audio_array) / config.AUDIO_SAMPLE_RATE
    logger.info(f"Transcribing {duration:.2f}s of audio...")
    
    # Transcribe with faster-whisper
    segments, info = model.transcribe(
        audio_array,
        language=language or config.STT_LANGUAGE,
        vad_filter=True,  # Use built-in VAD for better segmentation
        vad_parameters={
            "threshold": vad_threshold,
            "min_silence_duration_ms": silence_duration_ms
        }
    )
    
    # Combine all segments into final transcript
    transcript_parts = []
    for segment in segments:
        transcript_parts.append(segment.text.strip())
    
    final_transcript = " ".join(transcript_parts).strip()
    
    logger.info(f"Transcription complete: '{final_transcript[:100]}...'")
    
    return final_transcript


def transcribe_audio(audio_bytes: bytes, language: str = None) -> str:
    """Transcribe audio from raw bytes (non-streaming, simpler interface).
    
    Args:
        audio_bytes: Raw audio data (16kHz, mono, 16-bit PCM)
        language: Optional language code (e.g., 'en'). If None, auto-detect.
    
    Returns:
        str: Transcription text
    
    Example:
        >>> audio_data = record_audio()
        >>> transcript = transcribe_audio(audio_data)
    """
    model = _get_model()
    
    # Convert bytes to numpy array
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    duration = len(audio_array) / config.AUDIO_SAMPLE_RATE
    logger.info(f"Transcribing {duration:.2f}s of audio...")
    
    # Transcribe
    segments, info = model.transcribe(
        audio_array,
        language=language or config.STT_LANGUAGE,
        vad_filter=True
    )
    
    # Combine segments
    transcript_parts = []
    for segment in segments:
        transcript_parts.append(segment.text.strip())
    
    final_transcript = " ".join(transcript_parts).strip()
    
    logger.info(f"Transcription complete: '{final_transcript[:100]}...'")
    
    return final_transcript


def check_model_available() -> bool:
    """Check if the Whisper model can be loaded.
    
    Returns:
        bool: True if model loads successfully, False otherwise
    """
    try:
        _get_model()
        return True
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {str(e)}")
        return False
