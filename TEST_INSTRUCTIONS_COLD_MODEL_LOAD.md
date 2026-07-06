# Test Instructions: Cold Model Load Stop Timing

## Purpose

Verify whether `stop_pipeline()` can interrupt the pipeline during InsightFace model loading, or if the model load blocks stop until completion.

## Critical Requirement

This test **MUST** be run in a **completely fresh Python process** with no prior scripts executed.

## Why Fresh Process Required

- InsightFace models are loaded into memory on first `identify_face()` call
- Once loaded, they stay in Python process memory
- Running any prior script that uses face_id will pre-load the models
- A pre-loaded test cannot measure cold load behavior

## Test Procedure

### Step 1: Close Everything
```bash
# Close ALL terminals running Python
# Close VS Code or any IDE running Python
# This ensures no Python process has models loaded
```

### Step 2: Open Fresh Terminal
```bash
# Open a NEW terminal window
# Navigate to project directory
cd d:\robot
```

### Step 3: Run Test (ONLY this script)
```bash
python scripts\test_cold_model_load_stop_timing.py
```

### Step 4: Follow On-Screen Instructions
- Position yourself clearly in front of webcam
- Press Enter to start
- **Move around continuously** for the full 15 seconds to trigger:
  - Motion detection
  - YOLO person detection
  - Face identification (which loads models)
- Watch console logs carefully

## What to Look For

### During 15-Second Run

**Expected logs if test is VALID:**
```
Loading InsightFace buffalo_s model      ← Model loading started
InsightFace buffalo_s loaded successfully ← Model loading complete
[T1] InsightFace detected 1 face(s) in frame
Face identified for track T1: ...
```

**If these don't appear:**
- No motion detected (move more)
- No YOLO person detection (move closer to camera)
- Test is INVALID - retry

### During Stop Call

**Key measurement:**
```
Calling stop_pipeline() now...
Pipeline stopped in X.XXXs
```

**Interpretation:**
- **<1s**: Stop event is checked frequently, even during model load ✓
- **5-15s**: Model load blocks stop until complete ✗
- **>15s or timeout**: Serious issue with stop mechanism ✗✗

## Expected Outcomes

### Scenario A: Stop Event Checked During Load (Good)
- Stop time: <1s even if model was loading
- Means: Pipeline checks stop_event before/during `_get_face_app()` call
- Verdict: Current implementation is correct

### Scenario B: Model Load Blocks Stop (Bad)
- Stop time: 5-15s if model was loading
- Means: `_get_face_app()` is synchronous blocking call, stop_event not checked during it
- Verdict: Need to refactor or document as known limitation

## Current Code Analysis

From `face_id.py`:
```python
def identify_face(frame, bbox, track_id):
    # ...
    face_app = _get_face_app()  # ← Synchronous, blocks until loaded
    faces = face_app.get(frame)
    # ...
```

From `pipeline.py`:
```python
# Stop event checked BEFORE face_id stage
if _pipeline_stop_event.is_set():
    logger.info("Pipeline stop signal received before face_id")
    break

# Face ID runs here (may load models)
result = face_id.identify_face(frame, bbox, str(track_id))

# Stop event checked AFTER each face_id call
if _pipeline_stop_event.is_set():
    logger.info("Pipeline stop signal received during face_id processing")
    break
```

**Analysis:** Stop is checked BEFORE and AFTER `identify_face()`, but NOT DURING the `_get_face_app()` model load inside it. If model load takes 10s, stop will be delayed by up to 10s.

## Post-Test Decision Tree

### If Stop Time < 1s
→ Model was already loaded (invalid test) OR model loads very fast on your machine
→ **Action:** Retry in fresh process, verify logs show model loading

### If Stop Time 5-15s AND Model Loading Logged
→ Model load blocks stop (this is the issue we're investigating)
→ **Decision Required:**
  - **Option A (Accept):** Document as known limitation:
    ```
    "First face detection in a session may delay pipeline shutdown
    by up to 15s while InsightFace models finish loading from disk.
    Subsequent stops are fast (<1s). This is a one-time cost."
    ```
  - **Option B (Fix):** Refactor to make model loading interruptible:
    - Move model loading to startup (pre-load before pipeline starts)
    - OR add stop_event checks inside _get_face_app()
    - OR load models in separate thread with periodic stop checks

### If Test Invalid (No Model Loading Logs)
→ Test didn't exercise the code path
→ **Action:** Retry with better movement/positioning, verify YOLO detects you

## Run Test Now

Close this file, close terminal, open fresh terminal, run:
```bash
python scripts\test_cold_model_load_stop_timing.py
```
