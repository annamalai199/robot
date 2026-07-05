"""Text-to-Speech using Piper for local voice synthesis.

Provides streaming synthesis with en_US-lessac-medium voice.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Generator, Optional
from robot_assistant.config import config

logger = logging.getLogger(__name__)

# Global model path (lazy loaded)
_model_path: Optional[Path] = None


def _get_model_path() -> Path:
    """Get or locate the Piper model file.
    
    Returns:
        Path to the Piper model file (.onnx)
    
    Raises:
        FileNotFoundError: If model not found in expected locations
    """
    global _model_path
    
    if _model_path is not None and _model_path.exists():
        return _model_path
    
    # Check common installation locations
    possible_paths = [
        Path.home() / ".local/share/piper" / f"{config.TTS_VOICE}.onnx",
        Path("/usr/share/piper") / f"{config.TTS_VOICE}.onnx",
        Path("models") / f"{config.TTS_VOICE}.onnx",
        Path(config.TTS_VOICE + ".onnx"),
    ]
    
    for path in possible_paths:
        if path.exists():
            logger.info(f"Found Piper model at: {path}")
            _model_path = path
            return _model_path
    
    # If not found, provide helpful error message
    raise FileNotFoundError(
        f"Piper model not found: {config.TTS_VOICE}.onnx\n"
        f"Please download from: https://github.com/rhasspy/piper/releases\n"
        f"Or install via: pip install piper-tts && piper --download-dir ~/.local/share/piper --model {config.TTS_VOICE}"
    )


def synthesize(text: str, streaming: bool = True) -> bytes:
    """Synthesize speech from text using Piper.
    
    Args:
        text: Text to synthesize
        streaming: If True, use streaming mode (lower first-chunk latency)
    
    Returns:
        bytes: Raw audio data (16kHz, mono, 16-bit PCM)
    
    Example:
        >>> audio = synthesize("Hello, how can I help you?")
        >>> from robot_assistant.voice.audio_io import play_audio
        >>> play_audio(audio)
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for synthesis")
        return b''
    
    try:
        model_path = _get_model_path()
    except FileNotFoundError as e:
        logger.error(str(e))
        raise
    
    logger.info(f"Synthesizing text: '{text[:50]}...'")
    
    try:
        # Run Piper as subprocess
        # Output format: raw PCM (matches AUDIO_FORMAT from config)
        cmd = [
            "piper",
            "--model", str(model_path),
            "--output-raw",  # Raw PCM output (no WAV header)
        ]
        
        # Run synthesis
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False  # Binary mode for audio
        )
        
        # Send text and get audio
        audio_data, stderr = process.communicate(input=text.encode('utf-8'), timeout=10)
        
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='ignore')
            logger.error(f"Piper synthesis failed: {error_msg}")
            raise RuntimeError(f"Piper synthesis failed: {error_msg}")
        
        logger.info(f"Synthesis complete: {len(audio_data)} bytes")
        return audio_data
    
    except subprocess.TimeoutExpired:
        logger.error("Piper synthesis timed out")
        process.kill()
        raise TimeoutError("Speech synthesis timed out after 10 seconds")
    
    except FileNotFoundError:
        logger.error("Piper executable not found. Install via: pip install piper-tts")
        raise RuntimeError("Piper not installed. Run: pip install piper-tts")


def synthesize_stream(text: str) -> Generator[bytes, None, None]:
    """Synthesize speech with streaming output (yields chunks as they're generated).
    
    Allows playback to start before synthesis completes, reducing perceived latency.
    
    Args:
        text: Text to synthesize
    
    Yields:
        bytes: Audio chunks (16kHz, mono, 16-bit PCM)
    
    Example:
        >>> for chunk in synthesize_stream("Hello world"):
        ...     play_audio(chunk)  # Start playing immediately
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for streaming synthesis")
        return
    
    try:
        model_path = _get_model_path()
    except FileNotFoundError as e:
        logger.error(str(e))
        raise
    
    logger.info(f"Streaming synthesis: '{text[:50]}...'")
    
    try:
        # Run Piper with streaming output
        cmd = [
            "piper",
            "--model", str(model_path),
            "--output-raw",
        ]
        
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False
        )
        
        # Send text to stdin (non-blocking)
        if process.stdin:
            process.stdin.write(text.encode('utf-8'))
            process.stdin.close()
        
        # Read audio chunks from stdout
        chunk_size = config.AUDIO_CHUNK_SIZE * 2  # 2 bytes per sample (int16)
        
        while True:
            chunk = process.stdout.read(chunk_size)
            if not chunk:
                break
            yield chunk
        
        # Wait for process to complete
        process.wait(timeout=10)
        
        if process.returncode != 0:
            stderr = process.stderr.read().decode('utf-8', errors='ignore')
            logger.error(f"Piper streaming synthesis failed: {stderr}")
            raise RuntimeError(f"Piper synthesis failed: {stderr}")
        
        logger.info("Streaming synthesis complete")
    
    except subprocess.TimeoutExpired:
        logger.error("Piper streaming synthesis timed out")
        process.kill()
        raise TimeoutError("Speech synthesis timed out")
    
    except FileNotFoundError:
        logger.error("Piper executable not found")
        raise RuntimeError("Piper not installed. Run: pip install piper-tts")


def check_piper_available() -> bool:
    """Check if Piper is installed and model is available.
    
    Returns:
        bool: True if Piper can be used, False otherwise
    """
    try:
        # Check if piper executable exists
        result = subprocess.run(
            ["piper", "--version"],
            capture_output=True,
            timeout=5
        )
        if result.returncode != 0:
            return False
        
        # Check if model exists
        _get_model_path()
        return True
    
    except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError):
        return False
