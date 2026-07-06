"""Debug which component causes nondeterminism.

Tests each stage independently to isolate the source of randomness.
"""

import cv2
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import detector
from insightface.app import FaceAnalysis


def main():
    print("=" * 80)
    print("DEBUGGING NONDETERMINISM SOURCE")
    print("=" * 80)
    print()
    
    # Capture test frame
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
    
    # Test 1: YOLO detection determinism
    print("=" * 80)
    print("TEST 1: YOLO Pose Detection Determinism")
    print("=" * 80)
    
    det1 = detector.detect_poses(test_frame)
    det2 = detector.detect_poses(test_frame)
    
    if len(det1) > 0 and len(det2) > 0:
        bbox1 = det1[0]['bbox']
        bbox2 = det2[0]['bbox']
        
        bbox_diff = np.abs(np.array(bbox1) - np.array(bbox2))
        print(f"Run 1 bbox: {bbox1}")
        print(f"Run 2 bbox: {bbox2}")
        print(f"Difference: {bbox_diff}")
        print(f"Max diff: {np.max(bbox_diff):.6f}")
        
        if np.max(bbox_diff) < 0.001:
            print("✓ YOLO is deterministic")
        else:
            print("⚠ YOLO has variance (but this is expected for pose estimation)")
    print()
    
    # Test 2: InsightFace face detection determinism
    print("=" * 80)
    print("TEST 2: InsightFace Face Detection Determinism")
    print("=" * 80)
    
    face_app = FaceAnalysis(name='buffalo_s')
    face_app.prepare(ctx_id=-1, det_size=(640, 640))
    
    faces1 = face_app.get(test_frame)
    faces2 = face_app.get(test_frame)
    
    if len(faces1) > 0 and len(faces2) > 0:
        face1 = faces1[0]
        face2 = faces2[0]
        
        bbox1 = face1.bbox
        bbox2 = face2.bbox
        bbox_diff = np.abs(bbox1 - bbox2)
        
        print(f"Run 1 face bbox: {bbox1}")
        print(f"Run 2 face bbox: {bbox2}")
        print(f"Difference: {bbox_diff}")
        print(f"Max diff: {np.max(bbox_diff):.6f}")
        
        if np.max(bbox_diff) < 0.001:
            print("✓ InsightFace face detection is deterministic")
        else:
            print("✗ InsightFace face detection is NOT deterministic!")
            print("  → This could cause different face crops each time")
        
        print()
        
        # Test 3: Embedding determinism
        print("=" * 80)
        print("TEST 3: InsightFace Embedding Determinism")
        print("=" * 80)
        
        emb1 = face1.embedding
        emb2 = face2.embedding
        
        print(f"Embedding 1 norm: {np.linalg.norm(emb1):.6f}")
        print(f"Embedding 2 norm: {np.linalg.norm(emb2):.6f}")
        
        emb_diff = np.abs(emb1 - emb2)
        print(f"Embedding difference (max): {np.max(emb_diff):.10f}")
        print(f"Embedding difference (mean): {np.mean(emb_diff):.10f}")
        
        # Normalize and compute distance
        emb1_norm = emb1 / np.linalg.norm(emb1)
        emb2_norm = emb2 / np.linalg.norm(emb2)
        distance = np.linalg.norm(emb1_norm - emb2_norm)
        
        print(f"L2 distance (normalized): {distance:.10f}")
        print()
        
        if distance < 0.001:
            print("✓ InsightFace embeddings are deterministic")
        elif distance < 0.01:
            print("⚠ InsightFace embeddings have minor variance (likely float rounding)")
        else:
            print("✗ InsightFace embeddings are NOT deterministic!")
            print("  → This is the source of the bug")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("If InsightFace face detection bbox varies:")
    print("  → Different crops → different embeddings")
    print("  → This is likely the root cause")
    print()
    print("If InsightFace embeddings vary with same bbox:")
    print("  → Model has nondeterminism (shouldn't happen with CPU)")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
