"""Integration example showing how the event bus connects components.

This demonstrates the full flow from gesture detection to action execution.
"""

import pytest
from robot_assistant.events import (
    subscribe,
    publish,
    clear_subscribers,
    GestureDetectedEvent,
    ActionEvent,
    ActionBlockedEvent,
)


@pytest.fixture(autouse=True)
def reset_bus():
    """Clear all subscribers before and after each test."""
    clear_subscribers()
    yield
    clear_subscribers()


def test_gesture_to_action_flow():
    """Test the full flow: GESTURE_DETECTED -> ACTION (simulating Decision Engine)."""
    received_actions = []
    
    # Simulate Decision Engine subscribing to gestures
    def handle_gesture(event: GestureDetectedEvent):
        """Decision Engine: convert gesture to action."""
        if event["gesture"] == "HAND_RAISED":
            action_event: ActionEvent = {
                "event": "ACTION",
                "action": "HANDSHAKE",
                "track_id": event["track_id"]
            }
            publish(action_event)
    
    # Simulate Motion Planner subscribing to actions
    def handle_action(event: ActionEvent):
        """Motion Planner: log action (simulated, no real servos yet)."""
        received_actions.append(event)
    
    subscribe("GESTURE_DETECTED", handle_gesture)
    subscribe("ACTION", handle_action)
    
    # Simulate Vision system publishing gesture detection
    gesture_event: GestureDetectedEvent = {
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T1"
    }
    publish(gesture_event)
    
    # Verify the action was received by motion planner
    assert len(received_actions) == 1
    assert received_actions[0]["action"] == "HANDSHAKE"
    assert received_actions[0]["track_id"] == "T1"


def test_safety_gate_blocking_flow():
    """Test SafetyGate blocking an action and publishing ACTION_BLOCKED."""
    blocked_actions = []
    executed_actions = []
    
    # Simulate SafetyGate checking actions before execution
    def safety_gate_check(event: ActionEvent):
        """SafetyGate: check if action is safe (simulated distance check)."""
        # Simulate: distance too close
        distance_cm = 5  # Below min threshold (10cm)
        
        if distance_cm < 10:
            blocked_event: ActionBlockedEvent = {
                "event": "ACTION_BLOCKED",
                "action": event["action"],
                "track_id": event["track_id"],
                "reason": "target_too_close"
            }
            publish(blocked_event)
        else:
            # Would execute the action (not tested here)
            executed_actions.append(event)
    
    def handle_blocked(event: ActionBlockedEvent):
        """Log blocked actions."""
        blocked_actions.append(event)
    
    subscribe("ACTION", safety_gate_check)
    subscribe("ACTION_BLOCKED", handle_blocked)
    
    # Publish action
    action_event: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    publish(action_event)
    
    # Verify action was blocked
    assert len(blocked_actions) == 1
    assert blocked_actions[0]["reason"] == "target_too_close"
    assert len(executed_actions) == 0


def test_multiple_components_listening():
    """Test multiple components listening to the same event (fan-out)."""
    # Simulate multiple systems interested in identity resolution
    decision_engine_log = []
    session_state_log = []
    ui_log = []
    
    def decision_engine_handler(event):
        decision_engine_log.append(f"DE: {event['embedding_id']}")
    
    def session_state_handler(event):
        session_state_log.append(f"SS: {event['embedding_id']}")
    
    def ui_handler(event):
        ui_log.append(f"UI: {event.get('name', 'Unknown')}")
    
    subscribe("IDENTITY_RESOLVED", decision_engine_handler)
    subscribe("IDENTITY_RESOLVED", session_state_handler)
    subscribe("IDENTITY_RESOLVED", ui_handler)
    
    # Publish identity resolution
    publish({
        "event": "IDENTITY_RESOLVED",
        "track_id": "T1",
        "embedding_id": "E0042",
        "status": "known",
        "name": "Annamalai",
        "confidence": 0.91
    })
    
    # All three components should have received it
    assert len(decision_engine_log) == 1
    assert len(session_state_log) == 1
    assert len(ui_log) == 1
    
    assert "E0042" in decision_engine_log[0]
    assert "E0042" in session_state_log[0]
    assert "Annamalai" in ui_log[0]


def test_event_chain():
    """Test a chain of events: GESTURE -> ACTION -> SERVO_COMMAND."""
    event_chain = []
    
    def handle_gesture(event):
        event_chain.append("1_GESTURE")
        # Decision Engine emits ACTION
        publish({"event": "ACTION", "action": "HANDSHAKE", "track_id": event["track_id"]})
    
    def handle_action(event):
        event_chain.append("2_ACTION")
        # SafetyGate passes, Motion Planner emits SERVO_COMMAND
        publish({
            "event": "SERVO_COMMAND",
            "preset": "HANDSHAKE_READY",
            "joints": {"shoulder": 45, "elbow": 90, "wrist": 0}
        })
    
    def handle_servo(event):
        event_chain.append("3_SERVO")
    
    subscribe("GESTURE_DETECTED", handle_gesture)
    subscribe("ACTION", handle_action)
    subscribe("SERVO_COMMAND", handle_servo)
    
    # Trigger the chain
    publish({
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T1"
    })
    
    # Verify the entire chain executed
    assert event_chain == ["1_GESTURE", "2_ACTION", "3_SERVO"]
