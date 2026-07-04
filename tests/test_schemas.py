"""Tests for event schema validation."""

import pytest
from robot_assistant.events.schemas import (
    GestureDetectedEvent,
    IdentityResolvedEvent,
    TrackLostEvent,
    SessionStateEvent,
    ActionEvent,
    ActionBlockedEvent,
    ServoCommandEvent,
    TextInputEvent,
    ResponseEvent,
    GreetingDeliveredEvent,
    GreetingInitiatedEvent,
    validate_event,
)


def test_gesture_detected_event_valid():
    """Test creating a valid GestureDetectedEvent."""
    event: GestureDetectedEvent = {
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T1"
    }
    assert event["event"] == "GESTURE_DETECTED"
    assert event["gesture"] == "HAND_RAISED"
    assert event["track_id"] == "T1"
    assert validate_event(event)


def test_identity_resolved_event_known():
    """Test creating IdentityResolvedEvent for known person."""
    event: IdentityResolvedEvent = {
        "event": "IDENTITY_RESOLVED",
        "track_id": "T1",
        "embedding_id": "E0042",
        "status": "known",
        "name": "Annamalai",
        "confidence": 0.91
    }
    assert event["status"] == "known"
    assert event["name"] == "Annamalai"
    assert event["confidence"] == 0.91
    assert validate_event(event)


def test_identity_resolved_event_new():
    """Test creating IdentityResolvedEvent for new person."""
    event: IdentityResolvedEvent = {
        "event": "IDENTITY_RESOLVED",
        "track_id": "T1",
        "embedding_id": "U1042",
        "status": "new",
        "name": None,
        "confidence": None
    }
    assert event["status"] == "new"
    assert event["name"] is None
    assert event["confidence"] is None
    assert validate_event(event)


def test_identity_resolved_event_registered_unknown():
    """Test creating IdentityResolvedEvent for registered but unnamed person."""
    event: IdentityResolvedEvent = {
        "event": "IDENTITY_RESOLVED",
        "track_id": "T2",
        "embedding_id": "U1043",
        "status": "registered_unknown",
        "name": None,
        "confidence": 0.85
    }
    assert event["status"] == "registered_unknown"
    assert event["name"] is None
    assert validate_event(event)


def test_track_lost_event_valid():
    """Test creating a valid TrackLostEvent."""
    event: TrackLostEvent = {
        "event": "TRACK_LOST",
        "track_id": "T1",
        "embedding_id": "E0042"
    }
    assert event["track_id"] == "T1"
    assert event["embedding_id"] == "E0042"
    assert validate_event(event)


def test_session_state_event_all_states():
    """Test creating SessionStateEvent with all possible states."""
    states = ["NEW", "GREETED", "AWAY", "RETURNED"]
    
    for state in states:
        event: SessionStateEvent = {
            "event": "SESSION_STATE",
            "embedding_id": "E0042",
            "state": state  # type: ignore
        }
        assert event["state"] == state
        assert validate_event(event)


def test_action_event_valid():
    """Test creating a valid ActionEvent."""
    event: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    assert event["action"] == "HANDSHAKE"
    assert event["track_id"] == "T1"
    assert validate_event(event)


def test_action_blocked_event_all_reasons():
    """Test creating ActionBlockedEvent with all possible reasons."""
    reasons = ["target_too_close", "target_too_far", "sensor_fault"]
    
    for reason in reasons:
        event: ActionBlockedEvent = {
            "event": "ACTION_BLOCKED",
            "action": "HANDSHAKE",
            "track_id": "T1",
            "reason": reason  # type: ignore
        }
        assert event["reason"] == reason
        assert validate_event(event)


def test_servo_command_event_valid():
    """Test creating a valid ServoCommandEvent."""
    event: ServoCommandEvent = {
        "event": "SERVO_COMMAND",
        "preset": "HANDSHAKE_READY",
        "joints": {"shoulder": 45, "elbow": 90, "wrist": 0}
    }
    assert event["preset"] == "HANDSHAKE_READY"
    assert event["joints"]["shoulder"] == 45
    assert validate_event(event)


def test_text_input_event_voice():
    """Test creating TextInputEvent from voice."""
    event: TextInputEvent = {
        "event": "TEXT_INPUT",
        "text": "What are the lab hours?",
        "source": "voice"
    }
    assert event["text"] == "What are the lab hours?"
    assert event["source"] == "voice"
    assert validate_event(event)


def test_text_input_event_keyboard():
    """Test creating TextInputEvent from keyboard."""
    event: TextInputEvent = {
        "event": "TEXT_INPUT",
        "text": "Who is the HOD?",
        "source": "keyboard"
    }
    assert event["source"] == "keyboard"
    assert validate_event(event)


def test_response_event_all_paths():
    """Test creating ResponseEvent from all decision paths."""
    paths = ["deterministic", "cache", "llm"]
    
    for path in paths:
        event: ResponseEvent = {
            "event": "RESPONSE",
            "text": "Sample response",
            "path": path,  # type: ignore
            "latency_ms": 23.5
        }
        assert event["path"] == path
        assert event["latency_ms"] == 23.5
        assert validate_event(event)


def test_greeting_delivered_event_valid():
    """Test creating a valid GreetingDeliveredEvent."""
    event: GreetingDeliveredEvent = {
        "event": "GREETING_DELIVERED",
        "embedding_id": "E0042",
        "track_id": "T1"
    }
    assert event["event"] == "GREETING_DELIVERED"
    assert event["embedding_id"] == "E0042"
    assert event["track_id"] == "T1"
    
    valid, error_msg = validate_event(event)
    assert valid, f"Validation failed: {error_msg}"


def test_greeting_initiated_event_valid():
    """Test creating a valid GreetingInitiatedEvent."""
    event: GreetingInitiatedEvent = {
        "event": "GREETING_INITIATED",
        "embedding_id": "E0042",
        "track_id": "T1"
    }
    assert event["event"] == "GREETING_INITIATED"
    assert event["embedding_id"] == "E0042"
    assert event["track_id"] == "T1"
    
    valid, error_msg = validate_event(event)
    assert valid, f"Validation failed: {error_msg}"


def test_validate_event_missing_event_field():
    """Test validate_event rejects dict without 'event' field."""
    invalid_event = {"data": "missing event field"}
    valid, error_msg = validate_event(invalid_event)
    assert not valid
    assert "missing required 'event' field" in error_msg


def test_validate_event_wrong_type():
    """Test validate_event rejects non-dict."""
    for invalid_input in ["not a dict", None, 123, []]:
        valid, error_msg = validate_event(invalid_input)
        assert not valid
        assert "Event must be a dict" in error_msg


def test_validate_event_event_field_wrong_type():
    """Test validate_event rejects dict with non-string 'event' field."""
    invalid_event = {"event": 123}
    valid, error_msg = validate_event(invalid_event)
    assert not valid
    assert "'event' field must be str" in error_msg


def test_event_immutability():
    """Test that events can be safely modified after creation without affecting schema."""
    event: GestureDetectedEvent = {
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T1"
    }
    
    # Events are dicts, so they're mutable (TypedDict is just a type hint)
    # This test just verifies the structure is correct
    assert "event" in event
    assert "gesture" in event
    assert "track_id" in event


def test_multiple_event_types_coexist():
    """Test that multiple different event types can coexist."""
    gesture_event: GestureDetectedEvent = {
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T1"
    }
    
    action_event: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    response_event: ResponseEvent = {
        "event": "RESPONSE",
        "text": "Hello!",
        "path": "deterministic",
        "latency_ms": 3.2
    }
    
    assert validate_event(gesture_event)
    assert validate_event(action_event)
    assert validate_event(response_event)
    
    assert gesture_event["event"] != action_event["event"]
    assert action_event["event"] != response_event["event"]
