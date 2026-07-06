# Task 3.6: Face ID Confidence Investigation

## Issue
Real-time smoke test revealed LOW confidence values (0.22-0.35) for genuine same-person matches, and one FALSE NEGATIVE (same person registered as different face).

## Test Results

### Smoke Test Run (Same Person, 4 Identifications)
1. **Run #1**: status='new', embedding_id='U0001', confidence=None
2. **Run #2**: status='registered_unknown', embedding_id='U0001', **confidence=0.35**
   - ✓ Correctly matched to U0001
   - ✗ Low confidence (expected >0.8)
3. **Run #3**: status='new', embedding_id='U0002', confidence=None
   - ✗ **FALSE NEGATIVE**: Should have matched U0001 but created new face!
   - Reason: L2 distance exceeded threshold (0.6)
4. **Run #4**: status='registered_unknown', embedding_id='U0001', **confidence=0.08**
   - ✓ Matched back to U0001
   - ✗ Very low confidence (distance ≈ 0.55, just under 0.6 threshold)

## Root Cause Analysis

### Confidence Formula
```python
confidence = max(0.0, 1.0 - (distance / FACE_MATCH_THRESHOLD))
```
With `FACE_MATCH_THRESHOLD = 0.6`:
- distance = 0.0 → confidence = 1.0 (perfect)
- distance = 0.3 → confidence = 0.5
- distance = 0.39 → confidence = 0.35 (run #2)
- distance = 0.55 → confidence = 0.08 (run #4)
- distance = 0.6 → confidence = 0.0 (threshold)
- distance > 0.6 → NO MATCH (run #3 false negative)

### Expected L2 Distance Ranges (Normalized Embeddings)
Based on InsightFace/ArcFace literature:
- **Same person, same photo**: 0.0 - 0.1
- **Same person, different pose/lighting**: 0.2 - 0.5
- **Different person**: 0.6 - 1.5+

### Actual Observed Distances
- Run #2: ~0.39 (same person, slight variation)
- Run #3: >0.6 (same person, but exceeded threshold!)
- Run #4: ~0.55 (same person, barely under threshold)

## Problem Diagnosis

**The threshold of 0.6 is TOO STRICT for real-world face recognition with varying conditions.**

1. **False Negative in Run #3**: Same person with changed angle/lighting exceeded threshold, creating duplicate identity
2. **Low Confidence Values**: Distances of 0.35-0.55 are NORMAL for same-person with pose variation, but formula treats them as low confidence
3. **Threshold vs Reality Gap**: Design doc assumed 0.6 threshold, but real testing shows same-person can easily exceed this with head rotation, different lighting, or distance from camera

## Recommendations

### Option 1: Increase Threshold (Recommended)
**Increase `FACE_MATCH_THRESHOLD` from 0.6 to 0.8**

Rationale:
- Accommodates real-world pose/lighting variance
- Reduces false negatives (failing to recognize same person)
- Confidence formula automatically adjusts:
  - distance = 0.4 → confidence = 0.5 (reasonable)
  - distance = 0.6 → confidence = 0.25 (low but not rejected)
  - distance = 0.8 → confidence = 0.0 (threshold)

Trade-off:
- Higher risk of false positives (two different people matching)
- Acceptable for assistive robot scenario (greeting wrong person is less harmful than ignoring known person)

### Option 2: Adjust Confidence Formula Only
Keep threshold at 0.6, but use different confidence mapping:
```python
# Sigmoid-like mapping: low distances → high confidence, high distances → rapid dropoff
confidence = 1.0 / (1.0 + np.exp(10 * (distance - 0.3)))
```

Rationale:
- Gives high confidence (>0.8) for distances < 0.3
- Rapid dropoff for distances > 0.4
- Still matches up to 0.6 threshold

Trade-off:
- Doesn't fix Run #3 false negative (still rejected at >0.6)
- More complex formula

### Option 3: Two-Tier Threshold
- **Hard threshold** (reject): 0.8 (prevents false positives)
- **Confidence tier 1** (high): < 0.4
- **Confidence tier 2** (medium): 0.4 - 0.6
- **Confidence tier 3** (low): 0.6 - 0.8

## Recommendation

**Implement Option 1: Increase threshold to 0.8**

This is the simplest fix that addresses both issues:
1. Prevents Run #3 style false negatives
2. Automatically improves confidence values via formula
3. Aligns with real-world embedding distance distributions
4. Minimal code change (just config value)

## Implementation Plan

1. Change `config.FACE_MATCH_THRESHOLD` from 0.6 to 0.8
2. Re-run smoke test with same person (expect higher confidence, no false negatives)
3. Test with DIFFERENT person to verify no false positives
4. Update test assertions to expect confidence > 0.5 (instead of > 0.8) for same-person matches
5. Document threshold rationale in code comments

## Test Plan

### Same-Person Test (3+ runs)
- Expected: All match to same embedding_id
- Expected confidence: > 0.5 (varying by pose/lighting)
- No false negatives

### Different-Person Test
- Expected: Different embedding_id (no match)
- Expected: L2 distance > 0.8 (exceeds threshold)
- No false positives

## Status

**Task 3.6 BLOCKED pending threshold adjustment and re-validation.**

Do NOT mark as complete until:
1. Threshold increased to 0.8
2. Smoke test passes with 3+ same-person runs (all matching, no false negatives)
3. Different-person test confirms no false positives
4. Confidence values documented as reasonable (>0.3 for same person with variance)
