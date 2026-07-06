# Task 3.6: Nondeterminism Bug Found and Diagnosed

## Bug Discovery

**Determinism test revealed:**
- Same frame processed twice → L2 distance = **0.685 to 0.74** between embeddings
- **Expected**: distance ≈ 0.0 (perfect determinism)
- **Actual**: MASSIVE nondeterminism

## Root Cause Diagnosis

### Tests Performed:

1. **InsightFace alone (direct calls):**
   - ✓ Face detection bbox: identical across runs
   - ✓ Embeddings: distance = 0.0 (perfectly deterministic)
   
2. **Through identify_face() pipeline:**
   - ✗ Embeddings: distance = 0.68-0.74 (nondeterministic!)

### Conclusion:
- InsightFace itself IS deterministic
- The bug is in OUR pipeline (identify_face.py)
- Something between getting the face and storing/comparing the embedding causes variance

## Probable Cause

The nondeterminism was introduced when we switched from pre-cropping to YOLO bbox to using the full frame.

**Old approach (deterministic):**
```python
crop = frame[y1:y2, x1:x2]  # Same crop every time
faces = face_app.get(crop)   # Same result
face = faces[0]              # Same face
```

**New approach (nondeterministic):**
```python
faces = face_app.get(frame)   # All faces in frame
faces = sorted(faces, key=...) # Sort attempt
# Select face via bbox overlap logic
```

**Hypothesis**: Even with sorting, the face selection logic (bbox overlap calculation) might be selecting DIFFERENT faces on repeated calls, possibly due to:
1. Multiple faces detected (reflections, background)
2. Floating-point rounding in overlap calculations
3. Faces with identical x-coordinates sorted non-deterministically

## Impact

**This bug invalidates ALL previous measurements:**
- The 0.84-0.96 "same-person" distances we measured
- Were NOT genuine capture-to-capture variance
- Were artifacts of THIS nondeterminism bug
- Each "capture" was actually processing a different face or face region

**We cannot validate threshold until this is fixed.**

## Solution

**REVERT to pre-cropping approach** (Option 4 rollback):

The full-frame approach was meant to improve embedding quality by letting InsightFace find the face with its own detector. But it introduced nondeterminism that makes the system unusable.

The pre-cropped approach was:
- ✓ Deterministic
- ✓ Working
- ✗ Had slightly higher variance (but that was REAL variance, not a bug)

**Action**: Revert face_id.py to crop to YOLO bbox first, then pass crop to InsightFace.

This will:
1. Restore determinism
2. Give us REAL same-person variance measurements
3. Allow proper threshold calibration

## Status

Task 3.6 remains BLOCKED until:
1. Revert to pre-crop approach
2. Verify determinism (distance ≈ 0 on same frame twice)
3. Re-measure same-person variance with deterministic pipeline
4. Test with different person (still requires second human)
5. Calculate evidence-based threshold

**Current code is BROKEN and cannot be used for any validation.**
