"""In-process event bus for robot assistant.

Simple pub/sub system for communication between modules.
MQTT transport deferred until Pi becomes a separate device (Phase 5).

Core Principle 6: "Modular services, structured JSON events between them.
In-process calls/async queues while everything runs on one machine; MQTT only
once genuinely distributed."
"""

import logging
from typing import Callable, Dict, List
from collections import defaultdict
import threading

from robot_assistant.events.schemas import validate_event

logger = logging.getLogger(__name__)


# Global subscribers registry: event_type -> list of callbacks
_subscribers: Dict[str, List[Callable]] = defaultdict(list)

# Thread lock for thread-safe subscription/publishing
_lock = threading.Lock()

# Debug flag from config (will be imported after config is loaded)
_debug_log_events = False


def set_debug_logging(enabled: bool):
    """Enable or disable debug logging of all events.
    
    Args:
        enabled: True to log all events, False to log only errors.
    """
    global _debug_log_events
    _debug_log_events = enabled


def subscribe(event_type: str, callback: Callable[[dict], None]) -> None:
    """Register a callback to be invoked whenever an event of the given type is published.
    
    Args:
        event_type: The 'event' field value to filter on (e.g., 'GESTURE_DETECTED').
        callback: Function accepting one dict argument (the event payload).
                  Should not raise exceptions; errors are logged but don't stop other callbacks.
    
    Example:
        def handle_gesture(event: dict):
            print(f"Gesture detected: {event['gesture']}")
        
        subscribe("GESTURE_DETECTED", handle_gesture)
    """
    if not callable(callback):
        raise TypeError(f"Callback must be callable, got {type(callback)}")
    
    with _lock:
        _subscribers[event_type].append(callback)
        logger.info(f"Subscribed to '{event_type}' (total subscribers: {len(_subscribers[event_type])})")


def unsubscribe(event_type: str, callback: Callable[[dict], None]) -> bool:
    """Remove a callback from an event type's subscriber list.
    
    Args:
        event_type: The event type to unsubscribe from.
        callback: The callback function to remove.
    
    Returns:
        True if callback was found and removed, False otherwise.
    """
    with _lock:
        if event_type in _subscribers and callback in _subscribers[event_type]:
            _subscribers[event_type].remove(callback)
            logger.info(f"Unsubscribed from '{event_type}' (remaining subscribers: {len(_subscribers[event_type])})")
            
            # Clean up empty lists
            if not _subscribers[event_type]:
                del _subscribers[event_type]
            
            return True
        return False


def publish(event: dict) -> None:
    """Publish an event to all subscribers of its 'event' type.
    
    Args:
        event: Dict matching one of the schemas in schemas.py.
               Must have an 'event' field specifying the event type.
               Required fields and valid enum values are validated at runtime.
    
    Raises:
        ValueError: If event validation fails (missing required fields, invalid enum values, etc.)
    
    Example:
        publish({
            "event": "GESTURE_DETECTED",
            "gesture": "HAND_RAISED",
            "track_id": "T1"
        })
    
    Note:
        Callbacks are invoked synchronously in the publishing thread.
        If a callback raises an exception, it's logged but other callbacks still run.
    """
    # Validate event structure and contents
    valid, error_msg = validate_event(event)
    if not valid:
        logger.error(f"Invalid event: {error_msg} - Event: {event}")
        raise ValueError(f"Invalid event: {error_msg}")
    
    event_type = event["event"]
    
    # Debug logging if enabled
    if _debug_log_events:
        logger.debug(f"Publishing: {event_type} - {event}")
    
    # Get subscribers (thread-safe copy)
    with _lock:
        callbacks = _subscribers.get(event_type, []).copy()
    
    # Invoke all callbacks
    if not callbacks:
        if _debug_log_events:
            logger.debug(f"No subscribers for '{event_type}'")
        return
    
    for callback in callbacks:
        try:
            callback(event)
        except Exception as e:
            # Log error but don't stop other callbacks
            logger.error(
                f"Error in callback {callback.__name__} for event '{event_type}': {e}",
                exc_info=True
            )


def clear_subscribers(event_type: str = None) -> None:
    """Clear subscribers for testing or reset.
    
    Args:
        event_type: If specified, clear only this event type's subscribers.
                    If None, clear all subscribers.
    """
    with _lock:
        if event_type is None:
            _subscribers.clear()
            logger.info("Cleared all subscribers")
        elif event_type in _subscribers:
            del _subscribers[event_type]
            logger.info(f"Cleared subscribers for '{event_type}'")


def get_subscriber_count(event_type: str = None) -> int:
    """Get the number of subscribers for an event type.
    
    Args:
        event_type: Event type to check. If None, returns total subscribers across all types.
    
    Returns:
        Number of subscribers.
    """
    with _lock:
        if event_type is None:
            return sum(len(callbacks) for callbacks in _subscribers.values())
        return len(_subscribers.get(event_type, []))


def get_event_types() -> List[str]:
    """Get list of all event types that have subscribers.
    
    Returns:
        List of event type strings.
    """
    with _lock:
        return list(_subscribers.keys())
