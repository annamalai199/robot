"""Tests for gesture-to-action mapping."""

import pytest
from robot_assistant.decision_engine import gesture_actions
from robot_assistant.events import bus, GestureDetectedEvent


@pytest.fixture(autouse=True)
def reset_bus():
    """Clear all subscribers before and after each test."""
    bus.clear_subscribers()
    yield
    bus.clear_subscribers()


def test_known_gesture_returns_action():
    """Test that known gesture returns mapped action."""
    action = gesture_actions.get_action("HAND_RAISED")
    
    assert action is not None
    assert action == "HANDSHAKE"


def test_unknown_gesture_returns_none():
    """Test that unknown gesture returns None (safe no-op)."""
    action = gesture_actions.get_action("UNKNOWN_GESTURE")
    
    assert action is None


def test_gesture_event_publishes_action():
    """Test that GESTURE_DETECTED event triggers ACTION event."""
    action_events = []
    bus.subscribe("ACTION", lambda e: action_events.append(e))
    
    # Publish GESTURE_DETECTED event (simulating vision pipeline)
    gesture_event: GestureDetectedEvent = {
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T1"
    }
    
    # Handle the event
    gesture_actions.handle_gesture_event(gesture_event)
    
    # Should have published ACTION event
    assert len(action_events) == 1
    assert action_events[0]["event"] == "ACTION"
    assert action_events[0]["action"] == "HANDSHAKE"
    assert action_events[0]["track_id"] == "T1"


def test_unknown_gesture_does_not_publish_action():
    """Test that unrecognized gesture does NOT publish ACTION event (safe no-op)."""
    action_events = []
    bus.subscribe("ACTION", lambda e: action_events.append(e))
    
    # Publish unknown gesture
    gesture_event: GestureDetectedEvent = {
        "event": "GESTURE_DETECTED",
        "gesture": "COMPLETELY_UNKNOWN",
        "track_id": "T2"
    }
    
    # Handle the event - should be safe no-op
    gesture_actions.handle_gesture_event(gesture_event)
    
    # Should NOT have published any ACTION event
    assert len(action_events) == 0


def test_gesture_handler_subscription():
    """Test that gesture handler subscribes to GESTURE_DETECTED."""
    # Start handler
    gesture_actions.start_gesture_handler()
    
    # Check subscription
    event_types = bus.get_event_types()
    assert "GESTURE_DETECTED" in event_types
    assert bus.get_subscriber_count("GESTURE_DETECTED") >= 1


def test_gesture_handler_end_to_end():
    """Test full flow: start handler → publish gesture → receive action."""
    action_events = []
    bus.subscribe("ACTION", lambda e: action_events.append(e))
    
    # Start gesture handler (subscribes to GESTURE_DETECTED)
    gesture_actions.start_gesture_handler()
    
    # Publish gesture event via bus (simulating vision pipeline)
    gesture_event: GestureDetectedEvent = {
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T3"
    }
    bus.publish(gesture_event)
    
    # Should have triggered action
    assert len(action_events) == 1
    assert action_events[0]["action"] == "HANDSHAKE"


def test_multiple_gestures_same_track():
    """Test multiple gestures from same track produce multiple actions."""
    action_events = []
    bus.subscribe("ACTION", lambda e: action_events.append(e))
    
    gesture_actions.start_gesture_handler()
    
    # Same track, multiple gestures
    for i in range(3):
        bus.publish({
            "event": "GESTURE_DETECTED",
            "gesture": "HAND_RAISED",
            "track_id": "T1"
        })
    
    # Should have 3 action events
    assert len(action_events) == 3
    assert all(e["track_id"] == "T1" for e in action_events)


def test_multiple_tracks_different_gestures():
    """Test gestures from different tracks are handled independently."""
    action_events = []
    bus.subscribe("ACTION", lambda e: action_events.append(e))
    
    gesture_actions.start_gesture_handler()
    
    # Different tracks
    bus.publish({
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T1"
    })
    
    bus.publish({
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T2"
    })
    
    # Should have 2 actions, different tracks
    assert len(action_events) == 2
    assert action_events[0]["track_id"] == "T1"
    assert action_events[1]["track_id"] == "T2"


def test_add_gesture_mapping_runtime():
    """Test adding new gesture mapping at runtime."""
    # Should not match initially
    assert gesture_actions.get_action("WAVE") is None
    
    # Add mapping
    gesture_actions.add_gesture_mapping("WAVE", "WAVE_BACK")
    
    # Should now match
    action = gesture_actions.get_action("WAVE")
    assert action == "WAVE_BACK"
    
    # Test via event handler
    action_events = []
    bus.subscribe("ACTION", lambda e: action_events.append(e))
    
    gesture_actions.handle_gesture_event({
        "event": "GESTURE_DETECTED",
        "gesture": "WAVE",
        "track_id": "T1"
    })
    
    assert len(action_events) == 1
    assert action_events[0]["action"] == "WAVE_BACK"


def test_remove_gesture_mapping_runtime():
    """Test removing gesture mapping at runtime."""
    # Add a temporary mapping
    gesture_actions.add_gesture_mapping("TEMP_GESTURE", "TEMP_ACTION")
    assert gesture_actions.get_action("TEMP_GESTURE") == "TEMP_ACTION"
    
    # Remove it
    removed = gesture_actions.remove_gesture_mapping("TEMP_GESTURE")
    assert removed is True
    
    # Should no longer map
    assert gesture_actions.get_action("TEMP_GESTURE") is None
    
    # Removing again should return False
    removed = gesture_actions.remove_gesture_mapping("TEMP_GESTURE")
    assert removed is False


def test_get_all_gesture_mappings():
    """Test retrieving all gesture mappings."""
    all_mappings = gesture_actions.get_all_gesture_mappings()
    
    assert isinstance(all_mappings, dict)
    assert "HAND_RAISED" in all_mappings
    assert all_mappings["HAND_RAISED"] == "HANDSHAKE"


def test_does_not_emit_response_event():
    """Test that gestures do NOT emit RESPONSE events (that's intents.py)."""
    response_events = []
    bus.subscribe("RESPONSE", lambda e: response_events.append(e))
    
    # Handle gesture
    gesture_actions.handle_gesture_event({
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T1"
    })
    
    # Should NOT have published RESPONSE event
    assert len(response_events) == 0


def test_does_not_call_safety_gate_directly():
    """Test that gesture handler does NOT call SafetyGate directly.
    
    This is verified by the fact that it only publishes ACTION events.
    SafetyGate (built in Task 1.5) will subscribe to ACTION events downstream.
    """
    # This is a design test - gesture_actions.py should not import safety_gate
    import robot_assistant.decision_engine.gesture_actions as ga
    
    # Check that safety_gate is not imported
    assert not hasattr(ga, 'safety_gate')
    
    # Verify it only publishes events, doesn't call other modules
    action_events = []
    bus.subscribe("ACTION", lambda e: action_events.append(e))
    
    gesture_actions.handle_gesture_event({
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T1"
    })
    
    # Should have published ACTION event (SafetyGate will handle it later)
    assert len(action_events) == 1


def test_case_sensitivity():
    """Test that gesture names are case-sensitive (unlike intents)."""
    # Config has "HAND_RAISED" (uppercase)
    assert gesture_actions.get_action("HAND_RAISED") == "HANDSHAKE"
    
    # Lowercase should not match (gestures are enum-like constants)
    assert gesture_actions.get_action("hand_raised") is None


def test_mixed_known_and_unknown_gestures():
    """Test sequence of known and unknown gestures."""
    action_events = []
    bus.subscribe("ACTION", lambda e: action_events.append(e))
    
    gesture_actions.start_gesture_handler()
    
    # Sequence: known, unknown, known, unknown
    gestures = [
        ("HAND_RAISED", True),    # Should produce action
        ("UNKNOWN_1", False),      # Should be ignored
        ("HAND_RAISED", True),    # Should produce action
        ("UNKNOWN_2", False),      # Should be ignored
    ]
    
    for gesture, should_produce_action in gestures:
        bus.publish({
            "event": "GESTURE_DETECTED",
            "gesture": gesture,
            "track_id": "T1"
        })
    
    # Should have exactly 2 actions (only the known gestures)
    assert len(action_events) == 2
    assert all(e["action"] == "HANDSHAKE" for e in action_events)


def test_gesture_extensibility():
    """Test that system is extensible for future gestures."""
    # Add multiple new gestures
    new_mappings = {
        "THUMBS_UP": "ACKNOWLEDGE",
        "PEACE_SIGN": "GREET_FRIENDLY",
        "POINTING": "INDICATE_DIRECTION",
    }
    
    for gesture, action in new_mappings.items():
        gesture_actions.add_gesture_mapping(gesture, action)
    
    # Verify all work
    for gesture, expected_action in new_mappings.items():
        actual_action = gesture_actions.get_action(gesture)
        assert actual_action == expected_action


def test_no_default_action():
    """Test that there is NO default action for unknown gestures.
    
    Safety-critical: Unknown gestures should NOT trigger any action.
    """
    action_events = []
    bus.subscribe("ACTION", lambda e: action_events.append(e))
    
    # Try various unknown gestures
    unknown_gestures = [
        "RANDOM_GESTURE",
        "UNDEFINED",
        "",  # Empty string
        "HAND_LOWERED",  # Similar to known but not exact
    ]
    
    for gesture in unknown_gestures:
        gesture_actions.handle_gesture_event({
            "event": "GESTURE_DETECTED",
            "gesture": gesture,
            "track_id": "T1"
        })
    
    # NONE of these should produce actions
    assert len(action_events) == 0
