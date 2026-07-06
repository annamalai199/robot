"""Vision module for camera capture, pose detection, tracking, and face identification.

Components:
- capture: Video capture from webcam/Pi camera
- motion_gate: Frame difference filter to skip processing on static frames
- detector: YOLO pose detection for person identification
- tracker: ByteTrack multi-person tracking with stable IDs
- gesture: Gesture recognition from keypoints
- face_id: Face embedding and identification with FAISS
- pipeline: Integrated vision pipeline orchestrating all stages
"""

# Lazy imports - modules are imported when accessed to avoid dependency issues
__all__ = ['capture', 'motion_gate', 'detector', 'tracker', 'gesture', 'face_id', 'pipeline']
