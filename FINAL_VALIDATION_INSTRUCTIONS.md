# Final Validation Instructions - Bug Fixed, Ready for Clean Test

## Status: clear_index() Bug FIXED ✓

**What was wrong:**
- clear_index() reset memory but didn't delete disk files
- Next load brought back stale data
- Caused: duplicate IDs, wrong status, distance contamination

**What was fixed:**
- Now explicitly deletes .index and .json files from disk
- Regression test added and passing
- Prevents reload of stale data

## Ready to Run Final Validation

### Prerequisites

1. ✓ Shared face selection function in place
2. ✓ clear_index() bug fixed and tested
3. ✓ Clean single-subject images ready (1 face per image)

### Test Sequence

#### 1. Same-Person Variance Test

```bash
python scripts\test_same_person_variance.py
```

**What to capture:**
- 3+ captures of same person
- Slight variations (head turn, expression, distance)
- **Empty/simple background** (no other people visible)

**What to report verbatim:**
```
Capture 1 vs Capture 2: X.XXXXXX
Capture 1 vs Capture 3: X.XXXXXX
Capture 2 vs Capture 3: X.XXXXXX

Min distance: X.XXXXXX
Max distance: X.XXXXXX
Mean distance: X.XXXXXX
Std deviation: X.XXXXXX
```

#### 2. Different-Person Test

```bash
python scripts\test_different_person.py
```

**Mode 3 setup:**
- Capture Person A from webcam (empty background)
- Place 2 clean single-subject photos in test_images/
- Each image should show "InsightFace detected 1 face(s)"

**What to report verbatim:**
```
person_A vs person_B: X.XXXXXX
person_A vs person_C: X.XXXXXX
person_B vs person_C: X.XXXXXX

Min distance: X.XXXXXX
Max distance: X.XXXXXX
Mean distance: X.XXXXXX
```

### Critical Verification

**The key check that proves the bug is fixed:**

For any pair (e.g., person_A vs image1):
1. identify_face() reports internal distance via confidence
   - Example: confidence=0.4791 → distance = (1-0.4791)*0.8 = 0.417
2. Pairwise table reports direct distance
   - Example: "person_A vs image1: 1.443"

**Before fix:** These contradicted (0.417 vs 1.443)
**After fix:** These should MATCH (same distance both ways)

**Report for each pair:**
- identify_face() internal distance (from confidence)
- Pairwise table distance
- Do they match? (within 0.01 tolerance)

### Expected Results

Based on previous pairwise data (which bypassed broken FAISS):
- Same-person range: ~0.72-0.81
- Different-person range: ~1.22-1.34
- Clear separation: min_different > max_same

**If this holds:**
- Evidence-based threshold ≈ (0.81 + 1.22) / 2 = **1.015** (round to 1.0)
- Current threshold of 0.8 is TOO TIGHT (would cause false negatives)

### Threshold Calculation Formula

Once we have both datasets:

```
max_same_person = max(same-person distances)
min_different_person = min(different-person distances)

if min_different_person > max_same_person:
    # Clean separation
    threshold = (max_same_person + min_different_person) / 2
    margin = min_different_person - threshold
    
    print(f"Recommended threshold: {threshold:.2f}")
    print(f"Safety margin: {margin:.2f}")
else:
    # Overlap case
    print("WARNING: Same-person and different-person ranges overlap")
    print("Need to choose tradeoff between false positives/negatives")
```

### What Success Looks Like

1. ✓ All images show "1 face detected"
2. ✓ identify_face() distances match pairwise distances
3. ✓ Same-person distances clustered in narrow range
4. ✓ Different-person distances clearly separated
5. ✓ No duplicate IDs assigned
6. ✓ First image shows status="new" (not "registered_unknown")

### Files to Report

Paste complete terminal output from:
1. test_same_person_variance.py
2. test_different_person.py

Include all logged information:
- Face detection counts
- Selected face indices
- All distances
- Statistics
- Pass/fail checks

## After Validation

Once we have converging distances and confirmed separation:

1. Calculate final threshold from formula
2. Update config.FACE_MATCH_THRESHOLD
3. Update test assertions to match validated threshold
4. Document rationale in config.py comments
5. Mark Task 3.6 complete

Ready to run when you are!
