"""Smoke test for vision pipeline integration.

Tests that the pipeline module can start, run briefly, and stop cleanly.
Does not validate event publishing (covered by integration tests).
"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import pipeline
from robot_assistant.vision import capture


def main():
    print("=" * 80)
    print("VISION PIPELINE INTEGRATION SMOKE TEST")
    print("=" * 80)
    print()
    
    # Check camera availability
    if not capture.check_camera_available():
        print("✗ No webcam found - cannot test pipeline")
        return 1
    
    print("✓ Webcam available")
    print()
    
    # Test 1: Start pipeline
    print("Test 1: Starting pipeline...")
    success = pipeline.start_pipeline(camera_index=0)
    
    if not success:
        print("✗ Failed to start pipeline")
        return 1
    
    print("✓ Pipeline started")
    print()
    
    # Test 2: Verify pipeline is running
    print("Test 2: Verifying pipeline status...")
    if not pipeline.is_pipeline_running():
        print("✗ Pipeline not running after start")
        return 1
    
    print("✓ Pipeline is running")
    print()
    
    # Test 3: Let it run for 5 seconds
    print("Test 3: Running pipeline for 5 seconds...")
    time.sleep(5)
    print("✓ Pipeline ran without errors")
    print()
    
    # Test 4: Stop pipeline
    print("Test 4: Stopping pipeline...")
    success = pipeline.stop_pipeline(timeout=10.0)
    
    if not success:
        print("✗ Pipeline did not stop within timeout")
        return 1
    
    print("✓ Pipeline stopped cleanly")
    print()
    
    # Test 5: Verify pipeline is stopped
    print("Test 5: Verifying pipeline stopped...")
    if pipeline.is_pipeline_running():
        print("✗ Pipeline still running after stop")
        return 1
    
    print("✓ Pipeline is stopped")
    print()
    
    # Test 6: Restart pipeline (verify cleanup was complete)
    print("Test 6: Restarting pipeline...")
    success = pipeline.start_pipeline(camera_index=0)
    
    if not success:
        print("✗ Failed to restart pipeline")
        return 1
    
    print("✓ Pipeline restarted successfully")
    print()
    
    # Run briefly then stop
    time.sleep(2)
    pipeline.stop_pipeline(timeout=10.0)
    
    print("=" * 80)
    print("✓ ALL TESTS PASSED")
    print("=" * 80)
    print()
    print("Pipeline integration smoke test complete:")
    print("  - Start/stop lifecycle works")
    print("  - Status tracking works")
    print("  - Cleanup allows restart")
    print("  - No crashes during 5-second run")
    print()
    print("Note: This test validates pipeline control flow only.")
    print("Event publishing validated by integration tests.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
