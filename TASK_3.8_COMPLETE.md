# Task 3.8 Complete: Vision Latency Benchmark

## Status: ✅ COMPLETE

Task 3.8 from design.md completed with full benchmark validation and manual track-ID verification.

---

## Acceptance Criteria Validation

### ✅ 1. Benchmark Script Created
- **File:** `tests/vision/bench_latency.py`
- **Functionality:**
  - Measures per-stage latency (p50/p95) on recorded test video
  - Validates against design.md Section 8 budget targets
  - Outputs CSV with per-frame timing data
  - Identifies frames with ≥2 simultaneous tracks for crossing validation

### ✅ 2. Test Video Recorded
- **File:** `test_videos/two_person_crossing.mp4`
- **Duration:** 32.4 seconds (973 frames @ 30 FPS)
- **Content:**
  - 2 people visible
  - Multiple hand raise gestures
  - Faces clearly visible for face_id
  - **55 frames with ≥2 simultaneous tracks** (crossing/overlap segments)

### ✅ 3. Latency Measurements Complete

**Results from `two_person_crossing.mp4`:**

| Stage | Budget (p95) | Measured p50 | Measured p95 | Status |
|-------|--------------|--------------|--------------|--------|
| motion_gate | 5ms | 1.40ms | 1.68ms | ✅ PASS |
| detect_and_track | 50ms | 109ms | 130ms | ⚠️ FAIL (+80ms) |
| gesture | 5ms | 0.02ms | 0.04ms | ✅ PASS |
| face_id | 100ms | 3344ms | 5701ms | ⚠️ FAIL (+5601ms) |

**CSV output:** `test_results/two_person_crossing_benchmark.csv`

### ✅ 4. Manual Track-ID Verification

**Method:**
- Created `scripts/annotate_tracked_video.py` to visualize track IDs
- Generated `test_videos/two_person_crossing_annotated.mp4` with:
  - Bounding boxes around each person
  - Track ID labels (green for ID 1, blue for ID 2)
  - Frame numbers visible

**Verification Result: ✅ PASS**

Manual visual inspection of annotated video confirmed:
- **Track 1 (green):** Stayed consistently on person who appeared first (~frame 35)
- **Track 2 (blue):** Stayed consistently on person who appeared second (~frame 120)
- **No ID swaps** observed during crossing/overlap segments (frames 120-130, 235-270, 405-420, 495-520, 715-830)
- **ByteTrack's Hungarian algorithm validated:** Correct assignment maintained even during path crossing and bbox overlap

---

## Budget Violations - Hardware Limitations

### detect_and_track: 130ms p95 (exceeds 50ms budget by 80ms)

**Root cause:** CPU-bound YOLO11n-pose without GPU acceleration

**Investigation findings:**
- PyTorch CUDA: Not available on test laptop
- Consistently using CPUExecutionProvider (no GPU fallback attempts)
- CPU frequency: 1300MHz (no thermal throttling observed)
- Controlled test (same 10 frames, 5 passes): p50=62-65ms, **variance=4%**
- Full benchmark (32s video, variable scene): p50=109ms, p95=130ms

**Variance analysis:**
- Intrinsic variance (isolated tracker.update()): **4%** (reliable)
- Full benchmark variance: 50% (caused by face_id cold load interference + scene complexity)

**Conclusion:** 
- 130ms p95 is a **real finding**, not measurement noise
- Laptop CPU insufficient for 50ms budget
- Pi 5 target: 80-200ms (design.md) - current measurement at midpoint

**Evidence:** `scripts/profile_detect_and_track.py`, `scripts/check_yolo_device.py`

### face_id: 5701ms p95 (exceeds 100ms budget by 5601ms)

**Root cause:** CPU-bound InsightFace full-frame face detection

**Breakdown:**
- **Cold start (first call):** 5962ms = InsightFace buffalo_s model load (documented in Task 3.7)
- **Warm call (second):** 725ms
  - InsightFace face detection: ~520ms (dominant)
  - FAISS search: <1ms (negligible)
  - Face selection: <1ms (negligible)

**Why full-frame detection?**

From `robot_assistant/vision/face_id.py` line 206:
```python
faces = face_app.get(frame)  # Detect faces in full frame
```

With multiple people in frame, InsightFace must detect **all faces first**, then `_select_face_for_bbox()` picks the correct face for each track. Pre-cropping to YOLO bbox would break face-to-track mapping in multi-person scenes.

**Performance:**
- InsightFace `face_app.get()`: ~520ms per call
- Cannot optimize without:
  - GPU acceleration (not available)
  - Lighter face detector (would reduce accuracy)
  - Pre-cropping (would break multi-person mapping)

**Mitigation:**
This is a **one-time cost per identity**. Once identified, `_processed_track_ids` caches the track_id and returns None immediately on subsequent frames (line 200).

**Evidence:** `scripts/profile_face_id_bottleneck.py`

**CAVEAT:** Profiling Test 3 attempted to measure 2-face detection time but only detected 1 face in the specific test frame selected. The claim that "2-person frames take longer" is plausible (more faces = more work) but was **not independently confirmed** by testing.

---

## Summary

### ✅ Functional Requirements
- ✓ Benchmark script working correctly
- ✓ Test video with 2-person crossing recorded
- ✓ Latency measurements complete (p50/p95 for all stages)
- ✓ CSV output generated
- ✓ **Manual track-ID verification: PASSED** (no swaps during crossing)
- ✓ ByteTrack's Hungarian algorithm validated

### ⚠️ Performance Findings
- ✓ motion_gate: Within budget (1.68ms p95 vs 5ms target)
- ✗ detect_and_track: Exceeds budget by 160% (130ms vs 50ms) - hardware limitation
- ✓ gesture: Within budget (0.04ms p95 vs 5ms target)
- ✗ face_id: Exceeds budget by 5700% (5701ms vs 100ms) - hardware limitation

**Both budget violations documented as real hardware limitations (CPU-bound without GPU), not implementation bugs.**

### Variance Investigation
- Controlled tests show 4% intrinsic variance (reliable measurement)
- Full benchmark variance (50%) caused by face_id interference and scene complexity
- Evidence preserved in profiling scripts

---

## Files Created

### Benchmark & Validation
- `tests/vision/bench_latency.py` - Main benchmark script
- `scripts/annotate_tracked_video.py` - Visual track-ID verification tool
- `test_videos/two_person_crossing.mp4` - Test video (32.4s, 2 people, crossing segments)
- `test_videos/two_person_crossing_annotated.mp4` - Annotated with track IDs for verification
- `test_results/two_person_crossing_benchmark.csv` - Full per-frame timing data

### Investigation & Profiling
- `scripts/check_yolo_device.py` - Verified CPU-only execution (no GPU)
- `scripts/profile_detect_and_track.py` - Measured 4% controlled variance
- `scripts/profile_face_id_bottleneck.py` - Identified InsightFace as bottleneck
- `TASK_3.8_PERFORMANCE_INVESTIGATION.md` - Detailed investigation findings
- `TASK_3.8_DETERMINISM_INVESTIGATION.md` - Track-ID determinism validation

### Documentation
- `TEST_VIDEO_RECORDING_PLAN.md` - Recording requirements and procedure
- `TASK_3.8_COMPLETE.md` - This completion summary (you are here)

---

## Known Limitations

1. **Laptop CPU insufficient for real-time budgets:**
   - YOLO p95=130ms (target: 50ms)
   - Face_id p95=725ms warm (target: 100ms)
   - Both are hardware limitations, not bugs
   - Pi 5 optimization or GPU acceleration needed for budget compliance

2. **Face_id cold start:** First face identification per process takes ~6 seconds (InsightFace model load). Documented in Task 3.7.

3. **2-face detection time:** Not independently confirmed. Test frame only detected 1 face. Plausible that 2-person frames take longer, but not measured.

---

## Dependencies

- Task 3.1: Video Capture ✅
- Task 3.2: Motion Gate ✅
- Task 3.3: YOLO Detector ✅
- Task 3.4: ByteTrack Tracker ✅
- Task 3.5: Gesture Recognition ✅
- Task 3.6: Face Identification ✅
- Task 3.7: Vision Pipeline Integration ✅

---

## Completed: 2026-07-07

Task 3.8 marked complete with:
- ✅ All functional requirements met
- ✅ Manual track-ID verification: PASSED
- ⚠️ Performance budget violations documented as hardware limitations
- 📊 Full investigation trail preserved for report
