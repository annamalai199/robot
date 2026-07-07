"""End-to-end test for gesture → action flow (Path A deterministic).

Tests the complete flow:
    GESTURE_DETECTED → gesture_actions → ACTION → SafetyGate

Verifies:
- Gesture-to-action mapping works (HAND_RAISED → HANDSHAKE)
- ACTION event is published with correct structure
- SafetyGate processes ACTION and allows it (distance_cm=None simulation mode)
- No ACTION_BLOCKED event is published
- Zero LLM calls (gesture flow doesn't trigger text routing)
- Full E2E test completes in <100ms
"""

import pytest
import time
import logging
from unittest.mock import patch

from robot_assistant.events import publish, subscribe, clear_subscribers
from robot_assistant.events.schemas import GestureDetectedEvent, ActionEvent, ActionBlockedEvent
from robot_assistant.decision_engine.gesture_actions import start_gesture_handler
from robot_assistant.decision_engine.safety_gate import start_safety_gate


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup event handlers and cleanup subscribers after each test."""
    # Clear any existing subscribers from previous tests
    clear_subscribers()
    
    # Start handlers (must be called to subscribe to events)
    start_gesture_handler()
    start_safety_gate()
    
    yield
    
    # Cleanup after test
    clear_subscribers()


def test_e2e_gesture_handshake(caplog):
    """E2E test: GESTURE_DETECTED → gesture_actions → ACTION → SafetyGate.
    
    This is a true end-to-end test that verifies the complete flow:
    1. Publish GESTURE_DETECTED event
    2. gesture_actions.handle_gesture_event() maps it to ACTION event
    3. Capture the REAL ACTION event published by gesture_actions
    4. SafetyGate.handle_action_event() processes that ACTION event
    5. Verify SafetyGate allows action (distance_cm=None) and logs correctly
    6. Verify NO ACTION_BLOCKED event was published
    7. Verify zero LLM calls (gesture flow is separate from text routing)
    8. Verify test completes in <100ms
    """
    # Set log level to capture SafetyGate's logs (WARNING for simulation, INFO for motion planner)
    caplog.set_level(logging.INFO, logger="robot_assistant.decision_engine.safety_gate")
    
    # Capture published ACTION events (from gesture_actions)
    captured_actions = []
    def capture_action(event: ActionEvent):
        captured_actions.append(event)
    subscribe("ACTION", capture_action)
    
    # Capture ACTION_BLOCKED events (should remain empty)
    captured_blocked = []
    def capture_blocked(event: ActionBlockedEvent):
        captured_blocked.append(event)
    subscribe("ACTION_BLOCKED", capture_blocked)
    
    # Mock LLM stub to verify zero calls
    with patch('robot_assistant.decision_engine.engine._stub_llm_generate') as mock_llm:
        # Start timing
        start_time = time.time()
        
        # Publish GESTURE_DETECTED event
        gesture_event: GestureDetectedEvent = {
            "event": "GESTURE_DETECTED",
            "gesture": "HAND_RAISED",  # From config.GESTURE_ACTIONS
            "track_id": "T1"
        }
        publish(gesture_event)
        
        # Note: publish() is synchronous - all callbacks execute before it returns
        # No need for sleep() - all processing is complete by here
        
        # End timing
        elapsed_ms = (time.time() - start_time) * 1000
        
        # =====================================================================
        # ASSERTIONS
        # =====================================================================
        
        # Assert 1: gesture_actions published exactly one ACTION event
        assert len(captured_actions) == 1, f"Expected 1 ACTION event, got {len(captured_actions)}"
        
        # Assert 2: ACTION event has correct structure (from gesture_actions)
        action = captured_actions[0]
        assert action["event"] == "ACTION"
        assert action["action"] == "HANDSHAKE", f"Expected HANDSHAKE, got {action['action']}"
        assert action["track_id"] == "T1", f"Expected T1, got {action['track_id']}"
        
        # Assert 3: SafetyGate logged simulation warning (distance_cm=None)
        assert "SafetyGate ALLOWED (simulated)" in caplog.text, \
            "Missing SafetyGate simulation log"
        assert "HANDSHAKE (track T1)" in caplog.text, \
            "Missing action/track info in SafetyGate log"
        assert "No sensor wired up (distance_cm=None)" in caplog.text, \
            "Missing distance_cm=None explanation in SafetyGate log"
        
        # Assert 4: SafetyGate logged motion planner message (action allowed)
        assert "would proceed to motion planner" in caplog.text, \
            "Missing motion planner log (action should be allowed)"
        
        # Assert 5: NO ACTION_BLOCKED event was published
        assert len(captured_blocked) == 0, \
            f"Expected no ACTION_BLOCKED events, got {len(captured_blocked)}: {captured_blocked}"
        
        # Assert 6: LLM was never called (gesture flow doesn't trigger text routing)
        assert mock_llm.call_count == 0, \
            f"LLM stub should not be called for gesture flow, but was called {mock_llm.call_count} times"
        
        # Assert 7: Test completes in <100ms
        assert elapsed_ms < 100, \
            f"Test took {elapsed_ms:.1f}ms, should be <100ms"
        
        print(f"✓ E2E gesture handshake test passed in {elapsed_ms:.1f}ms")
