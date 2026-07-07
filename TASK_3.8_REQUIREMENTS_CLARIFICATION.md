# Task 3.8 Requirements Clarification

## Critical Distinction: Two-Person Video is MANDATORY

### Why Single-Person Video is Insufficient

**The task acceptance criteria states:**
> "Test video MUST include segment where two people's paths cross or bboxes overlap"
> 
> "Manual validation checklist: inspect logged track_ids during crossing segment, confirm no ID swap occurred (this validates ByteTrack's Hungarian algorithm vs greedy matching)"

**What this tests:**
- ByteTrack uses **Hungarian algorithm** for optimal detection-to-track assignment
- When 2 people cross paths: 2 detections → 2 existing tracks
- **Ambiguous assignment:** Which detection corresponds to which track?
- **Greedy nearest-neighbor** would pick closest match (causes ID swaps during crossing)
- **Hungarian algorithm** solves global optimal assignment problem (prevents swaps)

**Why single-person video fails this:**
- Only 1 detection at a time = **no ambiguity**
- Tracker has no assignment problem to solve
- Cannot validate Hungarian vs greedy (no difference with N=1)
- Walk out/in tests track **persistence**, not track **assignment**

## Two-Path Approach

### Path A: Complete Task (Requires Second Person)

**Video:** Option A - Two people crossing paths

**Validation:**
1. ✅ Latency benchmarks (p50/p95 vs budgets)
2. ✅ CSV output with per-frame timings
3. ✅ Manual track ID verification during crossing
   - Example PASS: Track 1 stays 1, Track 2 stays 2 throughout
   - Example FAIL: Track 1 becomes 2, Track 2 becomes 1 (ID swap)

**Result:** Task 3.8 marked COMPLETE

### Path B: Partial Progress (Single Person)

**Video:** Option B - One person walk-around

**Validation:**
1. ✅ Latency benchmarks (p50/p95 vs budgets) - works fine
2. ✅ CSV output with per-frame timings - works fine
3. ❌ Hungarian algorithm validation - **CANNOT TEST** with N=1

**Result:** Task 3.8 marked INCOMPLETE with explicit note in tasks.md:
```markdown
**Status:** partial

**Completed:**
- [x] Latency benchmarks (motion_gate, YOLO, tracker, gesture, face_id)
- [x] CSV output with per-frame timings
- [x] Budget validation (p50/p95 vs Section 8 targets)

**Incomplete:**
- [ ] Two-person crossing/occlusion segment (single-person video recorded)
- [ ] Manual track ID swap verification (cannot validate with N=1 detections)

**Reason:** Hungarian algorithm track assignment requires ≥2 simultaneous 
detections to create ambiguity. Single-person video only ever has 1 detection, 
so there's no assignment problem to solve and no way to verify Hungarian vs 
greedy matching behavior.

**Next Steps:** Record two-person video (Option A), re-run benchmark, verify 
no track swaps during crossing, then mark complete.
```

## Recommendation

**If second person available:** Record Option A now, complete task fully.

**If second person unavailable:** 
- Record Option B to unblock latency measurements
- Get p50/p95 data for all stages
- Mark task as INCOMPLETE with clear note
- Record Option A later
- Re-run benchmark and verify
- Then mark COMPLETE

**Do NOT mark Task 3.8 complete without two-person crossing validation.**

## Summary

| Requirement | Single-Person Video | Two-Person Video |
|------------|---------------------|------------------|
| Latency benchmarks | ✅ Works | ✅ Works |
| CSV output | ✅ Works | ✅ Works |
| Budget validation | ✅ Works | ✅ Works |
| Hungarian algorithm test | ❌ Impossible | ✅ Required |
| Task completion | ❌ No | ✅ Yes |

**Single-person video is useful for partial progress but insufficient for task completion.**
