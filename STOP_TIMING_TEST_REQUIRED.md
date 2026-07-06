# ⚠️ ACTION REQUIRED: Stop Timing Test

## Summary

Task 3.7 investigation identified that stop timing during face_id execution has NOT been properly tested. We need to measure stop latency when stop_pipeline() is called WHILE identify_face() is actively executing.

## Previous Test Gap

**Manual test results:**
- ✅ Cold model load happened (4.7s)
- ✅ Face ID call happened (6739.6ms)
- ❌ BUT stop was called 1.7s AFTER face_id completed
- Result: Measured stop time during idle gap, not during active call

**Why timing matters:**
- Stop event is checked BEFORE and AFTER identify_face()
- Stop event is NOT checked DURING identify_face() or _get_face_app()
- If stop arrives while face_id is executing, Python threading cannot preempt mid-call
- Need to measure actual delay in this specific scenario

## Automated Test Solution

Created `scripts/test_stop_during_face_id.py` which:
1. Starts pipeline
2. Monitors logs for "InsightFace detected" (face_id entry)
3. Immediately calls stop_pipeline() when detected
4. Measures stop duration when stop arrives DURING active call

## Required Test

### Prerequisites
1. Close ALL terminals
2. Open ONE fresh terminal  
3. cd to d:\robot
4. Run ONLY this command (no other scripts first)

### Command
```bash
python scripts\test_stop_during_face_id.py
```

### During Test
1. Position yourself CLEARLY in front of webcam BEFORE pressing Enter
2. Press Enter to start
3. **MOVE CONTINUOUSLY** to trigger YOLO
4. Test will automatically call stop when face_id starts

### What to Report

The test will print a verdict automatically. Look for:

**If stop_duration < 1s:**
- ✅ Stop works correctly
- Mark Task 3.7 complete

**If stop_duration 1-5s:**
- ✅ Acceptable delay
- Document as expected behavior
- Mark Task 3.7 complete

**If stop_duration ≥ 5s:**
- ⚠️ Known limitation confirmed
- Must document before marking complete:
  ```
  "First face identification may delay pipeline shutdown by up to Ns
  while InsightFace models load. This is a one-time cost per process.
  Subsequent stops are fast (<1s)."
  ```

## Expected Behavior

Given the code structure:
```python
# pipeline.py
if _pipeline_stop_event.is_set():
    break

result = face_id.identify_face(...)  # ← 5-15s blocking on cold load
                                      # ← stop_event NOT checked here

if _pipeline_stop_event.is_set():
    break
```

**Expected delay:** 5-15s if stop arrives during model load

This is NOT a bug - it's inherent to Python's threading model. Synchronous calls cannot be interrupted mid-execution. The question is whether this is acceptable or needs refactoring.

## Decision Tree

### If Test Shows <5s Delay
→ **Accept:** Current implementation is fine
→ **Action:** Mark Task 3.7 complete

### If Test Shows ≥5s Delay  
→ **Decision Required:**

**Option A (Accept as-is):**
- Document limitation explicitly in code and task completion
- Note it's one-time per process
- Mark Task 3.7 complete

**Option B (Refactor to fix):**
- Pre-load InsightFace models at application startup
- OR load models in separate thread with periodic stop checks
- OR add timeout mechanism to model loading
- Don't mark Task 3.7 complete until fixed

## Current Status

🔴 **BLOCKED** - Cannot mark Task 3.7 complete until this test runs

## Files for This Test

- `scripts/test_stop_during_face_id.py` - Automated test (NEW)
- `scripts/test_cold_model_load_stop_timing.py` - Manual test (previous)
- `TEST_INSTRUCTIONS_COLD_MODEL_LOAD.md` - Manual test instructions
- `STOP_TIMING_TEST_REQUIRED.md` - This file
