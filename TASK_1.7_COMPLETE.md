# Task 1.7: Decision Engine Router - COMPLETE

## Summary
Successfully implemented the Decision Engine Router, which serves as the central coordinator for routing inputs through the 3-way decision path system (Path A: Deterministic → Path B: Cache → Path C: LLM).

## Implementation Details

### Files Created/Modified

#### New Files:
1. **`robot_assistant/decision_engine/engine.py`** (317 lines)
   - Main 3-way router implementation
   - Greeting flow management for NEW/RETURNED identities
   - Text question routing through Path A/B/C
   - Stub functions for TTS, cache, and LLM (to be replaced in later tasks)
   - Event handlers for IDENTITY_RESOLVED and TEXT_INPUT

2. **`robot_assistant/decision_engine/__init__.py`**
   - Module exports for decision engine components

3. **`tests/decision_engine/test_engine.py`** (557 lines)
   - 19 comprehensive tests covering all greeting flows and routing logic
   - Tests clearly labeled as REAL LOGIC vs STUB TESTING
   - Tests verify routing decisions and confirm stubs are called correctly

#### Modified Files:
4. **`robot_assistant/events/__init__.py`**
   - Added exports for GreetingDeliveredEvent and GreetingInitiatedEvent

5. **`robot_assistant/decision_engine/intents.py`**
   - **IMPORTANT FIX:** Removed RESPONSE event publishing from intents.py
   - Intents now only return text; Decision Engine publishes RESPONSE events
   - This fixes a double-publishing bug and ensures proper separation of concerns

6. **`tests/decision_engine/test_intents.py`**
   - Updated 2 tests to reflect that intents.py no longer publishes events
   - Tests now verify return values instead of event publishing

## Key Design Decisions

### 1. Greeting Flow Management
- **NEW identities:** 
  - Publish GREETING_INITIATED → call TTS stub → publish GREETING_DELIVERED on success
  - GREETING_DELIVERED triggers NEW → GREETED state transition
  - TTS failure handled by 5-second timeout in session_state (Task 1.6)

- **RETURNED identities:**
  - Call TTS for "welcome back" message
  - Do NOT publish GREETING_DELIVERED (no state transition needed)

- **GREETED/AWAY identities:**
  - No greeting needed

### 2. Text Routing (3-Way Paths)
- **Path A (Deterministic):** intents.py - exact intent match (<5ms)
- **Path B (Cache):** stub for now - will check QA cache in Task 1.11 (<35ms target)
- **Path C (LLM):** stub for now - will use LangGraph + Ollama in Task 1.14 (1-3s)
- Takes first non-None result in A → B → C order
- Publishes RESPONSE event with path metadata and latency

### 3. Event Subscriptions
- Decision Engine subscribes to: IDENTITY_RESOLVED, TEXT_INPUT
- Does NOT subscribe to: ACTION (SafetyGate handles this directly per Task 1.5)
- Does NOT subscribe to: GESTURE_DETECTED (gesture_actions.py handles this per Task 1.4)

### 4. Stub Dependencies
All stubs are clearly labeled with `[STUB]` logging and TODO comments:
- `_stub_tts_synthesize()` - will be replaced in Task 2.3
- `_stub_cache_check()` - will be replaced in Task 1.11
- `_stub_llm_generate()` - will be replaced in Task 1.14

## Bug Fix: Double RESPONSE Publishing
During implementation, discovered and fixed a critical bug:
- **Problem:** RESPONSE events were being published TWICE
- **Root Cause:** Both intents.py AND engine.py were publishing RESPONSE events
- **Solution:** Removed event publishing from intents.py; engine.py now has sole responsibility
- **Benefit:** Proper separation of concerns - intents.py is a pure lookup function

### Follow-up Fixes (Per User Request):
1. **Updated tasks.md Task 1.3:** Amended acceptance criteria to reflect corrected architecture with strikethrough on old criteria and explanatory note about the change in Task 1.7
2. **Fixed examples/intent_demo.py:** Updated to work as standalone component demo without relying on RESPONSE event publishing; added clear notes explaining integration with Decision Engine

## Test Results
```
tests/decision_engine/test_engine.py::test_new_identity_triggers_full_greeting_flow PASSED
tests/decision_engine/test_engine.py::test_new_identity_with_name_gets_personalized_greeting PASSED
tests/decision_engine/test_engine.py::test_returned_identity_gets_welcome_back_without_greeting_delivered PASSED
tests/decision_engine/test_engine.py::test_greeted_identity_no_re_greeting PASSED
tests/decision_engine/test_engine.py::test_tts_failure_does_not_publish_greeting_delivered PASSED
tests/decision_engine/test_engine.py::test_path_a_deterministic_intent_match PASSED
tests/decision_engine/test_engine.py::test_path_b_cache_stub_called_for_non_intent PASSED
tests/decision_engine/test_engine.py::test_path_c_llm_stub_called_for_cache_miss PASSED
tests/decision_engine/test_engine.py::test_three_way_routing_order PASSED
tests/decision_engine/test_engine.py::test_response_event_includes_latency PASSED
tests/decision_engine/test_engine.py::test_generate_greeting_new_with_name PASSED
tests/decision_engine/test_engine.py::test_generate_greeting_new_without_name PASSED
tests/decision_engine/test_engine.py::test_generate_greeting_returned_with_name PASSED
tests/decision_engine/test_engine.py::test_generate_greeting_returned_without_name PASSED
tests/decision_engine/test_engine.py::test_generate_greeting_greeted_state_returns_empty PASSED
tests/decision_engine/test_engine.py::test_multiple_text_inputs_sequential PASSED
tests/decision_engine/test_engine.py::test_greeting_and_text_input_interleaved PASSED
tests/decision_engine/test_engine.py::test_engine_does_not_subscribe_to_action_events PASSED
tests/decision_engine/test_engine.py::test_start_and_stop_decision_engine PASSED

All Decision Engine tests: 19/19 PASSED
Full test suite: 181/181 PASSED
```

## Integration Points

### Consumes Events From:
- Task 3.6: IDENTITY_RESOLVED (from face recognition)
- Task 2.1: TEXT_INPUT (from voice STT or keyboard)

### Publishes Events To:
- GREETING_INITIATED - starts greeting timeout timer
- GREETING_DELIVERED - completes greeting flow for NEW identities
- RESPONSE - answers to user questions (all paths)

### Calls Functions From:
- Task 1.6: `get_state()`, `update_identity_state()` - session state management
- Task 1.3: `get_intent_response()` - Path A deterministic intents
- Stubs for Tasks 1.11 (cache), 1.14 (LLM), 2.3 (TTS)

### Called By:
- Task 4.5: Main application will call `start_decision_engine()` at startup
- Task 4.5: Main loop will call `check_timeouts()` from session_state ~1x/second

## Verification Checklist
- [x] Subscribes to IDENTITY_RESOLVED and TEXT_INPUT
- [x] Does NOT subscribe to ACTION (SafetyGate handles it)
- [x] Greeting flow works for NEW, RETURNED, GREETED states
- [x] GREETING_DELIVERED only published for NEW → GREETED
- [x] Text routing tries Path A → B → C in order
- [x] RESPONSE events include path metadata and latency
- [x] All stubs clearly labeled with [STUB] and TODO comments
- [x] Tests distinguish REAL LOGIC from STUB TESTING
- [x] Fixed double-publishing bug in intents.py
- [x] All 181 tests passing (19 new + 162 previous)

## Next Steps
- Task 1.8-1.10: Memory management (embedding storage, SQLite ops, semantic search)
- Task 1.11: QA Cache Manager (replace cache stub in Path B)
- Task 1.14: LangGraph reasoning (replace LLM stub in Path C)
- Task 2.3: Piper TTS (replace TTS stub)
- Task 4.5: Main application loop (will call start_decision_engine and check_timeouts)

## Notes for Future Tasks
- When implementing Task 1.11 (Cache), replace `_stub_cache_check()` call with real cache manager
- When implementing Task 1.14 (LLM), replace `_stub_llm_generate()` call with LangGraph reasoning
- When implementing Task 2.3 (TTS), replace `_stub_tts_synthesize()` call with Piper TTS
- When implementing Task 4.5 (Main Loop), must call `session_state.check_timeouts()` ~1x/second

---

**Task 1.7 Status: COMPLETE** ✅  
**Date:** 2026-07-04  
**Test Count:** 181 total (19 new Decision Engine tests)  
**All Tests:** PASSING
