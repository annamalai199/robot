"""Test to confirm if first-run model loading causes the timeout.

Compares stop timing on:
1. First run (when InsightFace models may need to load)
2. Second run (models already cached in memory)
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import pipeline
from robot_assistant.vision import capture


def test_stop_timing(test_name: str, run_duration: float = 2.0):
    """Test stop timing for one cycle."""
    print(f"\n{test_name}")
    print("-" * 60)
    
    if not pipeline.start_pipeline(camera_index=0):
        print("✗ Failed to start pipeline")
        return None
    
    print(f"Running for {run_duration}s...")
    time.sleep(run_duration)
    
    print("Stopping...")
    stop_start = time.time()
    success = pipeline.stop_pipeline(timeout=15.0)
    stop_time = time.time() - stop_start
    
    if success:
        print(f"✓ Stopped in {stop_time:.3f}s")
    else:
        print(f"✗ Did NOT stop within timeout (took {stop_time:.3f}s)")
    
    return stop_time if success else None


def main():
    print("=" * 80)
    print("FIRST RUN VS SUBSEQUENT RUN TIMING TEST")
    print("=" * 80)
    print()
    print("Hypothesis: First run is slow due to InsightFace model loading")
    print("            Subsequent runs are fast (models cached)")
    print()
    
    if not capture.check_camera_available():
        print("✗ No webcam found")
        return 1
    
    # Test 1: First run (may trigger model loading)
    time1 = test_stop_timing("TEST 1: First run (models may load)", run_duration=2.0)
    
    # Brief pause
    time.sleep(1)
    
    # Test 2: Second run (models should be cached)
    time2 = test_stop_timing("TEST 2: Second run (models cached)", run_duration=2.0)
    
    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if time1 and time2:
        print(f"\nFirst run stop time:  {time1:.3f}s")
        print(f"Second run stop time: {time2:.3f}s")
        print(f"Difference: {time1 - time2:.3f}s")
        print()
        
        if time1 > 5.0 and time2 < 1.0:
            print("✓ CONFIRMED: First run is slow, subsequent runs are fast")
            print("  → This is expected behavior (one-time model initialization)")
            print("  → Not a pipeline stop issue, just model loading cost")
        elif time1 < 1.0 and time2 < 1.0:
            print("✓ Both runs fast - models were already loaded before test")
            print("  → Pipeline stop works correctly")
        else:
            print("⚠ Unexpected timing pattern")
            print(f"  → Expected: first run slow (>5s), second run fast (<1s)")
            print(f"  → Actual: first={time1:.3f}s, second={time2:.3f}s")
        
        return 0
    else:
        print("\n✗ One or more runs failed to stop within timeout")
        return 1


if __name__ == '__main__':
    sys.exit(main())
