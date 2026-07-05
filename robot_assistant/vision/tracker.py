"""ByteTrack multi-person tracking using Ultralytics' built-in tracker.

Uses YOLO11n-pose's integrated ByteTrack tracker (via model.track()) to maintain
stable track IDs across frames, even through brief occlusion. ByteTrack uses
Hungarian algorithm (via LAP library) for optimal assignment and two-stage
high/low confidence matching to recover tracks during partial occlusion.
"""

import logging
import numpy as np
from typing import List, Dict, Set, Optional
from robot_assistant.config import config
from robot_assistant.vision.detector import _get_model
from robot_assistant.events.bus import publish
from robot_assistant.events.schemas import TrackLostEvent

logger = logging.getLogger(__name__)

# Track state for TRACK_LOST event detection
_active_tracks: Set[int] = set()
_track_to_embedding: Dict[int, str] = {}  # Will be set by face_id module later
_track_missing_frames: Dict[int, int] = {}  # Counts frames since track disappeared


def update(frame: np.ndarray, conf_threshold: float = 0.5) -> List[Dict]:
    """Update tracking state with new frame using ByteTrack.
    
    Uses Ultralytics' built-in ByteTrack tracker with persist=True to maintain
    track IDs across frames. ByteTrack uses Hungarian algorithm for optimal
    detection-to-track assignment and two-stage matching (high confidence first,
    then low confidence) to recover tracks during partial occlusion.
    
    Args:
        frame: BGR frame (shape: [height, width, 3], dtype: uint8)
        conf_threshold: Minimum confidence threshold for detections (default: 0.5)
    
    Returns:
        List of tracked objects, each containing:
        - track_id: int, stable tracking ID (persists across frames)
        - bbox: [x1, y1, x2, y2] bounding box coordinates
        - keypoints: (17, 3) array of [x, y, confidence] for each COCO keypoint
        - confidence: float, detection confidence
    
    Side Effects:
        - Publishes TRACK_LOST events when tracks are absent for >= TRACK_MAX_AGE frames
          (30 frames from config), allowing brief occlusions without losing identity
        - Updates internal _active_tracks set and _track_missing_frames counters
    
    Example:
        >>> frame = cv2.imread('people.jpg')
        >>> tracked = update(frame)
        >>> for obj in tracked:
        ...     print(f"Track {obj['track_id']} at {obj['bbox']}")
    
    Performance:
        - ByteTrack overhead: ~2-5ms per frame (on top of YOLO inference)
        - Uses LAP library's Hungarian algorithm for optimal assignment
    """
    global _active_tracks
    
    model = _get_model()
    
    # Run tracking with persist=True to maintain track IDs across frames
    # Uses custom ByteTrack config with track_buffer=30 (matches TRACK_MAX_AGE)
    tracker_config = config.PROJECT_ROOT.parent / 'robot_assistant' / 'config' / 'bytetrack_custom.yaml'
    results = model.track(
        frame,
        conf=conf_threshold,
        tracker=str(tracker_config),
        persist=True,
        verbose=False
    )
    
    tracked_objects = []
    current_tracks = set()
    
    # Process tracking results
    for result in results:
        # Skip if no detections or no keypoints
        if result.boxes is None or result.keypoints is None:
            continue
        
        boxes = result.boxes.data.cpu().numpy()  # Shape: (N, 7) [x1, y1, x2, y2, track_id, conf, cls]
        keypoints_data = result.keypoints.data.cpu().numpy()  # Shape: (N, 17, 3)
        
        # Check if tracking IDs are present
        if result.boxes.id is None:
            logger.warning("No tracking IDs in result - tracker may not be initialized")
            continue
        
        track_ids = result.boxes.id.cpu().numpy().astype(int)
        
        for i, (box, track_id) in enumerate(zip(boxes, track_ids)):
            cls = int(box[6])
            
            # Only keep person detections (class 0)
            if cls != 0:
                continue
            
            tracked_obj = {
                'track_id': int(track_id),
                'bbox': box[:4].tolist(),  # [x1, y1, x2, y2]
                'keypoints': keypoints_data[i],  # (17, 3) array
                'confidence': float(box[5])  # detection confidence
            }
            
            tracked_objects.append(tracked_obj)
            current_tracks.add(int(track_id))
    
    # Detect lost tracks and publish TRACK_LOST events
    # Note: ByteTrack internally buffers lost tracks but doesn't expose them in results.
    # We implement our own frame-counting: tracks absent for >= TRACK_MAX_AGE frames
    # trigger TRACK_LOST. This allows tracks to reappear within the tolerance window.
    global _track_missing_frames
    
    # Build list of all tracks we're monitoring (active + recently missing)
    all_monitored_tracks = _active_tracks | set(_track_missing_frames.keys())
    
    # Update missing frame counters
    for track_id in all_monitored_tracks:
        if track_id not in current_tracks:
            # Track absent this frame - increment counter
            _track_missing_frames[track_id] = _track_missing_frames.get(track_id, 0) + 1
            
            # Check if exceeded tolerance
            if _track_missing_frames[track_id] >= config.TRACK_MAX_AGE:
                # Truly lost - publish TRACK_LOST if we have embedding
                embedding_id = _track_to_embedding.get(track_id)
                
                if embedding_id:
                    event: TrackLostEvent = {
                        'event': 'TRACK_LOST',
                        'track_id': str(track_id),
                        'embedding_id': embedding_id
                    }
                    publish(event)
                    logger.info(f"Track {track_id} lost after {_track_missing_frames[track_id]} frames (embedding_id: {embedding_id})")
                    
                    # Clean up mappings
                    del _track_to_embedding[track_id]
                
                # Clean up counter regardless of embedding
                del _track_missing_frames[track_id]
        else:
            # Track reappeared - reset counter
            if track_id in _track_missing_frames:
                logger.debug(f"Track {track_id} reappeared after {_track_missing_frames[track_id]} frames")
                del _track_missing_frames[track_id]
    
    # Update active tracks
    _active_tracks = current_tracks
    
    logger.debug(f"Tracking {len(tracked_objects)} person(s) across {len(current_tracks)} track(s)")
    
    return tracked_objects


def register_embedding(track_id: int, embedding_id: str):
    """Register an embedding_id for a track_id (called by face_id module).
    
    This enables TRACK_LOST event publishing when the track disappears.
    
    Args:
        track_id: Vision tracker ID (transient)
        embedding_id: Persistent face embedding ID
    """
    _track_to_embedding[track_id] = embedding_id
    logger.debug(f"Registered track {track_id} -> embedding {embedding_id}")


def reset():
    """Reset tracker state (for testing or reinitialization).
    
    Clears all active tracks, track-to-embedding mappings, and missing frame counters.
    """
    global _active_tracks, _track_to_embedding, _track_missing_frames
    _active_tracks = set()
    _track_to_embedding = {}
    _track_missing_frames = {}
    logger.debug("Tracker state reset")
