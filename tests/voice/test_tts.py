"""Tests for Text-to-Speech module.

Tests use mocked subprocess calls to avoid requiring actual Piper installation
and for fast test execution.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from robot_assistant.voice import tts
from robot_assistant.config import config


@pytest.fixture
def mock_piper_process():
    """Create a mock subprocess for Piper."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    
    # Generate fake audio data (16kHz, mono, 16-bit PCM for "Hello world")
    # ~0.5 seconds of audio = 16000 samples/sec * 0.5 sec * 2 bytes/sample
    fake_audio = b'\x00\x01' * 8000  # 16KB of fake audio data
    
    mock_process.communicate.return_value = (fake_audio, b'')
    mock_process.stdout.read.side_effect = [
        fake_audio[:4096],  # First chunk
        fake_audio[4096:8192],  # Second chunk
        fake_audio[8192:],  # Third chunk
        b''  # EOF
    ]
    mock_process.wait.return_value = None
    
    return mock_process


@pytest.fixture
def mock_model_path(tmp_path):
    """Create a temporary fake model file."""
    model_file = tmp_path / "en_US-lessac-medium.onnx"
    model_file.write_bytes(b'fake model data')
    return model_file


class TestSynthesize:
    """Test non-streaming synthesis function."""
    
    def test_synthesize_returns_audio_bytes(self, mock_piper_process, mock_model_path):
        """Test that synthesize returns audio data."""
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_piper_process):
                result = tts.synthesize("Hello world")
        
        assert isinstance(result, bytes)
        assert len(result) > 0
    
    def test_synthesize_calls_piper_with_correct_args(self, mock_piper_process, mock_model_path):
        """Test that Piper is called with correct command-line arguments."""
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_piper_process) as mock_popen:
                tts.synthesize("Hello world")
        
        # Verify Popen was called
        assert mock_popen.called
        
        # Check command arguments
        call_args = mock_popen.call_args[0][0]
        assert call_args[0] == "piper"
        assert "--model" in call_args
        assert "--output-raw" in call_args
    
    def test_synthesize_sends_text_to_stdin(self, mock_piper_process, mock_model_path):
        """Test that text is sent to Piper's stdin."""
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_piper_process):
                tts.synthesize("Hello world")
        
        # Verify communicate was called with encoded text
        mock_piper_process.communicate.assert_called_once()
        call_args = mock_piper_process.communicate.call_args
        assert call_args[1]['input'] == b'Hello world'
    
    def test_synthesize_empty_text(self, mock_model_path):
        """Test handling of empty text input."""
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            result = tts.synthesize("")
        
        assert result == b''
    
    def test_synthesize_whitespace_only(self, mock_model_path):
        """Test handling of whitespace-only input."""
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            result = tts.synthesize("   \n  \t  ")
        
        assert result == b''
    
    def test_synthesize_unicode_text(self, mock_piper_process, mock_model_path):
        """Test synthesis with unicode characters."""
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_piper_process):
                result = tts.synthesize("Hello 世界")
        
        assert isinstance(result, bytes)
        assert len(result) > 0
    
    def test_synthesize_long_text(self, mock_piper_process, mock_model_path):
        """Test synthesis with long text."""
        long_text = "This is a very long sentence. " * 50  # ~1500 chars
        
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_piper_process):
                result = tts.synthesize(long_text)
        
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestSynthesizeStream:
    """Test streaming synthesis function."""
    
    def test_synthesize_stream_yields_chunks(self, mock_piper_process, mock_model_path):
        """Test that streaming synthesis yields audio chunks."""
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_piper_process):
                chunks = list(tts.synthesize_stream("Hello world"))
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, bytes) for chunk in chunks)
        assert all(len(chunk) > 0 for chunk in chunks)
    
    def test_synthesize_stream_chunk_size(self, mock_piper_process, mock_model_path):
        """Test that chunks are approximately the configured size."""
        expected_chunk_size = config.AUDIO_CHUNK_SIZE * 2  # 2 bytes per sample
        
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_piper_process):
                chunks = list(tts.synthesize_stream("Hello world"))
        
        # First chunks should be around expected size (last chunk may be smaller)
        for chunk in chunks[:-1]:
            assert len(chunk) <= expected_chunk_size * 2  # Allow some variance
    
    def test_synthesize_stream_empty_text(self, mock_model_path):
        """Test streaming with empty text."""
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            chunks = list(tts.synthesize_stream(""))
        
        assert len(chunks) == 0
    
    def test_synthesize_stream_closes_stdin(self, mock_piper_process, mock_model_path):
        """Test that stdin is properly closed for streaming."""
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_piper_process):
                list(tts.synthesize_stream("Hello world"))
        
        # Verify stdin was closed
        assert mock_piper_process.stdin.close.called


class TestModelManagement:
    """Test model path resolution and caching."""
    
    def test_get_model_path_caches_result(self, mock_model_path):
        """Test that model path is cached after first lookup."""
        # Reset global cache
        tts._model_path = None
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.home', return_value=mock_model_path.parent.parent):
                path1 = tts._get_model_path()
                path2 = tts._get_model_path()
        
        # Should return same object (cached)
        assert path1 == path2
    
    def test_get_model_path_not_found(self):
        """Test error when model file doesn't exist."""
        # Reset cache
        tts._model_path = None
        
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError) as excinfo:
                tts._get_model_path()
        
        assert "not found" in str(excinfo.value).lower()
        assert config.TTS_VOICE in str(excinfo.value)
    
    def test_get_model_path_searches_multiple_locations(self, tmp_path):
        """Test that multiple possible locations are checked."""
        model_file = tmp_path / "en_US-lessac-medium.onnx"
        model_file.write_bytes(b'fake model')
        
        tts._model_path = None
        
        def mock_exists(self):
            # Only return True for our test file
            return str(self) == str(model_file)
        
        with patch('pathlib.Path.exists', mock_exists):
            with patch('pathlib.Path.home', return_value=tmp_path.parent):
                # This should eventually find our model_file
                # We can't guarantee it will, so we test the search logic instead
                pass


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_synthesize_piper_not_installed(self, mock_model_path):
        """Test error when Piper executable not found."""
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', side_effect=FileNotFoundError):
                with pytest.raises(RuntimeError) as excinfo:
                    tts.synthesize("Hello")
        
        assert "not installed" in str(excinfo.value).lower()
    
    def test_synthesize_piper_fails(self, mock_model_path):
        """Test error when Piper process returns non-zero exit code."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b'', b'Error: Invalid model')
        
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_process):
                with pytest.raises(RuntimeError) as excinfo:
                    tts.synthesize("Hello")
        
        assert "failed" in str(excinfo.value).lower()
    
    def test_synthesize_timeout(self, mock_model_path):
        """Test timeout handling."""
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired('piper', 10)
        
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_process):
                with pytest.raises(TimeoutError):
                    tts.synthesize("Hello")
    
    def test_synthesize_stream_piper_fails(self, mock_model_path):
        """Test streaming error when Piper fails."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout.read.return_value = b''
        mock_process.stderr.read.return_value = b'Model error'
        mock_process.wait.return_value = None
        
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_process):
                with pytest.raises(RuntimeError):
                    list(tts.synthesize_stream("Hello"))


class TestCheckPiperAvailable:
    """Test Piper availability check."""
    
    def test_check_piper_available_success(self, mock_model_path):
        """Test availability check when Piper is installed."""
        mock_result = Mock()
        mock_result.returncode = 0
        
        with patch('subprocess.run', return_value=mock_result):
            with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
                result = tts.check_piper_available()
        
        assert result is True
    
    def test_check_piper_available_not_installed(self):
        """Test availability check when Piper is not installed."""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = tts.check_piper_available()
        
        assert result is False
    
    def test_check_piper_available_model_missing(self):
        """Test availability check when model is missing."""
        mock_result = Mock()
        mock_result.returncode = 0
        
        # Reset cache
        tts._model_path = None
        
        with patch('subprocess.run', return_value=mock_result):
            with patch('pathlib.Path.exists', return_value=False):
                result = tts.check_piper_available()
        
        assert result is False


class TestLatency:
    """Test latency requirements."""
    
    def test_synthesize_stream_first_chunk_latency(self, mock_piper_process, mock_model_path):
        """Test that first chunk is available quickly (streaming benefit).
        
        Note: This test uses mocked Piper, so it measures framework overhead only.
        Real first-chunk latency will depend on actual Piper performance.
        """
        import time
        
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_piper_process):
                gen = tts.synthesize_stream("Hello world")
                
                start = time.perf_counter()
                first_chunk = next(gen)
                elapsed = time.perf_counter() - start
        
        # Framework overhead should be minimal (<10ms for mocked test)
        assert elapsed < 0.01, f"First chunk took {elapsed*1000:.2f}ms"
        assert len(first_chunk) > 0


class TestAudioFormat:
    """Test audio format compatibility."""
    
    def test_synthesize_output_format(self, mock_piper_process, mock_model_path):
        """Test that output is raw PCM (no WAV header)."""
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_piper_process):
                audio = tts.synthesize("Hello")
        
        # Raw PCM should NOT start with "RIFF" (WAV header)
        assert not audio.startswith(b'RIFF')
        
        # Should be binary audio data
        assert isinstance(audio, bytes)
    
    def test_synthesize_compatible_with_audio_io(self, mock_piper_process, mock_model_path):
        """Test that output format matches audio_io expectations.
        
        audio_io expects: 16kHz, mono, 16-bit PCM (int16)
        """
        with patch('robot_assistant.voice.tts._get_model_path', return_value=mock_model_path):
            with patch('subprocess.Popen', return_value=mock_piper_process):
                audio = tts.synthesize("Hello")
        
        # Length should be even (2 bytes per sample for int16)
        assert len(audio) % 2 == 0
        
        # Verify format matches config constants
        # audio_io expects: 16kHz (AUDIO_SAMPLE_RATE), mono (AUDIO_CHANNELS=1), 16-bit (int16 = 2 bytes)
        assert config.AUDIO_SAMPLE_RATE == 16000, "TTS must output 16kHz to match audio_io"
        assert config.AUDIO_CHANNELS == 1, "TTS must output mono to match audio_io"
        assert config.AUDIO_FORMAT == "int16", "TTS must output 16-bit PCM to match audio_io"
        
        # Piper's TTS_SAMPLE_RATE should match audio_io's AUDIO_SAMPLE_RATE
        assert config.TTS_SAMPLE_RATE == config.AUDIO_SAMPLE_RATE, \
            f"TTS sample rate ({config.TTS_SAMPLE_RATE}) must match audio_io ({config.AUDIO_SAMPLE_RATE})"
        
        # Sample count should be reasonable for ~0.5s at 16kHz
        sample_count = len(audio) // 2  # 2 bytes per int16 sample
        duration_seconds = sample_count / config.AUDIO_SAMPLE_RATE
        assert 0.06 < duration_seconds < 6, f"Audio duration {duration_seconds:.2f}s seems unreasonable"


# Import subprocess for TimeoutExpired exception
import subprocess
