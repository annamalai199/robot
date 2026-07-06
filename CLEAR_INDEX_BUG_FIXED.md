# clear_index() Bug - Third Occurrence, Finally Fixed

## Bug Evidence (Third Time!)

**Symptoms observed:**
1. person_A (FIRST image after "Clearing FAISS index...") showed status="registered_unknown" instead of "new"
   - A cleared index cannot produce a match on the first image
   - Proof the index was NOT actually cleared

2. WIN_10_58_33_Pro assigned ID "U0001" - the SAME ID person_A already had
   - Two different people cannot share an ID
   - Proves the ID counter restarted but stale data remained

3. Distance mismatches between identify_face() and pairwise comparison
   - identify_face() matched against stale/wrong entries
   - Pairwise comparison (bypassing FAISS) showed real distances

## Root Cause (Confirmed)

**Old clear_index() implementation:**
```python
def clear_index():
    global _face_index, _id_mapping, _next_embedding_id
    
    if _face_index is not None:  # ← BUG: does nothing if None!
        _face_index = faiss.IndexFlatL2(512)
        _id_mapping = {}
        _next_embedding_id = 1
        _save_face_index()
```

**What was wrong:**
1. Only ran if `_face_index is not None` - did NOTHING if index wasn't loaded yet
2. Reset in-memory state ✓
3. Reset ID counter ✓
4. Saved new empty index ✓
5. **BUT did NOT delete the old files from disk** ✗

**Failure scenario:**
```
1. clear_index() called → resets memory, saves empty index
2. Script continues processing
3. _get_face_index() called → LOADS FROM DISK
4. Disk still has old .index and .json files
5. Stale data comes back into memory
6. First new face matches stale entry → "registered_unknown"
7. ID counter at 1 assigns "U0001" again → duplicate ID
```

## Fix Applied

**New clear_index() implementation:**
```python
def clear_index():
    global _face_index, _id_mapping, _next_embedding_id
    
    # Reset in-memory state (always, not conditional)
    _face_index = faiss.IndexFlatL2(512)
    _id_mapping = {}
    _next_embedding_id = 1
    
    # DELETE files from disk to prevent reload of stale data
    index_path = config.FAISS_FACE_INDEX_PATH
    mapping_path = config.FACE_ID_MAPPING_PATH
    
    if index_path.exists():
        index_path.unlink()  # ← NEW: Delete file
    
    if mapping_path.exists():
        mapping_path.unlink()  # ← NEW: Delete file
    
    # Save new empty index to disk
    _save_face_index()
```

**What's fixed:**
1. ✓ Unconditional reset (no `if _face_index is not None`)
2. ✓ Explicitly deletes index file from disk
3. ✓ Explicitly deletes mapping file from disk
4. ✓ Saves new empty index
5. ✓ Next reload gets empty index, not stale data

## Regression Test Added

**scripts/test_clear_index_regression.py**

This test was MISSING every time the bug resurfaced. It:
1. Adds dummy face to index
2. Verifies files exist on disk
3. Calls clear_index()
4. **Simulates fresh process by forcing reload from disk** ← CRITICAL
5. Asserts reloaded index size = 0

**Test result:** ✓ PASSED

This test must be run whenever clear_index() behavior changes.

## Why This Bug Kept Recurring

**Previous "fixes" only tested in-memory state:**
- Checked `_face_index.ntotal == 0` immediately after clear_index()
- Did NOT simulate reload from disk (fresh process start)
- In-memory state was correct, but disk files remained
- Bug only manifested on next load

**The missing test:** Reload from disk after clearing.

## Impact on Validation Tests

**All previous distance measurements are suspect:**
- identify_face() was matching against wrong/stale embeddings
- Reported distances were contaminated
- Pairwise distances (bypassing FAISS) were correct

**Encouraging sign:** 
Pairwise distances showed real separation:
- Same-person: 0.72-0.81
- Different-person: 1.22-1.34

These are trustworthy (direct embedding comparison, no FAISS contamination).

## Next Steps

**With bug FIXED:**

1. Re-run test_same_person_variance.py
   - Report all pairwise distances
   
2. Re-run test_different_person.py  
   - Report all pairwise distances
   
3. **Critical check:** Does identify_face()'s internal distance now MATCH the pairwise distance for the same pair?
   - Before fix: contradiction (0.417 vs 1.443)
   - After fix: should converge to same value
   
4. If distances converge and gap holds (same ~0.7-0.8, different ~1.2-1.3):
   - Evidence for threshold around 1.0
   - Final calculation: threshold = (max_same + min_diff) / 2

## Status

**Bug: FIXED**
**Regression test: ADDED and PASSING**
**Validation: NEEDS RE-RUN with clean index**

Ready to get trustworthy distance measurements.
