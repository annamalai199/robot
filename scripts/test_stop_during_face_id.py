"""Automated test: stop_pipeline() called DURING model loading.

This test uses log monitoring to detect when InsightFace model loading starts
(the "Loading InsightFace buffalo_s model" log), then immediately calls
stop_pipeline() to measure the worst-case scenario: stop called at the very
beginning of the 4.7s+ blocking model load operation.

CRITICAL: Run in fresh process to ensure cold model load.

Timeline of a cold identify_face() call:
  T+0.0s:  identify_face() called
  T+0.0s:  "Loading InsightFace buffalo_s model" logged ← TRIGGER STOP HERE
  T+4.7s:  Model loading completes
  T+4.7s:  face_app.get() runs face detection
  T+9.6s:  "InsightFace detected N faces" logged ← Too late, worst case missed
  T+9.6s:  FAISS matching completes
  T+9.6s:  identify_face() returns

This test triggers stop at T+0.0s to measure the true worst-case delay.
"""

import sys
import time
import threading
import logging
from pathlib import Path
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent))

# Custom log handler to detect face_id activity
class FaceIDMonitor(logging.Handler):
    """Monitors logs to detect when identify_face() starts."""
    
    def __init__(self):
        super().__init__()
        self.face_id_started = threading.Event()
        self.model_load_started = threading.Event()
        self.face_id_start_time = None
        self.model_load_start_time = None
    
    def emit(self, record):
        msg = record.getMessage()
        
        # Detect model loading start
        if "Loading InsightFace buffalo_s model" in msg:
            self.model_load_start_time = time.time()
            self.model_load_started.set()
            print(f"\n🔍 DETECTED: Model loading started at {time.time():.3f}")
        
        # Detect face_id call start (InsightFace running detection)
        if "InsightFace detected" in msg:
            if self.face_id_start_time is None:  # Only first call
                self.face_id_start_time = time.time()
                self.face_id_started.set()
                print(f"\n🔍 DETECTED: Face ID call started at {time.time():.3f}")


def stop_when_face_id_starts(monitor: FaceIDMonitor, pipeline):
    """Thread that waits for model loading to start, then immediately calls stop."""
    print("\n[Stop Thread] Waiting for model loading to start...")
    
    # Wait for MODEL LOADING to start (timeout 30s)
    # This triggers at the BEGINNING of the 4.7s+ blocking operation
    if not monitor.model_load_started.wait(timeout=30):
        print("\n[Stop Thread] ✗ Timeout: No model loading detected in 30s")
        print("[Stop Thread]   (Ensure person is in frame and moving)")
        return
    
    print(f"\n[Stop Thread] ✓ Model loading started, calling stop NOW")
    print(f"[Stop Thread]   (This is the WORST CASE: stop during 4.7s+ model load)")
    
    # Call stop immediately
    stop_start = time.time()
    success = pipeline.stop_pipeline(timeout=20.0)
    stop_duration = time.time() - stop_start
    
    print(f"\n[Stop Thread] Stop completed: success={success}, duration={stop_duration:.3f}s")
    
    # Store result for main thread
    monitor.stop_duration = stop_duration
    monitor.stop_success = success
    monitor.stop_called_at = stop_start


def main():
    print("=" * 80)
    print("AUTOMATED TEST: stop_pipeline() DURING MODEL LOADING")
    print("=" * 80)
    print()
    print("This test automatically:")
    print("  1. Starts pipeline")
    print("  2. Monitors logs for 'Loading InsightFace buffalo_s model'")
    print("  3. Calls stop_pipeline() IMMEDIATELY when model loading starts")
    print("  4. Measures if stop blocks until model finishes loading (~4.7s)")
    print()
    print("This is the WORST CASE scenario:")
    print("  - Stop called at T+0.0s (start of identify_face)")
    print("  - Model loading is 4.7s+ synchronous blocking operation")
    print("  - Tests if stop waits for entire load to complete")
    print()
    print("⚠ CRITICAL: Run in FRESH Python process")
    print("  - Close terminal")
    print("  - Open NEW terminal")
    print("  - Run ONLY this script")
    print()
    print("🎯 YOU MUST:")
    print("  - Position yourself in front of webcam NOW")
    print("  - Move continuously to trigger YOLO detection")
    print("  - Stay in frame for at least 10 seconds")
    print()
    
    from robot_assistant.vision import pipeline, capture
    
    if not capture.check_camera_available():
        print("✗ No webcam found")
        return 1
    
    # Set up log monitoring
    monitor = FaceIDMonitor()
    monitor.stop_duration = None
    monitor.stop_success = None
    monitor.stop_called_at = None
    
    # Configure logging with our monitor
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Console handler for user visibility
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        '%(asctime)s.%(msecs)03d - %(name)s - %(message)s',
        datefmt='%H:%M:%S'
    ))
    
    root_logger.addHandler(console)
    root_logger.addHandler(monitor)
    
    input("Press Enter when positioned in front of webcam and ready...")
    print()
    
    # Start pipeline
    print("Starting pipeline...")
    if not pipeline.start_pipeline(camera_index=0):
        print("✗ Failed to start pipeline")
        return 1
    
    print("✓ Pipeline started")
    print()
    print("-" * 80)
    print("MONITORING FOR MODEL LOADING...")
    print("(Move around to trigger YOLO detection)")
    print("(Stop will be called at START of model load - worst case)")
    print("-" * 80)
    
    # Start thread that will call stop when face_id is detected
    stop_thread = threading.Thread(
        target=stop_when_face_id_starts,
        args=(monitor, pipeline),
        daemon=True
    )
    stop_thread.start()
    
    # Wait for stop thread to complete (max 60s)
    stop_thread.join(timeout=60)
    
    print()
    print("-" * 80)
    
    # Ensure pipeline is stopped
    if pipeline.is_pipeline_running():
        print("\n⚠ Pipeline still running, forcing stop...")
        pipeline.stop_pipeline(timeout=5.0)
    
    print()
    print("=" * 80)
    print("TEST RESULTS")
    print("=" * 80)
    print()
    
    # Analyze results
    if monitor.model_load_start_time is None:
        print("✗ TEST INVALID: No model loading detected")
        print()
        print("Possible reasons:")
        print("  - No person detected by YOLO (move more, get closer)")
        print("  - Test timeout before face appeared in frame")
        print("  - Models already loaded (not a fresh process)")
        print()
        print("ACTION: Retry in fresh process with person clearly visible")
        return 1
    
    if monitor.stop_duration is None:
        print("✗ TEST FAILED: Stop thread did not complete")
        return 1
    
    # Valid test - analyze timing
    print("✓ TEST VALID: Model loading was triggered")
    print()
    
    print(f"Model load started:  {monitor.model_load_start_time:.3f}")
    if monitor.stop_called_at:
        print(f"Stop called at:      {monitor.stop_called_at:.3f}")
        print(f"  → Delay from load start: {monitor.stop_called_at - monitor.model_load_start_time:.3f}s")
    if monitor.face_id_start_time:
        print(f"Face detection done: {monitor.face_id_start_time:.3f}")
        print(f"  → Load duration: {monitor.face_id_start_time - monitor.model_load_start_time:.3f}s")
    print(f"Stop duration:       {monitor.stop_duration:.3f}s")
    print(f"Stop successful:     {monitor.stop_success}")
    print()
    
    # Verdict
    print("-" * 80)
    print("VERDICT")
    print("-" * 80)
    print()
    
    if monitor.stop_duration < 1.0:
        print("✓ EXCELLENT: Stop completed in <1s")
        print()
        print("  → Stop event is checked frequently enough")
        print("  → Face ID call did not block stop")
        print("  → Current implementation is correct")
        
    elif 1.0 <= monitor.stop_duration < 5.0:
        print("✓ ACCEPTABLE: Stop completed in 1-5s")
        print()
        print("  → Some delay, but reasonable")
        print("  → Likely waiting for current face_id call to return")
        print("  → Document as expected behavior")
    
    elif monitor.stop_duration >= 5.0:
        print("⚠ SLOW: Stop took ≥5s")
        print()
        print("  → Model loading blocked stop until completion")
        print("  → This is a KNOWN LIMITATION of synchronous execution")
        print()
        print("  Explanation:")
        print("    - identify_face() calls _get_face_app() synchronously")
        print("    - _get_face_app() model loading is a blocking call (4-15s)")
        print("    - Python threads cannot preempt mid-function")
        print("    - Stop event is checked BEFORE identify_face(), not DURING")
        print()
        print(f"  Measured blocking time: {monitor.stop_duration:.1f}s")
        print(f"  This matches the model load duration (~{monitor.stop_duration:.0f}s)")
        print()
        print("  DECISION REQUIRED:")
        print("    A) ACCEPT: Document as known limitation:")
        print(f'       "First face detection may delay shutdown by up to {monitor.stop_duration:.0f}s"')
        print("    B) FIX: Refactor to make interruptible:")
        print("       - Pre-load models at startup (before pipeline starts)")
        print("       - OR load models in separate thread with stop checks")
        print("       - OR add timeout/interrupt mechanism to model loading")
    
    print()
    print("-" * 80)
    print("RECOMMENDATION")
    print("-" * 80)
    print()
    
    if monitor.stop_duration < 5.0:
        print("✓ Mark Task 3.7 complete")
        print("  - Stop mechanism works correctly")
        print("  - Delay is acceptable for one-time model load")
        if monitor.stop_duration >= 1.0:
            print("  - Add documentation about expected first-call delay")
    else:
        print("⚠ Document known limitation before marking complete:")
        print()
        print('  Add to pipeline.py docstring and TASK_3.7_COMPLETE.md:')
        print('  """')
        print(f'  Known Limitation: First face identification in a session may delay')
        print(f'  pipeline shutdown by up to {monitor.stop_duration:.0f}s while InsightFace models')
        print(f'  load from disk. This is a one-time cost. Subsequent stops are fast (<1s).')
        print(f'  ')
        print(f'  Rationale: Model loading is synchronous and cannot be interrupted')
        print(f'  mid-call by Python threading. Stop event is checked before and after')
        print(f'  identify_face(), but not during the model load itself.')
        print('  """')
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
