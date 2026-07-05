"""Motion gate for filtering static frames.

Implements frame difference detection to avoid running expensive YOLO
inference on frames where nothing has changed. Uses grayscale conversion
and pixel-level absolute difference to detect motion.
"""

import cv2
import numpy as np
import logging
from robot_assistant.config import config

logger = logging.getLogger(__name__)


def has_motion(frame: np.ndarray, prev_frame: np.ndarray, threshold: float = None) -> bool:
    """Detect motion between two consecutive frames.
    
    Converts both frames to grayscale, computes absolute pixel difference,
    and checks if the mean difference exceeds the threshold. This provides
    a fast, lightweight motion detection suitable for gating expensive
    vision processing (YOLO pose detection).
    
    Args:
        frame: Current BGR frame (shape: [height, width, 3], dtype: uint8)
        prev_frame: Previous BGR frame (same shape as frame)
        threshold: Mean difference threshold. If None, uses config.MOTION_GATE_THRESHOLD (default: 5.0)
    
    Returns:
        bool: True if motion detected (mean diff > threshold), False otherwise
    
    Example:
        >>> prev = capture_frame()
        >>> curr = capture_frame()
        >>> if has_motion(curr, prev):
        ...     # Run YOLO pose detection
        ...     detections = detect_poses(curr)
        ... else:
        ...     # Skip expensive processing
        ...     pass
    
    Performance:
        - Grayscale conversion: ~1ms for 640x480 frame
        - Absolute difference: ~0.5ms
        - Mean calculation: ~0.1ms
        - Total: < 5ms on laptop CPU
    """
    if threshold is None:
        threshold = config.MOTION_GATE_THRESHOLD
    
    # Convert frames to grayscale for faster comparison
    gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray_prev = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    
    # Compute absolute pixel difference
    diff = cv2.absdiff(gray_curr, gray_prev)
    
    # Calculate mean difference
    mean_diff = np.mean(diff)
    
    # Check if motion detected
    motion_detected = bool(mean_diff > threshold)
    
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Motion gate: mean_diff={mean_diff:.2f}, threshold={threshold:.2f}, "
                    f"motion={'YES' if motion_detected else 'NO'}")
    
    return motion_detected


def get_motion_score(frame: np.ndarray, prev_frame: np.ndarray) -> float:
    """Get the motion score (mean pixel difference) between two frames.
    
    Similar to has_motion() but returns the actual numeric score instead of
    a boolean. Useful for debugging or adaptive threshold tuning.
    
    Args:
        frame: Current BGR frame
        prev_frame: Previous BGR frame
    
    Returns:
        float: Mean absolute pixel difference (0-255 range, typically 0-50 for real scenes)
    
    Example:
        >>> score = get_motion_score(curr_frame, prev_frame)
        >>> print(f"Motion intensity: {score:.2f}")
        Motion intensity: 12.45
    """
    gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray_prev = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    
    diff = cv2.absdiff(gray_curr, gray_prev)
    mean_diff = np.mean(diff)
    
    return float(mean_diff)
