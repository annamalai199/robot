"""Tests for LLM Client (Ollama API wrapper).

Uses mocked HTTP responses - does NOT require Ollama to be running.

Critical test cases:
1. Request shape verification (correct payload sent to Ollama)
2. Timeout behavior (raises TimeoutError, doesn't hang)
3. Streaming support (generator yields chunks)
4. Connection error handling
5. Context integration
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import requests

from robot_assistant.reasoning import llm_client
from robot_assistant.config import config


# =============================================================================
# BASIC GENERATION TESTS
# =============================================================================

@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_generate_basic(mock_post):
    """Test basic text generation with mocked Ollama response."""
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "The HOD's name is Dr. Rajesh Kumar.",
        "done": True
    }
    mock_post.return_value = mock_response
    
    # Generate
    result = llm_client.generate("What is the HOD's name?")
    
    # Verify result
    assert result == "The HOD's name is Dr. Rajesh Kumar."
    
    # Verify request was made correctly
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    
    # Check URL
    assert call_args[0][0] == f"{config.OLLAMA_BASE_URL}/api/generate"
    
    # Check payload
    payload = call_args[1]['json']
    assert payload['model'] == config.OLLAMA_MODEL
    assert payload['prompt'] == "What is the HOD's name?"
    assert payload['stream'] is False


@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_generate_with_context(mock_post):
    """Test generation with context prepended to prompt."""
    mock_response = Mock()
    mock_response.json.return_value = {"response": "Test response", "done": True}
    mock_post.return_value = mock_response
    
    # Generate with context
    llm_client.generate("What is the HOD's name?", context="HOD: Dr. Rajesh Kumar")
    
    # Verify context was prepended
    payload = mock_post.call_args[1]['json']
    expected_prompt = "Context: HOD: Dr. Rajesh Kumar\n\nQuestion: What is the HOD's name?\n\nAnswer:"
    assert payload['prompt'] == expected_prompt


# =============================================================================
# TIMEOUT TESTS (CRITICAL)
# =============================================================================

@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_generate_timeout_raises_error(mock_post):
    """CRITICAL: Test that timeout raises TimeoutError, doesn't hang.
    
    This is a safety feature - LLM generation must not hang indefinitely.
    """
    # Mock timeout exception
    mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
    
    # Should raise TimeoutError
    with pytest.raises(llm_client.TimeoutError) as exc_info:
        llm_client.generate("Test prompt", timeout=5)
    
    assert "5s timeout" in str(exc_info.value)


@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_generate_uses_specified_timeout(mock_post):
    """Test that specified timeout is passed to requests."""
    mock_response = Mock()
    mock_response.json.return_value = {"response": "Test", "done": True}
    mock_post.return_value = mock_response
    
    # Generate with custom timeout
    llm_client.generate("Test", timeout=15)
    
    # Verify timeout was passed to requests
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs['timeout'] == 15


@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_generate_default_timeout_30s(mock_post):
    """Test that default timeout is 30s (from design doc)."""
    mock_response = Mock()
    mock_response.json.return_value = {"response": "Test", "done": True}
    mock_post.return_value = mock_response
    
    # Generate without specifying timeout
    llm_client.generate("Test")
    
    # Verify default 30s timeout
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs['timeout'] == 30


# =============================================================================
# STREAMING TESTS
# =============================================================================

@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_generate_streaming_returns_generator(mock_post):
    """Test that streaming mode returns a generator."""
    # Mock streaming response
    mock_response = Mock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)
    
    # Mock iter_lines to return JSONL chunks
    chunks = [
        json.dumps({"response": "The ", "done": False}).encode(),
        json.dumps({"response": "HOD ", "done": False}).encode(),
        json.dumps({"response": "is Dr. Rajesh.", "done": True}).encode(),
    ]
    mock_response.iter_lines.return_value = iter(chunks)
    mock_response.raise_for_status = Mock()
    
    mock_post.return_value = mock_response
    
    # Generate in streaming mode
    result = llm_client.generate("Test", stream=True)
    
    # Should be a generator
    assert hasattr(result, '__iter__')
    assert hasattr(result, '__next__')
    
    # Consume generator
    chunks_received = list(result)
    
    # Verify chunks
    assert chunks_received == ["The ", "HOD ", "is Dr. Rajesh."]


@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_streaming_request_shape(mock_post):
    """Test that streaming request has correct payload."""
    mock_response = Mock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)
    mock_response.iter_lines.return_value = iter([
        json.dumps({"response": "Test", "done": True}).encode()
    ])
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    # Generate with streaming
    gen = llm_client.generate("Test prompt", stream=True)
    list(gen)  # Consume generator
    
    # Verify request
    call_kwargs = mock_post.call_args[1]
    payload = call_kwargs['json']
    
    assert payload['stream'] is True
    assert call_kwargs['stream'] is True  # requests stream flag


@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_streaming_timeout_raises_error(mock_post):
    """Test that streaming timeout raises TimeoutError."""
    # Mock timeout during streaming
    mock_response = Mock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)
    mock_response.raise_for_status = Mock()
    mock_response.iter_lines.side_effect = requests.exceptions.Timeout("Stream timed out")
    
    mock_post.return_value = mock_response
    
    # Should raise TimeoutError when consuming generator
    gen = llm_client.generate("Test", stream=True, timeout=5)
    
    with pytest.raises(llm_client.TimeoutError):
        list(gen)  # Consume generator


# =============================================================================
# CONNECTION ERROR TESTS
# =============================================================================

@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_connection_error_raised_when_ollama_down(mock_post):
    """Test that ConnectionError is raised when Ollama is not running."""
    mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
    
    with pytest.raises(ConnectionError) as exc_info:
        llm_client.generate("Test")
    
    assert "Could not connect to Ollama" in str(exc_info.value)
    assert "ollama serve" in str(exc_info.value)  # Helpful error message


@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_http_error_propagated(mock_post):
    """Test that HTTP errors from Ollama are propagated."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
    mock_post.return_value = mock_response
    
    with pytest.raises(requests.exceptions.HTTPError):
        llm_client.generate("Test")


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================

@patch('robot_assistant.reasoning.llm_client.requests.get')
def test_check_ollama_available_returns_true_when_running(mock_get):
    """Test Ollama health check returns True when running."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    
    assert llm_client.check_ollama_available() is True


@patch('robot_assistant.reasoning.llm_client.requests.get')
def test_check_ollama_available_returns_false_when_down(mock_get):
    """Test Ollama health check returns False when down."""
    mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
    
    assert llm_client.check_ollama_available() is False


@patch('robot_assistant.reasoning.llm_client.requests.get')
def test_list_models_returns_model_names(mock_get):
    """Test list_models returns available model names."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "models": [
            {"name": "gemma3:1b"},
            {"name": "llama3:1b"},
            {"name": "mistral:latest"}
        ]
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    
    models = llm_client.list_models()
    
    assert models == ["gemma3:1b", "llama3:1b", "mistral:latest"]


@patch('robot_assistant.reasoning.llm_client.requests.get')
def test_list_models_returns_empty_when_unavailable(mock_get):
    """Test list_models returns empty list when Ollama unavailable."""
    mock_get.side_effect = requests.exceptions.ConnectionError()
    
    models = llm_client.list_models()
    
    assert models == []


# =============================================================================
# EDGE CASES
# =============================================================================

@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_empty_prompt(mock_post):
    """Test that empty prompt is handled."""
    mock_response = Mock()
    mock_response.json.return_value = {"response": "", "done": True}
    mock_post.return_value = mock_response
    
    result = llm_client.generate("")
    
    assert result == ""


@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_very_long_prompt(mock_post):
    """Test that very long prompts are handled."""
    mock_response = Mock()
    mock_response.json.return_value = {"response": "Response", "done": True}
    mock_post.return_value = mock_response
    
    long_prompt = "Test " * 1000
    result = llm_client.generate(long_prompt)
    
    # Verify request was made with long prompt
    payload = mock_post.call_args[1]['json']
    assert payload['prompt'] == long_prompt


@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_unicode_in_prompt(mock_post):
    """Test that Unicode characters in prompt are handled."""
    mock_response = Mock()
    mock_response.json.return_value = {"response": "Response", "done": True}
    mock_post.return_value = mock_response
    
    unicode_prompt = "What is the library? 你好 नमस्ते"
    result = llm_client.generate(unicode_prompt)
    
    # Should not crash
    assert isinstance(result, str)


@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_response_missing_response_field(mock_post):
    """Test graceful handling of malformed Ollama response."""
    mock_response = Mock()
    mock_response.json.return_value = {"done": True}  # Missing 'response' field
    mock_post.return_value = mock_response
    
    result = llm_client.generate("Test")
    
    # Should return empty string, not crash
    assert result == ""
