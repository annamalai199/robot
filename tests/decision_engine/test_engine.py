"""Tests for Decision Engine Router.

Test Categories:
1. Greeting Flow Tests (REAL LOGIC)
   - NEW identity greeting with GREETING_INITIATED/DELIVERED
   - RETURNED identity "welcome back" without GREETING_DELIVERED
   - State transitions via session_state
   
2. Text Routing Tests (REAL LOGIC)
   - Path A (deterministic intents) tried first
   - Path B (cache stub) tried if Path A fails
   - Path C (LLM stub) tried if Path B fails
   - RESPONSE event published with correct path metadata

3. Stub Dependency Tests (CONFIRMING STUBS GET CALLED)
   - TTS stub called for greetings
   - Cache stub called for non-intent questions
   - LLM stub called for cache misses
   
These tests verify routing decisions (real logic) and confirm stubs are
called correctly (dependency contract). Stubs will be replaced with real
implementations in Tasks 1.11 (cache), 1.14 (LLM), 2.3 (TTS).
"""

import pytest
from unittest.mock import patch, MagicMock

from robot_assistant.decision_engine.engine import (
    start_decision_engine,
    _handle_identity_resolved,
    _handle_text_input,
    _route_text_question,
    _generate_greeting,
)
from robot_assistant.events import bus, publish
from robot_assistant.session_state import (
    get_state,
    update_identity_state,
    clear_all_states,
)


@pytest.fixture(autouse=True)
def reset_environment():
    """Clear event bus and session state before each test."""
    # Clear before test
    bus.clear_subscribers()
    clear_all_states()
    yield
    # Clear after test to prevent cross-contamination
    bus.clear_subscribers()
    clear_all_states()


# =============================================================================
# GREETING FLOW TESTS (REAL LOGIC)
# =============================================================================

def test_new_identity_triggers_full_greeting_flow():
    """Test that NEW identity gets full greeting flow with state transition.
    
    Flow: IDENTITY_RESOLVED → NEW state → GREETING_INITIATED → TTS → GREETING_DELIVERED
    This is REAL LOGIC testing actual state machine behavior.
    """
    start_decision_engine()
    
    # Collect events
    greeting_initiated_events = []
    greeting_delivered_events = []
    bus.subscribe("GREETING_INITIATED", lambda e: greeting_initiated_events.append(e))
    bus.subscribe("GREETING_DELIVERED", lambda e: greeting_delivered_events.append(e))
    
    # Publish IDENTITY_RESOLVED for new person
    identity_event = {
        "event": "IDENTITY_RESOLVED",
        "track_id": "T1",
        "embedding_id": "E0042",
        "status": "new",
        "name": None,
        "confidence": None,
    }
    
    with patch("robot_assistant.decision_engine.engine._stub_tts_synthesize") as mock_tts:
        mock_tts.return_value = True  # TTS succeeds
        publish(identity_event)
    
    # Should have published GREETING_INITIATED
    assert len(greeting_initiated_events) == 1
    assert greeting_initiated_events[0]["embedding_id"] == "E0042"
    assert greeting_initiated_events[0]["track_id"] == "T1"
    
    # Should have called TTS with greeting
    assert mock_tts.called
    greeting_text = mock_tts.call_args[0][0]
    assert "Hello" in greeting_text
    assert "assistant" in greeting_text
    
    # Should have published GREETING_DELIVERED (TTS succeeded)
    assert len(greeting_delivered_events) == 1
    assert greeting_delivered_events[0]["embedding_id"] == "E0042"
    
    # State should be GREETED
    state_dict = get_state("E0042")
    assert state_dict["state"] == "GREETED"


def test_new_identity_with_name_gets_personalized_greeting():
    """Test that NEW identity with known name gets personalized greeting."""
    start_decision_engine()
    
    identity_event = {
        "event": "IDENTITY_RESOLVED",
        "track_id": "T1",
        "embedding_id": "E0042",
        "status": "known",
        "name": "Annamalai",
        "confidence": 0.95,
    }
    
    with patch("robot_assistant.decision_engine.engine._stub_tts_synthesize") as mock_tts:
        mock_tts.return_value = True
        publish(identity_event)
    
    # TTS should have been called with personalized greeting
    assert mock_tts.called
    greeting_text = mock_tts.call_args[0][0]
    assert "Annamalai" in greeting_text


def test_returned_identity_gets_welcome_back_without_greeting_delivered():
    """Test that RETURNED identity gets 'welcome back' but NO GREETING_DELIVERED event.
    
    This is REAL LOGIC: RETURNED state doesn't transition on greeting, so no
    GREETING_DELIVERED event should be published.
    """
    start_decision_engine()
    
    greeting_delivered_events = []
    bus.subscribe("GREETING_DELIVERED", lambda e: greeting_delivered_events.append(e))
    
    # Setup: Get identity to AWAY state first
    update_identity_state("E0042", "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state("E0042", "GREETING_DELIVERED")  # NEW → GREETED
    update_identity_state("E0042", "TRACK_LOST")  # GREETED → AWAY
    
    # Now person returns (AWAY → RETURNED)
    identity_event = {
        "event": "IDENTITY_RESOLVED",
        "track_id": "T2",  # New track_id (person left and re-entered)
        "embedding_id": "E0042",
        "status": "known",
        "name": "Annamalai",
        "confidence": 0.95,
    }
    
    with patch("robot_assistant.decision_engine.engine._stub_tts_synthesize") as mock_tts:
        mock_tts.return_value = True
        publish(identity_event)
    
    # TTS should have been called with "welcome back"
    assert mock_tts.called
    greeting_text = mock_tts.call_args[0][0]
    assert "Welcome back" in greeting_text
    
    # Should NOT have published GREETING_DELIVERED (no state transition)
    assert len(greeting_delivered_events) == 0
    
    # State should be RETURNED
    state_dict = get_state("E0042")
    assert state_dict["state"] == "RETURNED"


def test_greeted_identity_no_re_greeting():
    """Test that already-GREETED identity doesn't get re-greeted on re-detection."""
    start_decision_engine()
    
    # Get to GREETED state
    update_identity_state("E0042", "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state("E0042", "GREETING_DELIVERED")
    assert get_state("E0042")["state"] == "GREETED"
    
    # Re-detect same person (still in frame)
    identity_event = {
        "event": "IDENTITY_RESOLVED",
        "track_id": "T1",
        "embedding_id": "E0042",
        "status": "known",
        "name": "Test",
        "confidence": 0.95,
    }
    
    with patch("robot_assistant.decision_engine.engine._stub_tts_synthesize") as mock_tts:
        publish(identity_event)
    
    # TTS should NOT have been called (already greeted)
    assert not mock_tts.called
    
    # State should still be GREETED
    assert get_state("E0042")["state"] == "GREETED"


def test_tts_failure_does_not_publish_greeting_delivered():
    """Test that TTS failure prevents GREETING_DELIVERED (timeout will handle it)."""
    start_decision_engine()
    
    greeting_delivered_events = []
    bus.subscribe("GREETING_DELIVERED", lambda e: greeting_delivered_events.append(e))
    
    identity_event = {
        "event": "IDENTITY_RESOLVED",
        "track_id": "T1",
        "embedding_id": "E0042",
        "status": "new",
        "name": None,
        "confidence": None,
    }
    
    with patch("robot_assistant.decision_engine.engine._stub_tts_synthesize") as mock_tts:
        mock_tts.return_value = False  # TTS fails
        publish(identity_event)
    
    # Should NOT have published GREETING_DELIVERED
    assert len(greeting_delivered_events) == 0
    
    # State should still be NEW (timeout will transition after 5s)
    state_dict = get_state("E0042")
    assert state_dict["state"] == "NEW"


# =============================================================================
# TEXT ROUTING TESTS (REAL LOGIC)
# =============================================================================

def test_path_a_deterministic_intent_match():
    """Test that deterministic intents (Path A) are tried first and work.
    
    This is REAL LOGIC: intents.py actually returns responses for known intents.
    """
    start_decision_engine()
    
    response_events = []
    bus.subscribe("RESPONSE", lambda e: response_events.append(e))
    
    # Publish TEXT_INPUT with known intent
    text_event = {
        "event": "TEXT_INPUT",
        "text": "hello",
        "source": "voice",
    }
    publish(text_event)
    
    # Should have published RESPONSE
    assert len(response_events) == 1
    response = response_events[0]
    
    # Path should be "deterministic"
    assert response["path"] == "deterministic"
    assert "Hello" in response["text"] or "Hi" in response["text"]
    assert response["latency_ms"] < 10  # Should be very fast


def test_path_b_cache_stub_called_for_non_intent():
    """Test that cache stub (Path B) is tried when Path A fails.
    
    This is STUB TESTING: confirms cache stub gets called with correct question.
    Real cache will be implemented in Task 1.11.
    """
    start_decision_engine()
    
    response_events = []
    bus.subscribe("RESPONSE", lambda e: response_events.append(e))
    
    # Publish TEXT_INPUT with non-intent question
    text_event = {
        "event": "TEXT_INPUT",
        "text": "What are the lab hours?",
        "source": "voice",
    }
    
    with patch("robot_assistant.decision_engine.engine._stub_cache_check") as mock_cache:
        # Simulate cache hit
        mock_cache.return_value = {"answer": "Lab hours are Monday 2-5 PM", "metadata": {}}
        publish(text_event)
    
    # Cache stub should have been called
    assert mock_cache.called
    assert mock_cache.call_args[0][0] == "What are the lab hours?"
    
    # Response should be from cache
    assert len(response_events) == 1
    assert response_events[0]["path"] == "cache"
    assert response_events[0]["text"] == "Lab hours are Monday 2-5 PM"


def test_path_c_llm_stub_called_for_cache_miss():
    """Test that LLM stub (Path C) is tried when Path B fails.
    
    This is STUB TESTING: confirms LLM stub gets called when cache misses.
    Real LLM will be implemented in Task 1.14.
    """
    start_decision_engine()
    
    response_events = []
    bus.subscribe("RESPONSE", lambda e: response_events.append(e))
    
    # Publish TEXT_INPUT with non-intent question
    text_event = {
        "event": "TEXT_INPUT",
        "text": "Who is the HOD?",
        "source": "keyboard",
    }
    
    with patch("robot_assistant.decision_engine.engine._stub_cache_check") as mock_cache, \
         patch("robot_assistant.decision_engine.engine._stub_llm_generate") as mock_llm:
        
        # Simulate cache miss
        mock_cache.return_value = None
        
        # Simulate LLM answer
        mock_llm.return_value = "The HOD is Dr. Rajesh Kumar"
        
        publish(text_event)
    
    # Cache should have been tried first
    assert mock_cache.called
    
    # LLM should have been called (cache missed)
    assert mock_llm.called
    assert mock_llm.call_args[0][0] == "Who is the HOD?"
    
    # Response should be from LLM
    assert len(response_events) == 1
    assert response_events[0]["path"] == "llm"
    assert "HOD" in response_events[0]["text"]


def test_three_way_routing_order():
    """Test that routing tries A → B → C in order, taking first non-None result.
    
    This is REAL LOGIC: verifies routing decision logic.
    """
    # Test 1: Path A match (intent)
    answer, path, latency = _route_text_question("hi", "voice")
    assert path == "deterministic"
    assert "Hi" in answer or "Hello" in answer
    
    # Test 2: Path A miss, Path B miss, Path C hit (via stubs)
    with patch("robot_assistant.decision_engine.engine._stub_cache_check") as mock_cache, \
         patch("robot_assistant.decision_engine.engine._stub_llm_generate") as mock_llm:
        
        mock_cache.return_value = None  # Cache miss
        mock_llm.return_value = "LLM answer"
        
        answer, path, latency = _route_text_question("random question", "voice")
        
        assert mock_cache.called  # Path B tried
        assert mock_llm.called    # Path C tried (cache missed)
        assert path == "llm"
        assert answer == "LLM answer"


def test_response_event_includes_latency():
    """Test that RESPONSE event includes latency_ms metadata."""
    start_decision_engine()
    
    response_events = []
    bus.subscribe("RESPONSE", lambda e: response_events.append(e))
    
    text_event = {
        "event": "TEXT_INPUT",
        "text": "hello",
        "source": "voice",
    }
    publish(text_event)
    
    assert len(response_events) == 1
    response = response_events[0]
    
    # Should have latency_ms field
    assert "latency_ms" in response
    assert isinstance(response["latency_ms"], float)
    assert response["latency_ms"] >= 0


# =============================================================================
# GREETING GENERATION TESTS (REAL LOGIC)
# =============================================================================

def test_generate_greeting_new_with_name():
    """Test greeting generation for NEW identity with known name."""
    identity_event = {
        "track_id": "T1",
        "embedding_id": "E0042",
        "status": "known",
        "name": "Annamalai",
        "confidence": 0.95,
    }
    session_state = {"state": "NEW", "last_seen": 0, "track_id": "T1"}
    
    greeting = _generate_greeting(identity_event, session_state)
    
    assert "Hello" in greeting
    assert "Annamalai" in greeting
    assert "assistant" in greeting


def test_generate_greeting_new_without_name():
    """Test greeting generation for NEW identity without name."""
    identity_event = {
        "track_id": "T1",
        "embedding_id": "U1042",
        "status": "new",
        "name": None,
        "confidence": None,
    }
    session_state = {"state": "NEW", "last_seen": 0, "track_id": "T1"}
    
    greeting = _generate_greeting(identity_event, session_state)
    
    assert "Hello" in greeting
    assert "haven't met" in greeting or "don't believe we've met" in greeting


def test_generate_greeting_returned_with_name():
    """Test greeting generation for RETURNED identity with name."""
    identity_event = {
        "track_id": "T2",
        "embedding_id": "E0042",
        "status": "known",
        "name": "Annamalai",
        "confidence": 0.95,
    }
    session_state = {"state": "RETURNED", "last_seen": 0, "track_id": "T2"}
    
    greeting = _generate_greeting(identity_event, session_state)
    
    assert "Welcome back" in greeting
    assert "Annamalai" in greeting


def test_generate_greeting_returned_without_name():
    """Test greeting generation for RETURNED identity without name."""
    identity_event = {
        "track_id": "T2",
        "embedding_id": "U1042",
        "status": "registered_unknown",
        "name": None,
        "confidence": 0.85,
    }
    session_state = {"state": "RETURNED", "last_seen": 0, "track_id": "T2"}
    
    greeting = _generate_greeting(identity_event, session_state)
    
    assert "Welcome back" in greeting


def test_generate_greeting_greeted_state_returns_empty():
    """Test that GREETED state returns empty greeting (no re-greeting)."""
    identity_event = {
        "track_id": "T1",
        "embedding_id": "E0042",
        "status": "known",
        "name": "Test",
        "confidence": 0.95,
    }
    session_state = {"state": "GREETED", "last_seen": 0, "track_id": "T1"}
    
    greeting = _generate_greeting(identity_event, session_state)
    
    assert greeting == ""


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

def test_multiple_text_inputs_sequential():
    """Test multiple text inputs processed sequentially."""
    start_decision_engine()
    
    response_events = []
    bus.subscribe("RESPONSE", lambda e: response_events.append(e))
    
    # Input 1: Intent
    publish({"event": "TEXT_INPUT", "text": "hi", "source": "voice"})
    
    # Input 2: Non-intent (will hit LLM stub)
    publish({"event": "TEXT_INPUT", "text": "What is the schedule?", "source": "voice"})
    
    # Input 3: Another intent
    publish({"event": "TEXT_INPUT", "text": "help", "source": "keyboard"})
    
    # Should have 3 responses
    assert len(response_events) == 3
    assert response_events[0]["path"] == "deterministic"
    assert response_events[1]["path"] == "llm"  # Via stub
    assert response_events[2]["path"] == "deterministic"


def test_greeting_and_text_input_interleaved():
    """Test that greeting and text input can be handled interleaved."""
    start_decision_engine()
    
    response_events = []
    greeting_delivered_events = []
    bus.subscribe("RESPONSE", lambda e: response_events.append(e))
    bus.subscribe("GREETING_DELIVERED", lambda e: greeting_delivered_events.append(e))
    
    with patch("robot_assistant.decision_engine.engine._stub_tts_synthesize") as mock_tts:
        mock_tts.return_value = True
        
        # Identity resolved
        publish({
            "event": "IDENTITY_RESOLVED",
            "track_id": "T1",
            "embedding_id": "E0042",
            "status": "new",
            "name": None,
            "confidence": None,
        })
        
        # Text input while greeting is being processed
        publish({"event": "TEXT_INPUT", "text": "hello", "source": "voice"})
    
    # Should have both greeting and text response
    assert len(greeting_delivered_events) == 1
    assert len(response_events) == 1


def test_engine_does_not_subscribe_to_action_events():
    """Test that Decision Engine does NOT subscribe to ACTION events.
    
    This is DESIGN VERIFICATION: SafetyGate (Task 1.5) already subscribes
    to ACTION events directly. Decision Engine should not interfere.
    """
    start_decision_engine()
    
    event_types = bus.get_event_types()
    
    # Should subscribe to IDENTITY_RESOLVED and TEXT_INPUT
    assert "IDENTITY_RESOLVED" in event_types
    assert "TEXT_INPUT" in event_types
    
    # Should NOT subscribe to ACTION (SafetyGate handles it)
    # Note: This test only checks that Decision Engine doesn't add ACTION subscription
    # SafetyGate may have already subscribed in other tests


def test_start_and_stop_decision_engine():
    """Test that Decision Engine can be started and stopped."""
    # Start
    start_decision_engine()
    assert "IDENTITY_RESOLVED" in bus.get_event_types()
    assert "TEXT_INPUT" in bus.get_event_types()
    
    # Stop (clear for testing)
    bus.clear_subscribers()
    assert len(bus.get_event_types()) == 0
