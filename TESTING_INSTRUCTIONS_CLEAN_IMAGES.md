# Testing Instructions: Clean Single-Subject Images Required

## Status of Refactor

✓ **Shared function refactor: COMPLETE**

The face selection logic is now in ONE place:
- `face_id._select_face_for_bbox()` - single implementation
- Used by: `identify_face()`, `test_different_person.py`, `test_same_person_variance.py`
- No duplicated logic exists

## Current Issue: Crowded Photos

The test images (person_A.jpg, image1.jpg, image2.jpg) are classroom photos with 3-7 background people visible. This causes:

1. **InsightFace detects multiple faces** (5+ faces per image)
2. **Face selection becomes ambiguous** - which person is the "main subject"?
3. **Distance measurements are unreliable** - may be measuring different background people

Example from logs:
```
InsightFace detected 5 face(s) in frame
  Face 0: bbox=[523.17, 173.87, 592.14, 257.37]
  Face 1: bbox=[167.27, 207.95, 228.85, 285.50]
  Face 2: bbox=[312.95, 103.15, 456.53, 283.64]  <- Selected
  ...
```

**This is testing two things at once:**
1. Do different people's embeddings separate? (what we want)
2. Does face selection work in crowds? (different question, test later)

## Required Action: Get Clean Single-Subject Images

### Option 1: Crop Existing Photos (Quick)
1. Open person_A.jpg, image1.jpg, image2.jpg in image editor
2. Crop tightly around ONLY the main subject (face + head/shoulders)
3. Remove ALL background people from frame
4. Save as new files: person_A_clean.jpg, person_B_clean.jpg, person_C_clean.jpg
5. Place in `robot_assistant\data\test_images\`

### Option 2: Capture Fresh Photos (Better)
1. Use webcam or phone camera
2. **Simple/empty background** (plain wall, outdoors with no people)
3. **Single person in frame** (no background faces visible)
4. Clear frontal face view
5. Minimum 300x300 resolution
6. Save 3 images of different people

### What "Clean" Means:
- ✓ ONE person visible in entire image
- ✓ Clear face (frontal or near-frontal angle)
- ✓ Simple background (wall, sky, blurred background)
- ✗ NO background people visible
- ✗ NO crowds, groups, or classroom scenes
- ✗ NO multiple faces (even far in background)

## Testing Sequence

Once you have clean single-subject images:

### 1. Same-Person Variance Test
```bash
python scripts\test_same_person_variance.py
```
- Default 3 captures
- Slight variations (turn head, change expression)
- **Empty background behind you**
- Report ALL pairwise distances verbatim

### 2. Different-Person Test
```bash
python scripts\test_different_person.py
```
- Choose Mode 3 (webcam + photos)
- Capture Person A from webcam (**empty background**)
- Place 2 clean single-subject photos in test_images/
- Report ALL pairwise distances verbatim

### What to Report:

**From test_same_person_variance.py:**
```
Capture 1 vs Capture 2: 0.XXXXXX
Capture 1 vs Capture 3: 0.XXXXXX
Capture 2 vs Capture 3: 0.XXXXXX

Min distance: 0.XXXXXX
Max distance: 0.XXXXXX
Mean distance: 0.XXXXXX
Std deviation: 0.XXXXXX

✓ or ✗ All same-person distances < threshold
```

**From test_different_person.py:**
```
person_A vs person_B: 0.XXXXXX
person_A vs person_C: 0.XXXXXX
person_B vs person_C: 0.XXXXXX

Min distance: 0.XXXXXX
Max distance: 0.XXXXXX
Mean distance: 0.XXXXXX

✓ or ✗ All different-person pairs >= threshold
✓ or ✗ False positive check passed
```

**Also report for EACH image:**
```
InsightFace detected N face(s)
Selected face X for comparison
```

If any image shows "detected 2+ faces", it's not clean enough - crop tighter or retake.

## Crowded Photos - Save for Later

Keep the original crowded classroom photos as:
- `robot_assistant\data\test_images\crowded\` (create this directory)
- person_A_crowded.jpg, image1_crowded.jpg, image2_crowded.jpg

**Future test (Task 3.7 or later):**
"Face selection in crowds" - test whether face selection correctly picks the tracked person when multiple faces are present. This is important for classroom scenarios but must be validated AFTER we trust the core embedding separation.

## Goal

**Separate concerns:**
1. **Now:** Test embedding separation with clean single-subject images (zero ambiguity)
2. **Later:** Test face selection robustness with crowded scenes (deliberate ambiguity)

Once we have clean single-subject results, we can calculate the evidence-based threshold with confidence.
