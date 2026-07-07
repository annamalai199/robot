"""Vision pipeline latency benchmark.

Measures per-stage latency (p50/p95) on recorded test video and validates
against design doc Section 8 budget targets.

Outputs:
- Console: p50/p95 vs budget for each stage
- CSV: Per-frame timing data
- Manual verification instructions for crossing segment (if two-person video)
"""

import cv2
import sys
import time
import numpy as np
import csv
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from robot_assistant.vision import motion_gate, tracker, gesture, face_id
from robot_assistant.config import config


# Latency budgets from design.md Section 8 (laptop targets, p95)
LATENCY_BUDGETS = {
    'motion_gate': 5.0,         # ms
    'detect_and_track': 50.0,   # ms (YOLO inference + ByteTrack matching combined)
    'gesture': 5.0,             # ms
    'face_id': 100.0,           # ms (one-time per identity)
}


def percentile(data, p):
    """Calculate percentile of data."""
    if not data:
        return 0.0
    return np.percentile(data, p)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Benchmark vision pipeline latency')
    parser.add_argument('video', type=str, help='Path to test video')
    parser.add_argument('--csv', type=str, default='test_results/latency_benchmark.csv',
                       help='CSV output path (default: test_results/latency_benchmark.csv)')
    
    args = parser.parse_args()
    
    video_path = Path(args.video)
    csv_path = Path(args.csv)
    
    print("=" * 80)
    print("VISION PIPELINE LATENCY BENCHMARK")
    print("=" * 80)
    print()
    print(f"Video: {video_path}")
    print(f"CSV output: {csv_path}")
    print()
    
    # Check video exists
    if not video_path.exists():
        print(f"✗ Video not found: {video_path}")
        return 1
    
    # Open video
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"✗ Failed to open video: {video_path}")
        return 1
    
    # Get video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count_total / fps
    
    print(f"Video: {width}x{height} @ {fps:.1f} FPS")
    print(f"Duration: {duration:.1f}s ({frame_count_total} frames)")
    print()
    print("-" * 80)
    print("PROCESSING...")
    print("-" * 80)
    print()
    
    # Storage for timing data
    timings = defaultdict(list)
    frame_data = []
    
    prev_frame = None
    frame_num = 0
    yolo_run_count = 0
    face_id_run_count = 0
    seen_track_ids = set()
    
    # Track detection history for crossing analysis
    detection_history = []  # [(frame_num, track_ids)]
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_num += 1
            
            # Show progress
            if frame_num % 100 == 0:
                print(f"  Frame {frame_num}/{frame_count_total} ({100*frame_num/frame_count_total:.1f}%)")
            
            frame_timing = {'frame': frame_num}
            
            # Stage 1: Motion gate
            if prev_frame is not None:
                start = time.perf_counter()
                has_motion = motion_gate.has_motion(frame, prev_frame)
                motion_time = (time.perf_counter() - start) * 1000  # ms
                
                timings['motion_gate'].append(motion_time)
                frame_timing['motion_gate_ms'] = motion_time
                frame_timing['has_motion'] = has_motion
            else:
                has_motion = True  # First frame
                frame_timing['has_motion'] = True
                frame_timing['motion_gate_ms'] = 0
            
            # Stage 2: YOLO detection + ByteTrack tracking (combined)
            # tracker.update() internally runs model.track() which performs full YOLO
            # inference followed by ByteTrack's Hungarian matching algorithm
            run_yolo = has_motion and (frame_num % config.YOLO_FRAME_INTERVAL_K == 0)
            
            if run_yolo:
                yolo_run_count += 1
                
                # Combined detect+track stage (tracker.update runs YOLO internally)
                start = time.perf_counter()
                tracked_objects = tracker.update(frame, conf_threshold=0.5)
                detect_and_track_time = (time.perf_counter() - start) * 1000
                
                timings['detect_and_track'].append(detect_and_track_time)
                frame_timing['detect_and_track_ms'] = detect_and_track_time
                frame_timing['tracks'] = len(tracked_objects)
                
                # Record track IDs for crossing analysis
                track_ids = [obj['track_id'] for obj in tracked_objects]
                detection_history.append((frame_num, track_ids))
                frame_timing['track_ids'] = ','.join(map(str, track_ids))
                
                # Stage 3: Gesture recognition
                gesture_times = []
                for obj in tracked_objects:
                    track_id = obj['track_id']
                    keypoints = obj['keypoints']
                    
                    start = time.perf_counter()
                    detected_gesture = gesture.check_gesture(keypoints, str(track_id))
                    gesture_time = (time.perf_counter() - start) * 1000
                    gesture_times.append(gesture_time)
                
                if gesture_times:
                    avg_gesture_time = sum(gesture_times) / len(gesture_times)
                    timings['gesture'].extend(gesture_times)
                    frame_timing['gesture_ms'] = avg_gesture_time
                
                # Stage 4: Face ID (new track IDs only)
                face_id_times = []
                for obj in tracked_objects:
                    track_id = obj['track_id']
                    
                    if track_id not in seen_track_ids:
                        seen_track_ids.add(track_id)
                        face_id_run_count += 1
                        
                        print(f"  [NEW TRACK] Frame {frame_num}: track_id={track_id} (first appearance)")
                        
                        bbox = obj['bbox']
                        start = time.perf_counter()
                        result = face_id.identify_face(frame, bbox, str(track_id))
                        face_id_time = (time.perf_counter() - start) * 1000
                        face_id_times.append(face_id_time)
                
                if face_id_times:
                    avg_face_id_time = sum(face_id_times) / len(face_id_times)
                    timings['face_id'].extend(face_id_times)
                    frame_timing['face_id_ms'] = avg_face_id_time
            
            frame_data.append(frame_timing)
            prev_frame = frame
    
    finally:
        cap.release()
    
    print()
    print("✓ Processing complete")
    print()
    
    # Calculate statistics
    print("=" * 80)
    print("LATENCY RESULTS")
    print("=" * 80)
    print()
    
    results = {}
    all_passed = True
    
    for stage, budget in LATENCY_BUDGETS.items():
        if stage in timings and timings[stage]:
            p50 = percentile(timings[stage], 50)
            p95 = percentile(timings[stage], 95)
            count = len(timings[stage])
            
            passed = p95 <= budget
            status = "✓ PASS" if passed else "✗ FAIL"
            
            results[stage] = {
                'p50': p50,
                'p95': p95,
                'count': count,
                'budget': budget,
                'passed': passed
            }
            
            print(f"{stage:15s} | p50: {p50:6.2f}ms | p95: {p95:6.2f}ms | budget: {budget:6.2f}ms | {status}")
            print(f"{'':15s} | (ran {count} times)")
            
            if not passed:
                all_passed = False
                print(f"{'':15s} | ⚠ EXCEEDS BUDGET by {p95 - budget:.2f}ms")
            
            print()
        else:
            print(f"{stage:15s} | (no data - stage may not have run)")
            print()
    
    # Summary
    print("-" * 80)
    print("SUMMARY")
    print("-" * 80)
    print()
    print(f"Total frames processed: {frame_num}")
    print(f"YOLO runs: {yolo_run_count}")
    print(f"Face ID runs: {face_id_run_count} (unique track IDs)")
    print()
    
    if all_passed:
        print("✓ ALL STAGES PASSED budget validation")
    else:
        print("✗ SOME STAGES FAILED budget validation")
        print("  (See above for details)")
    
    print()
    
    # Write CSV
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(csv_path, 'w', newline='') as f:
        fieldnames = ['frame', 'has_motion', 'motion_gate_ms', 'detect_and_track_ms',
                     'tracks', 'track_ids', 'gesture_ms', 'face_id_ms']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(frame_data)
    
    print(f"✓ CSV saved: {csv_path}")
    print()
    
    # Crossing segment analysis
    print("=" * 80)
    print("CROSSING SEGMENT ANALYSIS")
    print("=" * 80)
    print()
    
    # Find frames with multiple tracks
    multi_track_frames = [(f, ids) for f, ids in detection_history if len(ids) >= 2]
    
    if multi_track_frames:
        print(f"Found {len(multi_track_frames)} frames with ≥2 simultaneous tracks")
        print()
        print("MANUAL VERIFICATION REQUIRED:")
        print()
        print("1. Open the CSV file:")
        print(f"   {csv_path}")
        print()
        print("2. Look at these frame ranges (2+ tracks detected):")
        print()
        
        # Group consecutive frames
        if multi_track_frames:
            start_frame, start_ids = multi_track_frames[0]
            prev_frame = start_frame
            
            for frame, track_ids in multi_track_frames[1:] + [(None, None)]:
                if frame is None or frame > prev_frame + 10:
                    # End of segment
                    print(f"   Frames {start_frame}-{prev_frame}:")
                    print(f"     Track IDs present: check 'track_ids' column")
                    print(f"     ✓ GOOD: Same IDs throughout (e.g., '1,2' stays '1,2')")
                    print(f"     ✗ BAD: IDs swap (e.g., '1,2' becomes '2,1')")
                    print()
                    
                    if frame is not None:
                        start_frame = frame
                        start_ids = track_ids
                
                prev_frame = frame
        
        print("3. Verification checklist:")
        print("   [ ] Track IDs remain consistent during crossing")
        print("   [ ] No swaps observed (e.g., person A stays track 1)")
        print("   [ ] If swap found: note frame number and report")
        print()
        print("⚠ NOTE: This video is SINGLE-PERSON, so multiple simultaneous")
        print("  tracks are rare/unlikely. This does NOT satisfy the task's")
        print("  crossing/occlusion requirement. A two-person video is needed")
        print("  to properly validate Hungarian algorithm track assignment.")
    else:
        print("⚠ NO FRAMES with ≥2 simultaneous tracks detected")
        print()
        print("This is expected for single-person video (Option B).")
        print()
        print("TASK 3.8 INCOMPLETE:")
        print("  - Latency benchmarks: ✓ COMPLETE")
        print("  - Crossing validation: ✗ INCOMPLETE (need two-person video)")
        print()
        print("To complete Task 3.8:")
        print("  1. Record two-person video (Option A)")
        print("  2. Re-run this benchmark on that video")
        print("  3. Manually verify no track swaps during crossing")
        print("  4. Then mark task complete")
    
    print()
    print("=" * 80)
    
    # Return exit code based on budget validation
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
