"""Tests for Speech-to-Text module.

Tests use synthetic audio and mocked Whisper model to ensure fast execution
without requiring actual model downloads or long inference times.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from robot_assistant.voice import stt
from robot_assistant.config import config


@pytest.fixture
def mock_whisper_model():
    """Create a mock WhisperModel for testing."""
    mock_model = MagicMock()
    
    # Mock transcribe response
    mock_segment = Mock()
    mock_segment.text = "Hello world"
    
    mock_info = Mock()
    mock_info.language = "en"
    
    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    
    return mock_model


@pytest.fixture
def synthetic_audio_bytes():
    """Generate synthetic audio bytes for testing (16kHz, mono, 16-bit PCM)."""
    # Generate 1 second of sine wave audio
    duration = 1.0
    sample_rate = config.AUDIO_SAMPLE_RATE
    frequency = 440.0  # A4 note
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio = np.sin(2 * np.pi * frequency * t)
    
    # Convert to 16-bit PCM
    audio_int16 = (audio * 32767).astype(np.int16)
    
    return audio_int16.tobytes()


@pytest.fixture
def audio_generator(synthetic_audio_bytes):
    """Create a generator yielding audio chunks."""
    chunk_size = config.AUDIO_CHUNK_SIZE * 2  # 2 bytes per sample
    
    def gen():
        for i in range(0, len(synthetic_audio_bytes), chunk_size):
            yield synthetic_audio_bytes[i:i + chunk_size]
    
    return gen()


class TestTranscribeStream:
    """Test streaming transcription function."""
    
    def test_transcribe_stream_returns_text(self, mock_whisper_model, audio_generator):
        """Test that transcribe_stream returns transcribed text."""
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            result = stt.transcribe_stream(audio_generator)
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert result == "Hello world"
    
    def test_transcribe_stream_calls_model(self, mock_whisper_model, audio_generator):
        """Test that Whisper model is called with correct parameters."""
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            stt.transcribe_stream(audio_generator, language='en')
        
        # Verify model.transcribe was called
        assert mock_whisper_model.transcribe.called
        
        # Check arguments
        call_args = mock_whisper_model.transcribe.call_args
        assert call_args[1]['language'] == 'en'
        assert call_args[1]['vad_filter'] is True
    
    def test_transcribe_stream_empty_audio(self, mock_whisper_model):
        """Test handling of empty audio generator."""
        def empty_gen():
            return
            yield  # Never yields
        
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            result = stt.transcribe_stream(empty_gen())
        
        assert result == ""
        # Model should not be called with empty audio
        assert not mock_whisper_model.transcribe.called
    
    def test_transcribe_stream_multiple_segments(self, mock_whisper_model, audio_generator):
        """Test combining multiple segments into single transcript."""
        # Mock multiple segments
        segment1 = Mock()
        segment1.text = "Hello"
        segment2 = Mock()
        segment2.text = "world"
        
        mock_info = Mock()
        mock_whisper_model.transcribe.return_value = ([segment1, segment2], mock_info)
        
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            result = stt.transcribe_stream(audio_generator)
        
        assert result == "Hello world"
    
    def test_transcribe_stream_strips_whitespace(self, mock_whisper_model, audio_generator):
        """Test that segments are stripped of extra whitespace."""
        segment = Mock()
        segment.text = "  Hello world  \n"
        
        mock_info = Mock()
        mock_whisper_model.transcribe.return_value = ([segment], mock_info)
        
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            result = stt.transcribe_stream(audio_generator)
        
        assert result == "Hello world"
    
    def test_transcribe_stream_custom_vad_threshold(self, mock_whisper_model, audio_generator):
        """Test custom VAD threshold parameter."""
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            stt.transcribe_stream(audio_generator, vad_threshold=0.7)
        
        call_args = mock_whisper_model.transcribe.call_args
        assert call_args[1]['vad_parameters']['threshold'] == 0.7
    
    def test_transcribe_stream_custom_silence_duration(self, mock_whisper_model, audio_generator):
        """Test custom silence duration parameter."""
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            stt.transcribe_stream(audio_generator, silence_duration_ms=3000)
        
        call_args = mock_whisper_model.transcribe.call_args
        assert call_args[1]['vad_parameters']['min_silence_duration_ms'] == 3000


class TestTranscribeAudio:
    """Test non-streaming transcription function."""
    
    def test_transcribe_audio_returns_text(self, mock_whisper_model, synthetic_audio_bytes):
        """Test transcribe_audio with raw bytes."""
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            result = stt.transcribe_audio(synthetic_audio_bytes)
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert result == "Hello world"
    
    def test_transcribe_audio_with_language(self, mock_whisper_model, synthetic_audio_bytes):
        """Test language parameter."""
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            stt.transcribe_audio(synthetic_audio_bytes, language='es')
        
        call_args = mock_whisper_model.transcribe.call_args
        assert call_args[1]['language'] == 'es'
    
    def test_transcribe_audio_empty_bytes(self, mock_whisper_model):
        """Test handling of empty audio bytes."""
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            result = stt.transcribe_audio(b'')
        
        # Should still attempt transcription with empty array
        assert mock_whisper_model.transcribe.called


class TestModelManagement:
    """Test model loading and management."""
    
    def test_get_model_loads_once(self, mock_whisper_model):
        """Test that model is loaded only once (singleton pattern)."""
        with patch('robot_assistant.voice.stt.WhisperModel', return_value=mock_whisper_model) as mock_constructor:
            # Reset global model
            stt._model = None
            
            # Call multiple times
            model1 = stt._get_model()
            model2 = stt._get_model()
            
            # Constructor should be called only once
            assert mock_constructor.call_count == 1
            assert model1 is model2
    
    def test_check_model_available_success(self, mock_whisper_model):
        """Test check_model_available returns True when model loads."""
        with patch('robot_assistant.voice.stt.WhisperModel', return_value=mock_whisper_model):
            stt._model = None
            result = stt.check_model_available()
        
        assert result is True
    
    def test_check_model_available_failure(self):
        """Test check_model_available returns False on error."""
        with patch('robot_assistant.voice.stt.WhisperModel', side_effect=Exception("Model not found")):
            stt._model = None
            result = stt.check_model_available()
        
        assert result is False


class TestLatency:
    """Test latency requirements."""
    
    def test_transcribe_stream_latency_under_2s(self, mock_whisper_model, audio_generator):
        """Test that transcription completes in reasonable time.
        
        Note: This test uses mocked model, so it tests the framework overhead
        only, not actual model inference time.
        """
        import time
        
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            start = time.perf_counter()
            stt.transcribe_stream(audio_generator)
            elapsed = time.perf_counter() - start
        
        # Mocked test should be very fast (<100ms)
        assert elapsed < 0.1, f"Transcription took {elapsed*1000:.2f}ms (framework overhead)"


class TestAudioProcessing:
    """Test audio data processing and conversion."""
    
    def test_audio_bytes_to_numpy_conversion(self, mock_whisper_model, synthetic_audio_bytes):
        """Test that audio bytes are correctly converted to numpy array."""
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            stt.transcribe_audio(synthetic_audio_bytes)
        
        # Check that transcribe was called with numpy array
        call_args = mock_whisper_model.transcribe.call_args
        audio_array = call_args[0][0]
        
        assert isinstance(audio_array, np.ndarray)
        assert audio_array.dtype == np.float32
        # Values should be normalized to [-1, 1]
        assert audio_array.min() >= -1.0
        assert audio_array.max() <= 1.0
    
    def test_correct_sample_rate_assumed(self, mock_whisper_model, synthetic_audio_bytes):
        """Test that correct sample rate is used for duration calculation."""
        # Create 2-second audio
        duration = 2.0
        sample_rate = config.AUDIO_SAMPLE_RATE
        num_samples = int(sample_rate * duration)
        
        audio = np.zeros(num_samples, dtype=np.int16)
        audio_bytes = audio.tobytes()
        
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            stt.transcribe_audio(audio_bytes)
        
        # Verify correct array length was passed
        call_args = mock_whisper_model.transcribe.call_args
        audio_array = call_args[0][0]
        
        # Should match expected number of samples
        assert len(audio_array) == num_samples


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_very_short_audio(self, mock_whisper_model):
        """Test handling of very short audio (< 1 second)."""
        # 0.1 second of audio
        short_audio = np.zeros(config.AUDIO_SAMPLE_RATE // 10, dtype=np.int16)
        audio_bytes = short_audio.tobytes()
        
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            result = stt.transcribe_audio(audio_bytes)
        
        # Should still work with short audio
        assert isinstance(result, str)
    
    def test_no_speech_in_audio(self, mock_whisper_model):
        """Test handling of audio with no speech (silence)."""
        # Mock empty segments (no speech detected)
        mock_info = Mock()
        mock_whisper_model.transcribe.return_value = ([], mock_info)
        
        silence = np.zeros(config.AUDIO_SAMPLE_RATE, dtype=np.int16)
        audio_bytes = silence.tobytes()
        
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            result = stt.transcribe_audio(audio_bytes)
        
        assert result == ""
    
    def test_unicode_in_transcript(self, mock_whisper_model, synthetic_audio_bytes):
        """Test handling of unicode characters in transcript."""
        segment = Mock()
        segment.text = "Hello 你好 مرحبا"
        
        mock_info = Mock()
        mock_whisper_model.transcribe.return_value = ([segment], mock_info)
        
        with patch('robot_assistant.voice.stt._get_model', return_value=mock_whisper_model):
            result = stt.transcribe_audio(synthetic_audio_bytes)
        
        assert result == "Hello 你好 مرحبا"
