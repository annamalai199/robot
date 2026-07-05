"""Video capture for webcam and Pi camera.

Provides a unified generator-based interface for frame capture that works with
both laptop webcams (OpenCV) and Raspberry Pi Camera Module (future migration).

The generator signature is designed to be hardware-agnostic: any camera
implementation that yields numpy BGR frames can be swapped in without changing
downstream vision pipeline code.
"""

import cv2
import logging
import numpy as np
from typing import Generator, Optional

logger = logging.getLogger(__name__)


def get_frame_generator(camera_index: int = 0, 
                       width: Optional[int] = None,
                       height: Optional[int] = None) -> Generator[np.ndarray, None, None]:
    """Capture video frames from webcam as a generator.
    
    Opens the camera and yields BGR frames at the camera's native resolution
    (or specified resolution if provided). Continues indefinitely until the
    caller stops iteration or the camera becomes unavailable.
    
    This function uses OpenCV VideoCapture for laptop webcams. The interface
    is designed to be compatible with future Pi Camera Module integration:
    swapping to PiCamera2 requires only changing this function's implementation
    while keeping the same generator signature.
    
    Args:
        camera_index: Camera device index (default: 0 for primary webcam)
        width: Optional frame width. If None, uses camera's native resolution.
        height: Optional frame height. If None, uses camera's native resolution.
    
    Yields:
        np.ndarray: BGR frame (shape: [height, width, 3], dtype: uint8)
    
    Raises:
        RuntimeError: If camera cannot be opened or becomes unavailable
    
    Example:
        >>> for frame in get_frame_generator():
        ...     # Process frame (motion detection, YOLO, etc.)
        ...     cv2.imshow('Frame', frame)
        ...     if cv2.waitKey(1) & 0xFF == ord('q'):
        ...         break
    
    Pi Camera Migration Notes:
        When migrating to Raspberry Pi Camera Module 3, replace the OpenCV
        VideoCapture implementation with PiCamera2 while keeping the same
        generator signature:
        
        ```python
        from picamera2 import Picamera2
        
        camera = Picamera2()
        config = camera.create_preview_configuration(
            main={"size": (width or 640, height or 480), "format": "RGB888"}
        )
        camera.configure(config)
        camera.start()
        
        try:
            while True:
                # PiCamera2 returns RGB, convert to BGR for OpenCV compatibility
                rgb_frame = camera.capture_array()
                bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
                yield bgr_frame
        finally:
            camera.stop()
        ```
    """
    # Open camera using OpenCV
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open camera {camera_index}. Check if camera is connected and not in use.")
    
    # Set resolution if specified
    if width is not None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height is not None:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    # Get actual resolution (may differ from requested if camera doesn't support it)
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    
    logger.info(f"Camera opened: {actual_width}x{actual_height} @ {fps}fps")
    
    try:
        frame_count = 0
        while True:
            ret, frame = cap.read()
            
            if not ret:
                logger.error("Failed to read frame from camera")
                raise RuntimeError("Camera became unavailable or returned invalid frame")
            
            frame_count += 1
            yield frame
            
    except GeneratorExit:
        # Normal termination when caller stops iteration
        logger.info(f"Camera capture stopped after {frame_count} frames")
    
    except Exception as e:
        logger.error(f"Camera capture error after {frame_count} frames: {str(e)}")
        raise
    
    finally:
        cap.release()
        logger.info("Camera released")


def check_camera_available(camera_index: int = 0) -> bool:
    """Check if a camera is available at the specified index.
    
    Args:
        camera_index: Camera device index to check
    
    Returns:
        bool: True if camera can be opened, False otherwise
    
    Example:
        >>> if check_camera_available(0):
        ...     print("Primary webcam is available")
        ... else:
        ...     print("No webcam found")
    """
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        return False
    
    # Try to read one frame to verify camera actually works
    ret, _ = cap.read()
    cap.release()
    
    return ret


def list_available_cameras(max_check: int = 5) -> list[int]:
    """List indices of all available cameras.
    
    Args:
        max_check: Maximum number of camera indices to check (default: 5)
    
    Returns:
        list[int]: List of camera indices that are available
    
    Example:
        >>> cameras = list_available_cameras()
        >>> print(f"Found {len(cameras)} camera(s): {cameras}")
        Found 2 camera(s): [0, 1]
    """
    available = []
    
    for i in range(max_check):
        if check_camera_available(i):
            available.append(i)
    
    logger.info(f"Found {len(available)} available camera(s): {available}")
    return available
