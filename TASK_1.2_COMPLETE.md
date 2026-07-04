# Task 1.2 Complete: Event Bus & Schemas ✅

## Summary

Implemented a complete in-process pub/sub event system with TypedDict schemas for all event types. The event bus is thread-safe, handles errors gracefully, and will serve as the communication backbone for all robot assistant components.

## What Was Built

### 1. Event Schemas (`robot_assistant/events/schemas.py`)

Defined **9 TypedDict event schemas** covering all system interactions:

1. **GestureDetectedEvent** - Vision → Decision Engine
   ```python
   {"event": "GESTURE_DETECTED", "gesture": "HAND_RAISED", "track_id": "T1"}
   ```

2. **IdentityResolvedEvent** - Face ID → Session State & Decision Engine
   ```python
   {"event": "IDENTITY_RESOLVED", "track_id": "T1", "embedding_id": "E0042",
    "status": "known", "name": "Annamalai", "confidence": 0.91}
   ```

3. **TrackLostEvent** - Vision → Session State
   ```python
   {"event": "TRACK_LOST", "track_id": "T1", "embedding_id": "E0042"}
   ```

4. **SessionStateEvent** - Session State → Decision Engine
   ```python
   {"event": "SESSION_STATE", "embedding_id": "E0042", "state": "RETURNED"}
   ```

5. **ActionEvent** - Decision Engine → SafetyGate → Motion Planner
   ```python
   {"event": "ACTION", "action": "HANDSHAKE", "track_id": "T1"}
   ```

6. **ActionBlockedEvent** - SafetyGate → Logging/UI
   ```python
   {"event": "ACTION_BLOCKED", "action": "HANDSHAKE", "track_id": "T1",
    "reason": "target_too_close"}
   ```

7. **ServoCommandEvent** - Motion Planner → Servos (simulated now)
   ```python
   {"event": "SERVO_COMMAND", "preset": "HANDSHAKE_READY",
    "joints": {"shoulder": 45, "elbow": 90, "wrist": 0}}
   ```

8. **TextInputEvent** - Voice/Keyboard → Decision Engine
   ```python
   {"event": "TEXT_INPUT", "text": "What are lab hours?", "source": "voice"}
   ```

9. **ResponseEvent** - Decision Engine → TTS
   ```python
   {"event": "RESPONSE", "text": "Lab hours are 2-5 PM",
    "path": "cache", "latency_ms": 23.5}
   ```

**Benefits:**
- ✅ Type safety - field name typos caught at construction time
- ✅ Self-documenting - each event has clear structure
- ✅ IDE autocomplete - editors suggest valid field names

### 2. Event Bus (`robot_assistant/events/bus.py`)

**Core Functions:**
- `subscribe(event_type, callback)` - Register handler for event type
- `publish(event)` - Send event to all subscribers
- `unsubscribe(event_type, callback)` - Remove handler
- `clear_subscribers(event_type)` - Reset (for testing)
- `get_subscriber_count(event_type)` - Inspect subscriptions
- `get_event_types()` - List all subscribed event types
- `set_debug_logging(enabled)` - Toggle event logging

**Key Features:**
- ✅ **Thread-safe** - Locks protect subscriber list during concurrent access
- ✅ **Error isolation** - Exception in one callback doesn't stop others
- ✅ **Validation** - Invalid events (missing 'event' field) are rejected
- ✅ **Fan-out** - Multiple subscribers can listen to same event
- ✅ **Type filtering** - Subscribers only receive their registered event types
- ✅ **Debug logging** - Optional logging of all events for troubleshooting

**Design Decisions:**
- In-process for now (MQTT deferred until Pi becomes separate device)
- Synchronous callbacks (subscribers run in publisher's thread)
- Global subscriber registry (simplicity over dependency injection)
- Defensive programming (validate events, catch callback exceptions)

### 3. Package Interface (`robot_assistant/events/__init__.py`)

Clean public API exposing all functions and types:
```python
from robot_assistant.events import (
    subscribe, publish,  # Core bus functions
    GestureDetectedEvent, ActionEvent, ...  # Event types
)
```

## Test Coverage

### Test Suite 1: Bus Functionality (`tests/test_bus.py`) - **14 tests**

1. ✅ Basic subscribe and publish
2. ✅ Multiple subscribers to same event (fan-out)
3. ✅ Different event types don't interfere (isolation)
4. ✅ Unsubscribe stops receiving events
5. ✅ Unsubscribe nonexistent callback returns False
6. ✅ Publish without subscribers (no crash)
7. ✅ Invalid event rejected (missing 'event' field)
8. ✅ Callback exception doesn't stop other callbacks
9. ✅ Get subscriber count (per-type and total)
10. ✅ Get event types list
11. ✅ Clear specific event type subscribers
12. ✅ Clear all subscribers
13. ✅ Subscribe non-callable raises TypeError
14. ✅ Thread safety stress test (5 threads, 50 events)

### Test Suite 2: Schema Validation (`tests/test_schemas.py`) - **17 tests**

1. ✅ GestureDetectedEvent valid structure
2. ✅ IdentityResolvedEvent - known person
3. ✅ IdentityResolvedEvent - new person
4. ✅ IdentityResolvedEvent - registered but unnamed
5. ✅ TrackLostEvent valid structure
6. ✅ SessionStateEvent - all 4 states (NEW/GREETED/AWAY/RETURNED)
7. ✅ ActionEvent valid structure
8. ✅ ActionBlockedEvent - all 3 reasons (too_close/too_far/sensor_fault)
9. ✅ ServoCommandEvent valid structure
10. ✅ TextInputEvent - voice source
11. ✅ TextInputEvent - keyboard source
12. ✅ ResponseEvent - all 3 paths (deterministic/cache/llm)
13. ✅ validate_event rejects missing 'event' field
14. ✅ validate_event rejects non-dict
15. ✅ validate_event rejects non-string 'event' field
16. ✅ Event mutability (dicts are mutable, TypedDict is type hint only)
17. ✅ Multiple event types coexist

### Test Suite 3: Integration Examples (`tests/test_bus_integration_example.py`) - **4 tests**

1. ✅ Gesture to action flow (GESTURE_DETECTED → ACTION)
2. ✅ SafetyGate blocking flow (ACTION → ACTION_BLOCKED)
3. ✅ Multiple components listening (fan-out to 3 handlers)
4. ✅ Event chain (GESTURE → ACTION → SERVO_COMMAND)

**Total: 35 tests, all passing ✅**

## Usage Examples

### Example 1: Decision Engine Subscribing to Gestures

```python
from robot_assistant.events import subscribe, publish

def handle_gesture(event):
    if event["gesture"] == "HAND_RAISED":
        publish({
            "event": "ACTION",
            "action": "HANDSHAKE",
            "track_id": event["track_id"]
        })

subscribe("GESTURE_DETECTED", handle_gesture)
```

### Example 2: Vision Publishing Face Recognition

```python
from robot_assistant.events import publish

# After face recognition completes
publish({
    "event": "IDENTITY_RESOLVED",
    "track_id": "T1",
    "embedding_id": "E0042",
    "status": "known",
    "name": "Annamalai",
    "confidence": 0.91
})
```

### Example 3: Multiple Components Listening

```python
# Decision Engine listens for greeting logic
subscribe("IDENTITY_RESOLVED", decision_engine.handle_identity)

# Session State listens for state machine updates
subscribe("IDENTITY_RESOLVED", session_state.update_identity)

# UI listens for display updates
subscribe("IDENTITY_RESOLVED", ui.show_person_name)

# All three receive the same event (fan-out)
```

## Files Created

1. **`robot_assistant/events/schemas.py`** (190 lines)
   - 9 TypedDict event schemas
   - validate_event() helper
   - Event union type

2. **`robot_assistant/events/bus.py`** (180 lines)
   - Subscribe/publish/unsubscribe functions
   - Thread-safe implementation
   - Error handling and logging

3. **`robot_assistant/events/__init__.py`** (40 lines)
   - Public API exports

4. **`tests/test_bus.py`** (250 lines)
   - 14 comprehensive bus tests
   - Thread safety stress test

5. **`tests/test_schemas.py`** (220 lines)
   - 17 schema validation tests
   - Coverage of all event types

6. **`tests/test_bus_integration_example.py`** (150 lines)
   - 4 real-world integration examples
   - Demonstrates component communication patterns

## Verification

```bash
# All tests pass
✓ python -m pytest tests/ -v
  35 passed in 0.13s

# Specific test suites
✓ python -m pytest tests/test_bus.py -v
  14 passed in 0.12s

✓ python -m pytest tests/test_schemas.py -v
  17 passed in 0.10s

✓ python -m pytest tests/test_bus_integration_example.py -v
  4 passed in 0.05s
```

## Next Steps

The event bus is now ready to connect all components. Future tasks will subscribe to and publish these events:

**Task 1.3** - Deterministic intents → subscribe to TEXT_INPUT, publish RESPONSE  
**Task 1.4** - Gesture actions → subscribe to GESTURE_DETECTED, publish ACTION  
**Task 1.5** - SafetyGate → subscribe to ACTION, publish ACTION_BLOCKED or SERVO_COMMAND  
**Task 1.6** - Session state → subscribe to IDENTITY_RESOLVED/TRACK_LOST, publish SESSION_STATE  
**Task 1.7** - Decision Engine → orchestrates all of the above

The foundation for event-driven architecture is complete!

---

**Status:** ✅ Task 1.2 Complete  
**Time Spent:** ~2 hours (as estimated)  
**Tests:** 35/35 passing  
**Next:** Task 1.3 - Deterministic Intent Handler
