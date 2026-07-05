"""LLM Client - Thin wrapper around Ollama API for local LLM calls.

Provides a simple interface to Ollama's local LLM inference with:
- Configurable model selection (Gemma3:1b, Llama3:1b, etc.)
- Hard timeout to prevent hangs
- Streaming support for progressive response generation
- Automatic connection to localhost:11434

Design Rationale (from Section 5):
Local LLM inference keeps the system responsive without internet dependency.
Timeout prevents hangs (degrade to "I don't know" rather than silence).
Streaming enables TTS pipelining later (start speaking before full response generated).
"""

import logging
import time
import requests
from typing import Optional, Generator
from robot_assistant.config import config

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when LLM generation exceeds timeout."""
    pass


def generate(prompt: str, context: Optional[str] = None, stream: bool = False, timeout: int = 30) -> str | Generator[str, None, None]:
    """Generate text response using local Ollama LLM.
    
    Args:
        prompt: The question or instruction for the LLM.
        context: Optional context/background information (e.g., retrieved facts).
        stream: If True, returns generator yielding chunks. If False, returns full text.
        timeout: Maximum seconds to wait for response (default: 30s from design doc).
    
    Returns:
        Complete response text if stream=False.
        Generator yielding response chunks if stream=True.
    
    Raises:
        TimeoutError: If generation exceeds timeout seconds.
        ConnectionError: If Ollama is not running or unreachable.
        requests.exceptions.RequestException: For other HTTP errors.
    
    Example (non-streaming):
        >>> response = generate("What is the HOD's name?", context="HOD: Dr. Rajesh Kumar")
        >>> print(response)
        "The HOD's name is Dr. Rajesh Kumar."
    
    Example (streaming):
        >>> for chunk in generate("Tell me about the library", stream=True):
        ...     print(chunk, end='', flush=True)
        The library is located in Central Library, Block B...
    """
    # Build full prompt with context if provided
    if context:
        full_prompt = f"Context: {context}\n\nQuestion: {prompt}\n\nAnswer:"
    else:
        full_prompt = prompt
    
    # Ollama API endpoint
    url = f"{config.OLLAMA_BASE_URL}/api/generate"
    
    # Request payload
    payload = {
        "model": config.OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": stream
    }
    
    logger.debug(f"Sending request to Ollama: model={config.OLLAMA_MODEL}, stream={stream}, timeout={timeout}s")
    
    start_time = time.time()
    
    try:
        if stream:
            # Streaming mode - return generator
            return _generate_stream(url, payload, timeout, start_time)
        else:
            # Non-streaming mode - return complete text
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            
            result = response.json()
            generated_text = result.get("response", "")
            
            latency_s = time.time() - start_time
            logger.info(f"LLM generation complete: {len(generated_text)} chars in {latency_s:.2f}s")
            
            return generated_text
            
    except requests.exceptions.Timeout:
        latency_s = time.time() - start_time
        logger.error(f"LLM generation timeout after {latency_s:.2f}s (limit: {timeout}s)")
        raise TimeoutError(f"LLM generation exceeded {timeout}s timeout")
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Failed to connect to Ollama at {config.OLLAMA_BASE_URL}: {e}")
        raise ConnectionError(
            f"Could not connect to Ollama at {config.OLLAMA_BASE_URL}. "
            "Is Ollama running? Try: ollama serve"
        )
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama API error: {e}")
        raise


def _generate_stream(url: str, payload: dict, timeout: int, start_time: float) -> Generator[str, None, None]:
    """Internal generator for streaming responses.
    
    Args:
        url: Ollama API endpoint URL.
        payload: Request payload dict.
        timeout: Maximum seconds for entire stream.
        start_time: Time when request started (for timeout check).
    
    Yields:
        Response text chunks as they arrive.
    
    Raises:
        TimeoutError: If total streaming time exceeds timeout.
    """
    try:
        # Streaming request with timeout
        with requests.post(url, json=payload, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            
            for line in response.iter_lines():
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    logger.error(f"Streaming timeout after {elapsed:.2f}s (limit: {timeout}s)")
                    raise TimeoutError(f"LLM streaming exceeded {timeout}s timeout")
                
                if line:
                    # Parse JSON line
                    import json
                    data = json.loads(line)
                    
                    # Extract response chunk
                    chunk = data.get("response", "")
                    if chunk:
                        yield chunk
                    
                    # Check if done
                    if data.get("done", False):
                        break
            
            total_time = time.time() - start_time
            logger.info(f"Streaming complete in {total_time:.2f}s")
    
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        logger.error(f"Streaming timeout after {elapsed:.2f}s (limit: {timeout}s)")
        raise TimeoutError(f"LLM streaming exceeded {timeout}s timeout")
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection lost during streaming: {e}")
        raise ConnectionError("Connection to Ollama lost during streaming")


def check_ollama_available() -> bool:
    """Check if Ollama is running and accessible.
    
    Returns:
        True if Ollama responds to health check, False otherwise.
    
    Example:
        >>> if check_ollama_available():
        ...     response = generate("Hello")
        ... else:
        ...     print("Ollama not running")
    """
    try:
        url = f"{config.OLLAMA_BASE_URL}/api/tags"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        logger.debug("Ollama health check: OK")
        return True
    except Exception as e:
        logger.debug(f"Ollama health check failed: {e}")
        return False


def list_models() -> list[str]:
    """List available models in Ollama.
    
    Returns:
        List of model names (e.g., ['gemma3:1b', 'llama3:1b']).
        Empty list if Ollama unavailable.
    
    Example:
        >>> models = list_models()
        >>> print(models)
        ['gemma3:1b', 'llama3:1b', 'mistral:latest']
    """
    try:
        url = f"{config.OLLAMA_BASE_URL}/api/tags"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        models = [model['name'] for model in data.get('models', [])]
        
        logger.debug(f"Available models: {models}")
        return models
        
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return []
