"""Profile detect_and_track timing variance and identify bottlenecks.

Runs tracker.update() multiple times on same video frames to isolate:
1. System load variance (CPU usage, thermal throttling)
2. Model initialization overhead
3. Frame-specific complexity variance
"""

import sys
import cv2
import time
import psutil
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import tracker
from robot_assistant.config import config


def get_system_metrics():
    """Get current system metrics."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_freq = psutil.cpu_freq()
    memory = psutil.virtual_memory()
    
    return {
        'cpu_percent': cpu_percent,
        'cpu_freq_current': cpu_freq.current if cpu_freq else 0,
        'cpu_freq_max': cpu_freq.max if cpu_freq else 0,
        'memory_percent': memory.percent
    }


def main():
    video_path = 'test_videos/two_person_crossing.mp4'
    
    print("=" * 80)
    print("DETECT-AND-TRACK PROFILING")
    print("=" * 80)
    print()
    
    # Get initial system state
    print("System State:")
    metrics = get_system_metrics()
    print(f"  CPU usage: {metrics['cpu_percent']:.1f}%")
    print(f"  CPU frequency: {metrics['cpu_freq_current']:.0f}/{metrics['cpu_freq_max']:.0f} MHz")
    print(f"  Memory usage: {metrics['memory_percent']:.1f}%")
    print()
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    
    # Extract 10 frames at YOLO intervals
    test_frames = []
    frame_nums = []
    frame_count = 0
    
    print("Extracting test frames...")
    while len(test_frames) < 10:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        if frame_count % config.YOLO_FRAME_INTERVAL_K == 0:
            test_frames.append(frame.copy())
            frame_nums.append(frame_count)
    
    cap.release()
    
    print(f"Extracted {len(test_frames)} frames: {frame_nums}")
    print()
    
    # Warm up model (first call loads model)
    print("Warming up model (first call)...")
    start = time.perf_counter()
    _ = tracker.update(test_frames[0], conf_threshold=0.5)
    warmup_time = (time.perf_counter() - start) * 1000
    print(f"  Warmup time: {warmup_time:.1f}ms")
    print()
    
    # Run 5 passes over the same frames
    print("Running 5 passes over same 10 frames...")
    print()
    
    all_timings = []
    
    for pass_num in range(1, 6):
        print(f"Pass {pass_num}:")
        
        # Get system metrics before pass
        metrics_before = get_system_metrics()
        
        pass_timings = []
        
        for i, (frame, frame_num) in enumerate(zip(test_frames, frame_nums)):
            start = time.perf_counter()
            tracked = tracker.update(frame, conf_threshold=0.5)
            elapsed = (time.perf_counter() - start) * 1000
            
            pass_timings.append(elapsed)
            all_timings.append({
                'pass': pass_num,
                'frame_num': frame_num,
                'time_ms': elapsed,
                'detections': len(tracked)
            })
        
        # Get system metrics after pass
        metrics_after = get_system_metrics()
        
        p50 = np.percentile(pass_timings, 50)
        p95 = np.percentile(pass_timings, 95)
        
        print(f"  p50: {p50:.1f}ms, p95: {p95:.1f}ms")
        print(f"  CPU before: {metrics_before['cpu_percent']:.1f}%, after: {metrics_after['cpu_percent']:.1f}%")
        print(f"  CPU freq before: {metrics_before['cpu_freq_current']:.0f}MHz, after: {metrics_after['cpu_freq_current']:.0f}MHz")
        print()
    
    # Analyze variance
    print("=" * 80)
    print("VARIANCE ANALYSIS")
    print("=" * 80)
    print()
    
    # Group by frame_num to see frame-specific variance
    from collections import defaultdict
    frame_timings = defaultdict(list)
    
    for timing in all_timings:
        frame_timings[timing['frame_num']].append(timing['time_ms'])
    
    print("Per-frame variance (same frame, multiple passes):")
    print()
    
    max_variance = 0
    max_variance_frame = None
    
    for frame_num in sorted(frame_timings.keys()):
        times = frame_timings[frame_num]
        min_time = min(times)
        max_time = max(times)
        variance = max_time - min_time
        variance_pct = (variance / min_time) * 100
        
        print(f"  Frame {frame_num}: {min_time:.1f}-{max_time:.1f}ms (variance: {variance:.1f}ms, {variance_pct:.0f}%)")
        
        if variance > max_variance:
            max_variance = variance
            max_variance_frame = frame_num
    
    print()
    print(f"Maximum variance: {max_variance:.1f}ms at frame {max_variance_frame}")
    print()
    
    # Check if variance is correlated with CPU metrics
    pass_stats = []
    for pass_num in range(1, 6):
        pass_times = [t['time_ms'] for t in all_timings if t['pass'] == pass_num]
        pass_stats.append({
            'pass': pass_num,
            'mean': np.mean(pass_times),
            'p50': np.percentile(pass_times, 50),
            'p95': np.percentile(pass_times, 95)
        })
    
    print("Per-pass statistics:")
    print()
    for stats in pass_stats:
        print(f"  Pass {stats['pass']}: mean={stats['mean']:.1f}ms, p50={stats['p50']:.1f}ms, p95={stats['p95']:.1f}ms")
    
    print()
    
    # Calculate overall variance across passes
    all_p50s = [stats['p50'] for stats in pass_stats]
    p50_variance = max(all_p50s) - min(all_p50s)
    p50_variance_pct = (p50_variance / min(all_p50s)) * 100
    
    print(f"p50 variance across passes: {min(all_p50s):.1f}-{max(all_p50s):.1f}ms ({p50_variance_pct:.0f}%)")
    print()
    
    # Conclusion
    print("=" * 80)
    print("FINDINGS")
    print("=" * 80)
    print()
    
    if p50_variance_pct > 30:
        print(f"✗ HIGH VARIANCE: {p50_variance_pct:.0f}% variation in p50 across passes")
        print("  Likely causes:")
        print("  - CPU thermal throttling (check freq drops)")
        print("  - Background processes competing for CPU")
        print("  - Windows scheduler variance")
        print()
        print("  Recommendation: Latency benchmarks on this hardware are unreliable")
        print("  for precise budget validation (<50ms targets). Use for regression")
        print("  detection (2x+ slowdowns) only.")
    else:
        print(f"✓ LOW VARIANCE: {p50_variance_pct:.0f}% variation in p50 across passes")
        print("  Benchmark results are reliable.")
    
    print()


if __name__ == '__main__':
    main()
