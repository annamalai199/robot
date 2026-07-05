# Task 1.12: LLM Client - COMPLETE

## Summary
Successfully implemented a thin wrapper around the Ollama API for local LLM inference. Provides simple interface with timeout protection, streaming support, and comprehensive error handling. All tests use mocked HTTP responses - no actual Ollama instance required for testing.

## Implementation Details

### Files Created

1. **`robot_assistant/reasoning/llm_client.py`** (245 lines)
   - `generate(prompt, context, stream, timeout) -> str | Generator` - Main LLM generation function
   - `check_ollama_available() -> bool` - Health check
   - `list_models() -> list[str]` - List available models
   - **Timeout:** 30s hard limit (configurable)
   - **Streaming:** Returns generator when `stream=True`
   - **Error handling:** TimeoutError, ConnectionError, HTTPError

2. **`robot_assistant/reasoning/__init__.py`** - Module marker

3. **`tests/reasoning/test_llm_client.py`** (350 lines)
   - 18 comprehensive tests with mocked Ollama endpoints
   - **Critical tests:**
     - `test_generate_timeout_raises_error` ⭐⭐⭐ (timeout protection)
     - `test_generate_streaming_returns_generator` ⭐⭐ (streaming works)
     - `test_connection_error_raised_when_ollama_down` ⭐ (helpful error message)
     - Request shape verification tests
   - Edge cases: empty prompt, Unicode, malformed responses

4. **`tests/reasoning/__init__.py`** - Test module marker

### Configuration (Already in config.py)

```python
# Ollama Settings
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma2:2b"  # Or "llama3.2:1b"
LLM_TIMEOUT_SECONDS = 30
LLM_MAX_TOKENS = 256
```

## Key Design Decisions

### 1. Timeout Protection (Critical Safety Feature)
**Problem:** LLM generation can hang indefinitely on network issues or long-running inference.

**Solution:** Hard 30s timeout (configurable) that raises `TimeoutError`:
```python
try:
    response = requests.post(url, json=payload, timeout=30)
except requests.exceptions.Timeout:
    raise TimeoutError("LLM generation exceeded 30s timeout")
```

**Test:** `test_generate_timeout_raises_error` verifies timeout behavior

### 2. Streaming Support (For TTS Pipelining)
**Design Rationale (from design.md Section 5):**
> Streaming enables TTS pipelining later (start speaking before full response generated).

**Implementation:**
- `stream=False` (default): Returns complete text string
- `stream=True`: Returns generator yielding chunks
- Generator checks timeout on each chunk

**Example:**
```python
# Non-streaming
response = generate("Tell me about the library")
print(response)  # Complete text

# Streaming
for chunk in generate("Tell me about the library", stream=True):
    print(chunk, end='', flush=True)  # Progressive output
```

### 3. Context Integration
**Problem:** LLM needs retrieved facts/context for accurate answers.

**Solution:** Optional `context` parameter prepends context to prompt:
```python
generate(
    "What is the HOD's name?",
    context="HOD: Dr. Rajesh Kumar"
)
# Actual prompt: "Context: HOD: Dr. Rajesh Kumar\n\nQuestion: What is the HOD's name?\n\nAnswer:"
```

### 4. Helpful Error Messages
**Connection Error:**
```
Could not connect to Ollama at http://localhost:11434.
Is Ollama running? Try: ollama serve
```

**Timeout Error:**
```
LLM generation exceeded 30s timeout
```

### 5. Mocked Tests (No Ollama Required)
All tests use `@patch` to mock `requests.post/get` - development and CI don't require Ollama running:
```python
@patch('robot_assistant.reasoning.llm_client.requests.post')
def test_generate_basic(mock_post):
    mock_response = Mock()
    mock_response.json.return_value = {"response": "Test", "done": True}
    mock_post.return_value = mock_response
    
    result = llm_client.generate("Test")
    assert result == "Test"
```

## Test Results

```
All LLM Client tests: 18/18 PASSED ✅
Full test suite: 318/318 PASSED ✅

Critical tests:
- test_generate_timeout_raises_error ⭐⭐⭐ (timeout protection)
- test_generate_streaming_returns_generator ⭐⭐ (streaming works)
- test_connection_error_raised_when_ollama_down ⭐ (error handling)
- test_generate_basic, test_generate_with_context ⭐ (request shape)
+ 14 other tests for edge cases, helpers, streaming timeout
```

⭐⭐⭐ = Critical safety test (timeout protection)  
⭐⭐ = Critical functionality test  
⭐ = Important error handling test

## Integration Points

### Consumed By:
- Task 1.14: LangGraph will call `llm_client.generate()` for question answering
- Task 1.14: Will use streaming mode for progressive response generation

### Calls:
- Ollama API at `localhost:11434/api/generate`
- config.py for model selection and timeout

### Configuration:
- `config.OLLAMA_MODEL` - Model name (gemma2:2b, llama3.2:1b, etc.)
- `config.OLLAMA_BASE_URL` - API endpoint
- `config.LLM_TIMEOUT_SECONDS` - Hard timeout

## Acceptance Criteria Verification

- [x] `reasoning/llm_client.py` has `generate(prompt, context) -> str`
- [x] Connects to Ollama on localhost:11434
- [x] Uses Gemma3:1b or Llama3:1b (configurable via config.OLLAMA_MODEL)
- [x] Timeout: 30s hard limit, raises TimeoutError
- [x] Streaming support (returns generator)
- [x] `tests/reasoning/test_llm_client.py` mocks Ollama endpoint
- [x] Test verifies request shape and timeout behavior

**Additional:**
- [x] Helper functions: `check_ollama_available()`, `list_models()`
- [x] Comprehensive error handling: TimeoutError, ConnectionError, HTTPError
- [x] Edge case tests: empty prompt, Unicode, malformed responses
- [x] 18 tests with 100% pass rate

## Usage Example

```python
from robot_assistant.reasoning import llm_client

# Check if Ollama is running
if not llm_client.check_ollama_available():
    print("Ollama not running. Start with: ollama serve")
    exit()

# List available models
models = llm_client.list_models()
print(f"Available models: {models}")

# Basic generation
response = llm_client.generate("What is the HOD's name?")
print(response)
# → "I don't have specific information about who the HOD is..."

# With context (from memory retrieval)
response = llm_client.generate(
    "What is the HOD's name?",
    context="HOD: Dr. Rajesh Kumar, Professor of Computer Science"
)
print(response)
# → "The HOD's name is Dr. Rajesh Kumar."

# Streaming mode (for progressive output)
print("Response: ", end='', flush=True)
for chunk in llm_client.generate("Tell me about the library", stream=True):
    print(chunk, end='', flush=True)
print()  # Newline

# With custom timeout
try:
    response = llm_client.generate("Long question...", timeout=10)
except llm_client.TimeoutError:
    print("LLM took too long, using fallback response")
    response = "I don't have that information right now."
```

## Design Rationale Highlights

1. **Timeout is critical:** Prevents system from hanging on LLM issues; degrades gracefully

2. **Streaming enables TTS pipelining:** Start speaking while LLM still generating (future optimization)

3. **Context prepending:** Simple but effective way to provide retrieved facts to LLM

4. **Mocked tests:** Development/CI doesn't require Ollama running; tests are fast (<0.1s)

5. **Helpful error messages:** Suggests solutions ("Try: ollama serve") for common issues

6. **Configurable model:** Easy to swap between gemma2:2b (quality) and llama3.2:1b (speed)

## Known Limitations

1. **No retry logic:** Single attempt; timeout or connection error fails immediately
2. **No token counting:** Relies on Ollama's default token limit
3. **No temperature/top_p control:** Uses Ollama defaults (can be added if needed)
4. **No conversation history:** Each call is independent (fine for Q&A use case)

These are intentional simplifications for current scope. Can be added in future phases if needed.

---

**Task 1.12 Status: COMPLETE** ✅  
**Date:** 2026-07-05  
**Test Count:** 318 total (18 LLM client tests)  
**All Tests:** PASSING  
**Timeout:** 30s hard limit ⚡  
**Streaming:** Supported ✅  
**Model:** Configurable (gemma2:2b default)

