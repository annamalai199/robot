"""Tests for Audio I/O module.

Tests use mocked PyAudio to avoid requiring actual audio hardware.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from robot_assistant.voice import audio_io
from robot_assistant.config import config


@pytest.fixture
def mock_pyaudio():
    """Create a mock PyAudio instance."""
    mock_pa = MagicMock()
    mock_stream = MagicMock()
    
    # Mock stream.read() to return fake audio data
    mock_stream.read.return_value = b'\x00\x01' * config.AUDIO_CHUNK_SIZE
    mock_stream.is_active.return_value = True
    
    mock_pa.return_value.open.return_value = mock_stream
    mock_pa.return_value.get_default_input_device_info.return_value = {'index': 0, 'name': 'Default Mic'}
    mock_pa.return_value.get_default_output_device_info.return_value = {'index': 1, 'name': 'Default Speaker'}
    mock_pa.return_value.get_device_count.return_value = 2
    mock_pa.return_value.get_device_info_by_index.side_effect = [
        {'index': 0, 'name': 'Microphone', 'maxInputChannels': 2, 'maxOutputChannels': 0, 'defaultSampleRate': 44100.0},
        {'index': 1, 'name': 'Speaker', 'maxInputChannels': 0, 'maxOutputChannels': 2, 'defaultSampleRate': 44100.0}
    ]
    
    return mock_pa


class TestCaptureAudio:
    """Test audio capture function."""
    
    def test_capture_audio_returns_generator(self, mock_pyaudio):
        """Test that capture_audio returns a generator yielding bytes."""
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pyaudio):
            gen = audio_io.capture_audio(duration_seconds=1)
        
        # Should be a generator
        assert hasattr(gen, '__iter__')
        assert hasattr(gen, '__next__')
        
        # Should yield bytes
        chunk = next(gen)
        assert isinstance(chunk, bytes)
        assert len(chunk) > 0
    
    def test_capture_audio_opens_stream_with_correct_params(self, mock_pyaudio):
        """Test that PyAudio stream is opened with correct parameters."""
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pyaudio):
            gen = audio_io.capture_audio(duration_seconds=1)
            next(gen)  # Trigger stream open
        
        # Verify stream was opened with correct format
        mock_instance = mock_pyaudio.return_value
        open_call = mock_instance.open.call_args
        
        # audio_io uses pyaudio.paInt16 constant, which is 8
        assert open_call[1]['format'] == 8  # pyaudio.paInt16
        assert open_call[1]['channels'] == config.AUDIO_CHANNELS
        assert open_call[1]['rate'] == config.AUDIO_SAMPLE_RATE
        assert open_call[1]['input'] is True
        assert open_call[1]['frames_per_buffer'] == config.AUDIO_CHUNK_SIZE
    
    def test_capture_audio_respects_duration(self, mock_pyaudio):
        """Test that capture stops after specified duration."""
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pyaudio):
            duration = 0.5  # 0.5 seconds
            chunks = list(audio_io.capture_audio(duration_seconds=duration))
        
        # Calculate expected number of chunks
        # At 16kHz with chunk size 1024, we get ~15.6 chunks per second
        expected_chunks = int((config.AUDIO_SAMPLE_RATE * duration) / config.AUDIO_CHUNK_SIZE)
        
        # Should be approximately the expected number (±1 for rounding)
        assert abs(len(chunks) - expected_chunks) <= 1
    
    def test_capture_audio_chunk_size(self, mock_pyaudio):
        """Test that chunks are the expected size."""
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pyaudio):
            gen = audio_io.capture_audio(duration_seconds=0.1)
            chunk = next(gen)
        
        # Each chunk should be AUDIO_CHUNK_SIZE samples * 2 bytes/sample
        expected_bytes = config.AUDIO_CHUNK_SIZE * 2
        assert len(chunk) == expected_bytes
    
    def test_capture_audio_closes_stream(self, mock_pyaudio):
        """Test that audio stream is properly closed."""
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pyaudio):
            gen = audio_io.capture_audio(duration_seconds=0.1)
            list(gen)  # Consume all chunks
        
        # Verify cleanup
        mock_stream = mock_pyaudio.return_value.open.return_value
        assert mock_stream.stop_stream.called
        assert mock_stream.close.called
        assert mock_pyaudio.return_value.terminate.called


class TestPlayAudio:
    """Test audio playback function."""
    
    def test_play_audio_accepts_correct_format(self, mock_pyaudio):
        """Test that play_audio accepts bytes in correct format (16kHz, mono, 16-bit PCM)."""
        # Generate 1 second of fake audio data
        # 16kHz sample rate * 1 second * 2 bytes per sample (int16)
        duration = 1.0
        num_samples = int(config.AUDIO_SAMPLE_RATE * duration)
        audio_bytes = b'\x00\x01' * num_samples
        
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pyaudio):
            # Should not raise any exception
            audio_io.play_audio(audio_bytes)
        
        # Verify stream was opened with correct parameters
        mock_instance = mock_pyaudio.return_value
        open_call = mock_instance.open.call_args
        
        # audio_io uses pyaudio.paInt16 constant, which is 8
        assert open_call[1]['format'] == 8  # pyaudio.paInt16
        assert open_call[1]['channels'] == config.AUDIO_CHANNELS  # mono = 1
        assert open_call[1]['rate'] == config.AUDIO_SAMPLE_RATE  # 16000 Hz
        assert open_call[1]['output'] is True
    
    def test_play_audio_writes_data(self, mock_pyaudio):
        """Test that audio data is written to the stream."""
        audio_bytes = b'\x00\x01' * 1000
        
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pyaudio):
            audio_io.play_audio(audio_bytes)
        
        # Verify write was called with the audio data
        mock_stream = mock_pyaudio.return_value.open.return_value
        assert mock_stream.write.called
        
        # Check that data was written (may be in chunks)
        written_data = b''.join(call[0][0] for call in mock_stream.write.call_args_list)
        assert written_data == audio_bytes
    
    def test_play_audio_empty_bytes(self, mock_pyaudio):
        """Test handling of empty audio data."""
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pyaudio):
            audio_io.play_audio(b'')
        
        # Should not crash, but may not open stream
        # (implementation-dependent behavior)
    
    def test_play_audio_closes_stream(self, mock_pyaudio):
        """Test that playback stream is properly closed."""
        audio_bytes = b'\x00\x01' * 1000
        
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pyaudio):
            audio_io.play_audio(audio_bytes)
        
        # Verify cleanup
        mock_stream = mock_pyaudio.return_value.open.return_value
        assert mock_stream.stop_stream.called
        assert mock_stream.close.called
        assert mock_pyaudio.return_value.terminate.called


class TestDeviceManagement:
    """Test device enumeration and selection."""
    
    def test_list_audio_devices(self, mock_pyaudio):
        """Test listing available audio devices."""
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pyaudio):
            devices = audio_io.list_audio_devices()
        
        # list_audio_devices returns a dict with 'input' and 'output' keys
        assert isinstance(devices, dict)
        assert 'input' in devices
        assert 'output' in devices
        assert len(devices['input']) > 0
        assert len(devices['output']) > 0
        
        # Each device should have required fields
        for device in devices['input']:
            assert 'index' in device
            assert 'name' in device
        
        for device in devices['output']:
            assert 'index' in device
            assert 'name' in device
    
    def test_list_audio_devices_handles_none_channels(self):
        """Test that list_audio_devices handles None channel counts (virtual/disabled devices)."""
        mock_pa = MagicMock()
        
        # Simulate a virtual device with None channel counts (real scenario on some systems)
        mock_pa.return_value.get_device_count.return_value = 3
        mock_pa.return_value.get_device_info_by_index.side_effect = [
            {'index': 0, 'name': 'Real Mic', 'maxInputChannels': 2, 'maxOutputChannels': 0, 'defaultSampleRate': 44100.0},
            {'index': 1, 'name': 'Virtual Device', 'maxInputChannels': None, 'maxOutputChannels': None, 'defaultSampleRate': 44100.0},
            {'index': 2, 'name': 'Real Speaker', 'maxInputChannels': 0, 'maxOutputChannels': 2, 'defaultSampleRate': 44100.0},
        ]
        
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pa):
            # Should not raise TypeError
            devices = audio_io.list_audio_devices()
        
        # Virtual device with None channels should be excluded
        assert len(devices['input']) == 1  # Only Real Mic
        assert len(devices['output']) == 1  # Only Real Speaker
        assert devices['input'][0]['name'] == 'Real Mic'
        assert devices['output'][0]['name'] == 'Real Speaker'
    
    def test_get_default_device_indices(self, mock_pyaudio):
        """Test getting default input/output device indices."""
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pyaudio):
            result = audio_io.get_default_device_indices()
        
        # get_default_device_indices returns a dict with 'input' and 'output' keys
        assert isinstance(result, dict)
        assert 'input' in result
        assert 'output' in result
        assert isinstance(result['input'], int)
        assert isinstance(result['output'], int)
        assert result['input'] >= 0
        assert result['output'] >= 0


class TestAudioFormat:
    """Test audio format specifications."""
    
    def test_audio_format_matches_config(self):
        """Test that audio_io uses format constants from config."""
        # Verify constants are used correctly
        assert config.AUDIO_SAMPLE_RATE == 16000
        assert config.AUDIO_CHANNELS == 1
        assert config.AUDIO_CHUNK_SIZE == 1024
        assert config.AUDIO_FORMAT == "int16"
    
    def test_bytes_per_sample(self):
        """Test that int16 format means 2 bytes per sample."""
        # 16-bit PCM = 2 bytes per sample
        bytes_per_sample = 2
        
        # A chunk should be: AUDIO_CHUNK_SIZE samples * 2 bytes/sample
        expected_chunk_bytes = config.AUDIO_CHUNK_SIZE * bytes_per_sample
        
        assert expected_chunk_bytes == 2048


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_capture_audio_no_microphone(self):
        """Test handling when no microphone is available."""
        mock_pa = MagicMock()
        mock_pa.return_value.open.side_effect = OSError("No input device")
        
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pa):
            with pytest.raises(OSError):
                gen = audio_io.capture_audio(duration_seconds=1)
                next(gen)
    
    def test_play_audio_no_speaker(self):
        """Test handling when no speaker is available."""
        mock_pa = MagicMock()
        mock_pa.return_value.open.side_effect = OSError("No output device")
        
        with patch('robot_assistant.voice.audio_io.pyaudio.PyAudio', mock_pa):
            with pytest.raises(OSError):
                audio_io.play_audio(b'\x00\x01' * 1000)
