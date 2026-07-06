"""Diagnostic script to investigate pipeline stop timeout issue.

Runs 3 consecutive start/stop cycles and measures:
1. Time from stop_pipeline() call to thread completion
2. Whether timeout occurs consistently or intermittently
3. Detailed per-stage timing from pipeline logs

This diagnoses the "Pipeline thread did not stop within 10.0s" warning.
"""

import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import pipeline
from robot_assistant.vision import capture

# Enable debug logging to see per-stage timing
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)


def run_cycle(cycle_num: int, run_duration: float = 3.0, stop_timeout: float = 10.0):
    """Run one start/stop cycle and measure timing."""
    print()
    print("=" * 80)
    print(f"CYCLE {cycle_num}")
    print("=" * 80)
    
    # Start pipeline
    print(f"\n[{cycle_num}] Starting pipeline...")
    start_time = time.time()
    success = pipeline.start_pipeline(camera_index=0)
    
    if not success:
        print(f"[{cycle_num}] ✗ Failed to start pipeline")
        return False
    
    startup_time = time.time() - start_time
    print(f"[{cycle_num}] ✓ Pipeline started in {startup_time:.3f}s")
    
    # Let it run
    print(f"[{cycle_num}] Running for {run_duration}s...")
    time.sleep(run_duration)
    
    # Stop pipeline
    print(f"[{cycle_num}] Stopping pipeline (timeout={stop_timeout}s)...")
    stop_start = time.time()
    success = pipeline.stop_pipeline(timeout=stop_timeout)
    stop_time = time.time() - stop_start
    
    if success:
        print(f"[{cycle_num}] ✓ Pipeline stopped in {stop_time:.3f}s")
        return True
    else:
        print(f"[{cycle_num}] ✗ Pipeline did NOT stop within {stop_timeout}s timeout")
        print(f"[{cycle_num}]   Actual time elapsed: {stop_time:.3f}s")
        return False


def main():
    print("=" * 80)
    print("PIPELINE STOP TIMING DIAGNOSTIC")
    print("=" * 80)
    print()
    print("This test runs 3 consecutive start/stop cycles to diagnose")
    print("the 'Pipeline thread did not stop within 10.0s' warning.")
    print()
    print("Each cycle:")
    print("  1. Start pipeline")
    print("  2. Run for 3 seconds")
    print("  3. Stop with 10-second timeout")
    print("  4. Measure actual stop time")
    print()
    print("Watch the debug logs for per-stage timing (motion, YOLO, tracker, etc.)")
    print()
    
    # Check camera availability
    if not capture.check_camera_available():
        print("✗ No webcam found - cannot test pipeline")
        return 1
    
    print("✓ Webcam available")
    
    # Run 3 cycles
    results = []
    for i in range(1, 4):
        success = run_cycle(i, run_duration=3.0, stop_timeout=10.0)
        results.append(success)
        
        # Brief pause between cycles
        if i < 3:
            print(f"\nPausing 2 seconds before next cycle...")
            time.sleep(2)
    
    # Summary
    print()
    print("=" * 80)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 80)
    print()
    
    success_count = sum(results)
    print(f"Cycles completed within timeout: {success_count}/3")
    print()
    
    if success_count == 3:
        print("✓ ALL CYCLES stopped within timeout")
        print("  → Stop timeout issue appears to be resolved or was a fluke")
    elif success_count == 0:
        print("✗ ALL CYCLES exceeded timeout")
        print("  → Stop timeout issue is CONSISTENT")
        print("  → Review debug logs above for where time is spent")
        print("  → Check if stop_event is checked frequently enough")
    else:
        print("⚠ INTERMITTENT timeout issue")
        print(f"  → {3 - success_count} out of 3 cycles exceeded timeout")
        print("  → May depend on what operations are running when stop called")
        print("  → Review debug logs for differences between success/failure cases")
    
    print()
    print("Key questions to answer from logs:")
    print("  1. How often is stop_event checked? (look for 'stop signal received' logs)")
    print("  2. Where is time spent in each loop iteration? (look for 'Frame X total' logs)")
    print("  3. Does face_id call time exceed reasonable bounds? (look for 'face_id call' logs)")
    print("  4. Are there long gaps between loop iterations?")
    
    return 0 if success_count == 3 else 1


if __name__ == '__main__':
    sys.exit(main())
