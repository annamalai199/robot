"""Gesture-to-action mapping for deterministic physical responses.

This module handles gesture recognition events from the vision pipeline and
maps them to physical actions. It subscribes to GESTURE_DETECTED events and
publishes ACTION events.

This is separate from text intents (intents.py) - gestures trigger physical
actions, while text triggers verbal responses.

The ACTION events published here will be checked by SafetyGate (safety_gate.py)
before reaching the motion planner. This module does NOT call SafetyGate or
motion planner directly - it only publishes events.
"""

import logging
from typing import Optional

from robot_assistant.config import config
from robot_assistant.events import subscribe, publish, GestureDetectedEvent, ActionEvent

logger = logging.getLogger(__name__)


def get_action(gesture: str) -> Optional[str]:
    """Map a gesture to an action.
    
    Args:
        gesture: Gesture name (e.g., "HAND_RAISED").
    
    Returns:
        Action name (e.g., "HANDSHAKE") if gesture is recognized, None otherwise.
    
    Example:
        >>> get_action("HAND_RAISED")
        "HANDSHAKE"
        
        >>> get_action("UNKNOWN_GESTURE")
        None
    """
    return config.GESTURE_ACTIONS.get(gesture)


def handle_gesture_event(event: GestureDetectedEvent) -> None:
    """Handle GESTURE_DETECTED event from vision pipeline.
    
    Maps the gesture to an action and publishes ACTION event if recognized.
    Unrecognized gestures are safely ignored (no-op).
    
    Args:
        event: GESTURE_DETECTED event with gesture name and track_id.
    
    Side Effects:
        If gesture is recognized, publishes ACTION event to event bus.
        SafetyGate (downstream) will check the action before motion execution.
    """
    gesture = event["gesture"]
    track_id = event["track_id"]
    
    # Look up action for this gesture
    action = get_action(gesture)
    
    if action is None:
        # Unknown gesture - log and ignore (safe no-op)
        logger.debug(f"Unknown gesture '{gesture}' from track {track_id} - ignoring")
        return
    
    # Known gesture - publish ACTION event
    action_event: ActionEvent = {
        "event": "ACTION",
        "action": action,
        "track_id": track_id
    }
    
    publish(action_event)
    
    logger.info(f"Gesture '{gesture}' (track {track_id}) → ACTION '{action}'")


def start_gesture_handler() -> None:
    """Subscribe to GESTURE_DETECTED events.
    
    Call this once during application startup to activate gesture-to-action mapping.
    The handler will remain active until the application exits.
    """
    subscribe("GESTURE_DETECTED", handle_gesture_event)
    logger.info("Gesture-to-action handler started")


def add_gesture_mapping(gesture: str, action: str) -> None:
    """Add a new gesture-to-action mapping at runtime.
    
    Useful for testing or dynamic gesture addition.
    
    Args:
        gesture: Gesture name (e.g., "WAVE").
        action: Action name (e.g., "WAVE_BACK").
    """
    config.GESTURE_ACTIONS[gesture] = action
    logger.info(f"Added gesture mapping: '{gesture}' → '{action}'")


def remove_gesture_mapping(gesture: str) -> bool:
    """Remove a gesture-to-action mapping at runtime.
    
    Args:
        gesture: Gesture name to remove.
    
    Returns:
        True if mapping was found and removed, False otherwise.
    """
    if gesture in config.GESTURE_ACTIONS:
        del config.GESTURE_ACTIONS[gesture]
        logger.info(f"Removed gesture mapping: '{gesture}'")
        return True
    return False


def get_all_gesture_mappings() -> dict[str, str]:
    """Get all registered gesture-to-action mappings.
    
    Returns:
        Dict mapping gesture names to action names.
    """
    return dict(config.GESTURE_ACTIONS)
