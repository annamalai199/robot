"""Audio I/O for microphone capture and speaker playback using PyAudio.

Provides generator-based microphone streaming and blocking speaker playback.
All audio is 16kHz, mono, 16-bit PCM format for compatibility with STT/TTS.
"""

import pyaudio
import logging
from typing import Generator
from robot_assistant.config import config

logger = logging.getLogger(__name__)


def capture_audio(duration_seconds: float = None, device_index: int = None) -> Generator[bytes, None, None]:
    """Capture audio from microphone as a generator of audio chunks.
    
    Yields audio chunks (1024 frames each) from the default microphone.
    Continues until duration_seconds elapsed (if specified) or caller stops iteration.
    
    Args:
        duration_seconds: Optional duration limit. If None, captures indefinitely until stopped.
        device_index: Optional microphone device index. If None, uses system default.
    
    Yields:
        bytes: Audio data chunks (1024 frames * 2 bytes/frame = 2048 bytes per chunk)
    
    Example:
        >>> for audio_chunk in capture_audio(duration_seconds=5):
        ...     process(audio_chunk)  # Process each chunk as it arrives
    """
    audio = pyaudio.PyAudio()
    
    try:
        # Open microphone stream
        stream = audio.open(
            format=pyaudio.paInt16,  # 16-bit PCM
            channels=config.AUDIO_CHANNELS,  # Mono
            rate=config.AUDIO_SAMPLE_RATE,  # 16kHz
            input=True,
            input_device_index=device_index,
            frames_per_buffer=config.AUDIO_CHUNK_SIZE  # 1024 frames
        )
        
        logger.info(f"Microphone capture started (16kHz, mono, 16-bit PCM)")
        
        if duration_seconds is not None:
            # Calculate total chunks needed
            chunks_needed = int((duration_seconds * config.AUDIO_SAMPLE_RATE) / config.AUDIO_CHUNK_SIZE)
            
            for _ in range(chunks_needed):
                data = stream.read(config.AUDIO_CHUNK_SIZE, exception_on_overflow=False)
                yield data
        else:
            # Capture indefinitely until caller stops
            while True:
                data = stream.read(config.AUDIO_CHUNK_SIZE, exception_on_overflow=False)
                yield data
                
    except Exception as e:
        logger.error(f"Microphone capture error: {str(e)}")
        raise
    finally:
        if 'stream' in locals():
            stream.stop_stream()
            stream.close()
        audio.terminate()
        logger.info("Microphone capture stopped")


def play_audio(audio_bytes: bytes, device_index: int = None) -> None:
    """Play audio through speaker (blocking).
    
    Plays the entire audio buffer through the default speaker.
    Blocks until playback completes.
    
    Args:
        audio_bytes: Audio data to play (16kHz, mono, 16-bit PCM format)
        device_index: Optional speaker device index. If None, uses system default.
    
    Example:
        >>> audio_data = synthesize_speech("Hello world")
        >>> play_audio(audio_data)  # Plays and blocks until done
    """
    audio = pyaudio.PyAudio()
    
    try:
        # Open speaker stream
        stream = audio.open(
            format=pyaudio.paInt16,  # 16-bit PCM
            channels=config.AUDIO_CHANNELS,  # Mono
            rate=config.AUDIO_SAMPLE_RATE,  # 16kHz
            output=True,
            output_device_index=device_index
        )
        
        logger.info(f"Playing audio ({len(audio_bytes)} bytes)")
        
        # Write audio data in chunks
        chunk_size = config.AUDIO_CHUNK_SIZE * 2  # 1024 frames * 2 bytes/sample
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i:i + chunk_size]
            stream.write(chunk)
        
        logger.info("Audio playback complete")
        
    except Exception as e:
        logger.error(f"Audio playback error: {str(e)}")
        raise
    finally:
        if 'stream' in locals():
            stream.stop_stream()
            stream.close()
        audio.terminate()


def list_audio_devices() -> dict:
    """List all available audio input and output devices.
    
    Returns:
        dict with 'input' and 'output' keys, each containing list of device info dicts.
        Each device info has: index, name, channels, sample_rate.
    
    Example:
        >>> devices = list_audio_devices()
        >>> print(devices['input'][0])
        {'index': 0, 'name': 'Microphone (Realtek)', 'channels': 2, 'sample_rate': 44100}
    """
    audio = pyaudio.PyAudio()
    
    try:
        input_devices = []
        output_devices = []
        
        for i in range(audio.get_device_count()):
            device_info = audio.get_device_info_by_index(i)
            
            # Use .get() with default to handle None values from virtual/disabled devices
            max_input = device_info.get('maxInputChannels') or 0
            max_output = device_info.get('maxOutputChannels') or 0
            
            device_data = {
                'index': i,
                'name': device_info.get('name'),
                'channels': max_input if max_input > 0 else max_output,
                'sample_rate': int(device_info.get('defaultSampleRate', 0))
            }
            
            if max_input > 0:
                input_devices.append(device_data)
            
            if max_output > 0:
                output_devices.append(device_data)
        
        return {
            'input': input_devices,
            'output': output_devices
        }
        
    finally:
        audio.terminate()


def get_default_device_indices() -> dict:
    """Get default input and output device indices.
    
    Returns:
        dict with 'input' and 'output' keys containing default device indices.
    
    Example:
        >>> defaults = get_default_device_indices()
        >>> print(f"Default mic: {defaults['input']}, Default speaker: {defaults['output']}")
    """
    audio = pyaudio.PyAudio()
    
    try:
        default_input = audio.get_default_input_device_info()
        default_output = audio.get_default_output_device_info()
        
        return {
            'input': default_input.get('index'),
            'output': default_output.get('index')
        }
        
    finally:
        audio.terminate()
