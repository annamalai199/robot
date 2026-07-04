"""Session State Store - Per-identity state machine.

Tracks conversation state for each person (keyed by embedding_id, NOT track_id).
State machine handles greetings, away detection, and return detection.

State Transitions:
    NEW → GREETED (when GREETING_DELIVERED event fires)
    GREETED → AWAY (TRACK_LOST event, person left frame)
    AWAY → RETURNED (re-detected with same embedding_id)
    RETURNED → AWAY (left again)

CRITICAL: State only becomes GREETED after GREETING_DELIVERED event fires, NOT on
IDENTITY_RESOLVED. This ensures greeting is actually delivered by TTS before state
changes. The Decision Engine (Task 1.7) is responsible for:
1. Detecting NEW state after IDENTITY_RESOLVED
2. Generating greeting text and sending to TTS
3. Publishing GREETING_DELIVERED after TTS completes

TIMEOUT/FALLBACK: If GREETING_DELIVERED doesn't arrive within GREETING_TIMEOUT_SECONDS
(default 5s) after a greeting was initiated, the state automatically transitions to
GREETED with a logged warning. This prevents infinite re-greet loops if TTS fails,
crashes, or audio device errors out. Philosophy: "fail visibly, don't stall silently."

IMPORTANT - PERIODIC TIMEOUT ENFORCEMENT: The timeout is enforced via explicit periodic
check_timeouts() calls, NOT via lazy checking on incidental events. The main application
loop (Task 4.5) must call check_timeouts() approximately once per second. This scans all
NEW identities with pending greetings and applies timeout logic.

Rationale: IDENTITY_RESOLVED fires only ONCE per track appearance (Task 3.6: "face_id
only runs if track_id not seen before"), so we cannot rely on incidental state updates
to trigger timeout checks. Explicit periodic checking ensures timeouts fire reliably
even if the person stands still.

SESSION_STATE EVENT: When timeout auto-transitions NEW → GREETED, a SESSION_STATE event
is published on the bus so other components learn about the change (not just visible via
get_state() polling).

Key Design: Uses embedding_id (persistent face identity) not track_id (transient vision).
Two different track_ids with the same embedding_id share the same session state.
"""

import logging
import time
from typing import Literal, Optional

from robot_assistant.events import publish, SessionStateEvent

logger = logging.getLogger(__name__)

# Session states
SessionState = Literal["NEW", "GREETED", "AWAY", "RETURNED"]

# Greeting timeout (seconds) - how long to wait for GREETING_DELIVERED before auto-transitioning
GREETING_TIMEOUT_SECONDS = 5.0  # TTS should complete in 1-2s, 5s is generous

# In-memory store: {embedding_id: state_dict}
_session_store: dict[str, dict] = {}


def update_identity_state(embedding_id: str, event_type: str, track_id: Optional[str] = None) -> SessionState:
    """Update session state for an identity based on event type.
    
    Args:
        embedding_id: Persistent face embedding ID (e.g. "E0042", "U1042").
        event_type: Event that triggered the update. One of:
            - "IDENTITY_RESOLVED" (person detected/re-detected)
            - "TRACK_LOST" (person left frame)
            - "GREETING_DELIVERED" (TTS finished delivering greeting)
            - "GREETING_INITIATED" (Decision Engine sent greeting to TTS)
        track_id: Current vision track_id (for logging only, not used for state).
    
    Returns:
        The new session state after applying the event.
    
    State Machine Logic:
        NEW + IDENTITY_RESOLVED → stays NEW (waiting for greeting delivery)
        NEW + GREETING_INITIATED → stays NEW, but records greeting_initiated_at timestamp
        NEW + GREETING_DELIVERED → GREETED (greeting actually delivered)
        NEW + TRACK_LOST → AWAY (person left before greeting finished)
        
        GREETED + IDENTITY_RESOLVED → stays GREETED (person still present)
        GREETED + TRACK_LOST → AWAY (person left)
        
        AWAY + IDENTITY_RESOLVED → RETURNED (person came back)
        AWAY + TRACK_LOST → stays AWAY
        
        RETURNED + IDENTITY_RESOLVED → stays RETURNED (person still present)
        RETURNED + GREETING_DELIVERED → stays RETURNED (no re-greeting on return)
        RETURNED + TRACK_LOST → AWAY (person left again)
    
    TIMEOUT: If in NEW state with greeting_initiated_at set, the timeout is enforced
    by periodic check_timeouts() calls (once per second from main loop), NOT by this
    function. This function only handles explicit event-driven transitions.
    
    CRITICAL: IDENTITY_RESOLVED does NOT transition NEW → GREETED. Only
    GREETING_DELIVERED does that. This ensures the greeting is actually
    spoken by TTS before the state changes. The Decision Engine (Task 1.7)
    is responsible for publishing GREETING_DELIVERED after TTS completes.
    """
    current_state = get_state(embedding_id)
    
    if current_state is None:
        # First time seeing this identity
        _session_store[embedding_id] = {
            "state": "NEW",
            "last_seen": time.time(),
            "track_id": track_id,
            "created_at": time.time(),
            "greeting_initiated_at": None,  # Timestamp when greeting was sent to TTS
        }
        logger.info(f"Created new session for {embedding_id} (track {track_id}) - state: NEW")
        return "NEW"
    
    # Apply state transition
    old_state = current_state["state"]
    new_state = old_state
    
    if event_type == "IDENTITY_RESOLVED":
        if old_state == "NEW":
            # Stay NEW until greeting delivered
            new_state = "NEW"
        elif old_state == "GREETED":
            # Already greeted, still present
            new_state = "GREETED"
        elif old_state == "AWAY":
            # Person returned!
            new_state = "RETURNED"
            logger.info(f"Identity {embedding_id} RETURNED (was AWAY, now track {track_id})")
        elif old_state == "RETURNED":
            # Still returned, still present
            new_state = "RETURNED"
    
    elif event_type == "GREETING_INITIATED":
        if old_state == "NEW":
            # Record when greeting was sent to TTS
            current_state["greeting_initiated_at"] = time.time()
            new_state = "NEW"  # Stay NEW, wait for GREETING_DELIVERED
            logger.debug(f"Greeting initiated for {embedding_id}, waiting for delivery")
    
    elif event_type == "GREETING_DELIVERED":
        if old_state == "NEW":
            # First greeting delivered
            new_state = "GREETED"
            current_state["greeting_initiated_at"] = None  # Clear timeout
            logger.info(f"Identity {embedding_id} → GREETED (greeting delivered)")
        elif old_state in ("GREETED", "RETURNED"):
            # Already greeted or returned - no state change
            new_state = old_state
    
    elif event_type == "TRACK_LOST":
        if old_state in ("GREETED", "RETURNED"):
            # Person left frame
            new_state = "AWAY"
            logger.info(f"Identity {embedding_id} → AWAY (track {current_state.get('track_id')} lost)")
        elif old_state == "NEW":
            # Left before we could greet - transition to AWAY
            new_state = "AWAY"
            current_state["greeting_initiated_at"] = None  # Clear timeout
            logger.info(f"Identity {embedding_id} → AWAY (left before greeting)")
    
    # Update store
    _session_store[embedding_id]["state"] = new_state
    _session_store[embedding_id]["last_seen"] = time.time()
    if track_id is not None:
        _session_store[embedding_id]["track_id"] = track_id
    
    if new_state != old_state:
        logger.debug(f"State transition for {embedding_id}: {old_state} → {new_state} (event: {event_type})")
        # Publish SESSION_STATE event so other components learn about state change
        _publish_session_state_event(embedding_id, new_state)
    
    return new_state


def get_state(embedding_id: str) -> Optional[dict]:
    """Get current session state for an identity.
    
    Args:
        embedding_id: Face embedding ID to look up.
    
    Returns:
        Dict with keys: state, last_seen, track_id, created_at.
        Returns None if identity has never been seen.
    """
    return _session_store.get(embedding_id)


def get_all_states() -> dict[str, dict]:
    """Get all session states (for debugging/UI).
    
    Returns:
        Dict of {embedding_id: state_dict} for all tracked identities.
    """
    return _session_store.copy()


def clear_state(embedding_id: str) -> None:
    """Remove session state for an identity (for testing/admin).
    
    Args:
        embedding_id: Identity to remove.
    """
    if embedding_id in _session_store:
        del _session_store[embedding_id]
        logger.info(f"Cleared session state for {embedding_id}")


def clear_all_states() -> None:
    """Clear all session states (for testing/demo reset).
    
    Useful for starting fresh without restarting the application.
    """
    _session_store.clear()
    logger.info("Cleared all session states")


def get_state_summary() -> dict:
    """Get summary statistics of current sessions (for monitoring/UI).
    
    Returns:
        Dict with counts by state: {"NEW": 0, "GREETED": 2, "AWAY": 1, "RETURNED": 0}
    """
    summary = {"NEW": 0, "GREETED": 0, "AWAY": 0, "RETURNED": 0}
    
    for state_dict in _session_store.values():
        state = state_dict["state"]
        summary[state] += 1
    
    return summary


def cleanup_old_sessions(max_age_seconds: float = 3600) -> int:
    """Remove sessions that haven't been seen in a long time.
    
    Args:
        max_age_seconds: Remove sessions older than this (default 1 hour).
    
    Returns:
        Number of sessions removed.
    """
    now = time.time()
    to_remove = []
    
    for embedding_id, state_dict in _session_store.items():
        age = now - state_dict["last_seen"]
        if age > max_age_seconds:
            to_remove.append(embedding_id)
    
    for embedding_id in to_remove:
        del _session_store[embedding_id]
    
    if to_remove:
        logger.info(f"Cleaned up {len(to_remove)} old sessions (age > {max_age_seconds}s)")
    
    return len(to_remove)


def get_greeting_timeout() -> float:
    """Get the greeting timeout value in seconds.
    
    Returns:
        Timeout in seconds before NEW state auto-transitions to GREETED.
    """
    return GREETING_TIMEOUT_SECONDS


def check_timeouts() -> int:
    """Check all NEW identities for greeting timeouts and auto-transition if expired.
    
    This function should be called periodically (~1x per second) from the main application
    loop (Task 4.5). It scans all identities in NEW state with pending greetings and
    transitions them to GREETED if the timeout has expired.
    
    Returns:
        Number of identities that were auto-transitioned due to timeout.
    
    Side Effects:
        - Updates state NEW → GREETED for timed-out identities
        - Publishes SESSION_STATE event for each auto-transition
        - Logs WARNING for each timeout
    
    Example:
        # In main loop (Task 4.5):
        while running:
            # ... vision, voice, decision engine work ...
            time.sleep(1.0)
            session_state.check_timeouts()  # Check once per second
    
    Note:
        This is the PRIMARY timeout enforcement mechanism. Unlike the previous lazy-check
        approach, this does not rely on IDENTITY_RESOLVED events (which fire only once
        per track appearance). Explicit periodic checking ensures timeouts fire reliably.
    """
    now = time.time()
    timed_out_count = 0
    
    # Scan all sessions for NEW state with expired greeting timeout
    for embedding_id, state_dict in list(_session_store.items()):
        if state_dict["state"] == "NEW" and state_dict.get("greeting_initiated_at"):
            elapsed = now - state_dict["greeting_initiated_at"]
            
            if elapsed > GREETING_TIMEOUT_SECONDS:
                # Timeout expired - auto-transition to GREETED
                logger.warning(
                    f"Greeting timeout for {embedding_id}: {elapsed:.1f}s elapsed, "
                    f"no GREETING_DELIVERED received. Auto-transitioning to GREETED "
                    f"to prevent re-greet loop (TTS may have failed)."
                )
                
                state_dict["state"] = "GREETED"
                state_dict["greeting_initiated_at"] = None
                state_dict["last_seen"] = now
                
                # Publish SESSION_STATE event
                _publish_session_state_event(embedding_id, "GREETED")
                
                timed_out_count += 1
    
    if timed_out_count > 0:
        logger.info(f"check_timeouts(): Auto-transitioned {timed_out_count} identities due to timeout")
    
    return timed_out_count


def _publish_session_state_event(embedding_id: str, state: SessionState) -> None:
    """Publish SESSION_STATE event to notify other components of state change.
    
    Args:
        embedding_id: Identity whose state changed.
        state: New state value.
    """
    event: SessionStateEvent = {
        "event": "SESSION_STATE",
        "embedding_id": embedding_id,
        "state": state
    }
    publish(event)
    logger.debug(f"Published SESSION_STATE event for {embedding_id}: {state}")
