# Task 1.6 Corrections Applied ✅

**Date:** 2026-07-04

## Issue 1: GREETING_DELIVERED Event Missing from Schemas ✅

**Problem:** GREETING_DELIVERED was a new event type introduced in Task 1.6 but was not added to the original 9 event schemas from Task 1.2. It was falling through as an "unknown event type" with zero validation.

**Resolution:**

### 1a. Confirmed Intentional Addition ✅
- **Yes, GREETING_DELIVERED is intentional** - greeting is marked complete only once TTS actually delivers it, not just when it's decided
- This prevents race conditions where state changes to GREETED before the person actually hears the greeting

### 1b. Added Schema and Runtime Validation ✅

**Changes made to `robot_assistant/events/schemas.py`:**
- Added `GreetingDeliveredEvent` TypedDict schema
- Added to `Event` type union (now 10 event types)
- Added `_validate_greeting_delivered()` validator function
- Validates required fields: `embedding_id` (str), `track_id` (str)
- Type checking for both fields

**Changes made to `tests/test_event_validation.py`:**
- Added 5 new validation tests:
  1. `test_greeting_delivered_missing_embedding_id_raises`
  2. `test_greeting_delivered_missing_track_id_raises`
  3. `test_greeting_delivered_embedding_id_wrong_type_raises`
  4. `test_greeting_delivered_track_id_wrong_type_raises`
  5. `test_greeting_delivered_valid`

**Changes made to `tests/test_schemas.py`:**
- Added `test_greeting_delivered_event_valid` schema construction test

### 1c. Added to design.md Section 5 ✅

**Changes made to `.kiro/specs/humanoid-robot-assistant/design.md`:**
- Added GREETING_DELIVERED to event list in Section 5
- Added detailed event documentation:
  - **Purpose:** Marks that TTS has finished delivering a greeting
  - **Published by:** Decision Engine (Task 1.7) after TTS completes
  - **Subscribed by:** Session State Store
  - **Schema:** `{"event": "GREETING_DELIVERED", "embedding_id": str, "track_id": str}`
  - **Critical note:** State only transitions NEW → GREETED after this event fires, NOT on IDENTITY_RESOLVED
  - **Responsibility chain:** Decision Engine detects NEW state → generates greeting → sends to TTS → publishes GREETING_DELIVERED after completion

---

## Issue 2: State Transition Ambiguity ✅

**Problem:** It was unclear whether IDENTITY_RESOLVED alone transitions NEW → GREETED, or if GREETING_DELIVERED is required.

**Resolution:**

### Explicit Clarification: GREETING_DELIVERED Required ✅

**State Transition Rules (now documented):**
- **IDENTITY_RESOLVED does NOT transition NEW → GREETED**
- **Only GREETING_DELIVERED transitions NEW → GREETED**
- This ensures greeting is actually spoken by TTS before state changes

**Rationale:**
- Prevents race condition where person leaves before hearing greeting
- State accurately reflects what was delivered, not just decided
- TTS latency (100-500ms) is significant enough that person could leave during synthesis

### Documentation Updates ✅

**Changes made to `robot_assistant/session_state/store.py`:**

**Module docstring:**
```python
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
```

**Function docstring for `update_identity_state()`:**
- Added explicit state machine logic table showing all transitions
- Added CRITICAL note explaining IDENTITY_RESOLVED does NOT transition NEW → GREETED
- Clarified Decision Engine (Task 1.7) responsibility

**Changes made to design.md:**
- Added GREETING_DELIVERED to Section 5 event list
- Documented Decision Engine responsibility for publishing event
- Clarified Session State Store only responds to event, doesn't generate it

---

## Responsibility Breakdown (for Task 1.7)

### Decision Engine (Task 1.7) Responsibilities:
1. Subscribe to IDENTITY_RESOLVED events
2. Call `session_state.get_state(embedding_id)` to check state
3. If state is NEW:
   - Generate greeting text (generic: "Hello! I'm your assistant" or personalized if name exists)
   - Send to TTS for synthesis and playback
   - **After TTS completes**, publish GREETING_DELIVERED event
4. If state is RETURNED:
   - Generate "Welcome back [name]!" message
   - Send to TTS
   - Do NOT publish GREETING_DELIVERED (no state transition needed)

### Session State Store Responsibilities:
1. Subscribe to GREETING_DELIVERED events
2. When GREETING_DELIVERED received:
   - If current state is NEW → transition to GREETED
   - If current state is RETURNED or GREETED → stay in current state (no-op)
3. Maintain state, don't generate events

**Key Design Principle:** Session State Store owns state machine logic but does NOT contain greeting-decision logic. Decision Engine reads state and acts on it, then publishes completion events back to store.

---

## Test Results

**Before corrections:** 135/135 tests passing ✅  
**After corrections:** 141/141 tests passing ✅ (+6 tests for GREETING_DELIVERED validation)

**New test coverage:**
- GREETING_DELIVERED schema validation (5 tests)
- GREETING_DELIVERED schema construction (1 test)

---

## Files Modified

1. `robot_assistant/events/schemas.py` (+23 lines)
   - Added GreetingDeliveredEvent schema
   - Added validation function
   - Updated Event type union

2. `tests/test_event_validation.py` (+26 lines)
   - Added 5 validation rejection tests
   - Added 1 valid event test

3. `tests/test_schemas.py` (+11 lines)
   - Added schema construction test
   - Updated import

4. `robot_assistant/session_state/store.py` (updated docstrings)
   - Clarified state transition rules
   - Added CRITICAL note about GREETING_DELIVERED requirement
   - Documented Decision Engine responsibilities

5. `.kiro/specs/humanoid-robot-assistant/design.md` (+14 lines)
   - Added GREETING_DELIVERED to Section 5 event list
   - Added detailed event documentation
   - Clarified responsibility chain

---

## Summary

Both issues resolved:

✅ **Issue 1:** GREETING_DELIVERED now has full schema + runtime validation + documentation  
✅ **Issue 2:** State transition rules explicitly documented: GREETING_DELIVERED (not IDENTITY_RESOLVED) transitions NEW → GREETED

**Ready to proceed to Task 1.7: Decision Engine Router**
