"""Event schemas for the robot assistant.

All events are TypedDicts to provide type hints and validation.
A typo in a field name will fail at construction time, not silently at runtime.
"""

from typing import TypedDict, Literal, Optional


class GestureDetectedEvent(TypedDict):
    """Published when a gesture is recognized from pose keypoints.
    
    Example: {"event": "GESTURE_DETECTED", "gesture": "HAND_RAISED", "track_id": "T1"}
    """
    event: Literal["GESTURE_DETECTED"]
    gesture: str  # "HAND_RAISED", etc.
    track_id: str  # Vision tracker ID (transient, resets when person leaves/re-enters)


class IdentityResolvedEvent(TypedDict):
    """Published when face recognition completes for a track.
    
    Known face example:
    {"event": "IDENTITY_RESOLVED", "track_id": "T1", "embedding_id": "E0042", 
     "status": "known", "name": "Annamalai", "confidence": 0.91}
    
    New face example:
    {"event": "IDENTITY_RESOLVED", "track_id": "T1", "embedding_id": "U1042",
     "status": "new", "name": null, "confidence": null}
    """
    event: Literal["IDENTITY_RESOLVED"]
    track_id: str  # Current vision track ID (transient)
    embedding_id: str  # Persistent face embedding ID (e.g., "E0042" or "U1042")
    status: Literal["known", "new", "registered_unknown"]  # known=has name, new=never seen, registered_unknown=seen but no name
    name: Optional[str]  # Person's name if known, None otherwise
    confidence: Optional[float]  # Match confidence 0-1, None for new faces


class TrackLostEvent(TypedDict):
    """Published when a person leaves frame (track lost for >30 frames).
    
    Example: {"event": "TRACK_LOST", "track_id": "T1", "embedding_id": "E0042"}
    """
    event: Literal["TRACK_LOST"]
    track_id: str  # Track ID that was lost (transient)
    embedding_id: str  # Persistent identity (used for session state)


class SessionStateEvent(TypedDict):
    """Published when an identity's session state changes.
    
    Example: {"event": "SESSION_STATE", "embedding_id": "E0042", "state": "RETURNED"}
    
    State transitions:
    - NEW: Never seen before
    - GREETED: Currently in frame, already greeted this visit
    - AWAY: Track lost (person left)
    - RETURNED: Re-appeared after being AWAY
    """
    event: Literal["SESSION_STATE"]
    embedding_id: str  # Persistent face embedding ID
    state: Literal["NEW", "GREETED", "AWAY", "RETURNED"]


class ActionEvent(TypedDict):
    """Published when Decision Engine decides to execute a physical action.
    
    Must pass through SafetyGate before reaching motion planner.
    
    Example: {"event": "ACTION", "action": "HANDSHAKE", "track_id": "T1"}
    """
    event: Literal["ACTION"]
    action: str  # "HANDSHAKE", etc. (maps to servo presets)
    track_id: str  # Target person's track ID


class ActionBlockedEvent(TypedDict):
    """Published when SafetyGate blocks an action.
    
    Examples:
    {"event": "ACTION_BLOCKED", "action": "HANDSHAKE", "track_id": "T1", "reason": "target_too_close"}
    {"event": "ACTION_BLOCKED", "action": "HANDSHAKE", "track_id": "T1", "reason": "sensor_fault"}
    """
    event: Literal["ACTION_BLOCKED"]
    action: str  # Action that was blocked
    track_id: str  # Target person's track ID
    reason: Literal["target_too_close", "target_too_far", "sensor_fault"]


class ServoCommandEvent(TypedDict):
    """Published when an action is approved and ready for execution.
    
    Example:
    {"event": "SERVO_COMMAND", "preset": "HANDSHAKE_READY", 
     "joints": {"shoulder": 45, "elbow": 90, "wrist": 0}}
    """
    event: Literal["SERVO_COMMAND"]
    preset: str  # Preset name from config (e.g., "HANDSHAKE_READY", "REST")
    joints: dict[str, float]  # Joint name -> angle in degrees


class TextInputEvent(TypedDict):
    """Published when text input is received (from voice STT or text UI).
    
    Example: {"event": "TEXT_INPUT", "text": "What are the lab hours?", "source": "voice"}
    """
    event: Literal["TEXT_INPUT"]
    text: str  # Normalized input text
    source: Literal["voice", "keyboard"]  # Input source


class ResponseEvent(TypedDict):
    """Published when a response is generated (to be spoken via TTS).
    
    Example:
    {"event": "RESPONSE", "text": "Lab hours are Monday 2-5 PM.", 
     "path": "cache", "latency_ms": 23.5}
    """
    event: Literal["RESPONSE"]
    text: str  # Response text to speak
    path: Literal["deterministic", "cache", "llm"]  # Which decision path generated it
    latency_ms: float  # Time taken to generate response


class GreetingDeliveredEvent(TypedDict):
    """Published when TTS finishes delivering a greeting to a person.
    
    This event marks the completion of greeting delivery (not just decision).
    Only fires for NEW identities transitioning to GREETED state.
    
    Example:
    {"event": "GREETING_DELIVERED", "embedding_id": "E0042", "track_id": "T1"}
    """
    event: Literal["GREETING_DELIVERED"]
    embedding_id: str  # Persistent identity that was greeted
    track_id: str  # Current vision track ID


class GreetingInitiatedEvent(TypedDict):
    """Published when Decision Engine sends a greeting to TTS for synthesis.
    
    This event starts the greeting timeout timer in Session State Store.
    Does NOT change state - state only transitions NEW → GREETED after
    GREETING_DELIVERED fires (or after 5s timeout).
    
    Example:
    {"event": "GREETING_INITIATED", "embedding_id": "E0042", "track_id": "T1"}
    """
    event: Literal["GREETING_INITIATED"]
    embedding_id: str  # Persistent identity being greeted
    track_id: str  # Current vision track ID


# Type alias for any event
Event = (
    GestureDetectedEvent
    | IdentityResolvedEvent
    | TrackLostEvent
    | SessionStateEvent
    | ActionEvent
    | ActionBlockedEvent
    | ServoCommandEvent
    | TextInputEvent
    | ResponseEvent
    | GreetingDeliveredEvent
    | GreetingInitiatedEvent
)


def validate_event(event: dict) -> tuple[bool, str]:
    """Validate that an event dict has required fields and valid values.
    
    Args:
        event: Event dictionary to validate.
    
    Returns:
        Tuple of (is_valid: bool, error_message: str). 
        If valid, error_message is empty string.
    """
    # Basic structure check
    if not isinstance(event, dict):
        return False, f"Event must be a dict, got {type(event).__name__}"
    
    if "event" not in event:
        return False, "Event missing required 'event' field"
    
    if not isinstance(event["event"], str):
        return False, f"Event 'event' field must be str, got {type(event['event']).__name__}"
    
    event_type = event["event"]
    
    # Event-specific validation
    validators = {
        "GESTURE_DETECTED": _validate_gesture_detected,
        "IDENTITY_RESOLVED": _validate_identity_resolved,
        "TRACK_LOST": _validate_track_lost,
        "SESSION_STATE": _validate_session_state,
        "ACTION": _validate_action,
        "ACTION_BLOCKED": _validate_action_blocked,
        "SERVO_COMMAND": _validate_servo_command,
        "TEXT_INPUT": _validate_text_input,
        "RESPONSE": _validate_response,
        "GREETING_DELIVERED": _validate_greeting_delivered,
        "GREETING_INITIATED": _validate_greeting_initiated,
    }
    
    validator = validators.get(event_type)
    if validator is None:
        # Unknown event type - allow it (extensibility)
        return True, ""
    
    return validator(event)


def _validate_gesture_detected(event: dict) -> tuple[bool, str]:
    """Validate GestureDetectedEvent."""
    if "gesture" not in event:
        return False, "GESTURE_DETECTED missing required field 'gesture'"
    if "track_id" not in event:
        return False, "GESTURE_DETECTED missing required field 'track_id'"
    if not isinstance(event["gesture"], str):
        return False, f"GESTURE_DETECTED 'gesture' must be str, got {type(event['gesture']).__name__}"
    if not isinstance(event["track_id"], str):
        return False, f"GESTURE_DETECTED 'track_id' must be str, got {type(event['track_id']).__name__}"
    return True, ""


def _validate_identity_resolved(event: dict) -> tuple[bool, str]:
    """Validate IdentityResolvedEvent."""
    required_fields = ["track_id", "embedding_id", "status", "name", "confidence"]
    for field in required_fields:
        if field not in event:
            return False, f"IDENTITY_RESOLVED missing required field '{field}'"
    
    valid_statuses = ["known", "new", "registered_unknown"]
    if event["status"] not in valid_statuses:
        return False, f"IDENTITY_RESOLVED 'status' must be one of {valid_statuses}, got '{event['status']}'"
    
    return True, ""


def _validate_track_lost(event: dict) -> tuple[bool, str]:
    """Validate TrackLostEvent."""
    if "track_id" not in event:
        return False, "TRACK_LOST missing required field 'track_id'"
    if "embedding_id" not in event:
        return False, "TRACK_LOST missing required field 'embedding_id'"
    return True, ""


def _validate_session_state(event: dict) -> tuple[bool, str]:
    """Validate SessionStateEvent."""
    if "embedding_id" not in event:
        return False, "SESSION_STATE missing required field 'embedding_id'"
    if "state" not in event:
        return False, "SESSION_STATE missing required field 'state'"
    
    valid_states = ["NEW", "GREETED", "AWAY", "RETURNED"]
    if event["state"] not in valid_states:
        return False, f"SESSION_STATE 'state' must be one of {valid_states}, got '{event['state']}'"
    
    return True, ""


def _validate_action(event: dict) -> tuple[bool, str]:
    """Validate ActionEvent."""
    if "action" not in event:
        return False, "ACTION missing required field 'action'"
    if "track_id" not in event:
        return False, "ACTION missing required field 'track_id'"
    return True, ""


def _validate_action_blocked(event: dict) -> tuple[bool, str]:
    """Validate ActionBlockedEvent."""
    required_fields = ["action", "track_id", "reason"]
    for field in required_fields:
        if field not in event:
            return False, f"ACTION_BLOCKED missing required field '{field}'"
    
    valid_reasons = ["target_too_close", "target_too_far", "sensor_fault"]
    if event["reason"] not in valid_reasons:
        return False, f"ACTION_BLOCKED 'reason' must be one of {valid_reasons}, got '{event['reason']}'"
    
    return True, ""


def _validate_servo_command(event: dict) -> tuple[bool, str]:
    """Validate ServoCommandEvent."""
    if "preset" not in event:
        return False, "SERVO_COMMAND missing required field 'preset'"
    if "joints" not in event:
        return False, "SERVO_COMMAND missing required field 'joints'"
    if not isinstance(event["joints"], dict):
        return False, f"SERVO_COMMAND 'joints' must be dict, got {type(event['joints']).__name__}"
    return True, ""


def _validate_text_input(event: dict) -> tuple[bool, str]:
    """Validate TextInputEvent."""
    if "text" not in event:
        return False, "TEXT_INPUT missing required field 'text'"
    if "source" not in event:
        return False, "TEXT_INPUT missing required field 'source'"
    
    valid_sources = ["voice", "keyboard"]
    if event["source"] not in valid_sources:
        return False, f"TEXT_INPUT 'source' must be one of {valid_sources}, got '{event['source']}'"
    
    return True, ""


def _validate_response(event: dict) -> tuple[bool, str]:
    """Validate ResponseEvent."""
    required_fields = ["text", "path", "latency_ms"]
    for field in required_fields:
        if field not in event:
            return False, f"RESPONSE missing required field '{field}'"
    
    valid_paths = ["deterministic", "cache", "llm"]
    if event["path"] not in valid_paths:
        return False, f"RESPONSE 'path' must be one of {valid_paths}, got '{event['path']}'"
    
    return True, ""


def _validate_greeting_delivered(event: dict) -> tuple[bool, str]:
    """Validate GreetingDeliveredEvent."""
    if "embedding_id" not in event:
        return False, "GREETING_DELIVERED missing required field 'embedding_id'"
    if "track_id" not in event:
        return False, "GREETING_DELIVERED missing required field 'track_id'"
    if not isinstance(event["embedding_id"], str):
        return False, f"GREETING_DELIVERED 'embedding_id' must be str, got {type(event['embedding_id']).__name__}"
    if not isinstance(event["track_id"], str):
        return False, f"GREETING_DELIVERED 'track_id' must be str, got {type(event['track_id']).__name__}"
    return True, ""


def _validate_greeting_initiated(event: dict) -> tuple[bool, str]:
    """Validate GreetingInitiatedEvent."""
    if "embedding_id" not in event:
        return False, "GREETING_INITIATED missing required field 'embedding_id'"
    if "track_id" not in event:
        return False, "GREETING_INITIATED missing required field 'track_id'"
    if not isinstance(event["embedding_id"], str):
        return False, f"GREETING_INITIATED 'embedding_id' must be str, got {type(event['embedding_id']).__name__}"
    if not isinstance(event["track_id"], str):
        return False, f"GREETING_INITIATED 'track_id' must be str, got {type(event['track_id']).__name__}"
    return True, ""
