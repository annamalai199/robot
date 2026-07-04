"""Tests for runtime event validation."""

import pytest
from robot_assistant.events import bus


@pytest.fixture(autouse=True)
def reset_bus():
    """Clear all subscribers before and after each test."""
    bus.clear_subscribers()
    yield
    bus.clear_subscribers()


def test_publish_not_a_dict_raises():
    """Test that publishing non-dict raises ValueError."""
    with pytest.raises(ValueError, match="Event must be a dict"):
        bus.publish("not a dict")
    
    with pytest.raises(ValueError, match="Event must be a dict"):
        bus.publish(123)
    
    with pytest.raises(ValueError, match="Event must be a dict"):
        bus.publish(None)


def test_publish_missing_event_field_raises():
    """Test that event without 'event' field raises ValueError."""
    with pytest.raises(ValueError, match="missing required 'event' field"):
        bus.publish({"data": "no event field"})


def test_session_state_invalid_state_raises():
    """Test that SESSION_STATE with invalid state value raises."""
    with pytest.raises(ValueError, match="must be one of.*NEW.*GREETED.*AWAY.*RETURNED"):
        bus.publish({
            "event": "SESSION_STATE",
            "embedding_id": "E1",
            "state": "NOT_A_REAL_STATE"
        })


def test_session_state_missing_state_field_raises():
    """Test that SESSION_STATE without 'state' field raises."""
    with pytest.raises(ValueError, match="missing required field 'state'"):
        bus.publish({
            "event": "SESSION_STATE",
            "embedding_id": "E1"
        })


def test_session_state_missing_embedding_id_raises():
    """Test that SESSION_STATE without 'embedding_id' field raises."""
    with pytest.raises(ValueError, match="missing required field 'embedding_id'"):
        bus.publish({
            "event": "SESSION_STATE",
            "state": "NEW"
        })


def test_session_state_valid_all_states():
    """Test that all valid SESSION_STATE states are accepted."""
    valid_states = ["NEW", "GREETED", "AWAY", "RETURNED"]
    
    received = []
    bus.subscribe("SESSION_STATE", lambda e: received.append(e))
    
    for state in valid_states:
        bus.publish({
            "event": "SESSION_STATE",
            "embedding_id": "E1",
            "state": state
        })
    
    assert len(received) == 4


def test_identity_resolved_invalid_status_raises():
    """Test that IDENTITY_RESOLVED with invalid status raises."""
    with pytest.raises(ValueError, match="must be one of.*known.*new.*registered_unknown"):
        bus.publish({
            "event": "IDENTITY_RESOLVED",
            "track_id": "T1",
            "embedding_id": "E1",
            "status": "INVALID_STATUS",
            "name": None,
            "confidence": None
        })


def test_identity_resolved_missing_fields_raises():
    """Test that IDENTITY_RESOLVED with missing fields raises."""
    # Missing track_id
    with pytest.raises(ValueError, match="missing required field 'track_id'"):
        bus.publish({
            "event": "IDENTITY_RESOLVED",
            "embedding_id": "E1",
            "status": "new",
            "name": None,
            "confidence": None
        })
    
    # Missing status
    with pytest.raises(ValueError, match="missing required field 'status'"):
        bus.publish({
            "event": "IDENTITY_RESOLVED",
            "track_id": "T1",
            "embedding_id": "E1",
            "name": None,
            "confidence": None
        })


def test_action_blocked_invalid_reason_raises():
    """Test that ACTION_BLOCKED with invalid reason raises."""
    with pytest.raises(ValueError, match="must be one of.*target_too_close.*target_too_far.*sensor_fault"):
        bus.publish({
            "event": "ACTION_BLOCKED",
            "action": "HANDSHAKE",
            "track_id": "T1",
            "reason": "invalid_reason"
        })


def test_action_blocked_missing_fields_raises():
    """Test that ACTION_BLOCKED with missing fields raises."""
    with pytest.raises(ValueError, match="missing required field"):
        bus.publish({
            "event": "ACTION_BLOCKED",
            "action": "HANDSHAKE",
            "track_id": "T1"
            # Missing 'reason'
        })


def test_text_input_invalid_source_raises():
    """Test that TEXT_INPUT with invalid source raises."""
    with pytest.raises(ValueError, match="must be one of.*voice.*keyboard"):
        bus.publish({
            "event": "TEXT_INPUT",
            "text": "Hello",
            "source": "invalid_source"
        })


def test_text_input_missing_fields_raises():
    """Test that TEXT_INPUT with missing fields raises."""
    with pytest.raises(ValueError, match="missing required field 'text'"):
        bus.publish({
            "event": "TEXT_INPUT",
            "source": "voice"
        })


def test_response_invalid_path_raises():
    """Test that RESPONSE with invalid path raises."""
    with pytest.raises(ValueError, match="must be one of.*deterministic.*cache.*llm"):
        bus.publish({
            "event": "RESPONSE",
            "text": "Hello",
            "path": "invalid_path",
            "latency_ms": 10.0
        })


def test_response_missing_fields_raises():
    """Test that RESPONSE with missing fields raises."""
    with pytest.raises(ValueError, match="missing required field"):
        bus.publish({
            "event": "RESPONSE",
            "text": "Hello",
            "path": "cache"
            # Missing 'latency_ms'
        })


def test_gesture_detected_missing_fields_raises():
    """Test that GESTURE_DETECTED with missing fields raises."""
    with pytest.raises(ValueError, match="missing required field 'gesture'"):
        bus.publish({
            "event": "GESTURE_DETECTED",
            "track_id": "T1"
        })


def test_gesture_detected_wrong_type_raises():
    """Test that GESTURE_DETECTED with wrong field types raises."""
    with pytest.raises(ValueError, match="'gesture' must be str"):
        bus.publish({
            "event": "GESTURE_DETECTED",
            "gesture": 123,  # Should be string
            "track_id": "T1"
        })


def test_action_event_valid():
    """Test that valid ACTION event is accepted."""
    received = []
    bus.subscribe("ACTION", lambda e: received.append(e))
    
    bus.publish({
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    })
    
    assert len(received) == 1


def test_track_lost_missing_fields_raises():
    """Test that TRACK_LOST with missing fields raises."""
    with pytest.raises(ValueError, match="missing required field"):
        bus.publish({
            "event": "TRACK_LOST",
            "track_id": "T1"
            # Missing 'embedding_id'
        })


def test_servo_command_joints_not_dict_raises():
    """Test that SERVO_COMMAND with non-dict joints raises."""
    with pytest.raises(ValueError, match="'joints' must be dict"):
        bus.publish({
            "event": "SERVO_COMMAND",
            "preset": "HANDSHAKE_READY",
            "joints": "not a dict"
        })


def test_servo_command_valid():
    """Test that valid SERVO_COMMAND is accepted."""
    received = []
    bus.subscribe("SERVO_COMMAND", lambda e: received.append(e))
    
    bus.publish({
        "event": "SERVO_COMMAND",
        "preset": "HANDSHAKE_READY",
        "joints": {"shoulder": 45, "elbow": 90}
    })
    
    assert len(received) == 1


def test_greeting_delivered_missing_embedding_id_raises():
    """Test that GREETING_DELIVERED without embedding_id raises ValueError."""
    with pytest.raises(ValueError, match="GREETING_DELIVERED missing required field 'embedding_id'"):
        bus.publish({"event": "GREETING_DELIVERED", "track_id": "T1"})


def test_greeting_delivered_missing_track_id_raises():
    """Test that GREETING_DELIVERED without track_id raises ValueError."""
    with pytest.raises(ValueError, match="GREETING_DELIVERED missing required field 'track_id'"):
        bus.publish({"event": "GREETING_DELIVERED", "embedding_id": "E0042"})


def test_greeting_delivered_embedding_id_wrong_type_raises():
    """Test that GREETING_DELIVERED with non-string embedding_id raises ValueError."""
    with pytest.raises(ValueError, match="GREETING_DELIVERED 'embedding_id' must be str"):
        bus.publish({"event": "GREETING_DELIVERED", "embedding_id": 123, "track_id": "T1"})


def test_greeting_delivered_track_id_wrong_type_raises():
    """Test that GREETING_DELIVERED with non-string track_id raises ValueError."""
    with pytest.raises(ValueError, match="GREETING_DELIVERED 'track_id' must be str"):
        bus.publish({"event": "GREETING_DELIVERED", "embedding_id": "E0042", "track_id": 456})


def test_greeting_delivered_valid():
    """Test that valid GREETING_DELIVERED event is accepted."""
    events_received = []
    bus.subscribe("GREETING_DELIVERED", lambda e: events_received.append(e))
    
    bus.publish({"event": "GREETING_DELIVERED", "embedding_id": "E0042", "track_id": "T1"})
    
    assert len(events_received) == 1
    assert events_received[0]["event"] == "GREETING_DELIVERED"
    assert events_received[0]["embedding_id"] == "E0042"
    assert events_received[0]["track_id"] == "T1"


def test_greeting_initiated_missing_embedding_id_raises():
    """Test that GREETING_INITIATED without embedding_id raises ValueError."""
    with pytest.raises(ValueError, match="GREETING_INITIATED missing required field 'embedding_id'"):
        bus.publish({"event": "GREETING_INITIATED", "track_id": "T1"})


def test_greeting_initiated_missing_track_id_raises():
    """Test that GREETING_INITIATED without track_id raises ValueError."""
    with pytest.raises(ValueError, match="GREETING_INITIATED missing required field 'track_id'"):
        bus.publish({"event": "GREETING_INITIATED", "embedding_id": "E0042"})


def test_greeting_initiated_embedding_id_wrong_type_raises():
    """Test that GREETING_INITIATED with non-string embedding_id raises ValueError."""
    with pytest.raises(ValueError, match="GREETING_INITIATED 'embedding_id' must be str"):
        bus.publish({"event": "GREETING_INITIATED", "embedding_id": 123, "track_id": "T1"})


def test_greeting_initiated_track_id_wrong_type_raises():
    """Test that GREETING_INITIATED with non-string track_id raises ValueError."""
    with pytest.raises(ValueError, match="GREETING_INITIATED 'track_id' must be str"):
        bus.publish({"event": "GREETING_INITIATED", "embedding_id": "E0042", "track_id": 456})


def test_greeting_initiated_valid():
    """Test that valid GREETING_INITIATED event is accepted."""
    events_received = []
    bus.subscribe("GREETING_INITIATED", lambda e: events_received.append(e))
    
    bus.publish({"event": "GREETING_INITIATED", "embedding_id": "E0042", "track_id": "T1"})
    
    assert len(events_received) == 1
    assert events_received[0]["event"] == "GREETING_INITIATED"
    assert events_received[0]["embedding_id"] == "E0042"
    assert events_received[0]["track_id"] == "T1"


def test_unknown_event_type_accepted():
    """Test that unknown event types are accepted (extensibility)."""
    received = []
    bus.subscribe("CUSTOM_EVENT", lambda e: received.append(e))
    
    # Should not raise - unknown events are allowed
    bus.publish({
        "event": "CUSTOM_EVENT",
        "custom_field": "data"
    })
    
    assert len(received) == 1


def test_validation_error_doesnt_call_subscribers():
    """Test that invalid events don't reach subscribers."""
    received = []
    bus.subscribe("SESSION_STATE", lambda e: received.append(e))
    
    # Invalid event
    with pytest.raises(ValueError):
        bus.publish({
            "event": "SESSION_STATE",
            "embedding_id": "E1",
            "state": "INVALID"
        })
    
    # Subscriber should not have received it
    assert len(received) == 0
