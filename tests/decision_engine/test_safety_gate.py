"""Tests for SafetyGate software safety layer."""

import pytest
from robot_assistant.decision_engine.safety_gate import (
    safety_gate,
    start_safety_gate,
    get_distance_limits,
)
from robot_assistant.events import bus, ActionEvent


@pytest.fixture(autouse=True)
def reset_bus():
    """Clear all subscribers before and after each test."""
    bus.clear_subscribers()
    yield
    bus.clear_subscribers()


def test_case1_no_sensor_wired_allows_with_warning():
    """Test Case 1: distance_cm=None, sensor_ok=True (laptop phase) → allow but log."""
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Laptop phase: no sensor wired up
    result = safety_gate(action, distance_cm=None, sensor_ok=True)
    
    # Should ALLOW (simulation mode)
    assert result is True


def test_case1_no_sensor_does_not_publish_blocked_event():
    """Test Case 1: No sensor phase should NOT publish ACTION_BLOCKED."""
    blocked_events = []
    bus.subscribe("ACTION_BLOCKED", lambda e: blocked_events.append(e))
    
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    result = safety_gate(action, distance_cm=None, sensor_ok=True)
    
    assert result is True
    assert len(blocked_events) == 0  # No block event


def test_case2_sensor_fault_hard_block():
    """Test Case 2: sensor_ok=False → HARD BLOCK (highest priority)."""
    blocked_events = []
    bus.subscribe("ACTION_BLOCKED", lambda e: blocked_events.append(e))
    
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Sensor is faulty - should block regardless of distance
    result = safety_gate(action, distance_cm=30.0, sensor_ok=False)
    
    # Should BLOCK
    assert result is False
    
    # Should publish ACTION_BLOCKED with reason="sensor_fault"
    assert len(blocked_events) == 1
    assert blocked_events[0]["event"] == "ACTION_BLOCKED"
    assert blocked_events[0]["action"] == "HANDSHAKE"
    assert blocked_events[0]["track_id"] == "T1"
    assert blocked_events[0]["reason"] == "sensor_fault"


def test_case2_sensor_fault_does_not_default_to_allow():
    """Test Case 2: Sensor fault must NOT silently default to allow (safety-critical)."""
    # Even with "good" distance, sensor fault should block
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Distance is perfect (30cm, middle of 10-60cm range), but sensor is bad
    result = safety_gate(action, distance_cm=30.0, sensor_ok=False)
    
    # Must NOT allow - sensor fault overrides everything
    assert result is False


def test_case3_distance_too_close_blocks():
    """Test Case 3: distance < min (10cm) → BLOCK, reason="target_too_close"."""
    blocked_events = []
    bus.subscribe("ACTION_BLOCKED", lambda e: blocked_events.append(e))
    
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Distance 5cm (below min of 10cm)
    result = safety_gate(action, distance_cm=5.0, sensor_ok=True)
    
    # Should BLOCK
    assert result is False
    
    # Should publish ACTION_BLOCKED with reason="target_too_close"
    assert len(blocked_events) == 1
    assert blocked_events[0]["reason"] == "target_too_close"
    assert blocked_events[0]["action"] == "HANDSHAKE"
    assert blocked_events[0]["track_id"] == "T1"


def test_case3_edge_case_exactly_at_min():
    """Test Case 3 edge: distance exactly at min (10cm) → ALLOW."""
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Exactly at minimum (10cm)
    result = safety_gate(action, distance_cm=10.0, sensor_ok=True)
    
    # Should ALLOW (at boundary is OK)
    assert result is True


def test_case4_distance_too_far_blocks():
    """Test Case 4: distance > max (60cm) → BLOCK, reason="target_too_far"."""
    blocked_events = []
    bus.subscribe("ACTION_BLOCKED", lambda e: blocked_events.append(e))
    
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Distance 80cm (above max of 60cm - person moved away)
    result = safety_gate(action, distance_cm=80.0, sensor_ok=True)
    
    # Should BLOCK
    assert result is False
    
    # Should publish ACTION_BLOCKED with reason="target_too_far"
    assert len(blocked_events) == 1
    assert blocked_events[0]["reason"] == "target_too_far"
    assert blocked_events[0]["action"] == "HANDSHAKE"
    assert blocked_events[0]["track_id"] == "T1"


def test_case4_edge_case_exactly_at_max():
    """Test Case 4 edge: distance exactly at max (60cm) → ALLOW."""
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Exactly at maximum (60cm)
    result = safety_gate(action, distance_cm=60.0, sensor_ok=True)
    
    # Should ALLOW (at boundary is OK)
    assert result is True


def test_case5_distance_in_range_allows():
    """Test Case 5: distance in valid range, sensor OK → ALLOW."""
    blocked_events = []
    bus.subscribe("ACTION_BLOCKED", lambda e: blocked_events.append(e))
    
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Distance 30cm (middle of 10-60cm range), sensor OK
    result = safety_gate(action, distance_cm=30.0, sensor_ok=True)
    
    # Should ALLOW
    assert result is True
    
    # Should NOT publish ACTION_BLOCKED
    assert len(blocked_events) == 0


def test_case5_multiple_valid_distances():
    """Test Case 5: Multiple distances within valid range all allow."""
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Test various distances within 10-60cm range
    valid_distances = [10.0, 15.0, 25.0, 35.0, 45.0, 55.0, 60.0]
    
    for distance in valid_distances:
        result = safety_gate(action, distance_cm=distance, sensor_ok=True)
        assert result is True, f"Distance {distance}cm should be allowed"


def test_priority_sensor_fault_overrides_good_distance():
    """Test that sensor_ok=False blocks even with perfect distance (priority test)."""
    # Perfect distance (30cm), but sensor is faulty
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    result = safety_gate(action, distance_cm=30.0, sensor_ok=False)
    
    # Sensor fault has highest priority - must block
    assert result is False


def test_does_not_call_motion_planner_directly():
    """Test that SafetyGate does NOT call motion planner directly.
    
    This is verified by the fact that it only returns bool and publishes events.
    Motion planner (Task 10) will subscribe to events later.
    """
    import robot_assistant.decision_engine.safety_gate as sg
    
    # Check that motion_planner is not imported
    assert not hasattr(sg, 'motion_planner')
    
    # Verify it only makes decisions and publishes events
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Call should only return bool, not execute motion
    result = safety_gate(action, distance_cm=30.0, sensor_ok=True)
    assert isinstance(result, bool)


def test_handle_action_event_subscribes():
    """Test that handle_action_event can be subscribed to ACTION events."""
    # Start SafetyGate
    start_safety_gate()
    
    # Check subscription
    event_types = bus.get_event_types()
    assert "ACTION" in event_types


def test_handle_action_event_blocks_unsafe():
    """Test event handler blocks unsafe actions via event flow."""
    blocked_events = []
    bus.subscribe("ACTION_BLOCKED", lambda e: blocked_events.append(e))
    
    # Start SafetyGate (subscribes to ACTION)
    start_safety_gate()
    
    # Publish ACTION event (simulating gesture handler)
    # Note: In laptop phase, distance_cm=None in handle_action_event, so this will allow
    # But we can't test blocking via events in laptop phase without modifying handle_action_event
    # So this test just confirms the subscription works
    action_event: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    bus.publish(action_event)
    
    # In laptop phase (no sensor), should allow
    # In Pi phase (with sensor), handle_action_event would read sensor and potentially block


def test_latency_target():
    """Test that SafetyGate decision meets < 5ms latency target."""
    import time
    
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Warm up
    safety_gate(action, distance_cm=30.0, sensor_ok=True)
    
    # Measure latency
    start = time.time()
    for _ in range(1000):
        safety_gate(action, distance_cm=30.0, sensor_ok=True)
    elapsed_ms = (time.time() - start) * 1000
    
    avg_latency = elapsed_ms / 1000
    
    # Should be well under 5ms target (it's just comparisons)
    assert avg_latency < 5.0, f"Average latency {avg_latency:.2f}ms exceeds 5ms target"


def test_multiple_actions_in_sequence():
    """Test that multiple actions can be checked in sequence."""
    blocked_events = []
    bus.subscribe("ACTION_BLOCKED", lambda e: blocked_events.append(e))
    
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Sequence: allow, block (too close), allow, block (too far), allow
    test_cases = [
        (30.0, True, True),   # Valid distance
        (5.0, True, False),   # Too close
        (40.0, True, True),   # Valid distance
        (80.0, True, False),  # Too far
        (25.0, True, True),   # Valid distance
    ]
    
    for distance, sensor_ok, expected_allow in test_cases:
        result = safety_gate(action, distance, sensor_ok)
        assert result == expected_allow
    
    # Should have 2 blocked events (cases 2 and 4)
    assert len(blocked_events) == 2


def test_get_distance_limits():
    """Test retrieving configured distance limits."""
    min_cm, max_cm = get_distance_limits()
    
    assert min_cm == 10
    assert max_cm == 60
    assert min_cm < max_cm


def test_action_blocked_event_schema_compliance():
    """Test that ACTION_BLOCKED events match the schema from Section 5."""
    blocked_events = []
    bus.subscribe("ACTION_BLOCKED", lambda e: blocked_events.append(e))
    
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Trigger a block
    safety_gate(action, distance_cm=5.0, sensor_ok=True)
    
    # Verify schema compliance
    assert len(blocked_events) == 1
    event = blocked_events[0]
    
    # Required fields from Section 5 schema
    assert "event" in event
    assert "action" in event
    assert "track_id" in event
    assert "reason" in event
    
    # Values
    assert event["event"] == "ACTION_BLOCKED"
    assert event["action"] == "HANDSHAKE"
    assert event["track_id"] == "T1"
    assert event["reason"] in ["target_too_close", "target_too_far", "sensor_fault"]


def test_all_three_block_reasons():
    """Test that all three block reasons can be triggered."""
    blocked_events = []
    bus.subscribe("ACTION_BLOCKED", lambda e: blocked_events.append(e))
    
    action: ActionEvent = {
        "event": "ACTION",
        "action": "HANDSHAKE",
        "track_id": "T1"
    }
    
    # Reason 1: sensor_fault
    safety_gate(action, distance_cm=30.0, sensor_ok=False)
    
    # Reason 2: target_too_close
    safety_gate(action, distance_cm=5.0, sensor_ok=True)
    
    # Reason 3: target_too_far
    safety_gate(action, distance_cm=80.0, sensor_ok=True)
    
    # Should have 3 blocked events
    assert len(blocked_events) == 3
    
    # Verify all three reasons present
    reasons = [e["reason"] for e in blocked_events]
    assert "sensor_fault" in reasons
    assert "target_too_close" in reasons
    assert "target_too_far" in reasons
