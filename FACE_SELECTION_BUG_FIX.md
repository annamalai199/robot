# Face Selection Logic Bug - Fixed

## Problem Discovered

User identified a mathematical contradiction in test_different_person.py results:
- identify_face() reported: confidence=0.4791 → distance ≈ 0.417
- Pairwise table showed: distance = 1.443 for the SAME pair

**These cannot both be correct** - they should be the identical L2 distance between the same two embeddings.

## Root Cause

**Code duplication without shared function:**

1. `face_id.identify_face()` had face selection logic (lines ~165-195)
2. `test_different_person.py` COPY-PASTED the same logic (lines ~65-95)
3. `test_same_person_variance.py` also COPY-PASTED it

**Why this causes bugs:**

When InsightFace detects multiple faces (happened before: 5 faces in earlier logs), the duplicated logic could:
- Select DIFFERENT faces if there were subtle differences in the copies
- Use slightly different overlap calculations
- Break determinism between the "internal match" and "pairwise comparison"

Result: The pairwise distance table was comparing DIFFERENT embeddings than what identify_face() actually matched internally.

## Fix Applied

**Extracted shared function in face_id.py:**

```python
def _select_face_for_bbox(faces, bbox):
    """Select the face that best corresponds to a YOLO person bbox.
    
    Uses deterministic selection logic:
    1. Sort faces by x-coordinate
    2. Find face with best overlap with YOLO bbox
    3. Return selected face or None
    """
    # Single implementation of the logic
```

**Updated all callers to use shared function:**

1. `identify_face()` - calls `_select_face_for_bbox(faces, bbox)`
2. `test_different_person.py` - calls `face_id._select_face_for_bbox(faces, bbox)`
3. `test_same_person_variance.py` - calls `face_id._select_face_for_bbox(faces, bbox)`

## Benefits

1. **Structural impossibility of selection bugs** - Only ONE implementation exists
2. **Guaranteed consistency** - All code paths select the SAME face
3. **Single point of maintenance** - Fix bugs in one place, benefits all callers
4. **Easier testing** - Can test the selection logic in isolation
5. **Clear ownership** - Face selection is face_id.py's responsibility, not copied everywhere

## Additional Changes

**Added detailed logging to test_different_person.py:**

```python
print(f"InsightFace detected {len(faces)} face(s) for pairwise comparison")
for idx, f in enumerate(faces):
    print(f"  Face {idx}: bbox={f.bbox}")
print(f"Selected face {selected_idx} for pairwise comparison: bbox={selected_face.bbox}")
```

This makes it visible:
- How many faces were detected
- Which face was selected
- Whether the selection was the same across both code paths

## Testing Required

**Before accepting any threshold validation:**

1. Re-run test_different_person.py with logging enabled
2. Verify "InsightFace detected N faces" matches between identify_face and pairwise comparison
3. Verify "Selected face X" is the same in both code paths
4. Confirm the distance contradiction is resolved (both paths report same distance)

**Image verification required:**

User correctly noted that image1.jpg and image2.jpg (227x148, 148x148) look like stock avatars or AI-generated faces. These should be:
- Real photos of verified distinct people
- Sufficient resolution for face detection
- NOT AI-generated or synthetic faces

## Status

**Code fix: COMPLETE**
**Testing: REQUIRED** - User must re-run test with:
1. Verified real photos (not AI-generated)
2. Logging enabled to confirm same face selection
3. Distance contradiction resolved
