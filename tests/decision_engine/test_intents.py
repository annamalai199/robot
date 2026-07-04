"""Tests for deterministic intent handler."""

import pytest
from robot_assistant.decision_engine import intents
from robot_assistant.events import bus


@pytest.fixture(autouse=True)
def reset_bus():
    """Clear all subscribers before and after each test."""
    bus.clear_subscribers()
    yield
    bus.clear_subscribers()


def test_known_intent_returns_response():
    """Test that known intent returns canned response."""
    response = intents.get_intent_response("hi")
    
    assert response is not None
    assert "hello" in response.lower()


def test_known_intent_publishes_response_event():
    """Test that known intent publishes RESPONSE event with path='deterministic'."""
    received_events = []
    bus.subscribe("RESPONSE", lambda e: received_events.append(e))
    
    response = intents.get_intent_response("hello")
    
    assert response is not None
    assert len(received_events) == 1
    
    event = received_events[0]
    assert event["event"] == "RESPONSE"
    assert event["text"] == response
    assert event["path"] == "deterministic"
    assert event["latency_ms"] >= 0
    assert event["latency_ms"] < 10  # Should be < 10ms for dict lookup


def test_unknown_intent_returns_none():
    """Test that unknown intent returns None (fallthrough to cache/LLM)."""
    response = intents.get_intent_response("What's my attendance today?")
    
    assert response is None


def test_unknown_intent_does_not_publish_event():
    """Test that unknown intent does NOT publish RESPONSE event."""
    received_events = []
    bus.subscribe("RESPONSE", lambda e: received_events.append(e))
    
    response = intents.get_intent_response("Tell me about quantum physics")
    
    assert response is None
    assert len(received_events) == 0


def test_case_insensitive_matching():
    """Test that intent matching is case-insensitive (real STT varies casing)."""
    # All these should match "hi" intent
    test_cases = ["hi", "HI", "Hi", "hI"]
    
    for test_input in test_cases:
        response = intents.get_intent_response(test_input)
        assert response is not None, f"Failed for input: '{test_input}'"
        assert "hello" in response.lower()


def test_whitespace_normalization():
    """Test that extra whitespace is normalized (real STT has inconsistent spacing)."""
    # All these should match "thank you" intent
    test_cases = [
        "thank you",
        "  thank you  ",  # Leading/trailing spaces
        "thank  you",    # Double space
        "THANK   YOU",   # Multiple spaces + uppercase
    ]
    
    for test_input in test_cases:
        response = intents.get_intent_response(test_input)
        assert response is not None, f"Failed for input: '{test_input}'"
        assert "welcome" in response.lower()


def test_trailing_punctuation_removed():
    """Test that trailing punctuation is removed (STT often adds periods/question marks)."""
    # All these should match known intents
    test_cases = [
        ("hi!", "hello"),
        ("bye.", "goodbye"),
        ("help?", "answer"),  # Help response says "I can answer questions..."
        ("thanks.", "welcome"),
    ]
    
    for test_input, expected_keyword in test_cases:
        response = intents.get_intent_response(test_input)
        assert response is not None, f"Failed for input: '{test_input}'"
        assert expected_keyword.lower() in response.lower(), f"Expected '{expected_keyword}' in response for '{test_input}'"


def test_all_configured_intents_work():
    """Test that all intents from config are accessible."""
    from robot_assistant.config import config
    
    for intent_text in config.INTENT_RESPONSES.keys():
        response = intents.get_intent_response(intent_text)
        assert response is not None, f"Intent '{intent_text}' failed"
        assert response == config.INTENT_RESPONSES[intent_text]


def test_normalize_text_function():
    """Test text normalization function directly."""
    test_cases = [
        ("  Hello!  ", "hello"),
        ("THANK YOU.", "thank you"),
        ("what   can you do?", "what can you do"),
        ("Hi!!!", "hi"),
        ("   ", ""),  # Edge case: only whitespace
        ("Test;", "test"),
        ("Test:", "test"),
    ]
    
    for input_text, expected in test_cases:
        result = intents.normalize_text(input_text)
        assert result == expected, f"normalize_text('{input_text}') = '{result}', expected '{expected}'"


def test_add_intent_runtime():
    """Test adding a new intent at runtime."""
    test_intent = "test custom intent"
    test_response = "This is a test response"
    
    # Should not match initially
    assert intents.get_intent_response(test_intent) is None
    
    # Add intent
    intents.add_intent(test_intent, test_response)
    
    # Should now match
    response = intents.get_intent_response(test_intent)
    assert response == test_response
    
    # Should also match with different casing/spacing
    response = intents.get_intent_response("TEST  CUSTOM  INTENT!")
    assert response == test_response


def test_remove_intent_runtime():
    """Test removing an intent at runtime."""
    test_intent = "temporary intent"
    test_response = "Temporary response"
    
    # Add intent
    intents.add_intent(test_intent, test_response)
    assert intents.get_intent_response(test_intent) == test_response
    
    # Remove intent
    removed = intents.remove_intent(test_intent)
    assert removed is True
    
    # Should no longer match
    assert intents.get_intent_response(test_intent) is None
    
    # Removing again should return False
    removed = intents.remove_intent(test_intent)
    assert removed is False


def test_get_all_intents():
    """Test retrieving all registered intents."""
    all_intents = intents.get_all_intents()
    
    assert isinstance(all_intents, dict)
    assert len(all_intents) >= 5  # At least 5 intents from config
    
    # Check some expected intents exist
    assert "hi" in all_intents or "hello" in all_intents
    assert "bye" in all_intents or "goodbye" in all_intents


def test_does_not_emit_action_event():
    """Test that intents do NOT emit ACTION events (that's gesture_actions.py)."""
    action_events = []
    bus.subscribe("ACTION", lambda e: action_events.append(e))
    
    # Process a known intent
    intents.get_intent_response("hi")
    
    # Should NOT have published ACTION event
    assert len(action_events) == 0


def test_multiple_intents_in_sequence():
    """Test multiple intent lookups work correctly."""
    received_events = []
    bus.subscribe("RESPONSE", lambda e: received_events.append(e))
    
    # Process multiple intents
    r1 = intents.get_intent_response("hi")
    r2 = intents.get_intent_response("thanks")
    r3 = intents.get_intent_response("unknown intent")
    r4 = intents.get_intent_response("bye")
    
    assert r1 is not None
    assert r2 is not None
    assert r3 is None  # Unknown
    assert r4 is not None
    
    # Should have 3 RESPONSE events (not 4, since r3 is None)
    assert len(received_events) == 3
    assert all(e["path"] == "deterministic" for e in received_events)


def test_latency_target():
    """Test that deterministic intent lookup meets < 5ms latency target."""
    import time
    
    # Warm up (first call might be slower due to imports)
    intents.get_intent_response("hi")
    
    # Measure actual latency
    start = time.time()
    for _ in range(100):
        intents.get_intent_response("hi")
    elapsed_ms = (time.time() - start) * 1000
    
    avg_latency = elapsed_ms / 100
    
    # Should be well under 5ms on average (dict lookup is very fast)
    assert avg_latency < 5.0, f"Average latency {avg_latency:.2f}ms exceeds 5ms target"


def test_empty_string_intent():
    """Test that empty string is handled gracefully."""
    response = intents.get_intent_response("")
    assert response is None


def test_very_long_unknown_intent():
    """Test that very long unknown input doesn't cause issues."""
    long_text = "This is a very long question about something " * 20
    response = intents.get_intent_response(long_text)
    assert response is None
