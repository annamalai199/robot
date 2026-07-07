# Test Video Recording Plan for Task 3.8

## Purpose

Record a 60-second test video to benchmark vision pipeline latency and validate ByteTrack's Hungarian algorithm (no track ID swaps during crossing/occlusion).

## Latency Budgets (from design.md Section 8)

**Laptop Targets (what we're testing against):**

| Stage | Laptop Target (p95) | Notes |
|-------|---------------------|-------|
| Motion gate | <5ms | Frame difference |
| YOLO inference | <50ms | With laptop GPU/CPU |
| Tracker update | <5ms | ByteTrack algorithm |
| Gesture check | <5ms | Pure arithmetic |
| Face embedding | <100ms | One-time per identity |

**The benchmark will measure actual p50/p95 and FAIL if any stage's p95 exceeds its budget.**

## Test Video Requirements

### Duration
- **60 seconds total**

### Content Required
1. **1-2 people visible** (can be same person at different times, or two different people)
2. **Hand raise gesture** (at least once, clearly visible)
3. **Face clearly visible** (for face identification to trigger)
4. **CRITICAL: Crossing/Occlusion segment** (see below)

### Crossing/Occlusion Segment (MUST HAVE)

**Why this matters:**
- ByteTrack uses Hungarian algorithm for optimal detection-to-track assignment
- Greedy nearest-neighbor matching would swap IDs during crossing
- We need to validate Hungarian algorithm prevents swaps
- This cannot be automated - requires human visual verification

**What "crossing" means:**
- Two people's paths cross (walk past each other)
- OR two bounding boxes overlap (one person partially behind/in front of another)
- OR person walks out and back in (track should maintain same ID)

**Duration:**
- At least 5-10 seconds of crossing/overlap
- Need enough frames to log track IDs before/during/after crossing

## Recording Options

### Option A: Two People (REQUIRED for Task Completion)
**Scenario:** You + someone else

**Script:**
```
0:00-0:10  Both stand visible, one raises hand
0:10-0:30  Walk toward each other and cross paths (slow)
0:30-0:45  Both visible again on opposite sides
0:45-0:60  One person walks behind/in front of the other
```

**Why this is REQUIRED:**
- ByteTrack's Hungarian algorithm resolves ambiguous detection-to-track assignment
- With 2 detections and 2 tracks, algorithm must decide which detection → which track
- Greedy nearest-neighbor would swap IDs during crossing
- Hungarian algorithm uses global optimal assignment (prevents swaps)
- **This cannot be tested with only 1 person** - no ambiguity to resolve

**Status:** REQUIRED - Task 3.8 cannot be marked complete without this

### Option B: Single Person Walk-Around (Partial - Latency Only)
**Scenario:** Just you

**Script:**
```
0:00-0:10  Stand in frame, raise hand
0:10-0:20  Walk out of frame to the right
0:20-0:30  Walk back in from left (track reappears)
0:30-0:40  Walk close to camera then far (bbox size changes)
0:40-0:50  Walk diagonally across frame (bbox position shifts)
0:50-0:60  Stand still, raise hand again
```

**What this tests:**
- ✅ Motion gate latency
- ✅ YOLO inference latency
- ✅ Tracker update latency
- ✅ Gesture recognition latency
- ✅ Face identification latency
- ❌ Hungarian algorithm track assignment (NO - only 1 detection at a time)

**Use case:** 
- Unblock latency measurements while waiting for second person
- Run benchmark, get p50/p95 numbers vs budgets
- **EXPLICITLY mark in tasks.md that crossing requirement NOT SATISFIED**
- **Cannot mark Task 3.8 complete**

### Decision Logic

**If you have access to second person:**
- Record Option A immediately
- Satisfies all requirements
- Task can be marked complete after verification

**If second person not available now:**
- Can record Option B to unblock latency measurements
- Get p50/p95 data, CSV output, budget validation
- Benchmark code will work on either video
- **Mark as INCOMPLETE in tasks.md** with note: "Crossing/occlusion requirement pending - need two-person video"
- Record Option A later when second person available
- Re-run benchmark on two-person video
- Verify no track ID swaps manually
- Then mark Task 3.8 complete

## Recording Procedure

### Setup
1. **Position webcam:** Stable, wide view, good lighting
2. **Test framing:** Ensure full person visible when standing
3. **Audio cue:** Decide on start signal (e.g., count "3, 2, 1, start")

### Recording Command

We'll create a simple recording script:
```bash
python scripts/record_test_video.py --duration 60 --output test_videos/latency_benchmark_video.mp4
```

This will:
- Open webcam
- Show live preview
- Record for 60 seconds
- Save as MP4 at 30 FPS

### During Recording

**Timer callouts (for you to follow):**
- 0:00 - START (stand visible)
- 0:10 - RAISE HAND (hold 2 seconds)
- 0:15 - BEGIN CROSSING SEGMENT
- 0:25 - CROSSING COMPLETE
- 0:30 - Face camera clearly
- 0:50 - FINAL HAND RAISE
- 0:60 - STOP

### After Recording

1. **Playback check:** Watch the video, verify:
   - Full 60 seconds
   - Hand raise visible (at least once)
   - Face visible for face_id
   - Crossing/overlap segment is clear (≥5 seconds)

2. **Proceed to benchmark:** Run bench_latency.py on the video

3. **Manual ID verification:** After benchmark, review CSV logs for crossing segment

## What We'll Check

### Automated (Benchmark)
- ✅ p50/p95 latencies per stage
- ✅ Compare against budget, FAIL if exceeded
- ✅ CSV output with per-frame timings

### Manual (You Verify)
- ✅ During crossing segment (frame X to Y), check logged track_ids
- ✅ Example good log: Track 1 stays 1, Track 2 stays 2 throughout crossing
- ✅ Example bad log: Track 1 becomes 2, Track 2 becomes 1 during crossing (ID swap)

## When to Record

**I need you to record the test video BEFORE I write bench_latency.py.**

**CRITICAL DECISION:**

### If you CAN get a second person:
1. Record Option A (two people)
2. Satisfies ALL requirements including crossing/occlusion validation
3. Task 3.8 can be marked complete after benchmark + manual verification

### If you CANNOT get a second person right now:
1. Record Option B (single person) to unblock latency measurements
2. I'll write bench_latency.py to work with either video
3. Get p50/p95 vs budget data, CSV output
4. **Mark Task 3.8 as INCOMPLETE in tasks.md** with explicit note:
   ```
   Status: partial (latency benchmarks complete, crossing/occlusion 
   requirement NOT SATISFIED - single person video does not test 
   Hungarian algorithm track assignment)
   ```
5. Record Option A later when second person available
6. Re-run benchmark on two-person video
7. Verify no track swaps during crossing
8. THEN mark Task 3.8 complete

**Ready to record?** Let me know:
1. Which option you'll use (A or B)
2. If Option B: Acknowledge that Task 3.8 will be marked INCOMPLETE
3. Any questions about the requirements

I will NOT mark Task 3.8 complete based on a single-person video.
