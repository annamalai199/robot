"""Voice module for speech-to-text and text-to-speech.

Components:
- audio_io: Mic/speaker I/O using PyAudio
- stt: Speech-to-text using faster-whisper
- tts: Text-to-speech using Piper
"""

# Lazy imports - modules are imported when accessed to avoid dependency issues
__all__ = ['audio_io', 'stt', 'tts']
