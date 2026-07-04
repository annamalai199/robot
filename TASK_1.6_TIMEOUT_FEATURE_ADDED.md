# Task 1.6: Greeting Timeout/Fallback Feature Added ✅

**Date:** 2026-07-04

## Problem Identified

**Critical failure mode:** If GREETING_DELIVERED never fires (TTS fails, crashes mid-utterance, audio device errors), the identity would stay in NEW state indefinitely. Decision Engine would keep trying to greet the same person on every subsequent detection → **infinite re-greet loop**.

## Solution Implemented

**Timeout/Fallback mechanism with philosophy:** "Fail visibly, don't stall silently" (per design Section 7)

### Design Choice: Option (a) - Auto-transition with logged warning

**Auto-transition NEW → GREETED after timeout** (not FAILED/error state)

**Rationale:**
- Prevents annoying re-greet loops (user experience priority)
- Logs warning for debugging (fail visibly)
- Assumes greeting was probably fine (TTS usually works)
- Simpler than adding FAILED state and recovery logic
- Matches design philosophy: degrade gracefully, keep working

### Implementation Details

**Timeout:** 5 seconds (configurable via `GREETING_TIMEOUT_SECONDS`)
- TTS typically completes in 1-2s
- 5s is generous buffer for slow devices or long greetings

**New Event:** `GREETING_INITIATED`
- Published by Decision Engine when greeting is sent to TTS
- Records `greeting_initiated_at` timestamp in session state
- Does NOT change state (stays NEW)

**Timeout Check:**
- On every `IDENTITY_RESOLVED` event for NEW state identity
- If `greeting_initiated_at` exists and elapsed time > 5s:
  - Auto-transition NEW → GREETED
  - Clear `greeting_initiated_at` timestamp
  - Log WARNING with elapsed time and reason

**Timeout Cleared By:**
- `GREETING_DELIVERED` - normal case (greeting succeeded)
- `TRACK_LOST` - person left before greeting completed

### State Machine with Timeout

```
NEW (person detected, waiting for greeting)
  + GREETING_INITIATED → stays NEW, records timestamp
  + GREETING_DELIVERED → GREETED (clears timestamp)
  + IDENTITY_RESOLVED (after 5s timeout) → GREETED (auto-transition with warning)
  + TRACK_LOST → AWAY (clears timestamp)

GREETED (greeting delivered or timed out)
  + TRACK_LOST → AWAY
  + IDENTITY_RESOLVED → stays GREETED
```

### Code Changes

**`robot_assistant/session_state/store.py`:**

1. **Module constant:**
   ```python
   GREETING_TIMEOUT_SECONDS = 5.0  # TTS should complete in 1-2s, 5s is generous
   ```

2. **Session state dict structure updated:**
   ```python
   {
       "state": "NEW",
       "last_seen": 1720051200.0,
       "track_id": "T1",
       "created_at": 1720051200.0,
       "greeting_initiated_at": None  # NEW FIELD
   }
   ```

3. **`update_identity_state()` enhanced:**
   - Added `GREETING_INITIATED` event handler
   - Timeout check at start of function (catches any state update)
   - Timeout check on `IDENTITY_RESOLVED` for NEW state
   - Timestamp clearing on `GREETING_DELIVERED` and `TRACK_LOST`

4. **New helper function:**
   ```python
   def get_greeting_timeout() -> float:
       """Get the greeting timeout value in seconds."""
       return GREETING_TIMEOUT_SECONDS
   ```

5. **Updated docstrings:**
   - Module docstring explains timeout/fallback philosophy
   - Function docstring details timeout behavior and responsibility chain

**`robot_assistant/session_state/__init__.py`:**
- Added `get_greeting_timeout` to exports

### Test Coverage

**8 new tests added to `tests/session_state/test_store.py`:**

1. **`test_greeting_initiated_event`**
   - GREETING_INITIATED records timestamp but doesn't change state

2. **`test_greeting_timeout_auto_transitions_to_greeted`** ⭐
   - NEW state auto-transitions to GREETED after timeout

3. **`test_greeting_timeout_prevents_re_greet_loop`** ⭐ (CRITICAL)
   - Confirms no infinite loop if TTS fails

4. **`test_greeting_delivered_before_timeout_clears_timestamp`**
   - Normal case: GREETING_DELIVERED clears timeout

5. **`test_track_lost_before_greeting_clears_timeout`**
   - Person leaves before greeting completes

6. **`test_greeting_timeout_only_applies_to_new_state`**
   - Timeout doesn't affect GREETED/AWAY/RETURNED states

7. **`test_get_greeting_timeout`**
   - Timeout value is accessible

8. **`test_greeting_timeout_with_no_initiated_event`**
   - NEW state without GREETING_INITIATED doesn't timeout (no false positives)

### Log Output on Timeout

```
WARNING:robot_assistant.session_state.store:Greeting timeout for E0042: 5.1s elapsed, 
no GREETING_DELIVERED received. Auto-transitioning to GREETED to prevent re-greet loop 
(TTS may have failed).
```

## Responsibility for Task 1.7 (Decision Engine)

**Decision Engine must:**

1. **On IDENTITY_RESOLVED for NEW state:**
   ```python
   # Check session state
   state_dict = session_state.get_state(embedding_id)
   if state_dict["state"] == "NEW":
       # Generate greeting
       greeting_text = "Hello! I'm your assistant."
       
       # Record that greeting is being attempted
       session_state.update_identity_state(embedding_id, "GREETING_INITIATED", track_id)
       
       # Send to TTS
       tts.synthesize(greeting_text)
       
       # AFTER TTS completes
       bus.publish({"event": "GREETING_DELIVERED", "embedding_id": embedding_id, "track_id": track_id})
   ```

2. **Handle TTS failures gracefully:**
   - If TTS raises exception, DON'T publish GREETING_DELIVERED
   - Timeout will auto-transition after 5s
   - Log the TTS error for debugging

3. **Don't worry about the timeout:**
   - Session State Store handles timeout automatically
   - Decision Engine just publishes events normally

## Edge Cases Handled

✅ **TTS crashes mid-synthesis** - timeout triggers, person won't be greeted twice  
✅ **Audio device disconnected** - timeout triggers, prevents loop  
✅ **TTS hangs indefinitely** - timeout triggers after 5s  
✅ **Person leaves before greeting starts** - TRACK_LOST clears timeout  
✅ **Person leaves during greeting** - TRACK_LOST clears timeout  
✅ **Normal greeting succeeds** - GREETING_DELIVERED clears timeout  
✅ **Re-detection after timeout** - stays GREETED, doesn't loop back to NEW  
✅ **Multiple people with mixed success/failures** - each tracked independently  

## Test Results

```
tests/session_state/test_store.py::test_greeting_initiated_event PASSED
tests/session_state/test_store.py::test_greeting_timeout_auto_transitions_to_greeted PASSED
tests/session_state/test_store.py::test_greeting_timeout_prevents_re_greet_loop PASSED ⭐
tests/session_state/test_store.py::test_greeting_delivered_before_timeout_clears_timestamp PASSED
tests/session_state/test_store.py::test_track_lost_before_greeting_clears_timeout PASSED
tests/session_state/test_store.py::test_greeting_timeout_only_applies_to_new_state PASSED
tests/session_state/test_store.py::test_get_greeting_timeout PASSED
tests/session_state/test_store.py::test_greeting_timeout_with_no_initiated_event PASSED

33/33 session state tests passing ✅
149/149 total tests passing ✅ (+8 new timeout tests)
```

## Design Philosophy Applied

**"Fail visibly, don't stall silently" (Section 7):**
- ✅ Timeout triggers log WARNING (visible)
- ✅ State transitions forward, doesn't stall (graceful degradation)
- ✅ User experience preserved (no annoying re-greet loop)
- ✅ Debugging enabled (log shows elapsed time, reason)

**Alternative considered and rejected:** FAILED/error state
- Would require additional recovery logic
- Would complicate state machine (5 states instead of 4)
- Doesn't improve user experience (still need to prevent re-greet)
- Adds complexity without clear benefit

## Summary

**Problem:** TTS failure causes infinite re-greet loop  
**Solution:** 5-second timeout auto-transitions NEW → GREETED with logged warning  
**Result:** Graceful degradation, fail visibly, user experience preserved  
**Status:** Implemented, tested, documented ✅

**Ready to proceed to Task 1.7: Decision Engine Router**
