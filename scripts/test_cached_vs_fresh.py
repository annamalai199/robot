"""Test if cached FaceAnalysis instance causes nondeterminism."""

import cv2
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from insightface.app import FaceAnalysis


def main():
    print("Testing cached vs fresh FaceAnalysis")
    print()
    
    # Capture frame
    cap = cv2.VideoCapture(0)
    print("Press SPACE to capture")
    
    frame = None
    while True:
        ret, f = cap.read()
        if not ret:
            break
        cv2.imshow('Capture', f)
        if (cv2.waitKey(1) & 0xFF) == ord(' '):
            frame = f.copy()
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    print("Frame captured!")
    print()
    
    # Test 1: Fresh instances
    print("TEST 1: Fresh FaceAnalysis each time")
    app1 = FaceAnalysis(name='buffalo_s')
    app1.prepare(ctx_id=-1, det_size=(640, 640))
    faces1 = app1.get(frame)
    emb1 = faces1[0].embedding if len(faces1) > 0 else None
    
    app2 = FaceAnalysis(name='buffalo_s')
    app2.prepare(ctx_id=-1, det_size=(640, 640))
    faces2 = app2.get(frame)
    emb2 = faces2[0].embedding if len(faces2) > 0 else None
    
    if emb1 is not None and emb2 is not None:
        dist1 = np.linalg.norm(emb1 / np.linalg.norm(emb1) - emb2 / np.linalg.norm(emb2))
        print(f"Distance (fresh instances): {dist1:.10f}")
    
    print()
    
    # Test 2: Cached/reused instance
    print("TEST 2: Same (cached) FaceAnalysis instance")
    app_cached = FaceAnalysis(name='buffalo_s')
    app_cached.prepare(ctx_id=-1, det_size=(640, 640))
    
    faces_a = app_cached.get(frame)
    emb_a = faces_a[0].embedding if len(faces_a) > 0 else None
    
    faces_b = app_cached.get(frame)
    emb_b = faces_b[0].embedding if len(faces_b) > 0 else None
    
    if emb_a is not None and emb_b is not None:
        dist2 = np.linalg.norm(emb_a / np.linalg.norm(emb_a) - emb_b / np.linalg.norm(emb_b))
        print(f"Distance (cached instance): {dist2:.10f}")
    
    print()
    
    if dist1 < 0.001 and dist2 < 0.001:
        print("✓ Both deterministic")
    elif dist1 >= 0.001:
        print("✗ Fresh instances NOT deterministic")
    elif dist2 >= 0.001:
        print("✗ Cached instance NOT deterministic")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
