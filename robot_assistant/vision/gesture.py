"""Gesture recognition from pose keypoints.

Pure geometry-based gesture detection without any model calls. Recognizes
HAND_RAISED gesture by comparing wrist and shoulder y-coordinates from
COCO 17-point keypoints provided by the pose detector.
"""

import logging
import numpy as np
from typing import Optional
from robot_assistant.events.bus import publish
from robot_assistant.events.schemas import GestureDetectedEvent
from robot_assistant.config import config

logger = logging.getLogger(__name__)

# COCO keypoint indices
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_WRIST = 9
RIGHT_WRIST = 10


def check_gesture(keypoints: np.ndarray, track_id: str) -> Optional[str]:
    """Check for recognized gestures in pose keypoints.
    
    Pure arithmetic on keypoints - no model inference. Detects HAND_RAISED
    gesture when either wrist is above (y < ) its corresponding shoulder.
    Publishes GESTURE_DETECTED event to the bus when a gesture is recognized.
    
    Args:
        keypoints: (17, 3) array of [x, y, confidence] for each COCO keypoint
                   Indices: 5=left_shoulder, 6=right_shoulder,
                           9=left_wrist, 10=right_wrist
        track_id: Vision tracker ID for the person
    
    Returns:
        "HAND_RAISED" if either wrist is raised above shoulder, None otherwise
        
        Boundary case: wrist_y exactly equal to shoulder_y is NOT considered
        raised (requires wrist_y < shoulder_y, strict inequality).
    
    Side Effects:
        Publishes GestureDetectedEvent to the event bus when gesture detected
    
    Example:
        >>> keypoints = np.array([[...], ...])  # 17 keypoints from detector
        >>> gesture = check_gesture(keypoints, track_id="1")
        >>> if gesture:
        ...     print(f"Detected: {gesture}")
    
    Performance:
        Pure arithmetic, latency < 1ms per call
    """
    # Extract y-coordinates and confidence values
    left_shoulder_y = keypoints[LEFT_SHOULDER, 1]
    right_shoulder_y = keypoints[RIGHT_SHOULDER, 1]
    left_wrist_y = keypoints[LEFT_WRIST, 1]
    right_wrist_y = keypoints[RIGHT_WRIST, 1]
    
    # Check keypoint confidence (need visible keypoints for valid comparison)
    left_shoulder_conf = keypoints[LEFT_SHOULDER, 2]
    right_shoulder_conf = keypoints[RIGHT_SHOULDER, 2]
    left_wrist_conf = keypoints[LEFT_WRIST, 2]
    right_wrist_conf = keypoints[RIGHT_WRIST, 2]
    
    # Require minimum confidence threshold from config for keypoints to be considered
    min_conf = config.GESTURE_KEYPOINT_CONFIDENCE_THRESHOLD
    
    # Check left hand raised: left wrist above left shoulder
    left_hand_raised = False
    if left_wrist_conf > min_conf and left_shoulder_conf > min_conf:
        # In image coordinates, smaller y = higher position
        # Strict inequality: wrist_y < shoulder_y (wrist_y == shoulder_y is NOT raised)
        left_hand_raised = left_wrist_y < left_shoulder_y
    
    # Check right hand raised: right wrist above right shoulder
    right_hand_raised = False
    if right_wrist_conf > min_conf and right_shoulder_conf > min_conf:
        right_hand_raised = right_wrist_y < right_shoulder_y
    
    # Gesture detected if either hand is raised
    if left_hand_raised or right_hand_raised:
        gesture = "HAND_RAISED"
        
        # Publish GESTURE_DETECTED event
        event: GestureDetectedEvent = {
            'event': 'GESTURE_DETECTED',
            'gesture': gesture,
            'track_id': str(track_id)
        }
        publish(event)
        
        logger.debug(f"Gesture detected: {gesture} for track {track_id}")
        
        return gesture
    
    return None
