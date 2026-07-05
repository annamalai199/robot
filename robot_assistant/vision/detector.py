"""YOLO pose detection for person identification.

Uses YOLO11n-pose from Ultralytics to detect people and extract their pose
keypoints in COCO format (17 keypoints: nose, eyes, ears, shoulders, elbows,
wrists, hips, knees, ankles).
"""

import logging
import numpy as np
from typing import List, Dict, Optional
from ultralytics import YOLO
from robot_assistant.config import config

logger = logging.getLogger(__name__)

# Global model instance (loaded once on first use)
_model: Optional[YOLO] = None


def _get_model() -> YOLO:
    """Get or initialize the YOLO pose model (lazy loading).
    
    Returns:
        Initialized YOLO model instance.
    """
    global _model
    
    if _model is None:
        model_path = config.MODEL_PATHS["pose"]
        logger.info(f"Loading YOLO11n-pose model: {model_path}")
        _model = YOLO(model_path)
        logger.info("YOLO11n-pose model loaded successfully")
    
    return _model


def detect_poses(frame: np.ndarray, conf_threshold: float = 0.5) -> List[Dict]:
    """Detect people and their pose keypoints in a frame.
    
    Runs YOLO11n-pose inference on the frame and returns detected persons with
    their bounding boxes, keypoints, and confidence scores. Filters to only
    return person detections (class 0 in COCO).
    
    Args:
        frame: BGR frame (shape: [height, width, 3], dtype: uint8)
        conf_threshold: Minimum confidence threshold for detections (default: 0.5)
    
    Returns:
        List of detection dicts, each containing:
        - bbox: [x1, y1, x2, y2] bounding box coordinates (xyxy format)
        - keypoints: (17, 3) array of [x, y, confidence] for each keypoint
        - confidence: float, overall detection confidence
        
        Keypoints are in COCO 17-point format:
        0: nose, 1: left_eye, 2: right_eye, 3: left_ear, 4: right_ear,
        5: left_shoulder, 6: right_shoulder, 7: left_elbow, 8: right_elbow,
        9: left_wrist, 10: right_wrist, 11: left_hip, 12: right_hip,
        13: left_knee, 14: right_knee, 15: left_ankle, 16: right_ankle
    
    Example:
        >>> frame = cv2.imread('person.jpg')
        >>> detections = detect_poses(frame)
        >>> for det in detections:
        ...     bbox = det['bbox']
        ...     keypoints = det['keypoints']
        ...     print(f"Person at {bbox} with confidence {det['confidence']:.2f}")
        ...     print(f"Nose position: {keypoints[0, :2]}")
    
    Performance:
        - YOLO11n-pose on 640x480 frame: ~100-150ms on laptop CPU
        - This function should be called every Kth frame (K=5 in config)
          to maintain acceptable frame rate
    """
    model = _get_model()
    
    # Run inference
    # verbose=False suppresses per-frame logging
    results = model(frame, conf=conf_threshold, verbose=False)
    
    detections = []
    
    # Process results
    for result in results:
        # Filter to person class only (class 0 in COCO)
        if result.boxes is None or result.keypoints is None:
            continue
        
        boxes = result.boxes.data.cpu().numpy()  # Shape: (N, 6) [x1, y1, x2, y2, conf, cls]
        keypoints_data = result.keypoints.data.cpu().numpy()  # Shape: (N, 17, 3) [x, y, conf]
        
        for i, box in enumerate(boxes):
            cls = int(box[5])
            
            # Only keep person detections (class 0)
            if cls != 0:
                continue
            
            detection = {
                'bbox': box[:4].tolist(),  # [x1, y1, x2, y2]
                'keypoints': keypoints_data[i],  # (17, 3) array
                'confidence': float(box[4])  # detection confidence
            }
            
            detections.append(detection)
    
    logger.debug(f"Detected {len(detections)} person(s) in frame")
    
    return detections


def check_model_available() -> bool:
    """Check if the YOLO model can be loaded.
    
    Returns:
        bool: True if model loads successfully, False otherwise
    """
    try:
        _get_model()
        return True
    except Exception as e:
        logger.error(f"Failed to load YOLO model: {str(e)}")
        return False


def get_keypoint_names() -> List[str]:
    """Get the names of COCO 17-point keypoints in order.
    
    Returns:
        List of 17 keypoint names
    
    Example:
        >>> names = get_keypoint_names()
        >>> print(f"Keypoint 0 is: {names[0]}")
        Keypoint 0 is: nose
    """
    return [
        "nose",
        "left_eye",
        "right_eye",
        "left_ear",
        "right_ear",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle"
    ]
