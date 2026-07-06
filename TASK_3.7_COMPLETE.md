# Task 3.7: Vision Pipeline Integration - Complete

**Date:** 2026-07-06  
**Status:** ✅ Completed (after stop timing investigation and verification)

## Summary

Implemented a fully integrated vision pipeline that orchestrates all 5 vision processing stages in a single threaded loop with clean start/stop lifecycle management.

## Implementation

### Core Module: `robot_assistant/vision/pipeline.py`

**Public API:**
- `start_pipeline(camera_index=0)` - Start pipeline in background thread
- `stop_pipeline(timeout=5.0)` - Graceful shutdown with timeout
- `is_pipeline_running()` - Check running status
- `run_pipeline(camera_index=0)` - Main processing loop (internal, not called directly)

**Pipeline Flow:**
```
Frame → Motion Gate → (if motion detected) →
  YOLO Detection (every Kth frame) →
  ByteTrack Tracking (every YOLO frame) →
  Gesture Recognition (all tracked persons) →
  Face ID (new track_ids only)
```

**Threading Model:**
- Pipeline runs in daemon background thread
- Main thread can continue with other work
- Clean shutdown via stop event signaling
- Thread-safe state management

**Event Publishing:**
- GESTURE_DETECTED: Published by `gesture.check_gesture()` when hand raised
- IDENTITY_RESOLVED: Published by `face_id.identify_face()` for new faces
- TRACK_LOST: Published by `tracker.update()` when tracks disappear >30 frames

## Validation

### Smoke Test: `scripts/smoke_test_pipeline_integration.py`

Tests lifecycle management:
1. ✅ Start pipeline successfully
2. ✅ Verify running status
3. ✅ Run for 5 seconds without crashes
4. ✅ Stop cleanly
5. ✅ Verify stopped status
6. ✅ Restart (validates cleanup)

**Result:** All tests passed

### Stop Timing Investigation (Detailed)

**Issue Discovered:** Initial smoke test showed "Pipeline thread did not stop within 10.0s" warning on restart cycle.

**Investigation Phases:**

**Phase 1 - Initial Diagnostics:**
- Added per-stage timing logs
- Added 4 stop_event check points
- Ran 3 consecutive cycles: all stopped in 0.35-0.58s
- **Incorrect conclusion:** "Models already loaded, not a bug"

**Phase 2 - Gap Identified:**
- Tests never triggered face_id (no YOLO person detections)
- "Models already loaded" explanation was flawed (separate processes can't share memory)
- Test measured stop during idle periods, not during blocking calls

**Phase 3 - Manual Cold Load Test:**
- Ran test in fresh process with person in frame
- Model load: 4.7s, face_id call: 6739.6ms
- **Issue:** Stop called 1.7s AFTER face_id completed (measured idle period again)

**Phase 4 - Automated Test (First Attempt):**
- Created `test_stop_during_face_id.py` with log monitoring
- Triggered on "InsightFace detected" log
- **Issue:** This log appears at T+8.6s, after 4.7s model load already finished
- Only measured last ~1s of FAISS work

**Phase 5 - Automated Test (Corrected):**
- Fixed trigger to "Loading InsightFace buffalo_s model" (T+0.0s)
- This is the TRUE worst case: stop at start of 4.7s+ blocking operation
- **Result: Measured worst case = 7.199s**

### Measured Worst Case: 7.199s

**Test:** `scripts/test_stop_during_face_id.py` (corrected version)  
**Scenario:** stop_pipeline() called at exact moment model loading starts  
**Timeline:**
```
T+0.0s:  "Loading InsightFace buffalo_s model" logged → STOP CALLED HERE
         ↓
         | 4.7s+ BLOCKING MODEL LOAD (cannot be interrupted)
         ↓
T+4.7s:  Model loaded, face detection runs
T+8.6s:  "InsightFace detected" (detection complete)
T+7.2s:  stop_pipeline() returns (waited for identify_face to complete)
```

**Root Cause:**
- `_get_face_app()` in face_id.py performs synchronous blocking model load
- Python threads cannot preempt mid-function
- Stop event checked BEFORE and AFTER identify_face(), not DURING
- Therefore stop must wait for entire call to complete

**Verdict:** This is expected Python threading behavior, not a bug.

### Known Limitation (Documented)

**Limitation:** First face identification may delay shutdown by up to ~7s

**Conditions:**
- Only affects FIRST face detected in process (cold model load)
- Only if stop_pipeline() called during that exact moment
- Subsequent stops complete in <1s (model cached in memory)

**Scope:**
- One-time cost per process
- Does not affect actuator safety (hardware E-stop is independent)
- Acceptable for MVP use case

**Documentation:**
- Added to `pipeline.py` run_pipeline() docstring
- Added to this task completion document
- Investigation trail preserved in `PIPELINE_STOP_TIMING_INVESTIGATION.md`

See `PIPELINE_STOP_TIMING_INVESTIGATION.md` for complete investigation history.

### Demo: `examples/vision_pipeline_demo.py`

Interactive demo that:
- Subscribes to all pipeline events
- Prints events to console in real-time
- Shows gesture/identity/track_lost detection
- Ctrl+C for graceful shutdown

## Key Design Decisions

### 1. Threading over Asyncio
**Rationale:** Vision processing is CPU-bound (YOLO, face embeddings), not I/O-bound. Threading is simpler and more appropriate than asyncio for this workload.

### 2. Event Publishing Delegation
**Rationale:** Individual modules (gesture, face_id, tracker) publish their own events. Pipeline doesn't need to know event schemas, reducing coupling.

### 3. Track ID Caching
**Rationale:** Face ID runs once per track_id (expensive ~200ms), not every frame. Track IDs cached in Set to prevent redundant face embedding computation.

### 4. Motion Gate Integration
**Rationale:** Motion gate filter saves ~95% of YOLO calls on static scenes. Only frames with motion trigger YOLO → tracking → gesture → face_id cascade.

### 5. Multiple Stop Checks
**Rationale:** Stop event checked at loop start, before tracking, before face_id, and after each face_id call. Ensures <1s stop latency in normal operation (except cold model load case).

### 6. Accept Model Load Delay
**Rationale:** 7.199s worst-case delay is:
- One-time per process
- Only if stop coincides with first face detection
- Inherent to Python threading (cannot preempt mid-function)
- Does not affect hardware E-stop safety
- Acceptable for MVP, alternative would require significant refactoring (pre-load models, async loading, etc.)

## Performance Characteristics

**Measured on laptop webcam (640×480):**
- Frame rate: ~21 FPS average
- Motion detection: ~44% of frames trigger YOLO
- YOLO runs: Every 5th motion frame (K=5 from config)
- Gesture checks: Every tracked person, every YOLO frame (<1ms each)
- Face ID: Once per new track_id (~200ms one-time cost, or ~7s on first-ever with cold load)
- Stop latency: <1s (normal), ~7s (worst case: during cold model load)

## Files Created/Modified

**Created:**
- `robot_assistant/vision/pipeline.py` - Main integration module
- `examples/vision_pipeline_demo.py` - Interactive demo
- `scripts/smoke_test_pipeline_integration.py` - Lifecycle smoke test
- `scripts/diagnose_pipeline_stop_timing.py` - Diagnostic tool (Phase 1)
- `scripts/test_first_run_vs_subsequent.py` - Model load test (Phase 1, flawed)
- `scripts/test_cold_model_load_stop_timing.py` - Manual cold load test (Phase 3)
- `scripts/test_stop_during_face_id.py` - Automated test (Phase 4-5, corrected)
- `PIPELINE_STOP_TIMING_INVESTIGATION.md` - Complete investigation trail
- `TEST_INSTRUCTIONS_COLD_MODEL_LOAD.md` - Manual test instructions
- `STOP_TIMING_TEST_REQUIRED.md` - Investigation status tracking
- `FINAL_STOP_TIMING_TEST.md` - Final test explanation

**Modified:**
- `robot_assistant/vision/__init__.py` - Added pipeline to exports
- `.kiro/specs/humanoid-robot-assistant/tasks.md` - Marked Task 3.7 complete

**Preserved Investigation Trail:**
All test scripts preserved to show how incorrect conclusions were caught and corrected:
- Early tests that didn't trigger face_id
- Tests that measured wrong timing points
- Final corrected test that measured true worst case

## Dependencies Satisfied

Task 3.7 depends on Tasks 3.2-3.6, all now complete:
- ✅ Task 3.2: Motion Gate
- ✅ Task 3.3: YOLO Detector
- ✅ Task 3.4: ByteTrack Tracker
- ✅ Task 3.5: Gesture Recognition
- ✅ Task 3.6: Face Identification

## Next Steps

Proceed to **Task 3.8: Vision Latency Benchmark** to measure per-stage timing and validate performance targets from design document Section 8.
