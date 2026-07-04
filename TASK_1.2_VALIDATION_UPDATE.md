# Task 1.2 - Runtime Validation Added ✅

## Issue Found

TypedDict provides **zero runtime validation** - only static type hints. The original implementation accepted invalid events silently:

```python
# These were incorrectly accepted:
bus.publish({"event": "SESSION_STATE", "embedding_id": "E1", "state": "INVALID"})
bus.publish({"event": "SESSION_STATE", "embedding_id": "E1"})  # Missing 'state'
bus.publish("not even a dict")
```

## Solution Implemented

Added comprehensive **runtime validation** to `publish()`:

### 1. Updated `validate_event()` in `schemas.py`

**Before:** Simple bool return
```python
def validate_event(event: dict) -> bool:
    return isinstance(event, dict) and "event" in event
```

**After:** Detailed validation with error messages
```python
def validate_event(event: dict) -> tuple[bool, str]:
    """Returns (is_valid, error_message)"""
    # Basic checks
    # Event-specific validators for each event type
    # Enum validation (states, statuses, reasons, sources, paths)
```

### 2. Event-Specific Validators

Created 9 validator functions:
- `_validate_gesture_detected()` - Required fields: gesture, track_id
- `_validate_identity_resolved()` - Validates status enum (known/new/registered_unknown)
- `_validate_track_lost()` - Required fields: track_id, embedding_id
- **`_validate_session_state()`** - Validates state enum (NEW/GREETED/AWAY/RETURNED)
- `_validate_action()` - Required fields: action, track_id
- **`_validate_action_blocked()`** - Validates reason enum (target_too_close/target_too_far/sensor_fault)
- `_validate_servo_command()` - Validates joints is dict
- **`_validate_text_input()`** - Validates source enum (voice/keyboard)
- **`_validate_response()`** - Validates path enum (deterministic/cache/llm)

### 3. Updated `publish()` in `bus.py`

**Before:** Logged invalid events, continued silently
```python
if not validate_event(event):
    logger.error(f"Invalid event: {event}")
    return  # Silent failure
```

**After:** Raises ValueError with specific error message
```python
valid, error_msg = validate_event(event)
if not valid:
    logger.error(f"Invalid event: {error_msg} - Event: {event}")
    raise ValueError(f"Invalid event: {error_msg}")
```

## Test Coverage Added

**22 new validation tests** in `tests/test_event_validation.py`:

1. ✅ Not a dict raises ValueError
2. ✅ Missing 'event' field raises ValueError  
3. ✅ SESSION_STATE invalid state value raises
4. ✅ SESSION_STATE missing 'state' field raises
5. ✅ SESSION_STATE missing 'embedding_id' raises
6. ✅ SESSION_STATE all 4 valid states accepted
7. ✅ IDENTITY_RESOLVED invalid status raises
8. ✅ IDENTITY_RESOLVED missing fields raises
9. ✅ ACTION_BLOCKED invalid reason raises
10. ✅ ACTION_BLOCKED missing fields raises
11. ✅ TEXT_INPUT invalid source raises
12. ✅ TEXT_INPUT missing fields raises
13. ✅ RESPONSE invalid path raises
14. ✅ RESPONSE missing fields raises
15. ✅ GESTURE_DETECTED missing fields raises
16. ✅ GESTURE_DETECTED wrong field type raises
17. ✅ ACTION event valid
18. ✅ TRACK_LOST missing fields raises
19. ✅ SERVO_COMMAND joints not dict raises
20. ✅ SERVO_COMMAND valid
21. ✅ Unknown event types accepted (extensibility)
22. ✅ Validation errors don't reach subscribers

**Updated existing tests** to expect ValueError instead of silent acceptance.

## Verification

```bash
# All 57 tests pass (35 original + 22 validation)
✓ python -m pytest tests/ -q
  57 passed in 0.25s

# Validation now works correctly
✓ Invalid state value → ValueError
✓ Missing required field → ValueError
✓ Wrong data type → ValueError
✓ Valid events → Accepted
```

## Example Behavior

### Before (Silent Failure)
```python
bus.publish({"event": "SESSION_STATE", "embedding_id": "E1", "state": "INVALID"})
# No error, subscribers might receive bad data
```

### After (Explicit Failure)
```python
bus.publish({"event": "SESSION_STATE", "embedding_id": "E1", "state": "INVALID"})
# Raises: ValueError: Invalid event: SESSION_STATE 'state' must be one of
# ['NEW', 'GREETED', 'AWAY', 'RETURNED'], got 'INVALID'
```

## Benefits

1. **Fail fast** - Catch errors at publish time, not in subscribers
2. **Clear errors** - Specific message explains what's wrong
3. **Type safety** - Runtime validation complements TypedDict hints
4. **Debugging** - Invalid events never reach callbacks
5. **Extensibility** - Unknown event types still accepted

## Files Modified

- `robot_assistant/events/schemas.py` - Added validators (~130 lines)
- `robot_assistant/events/bus.py` - Updated publish() to raise ValueError
- `tests/test_bus.py` - Updated 1 test expecting ValueError
- `tests/test_schemas.py` - Updated 3 tests for new return signature
- **`tests/test_event_validation.py`** - Added 22 comprehensive validation tests

---

**Status:** ✅ Runtime Validation Complete  
**Tests:** 57/57 passing  
**Next:** Task 1.3 - Deterministic Intent Handler
