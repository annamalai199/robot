"""Decision Engine components for routing user input to appropriate handlers."""

from robot_assistant.decision_engine.intents import (
    get_intent_response,
    normalize_text,
    add_intent,
    remove_intent,
    get_all_intents,
)

from robot_assistant.decision_engine.gesture_actions import (
    get_action,
    handle_gesture_event,
    start_gesture_handler,
    add_gesture_mapping,
    remove_gesture_mapping,
    get_all_gesture_mappings,
)

from robot_assistant.decision_engine.safety_gate import (
    safety_gate,
    handle_action_event,
    start_safety_gate,
    get_distance_limits,
)

__all__ = [
    # Intents
    "get_intent_response",
    "normalize_text",
    "add_intent",
    "remove_intent",
    "get_all_intents",
    # Gestures
    "get_action",
    "handle_gesture_event",
    "start_gesture_handler",
    "add_gesture_mapping",
    "remove_gesture_mapping",
    "get_all_gesture_mappings",
    # SafetyGate
    "safety_gate",
    "handle_action_event",
    "start_safety_gate",
    "get_distance_limits",
]
