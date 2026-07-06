"""Vision pipeline integration - orchestrates all vision processing stages.

Wires together the 5-stage vision cascade:
1. Video capture (capture.py)
2. Motion gate filter (motion_gate.py)
3. YOLO pose detection every Kth frame (detector.py)
4. ByteTrack multi-person tracking (tracker.py)
5. Gesture recognition + Face ID (gesture.py, face_id.py)

Publishes events: GESTURE_DETECTED, IDENTITY_RESOLVED, TRACK_LOST
Designed to run in a separate thread/async task (non-blocking).
"""

import cv2
import logging
import time
import threading
from typing import Optional, Set
from robot_assistant.vision import capture, motion_gate, detector, tracker, gesture, face_id
from robot_assistant.config import config

logger = logging.getLogger(__name__)

# Global state for pipeline control
_pipeline_thread: Optional[threading.Thread] = None
_pipeline_running = False
_pipeline_stop_event = threading.Event()


def run_pipeline(camera_index: int = 0):
    """Run the complete vision pipeline.
    
    Orchestrates all 5 vision stages in a single processing loop:
    - Frame capture from webcam
    - Motion detection filter (skip processing if no motion)
    - YOLO pose detection every Kth frame (K from config)
    - ByteTrack tracking every frame when YOLO runs
    - Gesture recognition on all tracked persons
    - Face identification on new track IDs only
    
    Runs indefinitely until stop_pipeline() is called. Designed to run in
    a separate thread to avoid blocking main application.
    
    Stop Responsiveness:
        The stop_event is checked at 4 points in each loop iteration:
        1. Loop start (every frame)
        2. Before tracking (after YOLO completes)
        3. Before face_id stage
        4. After each face_id call (in case multiple new tracks)
        
        This ensures stop latency < 1s in normal operation.
    
    Known Limitation: If the FIRST face identification in a process
    occurs at the same moment stop_pipeline() is called, pipeline
    shutdown may be delayed by up to ~7s while InsightFace models
    finish loading from disk (measured worst case: 7.199s).
    
    Cause: _get_face_app() performs a synchronous, blocking model load
    inside identify_face(). Python threads cannot preempt a function
    mid-call, and the pipeline's stop_event is only checked before and
    after identify_face() runs, not during it.
    
    Scope: This is a one-time cost per process — only the first face
    ever detected triggers the cold load. All subsequent calls to
    identify_face() (and all subsequent stop_pipeline() calls) complete
    in <1s, since the model is already loaded in memory.
    
    This does not affect actuator safety: the hardware E-stop (Section
    4c of the architecture doc) cuts servo power independently of this
    software loop and is unaffected by pipeline shutdown timing.
    
    Args:
        camera_index: Camera device index (default: 0)
    
    Side Effects:
        - Publishes GESTURE_DETECTED events when hand raised
        - Publishes IDENTITY_RESOLVED events for new faces
        - Publishes TRACK_LOST events when tracks disappear
    
    Example:
        >>> # Start in background thread
        >>> start_pipeline()
        >>> # ... do other work ...
        >>> stop_pipeline()  # Clean shutdown
    
    Performance:
        Motion gate saves ~95% of YOLO calls on static scenes.
        YOLO runs every Kth frame (K=5 default) to balance latency and CPU.
        Face ID runs once per track_id (cached), not every frame.
    """
    logger.info("Starting vision pipeline")
    
    # Check camera availability
    if not capture.check_camera_available(camera_index):
        logger.error(f"Camera {camera_index} not available")
        raise RuntimeError(f"Camera {camera_index} not available")
    
    # Get frame generator
    frame_gen = capture.get_frame_generator(camera_index)
    
    # Pipeline state
    prev_frame = None
    frame_count = 0
    yolo_run_count = 0
    motion_detected_count = 0
    last_detections = []  # Cache detections for frames between YOLO runs
    seen_track_ids: Set[int] = set()  # Track IDs we've already run face_id on
    
    try:
        for frame in frame_gen:
            loop_start = time.time()
            
            # Check stop signal at loop start
            if _pipeline_stop_event.is_set():
                logger.info("Pipeline stop signal received at loop start")
                break
            
            frame_count += 1
            
            # Stage 1: Motion gate (skip processing on static frames)
            motion_start = time.time()
            if prev_frame is not None:
                has_motion = motion_gate.has_motion(frame, prev_frame)
                
                if has_motion:
                    motion_detected_count += 1
                else:
                    # No motion - skip YOLO/tracking/gesture/face_id
                    prev_frame = frame
                    motion_time = (time.time() - motion_start) * 1000
                    logger.debug(f"Frame {frame_count}: no motion (motion_gate: {motion_time:.1f}ms)")
                    continue
            else:
                # First frame - always process
                has_motion = True
                motion_detected_count += 1
            
            motion_time = (time.time() - motion_start) * 1000
            
            # Stage 2: YOLO pose detection (every Kth frame when motion detected)
            run_yolo = (frame_count % config.YOLO_FRAME_INTERVAL_K == 0)
            
            if run_yolo:
                yolo_start = time.time()
                yolo_run_count += 1
                detections = detector.detect_poses(frame, conf_threshold=0.5)
                last_detections = detections
                yolo_time = (time.time() - yolo_start) * 1000
                
                logger.debug(f"Frame {frame_count}: YOLO detected {len(detections)} person(s) "
                           f"(motion_gate: {motion_time:.1f}ms, YOLO: {yolo_time:.1f}ms)")
            else:
                # Use cached detections from previous YOLO run
                detections = last_detections
                yolo_time = 0
            
            # Check stop signal before expensive tracking/face_id
            if _pipeline_stop_event.is_set():
                logger.info("Pipeline stop signal received before tracking")
                break
            
            # Stage 3: ByteTrack tracking (runs every frame when we have detections)
            # Note: tracker.update() runs YOLO internally with tracking enabled
            # We need to refactor this to use our detections, but for now we call
            # tracker.update() which will run YOLO again with tracking
            if run_yolo:
                tracker_start = time.time()
                tracked_objects = tracker.update(frame, conf_threshold=0.5)
                tracker_time = (time.time() - tracker_start) * 1000
                
                logger.debug(f"Frame {frame_count}: Tracking {len(tracked_objects)} person(s) "
                           f"(tracker: {tracker_time:.1f}ms)")
                
                # Stage 4: Gesture recognition (all tracked persons)
                gesture_start = time.time()
                for obj in tracked_objects:
                    track_id = obj['track_id']
                    keypoints = obj['keypoints']
                    
                    # Check for gesture (gesture.check_gesture publishes event internally)
                    detected_gesture = gesture.check_gesture(keypoints, str(track_id))
                    
                    if detected_gesture:
                        logger.info(f"Gesture detected: {detected_gesture} from track {track_id}")
                
                gesture_time = (time.time() - gesture_start) * 1000
                
                # Check stop signal before expensive face_id
                if _pipeline_stop_event.is_set():
                    logger.info("Pipeline stop signal received before face_id")
                    break
                
                # Stage 5: Face identification (new track IDs only)
                face_id_start = time.time()
                face_id_count = 0
                for obj in tracked_objects:
                    track_id = obj['track_id']
                    
                    # Skip if we've already identified this track
                    if track_id in seen_track_ids:
                        continue
                    
                    # Mark as seen
                    seen_track_ids.add(track_id)
                    face_id_count += 1
                    
                    # Run face identification (this can be slow ~200ms)
                    bbox = obj['bbox']
                    face_id_call_start = time.time()
                    result = face_id.identify_face(frame, bbox, str(track_id))
                    face_id_call_time = (time.time() - face_id_call_start) * 1000
                    
                    if result:
                        logger.info(f"Face identified for track {track_id}: "
                                  f"embedding_id={result['embedding_id']}, "
                                  f"status={result['status']}, "
                                  f"name={result.get('name', 'N/A')} "
                                  f"(face_id call: {face_id_call_time:.1f}ms)")
                    
                    # Check stop signal after each face_id call (in case it's slow)
                    if _pipeline_stop_event.is_set():
                        logger.info(f"Pipeline stop signal received during face_id processing "
                                  f"(after {face_id_count} face_id calls)")
                        break
                
                face_id_time = (time.time() - face_id_start) * 1000
                
                loop_time = (time.time() - loop_start) * 1000
                logger.debug(f"Frame {frame_count} total: {loop_time:.1f}ms "
                           f"(motion: {motion_time:.1f}ms, YOLO: {yolo_time:.1f}ms, "
                           f"tracker: {tracker_time:.1f}ms, gesture: {gesture_time:.1f}ms, "
                           f"face_id: {face_id_time:.1f}ms for {face_id_count} new tracks)")
            
            prev_frame = frame
        
        # Pipeline stopped normally
        logger.info(f"Vision pipeline stopped after {frame_count} frames "
                   f"({yolo_run_count} YOLO runs, "
                   f"{motion_detected_count} motion detections)")
    
    except Exception as e:
        logger.error(f"Vision pipeline error: {str(e)}", exc_info=True)
        raise
    
    finally:
        # Cleanup
        cv2.destroyAllWindows()
        logger.info("Vision pipeline cleanup complete")


def start_pipeline(camera_index: int = 0) -> bool:
    """Start the vision pipeline in a background thread.
    
    Args:
        camera_index: Camera device index (default: 0)
    
    Returns:
        bool: True if pipeline started successfully, False if already running
    
    Example:
        >>> if start_pipeline():
        ...     print("Pipeline started")
        ... else:
        ...     print("Pipeline already running")
    """
    global _pipeline_thread, _pipeline_running
    
    if _pipeline_running:
        logger.warning("Pipeline already running")
        return False
    
    # Reset stop event
    _pipeline_stop_event.clear()
    
    # Start pipeline thread
    _pipeline_thread = threading.Thread(
        target=run_pipeline,
        args=(camera_index,),
        name="VisionPipeline",
        daemon=True
    )
    _pipeline_thread.start()
    _pipeline_running = True
    
    logger.info("Vision pipeline thread started")
    return True


def stop_pipeline(timeout: float = 5.0) -> bool:
    """Stop the vision pipeline and wait for thread to complete.
    
    Args:
        timeout: Maximum seconds to wait for pipeline to stop (default: 5.0)
    
    Returns:
        bool: True if pipeline stopped within timeout, False if timed out
    
    Example:
        >>> stop_pipeline(timeout=10.0)
        True
    """
    global _pipeline_thread, _pipeline_running
    
    if not _pipeline_running:
        logger.warning("Pipeline not running")
        return True
    
    # Signal pipeline to stop
    _pipeline_stop_event.set()
    
    # Wait for thread to complete
    if _pipeline_thread:
        _pipeline_thread.join(timeout=timeout)
        
        if _pipeline_thread.is_alive():
            logger.error(f"Pipeline thread did not stop within {timeout}s")
            _pipeline_running = False  # Force reset state
            return False
    
    _pipeline_thread = None
    _pipeline_running = False
    
    logger.info("Vision pipeline stopped")
    return True


def is_pipeline_running() -> bool:
    """Check if the vision pipeline is currently running.
    
    Returns:
        bool: True if pipeline is running, False otherwise
    """
    return _pipeline_running
