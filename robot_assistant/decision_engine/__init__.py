"""Decision Engine - 3-way routing and coordination.

Main components:
- engine.py: Central router (Path A/B/C), greeting management
- intents.py: Path A - Deterministic text intents
- gesture_actions.py: Path A - Deterministic gesture-to-action mapping
- safety_gate.py: Software safety layer for actions
"""

from robot_assistant.decision_engine.engine import (
    start_decision_engine,
    stop_decision_engine,
)
from robot_assistant.decision_engine.intents import (
    get_intent_response,
)
from robot_assistant.decision_engine.gesture_actions import (
    get_action,
    start_gesture_handler,
)
from robot_assistant.decision_engine.safety_gate import (
    safety_gate,
    start_safety_gate,
)

__all__ = [
    "start_decision_engine",
    "stop_decision_engine",
    "get_intent_response",
    "get_action",
    "start_gesture_handler",
    "safety_gate",
    "start_safety_gate",
]
