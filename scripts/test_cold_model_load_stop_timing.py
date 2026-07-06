"""Test stop timing during cold InsightFace model loading.

CRITICAL: This test must be run in a FRESH Python process with no prior
scripts run, to ensure InsightFace models are not already loaded.

Instructions:
1. Close this terminal completely
2. Open a NEW terminal
3. Run ONLY this script (no other scripts before it)
4. Position yourself clearly in front of webcam
5. Keep moving to trigger motion detection and YOLO
"""

import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Enable INFO logging to see when models load
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

from robot_assistant.vision import pipeline
from robot_assistant.vision import capture


def main():
    print("=" * 80)
    print("COLD MODEL LOAD STOP TIMING TEST")
    print("=" * 80)
    print()
    print("⚠ IMPORTANT: This test MUST be run in a FRESH Python process")
    print("  - Close terminal completely")
    print("  - Open NEW terminal")
    print("  - Run ONLY this script")
    print()
    print("This test will:")
    print("  1. Start pipeline")
    print("  2. Wait 15 seconds (enough time to detect your face)")
    print("  3. Call stop_pipeline() while model may still be loading")
    print("  4. Measure actual stop time")
    print()
    print("INSTRUCTIONS FOR YOU:")
    print("  - Position yourself clearly in front of webcam NOW")
    print("  - Keep moving during the 15-second window to trigger YOLO")
    print("  - Watch logs for 'Loading InsightFace' or 'Face identified'")
    print()
    
    if not capture.check_camera_available():
        print("✗ No webcam found")
        return 1
    
    input("Press Enter when you are positioned in front of webcam and ready...")
    print()
    
    # Start pipeline
    print("Starting pipeline...")
    if not pipeline.start_pipeline(camera_index=0):
        print("✗ Failed to start pipeline")
        return 1
    
    print("✓ Pipeline started")
    print()
    print("Running for 15 seconds...")
    print("  → Move around to trigger motion detection")
    print("  → Watch for 'Loading InsightFace' in logs below")
    print("  → Watch for 'Face identified' in logs below")
    print("-" * 80)
    
    # Run for 15 seconds - should be enough to detect face
    time.sleep(15)
    
    print()
    print("-" * 80)
    print("Calling stop_pipeline() now...")
    print("  (If InsightFace was loading, this will measure the delay)")
    print()
    
    # Stop and measure timing
    stop_start = time.time()
    success = pipeline.stop_pipeline(timeout=20.0)  # Increased timeout
    stop_time = time.time() - stop_start
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    
    if success:
        print(f"✓ Pipeline stopped in {stop_time:.3f}s")
    else:
        print(f"✗ Pipeline did NOT stop within 20s timeout")
        print(f"  Actual time: {stop_time:.3f}s")
    
    print()
    print("ANALYSIS QUESTIONS:")
    print("1. Did you see 'Loading InsightFace buffalo_s model' in logs above?")
    print("   → If YES: The model had to load from disk (cold start)")
    print("   → If NO: Model was already cached (invalid test)")
    print()
    print("2. Did you see 'Face identified for track N' in logs above?")
    print("   → If YES: Face ID was triggered, test is valid")
    print("   → If NO: You may not have been detected by YOLO")
    print()
    print("3. What was the stop time?")
    print(f"   → Measured: {stop_time:.3f}s")
    print("   → If <1s AND model loaded: stop_event checked during loading ✓")
    print("   → If >5s AND model loaded: stop_event NOT checked during loading ✗")
    print()
    
    # Check if test was valid
    print("VALIDITY CHECK:")
    print("  - If NO model loading log: Run in FRESH process (close terminal, reopen)")
    print("  - If NO face identified: Move more, ensure YOLO detects you")
    print("  - If BOTH appeared: Test is VALID, stop time is accurate")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
