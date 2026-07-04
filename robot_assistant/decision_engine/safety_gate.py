"""SafetyGate - Software safety layer for action execution.

This is Layer 1 of the two-layer safety system (Section 4c):
- Layer 1 (Software): SafetyGate - checks distance, sensor health, timeouts
- Layer 2 (Hardware): E-stop button - physical cutoff, works even if software fails

SafetyGate subscribes to ACTION events and decides whether it's safe to execute
the action. If safe, it would pass to motion planner (not built yet). If unsafe,
it publishes ACTION_BLOCKED event with specific reason.

IMPORTANT: SafetyGate does NOT call the motion planner directly. It only makes
allow/block decisions and publishes events. The motion planner (Task 10) will
subscribe to the appropriate events when it's built.
"""

import logging
import time
from typing import Optional

from robot_assistant.config import config
from robot_assistant.events import subscribe, publish, ActionEvent, ActionBlockedEvent

logger = logging.getLogger(__name__)


def safety_gate(action: dict, distance_cm: Optional[float], sensor_ok: bool = True) -> bool:
    """Decide whether it is safe to execute a physical action right now.
    
    This is the SOFTWARE safety layer. A hardware E-stop (independent of this code)
    provides additional protection if software fails or has bugs.
    
    Args:
        action: The pending ACTION event, e.g. {"event": "ACTION", "action": "HANDSHAKE", 
                "track_id": "T1"}.
        distance_cm: Latest HC-SR04 ultrasonic reading to the target, or None if no
                     sensor is wired up yet (e.g. laptop-only phase). The sensor's
                     physical read latency (~50-60ms sound round-trip) is separate from
                     this function's decision latency (<5ms).
        sensor_ok: False if the sensor is returning stale/erratic readings (e.g. no change
                   across many consecutive reads, or physically implausible jumps). A failed
                   or disconnected sensor should block the action, not silently default to allow.
    
    Returns:
        True if the action may proceed. False if the sensor has failed, distance is too
        close, or too far (person moved away). Caller should not execute the action if
        False is returned.
        
    Side Effects:
        If action is blocked, publishes ACTION_BLOCKED event with specific reason.
        During the no-sensor phase (sensor_ok=True, distance_cm=None), logs a warning
        but allows the action (simulation mode).
    
    Notes:
        - This function does NOT call the motion planner. It only makes decisions and
          publishes events.
        - The hardware E-stop (Layer 2) is independent of this function and works even
          if this software crashes or has bugs.
        - Decision latency target: <5ms (excludes the sensor's physical read time)
    """
    start_time = time.time()
    
    action_name = action.get("action", "UNKNOWN")
    track_id = action.get("track_id", "UNKNOWN")
    
    # Case 1: Sensor fault - HARD BLOCK (highest priority)
    # A failed sensor should NOT default to allow
    if not sensor_ok:
        reason = "sensor_fault"
        _publish_blocked_event(action_name, track_id, reason)
        
        latency_ms = (time.time() - start_time) * 1000
        logger.error(
            f"SafetyGate BLOCKED: {action_name} (track {track_id}) - "
            f"Reason: {reason} ({latency_ms:.2f}ms)"
        )
        return False
    
    # Case 2: No sensor wired up (laptop/simulation phase)
    # Allow but log it - this is NOT production-ready
    if distance_cm is None:
        latency_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"SafetyGate ALLOWED (simulated): {action_name} (track {track_id}) - "
            f"No sensor wired up (distance_cm=None). "
            f"Action logged but not executed. ({latency_ms:.2f}ms)"
        )
        return True
    
    # Case 3: Distance too close - BLOCK
    min_distance = config.HANDSHAKE_DISTANCE_MIN_CM
    if distance_cm < min_distance:
        reason = "target_too_close"
        _publish_blocked_event(action_name, track_id, reason)
        
        latency_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"SafetyGate BLOCKED: {action_name} (track {track_id}) - "
            f"Reason: {reason} (distance={distance_cm:.1f}cm < min={min_distance}cm) "
            f"({latency_ms:.2f}ms)"
        )
        return False
    
    # Case 4: Distance too far - BLOCK (person moved away)
    max_distance = config.HANDSHAKE_DISTANCE_MAX_CM
    if distance_cm > max_distance:
        reason = "target_too_far"
        _publish_blocked_event(action_name, track_id, reason)
        
        latency_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"SafetyGate BLOCKED: {action_name} (track {track_id}) - "
            f"Reason: {reason} (distance={distance_cm:.1f}cm > max={max_distance}cm) "
            f"({latency_ms:.2f}ms)"
        )
        return False
    
    # Case 5: Distance in valid range, sensor OK - ALLOW
    latency_ms = (time.time() - start_time) * 1000
    logger.info(
        f"SafetyGate ALLOWED: {action_name} (track {track_id}) - "
        f"distance={distance_cm:.1f}cm (range: {min_distance}-{max_distance}cm) "
        f"({latency_ms:.2f}ms)"
    )
    return True


def _publish_blocked_event(action: str, track_id: str, reason: str) -> None:
    """Publish ACTION_BLOCKED event with specific reason.
    
    Args:
        action: Action name that was blocked.
        track_id: Track ID of the target person.
        reason: One of "target_too_close", "target_too_far", "sensor_fault".
    """
    blocked_event: ActionBlockedEvent = {
        "event": "ACTION_BLOCKED",
        "action": action,
        "track_id": track_id,
        "reason": reason  # type: ignore - TypedDict will validate at runtime
    }
    
    publish(blocked_event)


def handle_action_event(event: ActionEvent) -> None:
    """Handle ACTION event from gesture handler or decision engine.
    
    This is the event-driven interface. Subscribe this handler to ACTION events
    to enable SafetyGate checking.
    
    Args:
        event: ACTION event with action name and track_id.
    
    Side Effects:
        - If action is allowed, would pass to motion planner (not built yet)
        - If action is blocked, publishes ACTION_BLOCKED event
    
    Notes:
        Currently, we don't have a real distance sensor (laptop phase), so
        distance_cm=None and sensor_ok=True. This simulates the action being
        logged but not executed.
        
        In Phase 5 (Pi with HC-SR04 sensor), this handler would read the actual
        distance and sensor health before calling safety_gate().
    """
    # Laptop phase: no sensor, simulate safe conditions
    distance_cm = None  # No HC-SR04 sensor wired up yet
    sensor_ok = True    # No sensor to fail
    
    # Check safety
    is_safe = safety_gate(event, distance_cm, sensor_ok)
    
    if is_safe:
        # In a real system with motion planner, would publish SERVO_COMMAND here
        # For now, just log that the action would proceed
        logger.info(f"Action '{event['action']}' for track {event['track_id']} would proceed to motion planner")
        # TODO: Phase 5 (Pi + sensors + servos): Publish SERVO_COMMAND event
    else:
        # Action was blocked - ACTION_BLOCKED event already published by safety_gate()
        logger.debug(f"Action '{event['action']}' for track {event['track_id']} was blocked by SafetyGate")


def start_safety_gate() -> None:
    """Subscribe to ACTION events to enable SafetyGate checking.
    
    Call this once during application startup. SafetyGate will then check
    every ACTION event before it reaches the motion planner.
    """
    subscribe("ACTION", handle_action_event)
    logger.info("SafetyGate started - monitoring ACTION events")


def get_distance_limits() -> tuple[float, float]:
    """Get current safe distance limits from config.
    
    Returns:
        Tuple of (min_cm, max_cm) for handshake distance.
    """
    return (config.HANDSHAKE_DISTANCE_MIN_CM, config.HANDSHAKE_DISTANCE_MAX_CM)
