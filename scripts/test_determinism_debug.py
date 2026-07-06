"""Test determinism with detailed debug logging."""

import cv2
import numpy as np
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging to show INFO level
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)

from robot_assistant.vision import detector, face_id
from robot_assistant.config import config


def main():
    print("=" * 80)
    print("DETERMINISM TEST WITH DEBUG LOGGING")
    print("=" * 80)
    print()
    
    # Clear state
    face_id.clear_index()
    face_id.reset()
    
    # Capture one frame
    print("Opening webcam...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open webcam")
        return 1
    
    print("Position face, press SPACE to capture")
    
    test_frame = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        cv2.imshow('Capture', frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            test_frame = frame.copy()
            break
        elif key == ord('q'):
            cap.release()
            cv2.destroyAllWindows()
            return 1
    
    cap.release()
    cv2.destroyAllWindows()
    
    print("Frame captured!")
    print()
    
    # Get YOLO bbox
    print("Running YOLO detection...")
    detections = detector.detect_poses(test_frame, conf_threshold=0.5)
    
    if len(detections) == 0:
        print("ERROR: No person detected")
        return 1
    
    bbox = detections[0]['bbox']
    print(f"YOLO bbox: {bbox}")
    print()
    
    # Process twice
    print("=" * 80)
    print("RUN 1")
    print("=" * 80)
    face_id.reset()
    result1 = face_id.identify_face(test_frame, bbox, track_id="TEST_1")
    
    if result1:
        print(f"Result: embedding_id={result1['embedding_id']}, status={result1['status']}")
    else:
        print("Result: None")
    
    print()
    print("=" * 80)
    print("RUN 2 (SAME FRAME)")
    print("=" * 80)
    face_id.reset()
    result2 = face_id.identify_face(test_frame, bbox, track_id="TEST_2")
    
    if result2:
        print(f"Result: embedding_id={result2['embedding_id']}, status={result2['status']}, confidence={result2['confidence']}")
        
        if result2['confidence'] is not None:
            distance = (1.0 - result2['confidence']) * config.FACE_MATCH_THRESHOLD
            print(f"L2 Distance: {distance:.6f}")
            
            if distance < 0.001:
                print("\n✓ DETERMINISTIC")
            else:
                print(f"\n✗ NONDETERMINISTIC (distance={distance:.6f})")
    else:
        print("Result: None")
    
    print()
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print("Review the logs above and check:")
    print("1. Did len(faces) differ between runs?")
    print("2. Did any face bbox differ between runs?")
    print("3. Did the SELECTED face index differ between runs?")
    print("4. Did the overlap_score differ between runs?")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
