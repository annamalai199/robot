"""Test same-person variance with multiple captures.

Captures 3+ images of the same person under different conditions
(slight pose/lighting variation) and measures embedding distances.
"""

import cv2
import numpy as np
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(
    level=logging.WARNING,  # Suppress debug logs for cleaner output
    format='%(levelname)s - %(name)s - %(message)s'
)

from robot_assistant.vision import detector, face_id
from robot_assistant.config import config


def capture_face(cap, capture_num):
    """Capture a single face and return frame, bbox, and embedding."""
    print(f"\n{'='*60}")
    print(f"CAPTURE {capture_num}")
    print(f"{'='*60}")
    print("Position face, press SPACE when ready")
    print("(Try slight variations: turn head, change expression, adjust lighting)")
    
    frame = None
    while True:
        ret, current_frame = cap.read()
        if not ret:
            break
        
        cv2.imshow('Capture', current_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            frame = current_frame.copy()
            break
        elif key == ord('q'):
            return None, None, None
    
    # Detect YOLO bbox
    detections = detector.detect_poses(frame, conf_threshold=0.5)
    
    if len(detections) == 0:
        print("ERROR: No person detected")
        return None, None, None
    
    bbox = detections[0]['bbox']
    print(f"YOLO bbox: {bbox}")
    
    # Get embedding via identify_face
    track_id = f"TEST_{capture_num}"
    result = face_id.identify_face(frame, bbox, track_id)
    
    if result is None:
        print("ERROR: No face identified")
        return None, None, None
    
    print(f"Result: {result['embedding_id']}, status={result['status']}")
    if result['confidence'] is not None:
        distance = (1.0 - result['confidence']) * config.FACE_MATCH_THRESHOLD
        print(f"Match distance: {distance:.6f}, confidence: {result['confidence']:.4f}")
    
    return frame, bbox, result


def compute_embedding(frame, bbox):
    """Extract just the embedding without side effects."""
    face_app = face_id._get_face_app()
    faces = face_app.get(frame)
    
    if len(faces) == 0:
        return None
    
    # Use SHARED face selection function (not duplicated logic!)
    selected_face = face_id._select_face_for_bbox(faces, bbox)
    
    if selected_face is None:
        return None
    
    # Normalize embedding (same as identify_face does)
    embedding = selected_face.embedding
    embedding = embedding / np.linalg.norm(embedding)
    
    return embedding


def main():
    print("=" * 80)
    print("SAME-PERSON VARIANCE TEST")
    print("=" * 80)
    print()
    print("This test will capture 3+ images of the SAME PERSON")
    print("with slight variations (pose, lighting, expression)")
    print("to measure genuine capture-to-capture variance.")
    print()
    
    num_captures = input("How many captures? (default: 3): ").strip()
    num_captures = int(num_captures) if num_captures else 3
    
    # Clear state
    face_id.clear_index()
    face_id.reset()
    
    # Open webcam
    print("\nOpening webcam...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open webcam")
        return 1
    
    # Capture multiple images
    captures = []
    embeddings = []
    
    for i in range(num_captures):
        frame, bbox, result = capture_face(cap, i + 1)
        
        if frame is None:
            print("Capture cancelled")
            cap.release()
            cv2.destroyAllWindows()
            return 1
        
        # Extract embedding for distance calculation
        embedding = compute_embedding(frame, bbox)
        if embedding is None:
            print("ERROR: Could not extract embedding")
            cap.release()
            cv2.destroyAllWindows()
            return 1
        
        captures.append({
            'num': i + 1,
            'result': result,
            'embedding': embedding
        })
        embeddings.append(embedding)
        
        # Reset for next capture (so we get "new" status each time)
        face_id.reset()
    
    cap.release()
    cv2.destroyAllWindows()
    
    # Calculate all pairwise distances
    print("\n" + "=" * 80)
    print("PAIRWISE DISTANCES (L2 norm)")
    print("=" * 80)
    
    distances = []
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            emb1 = embeddings[i].reshape(1, -1).astype('float32')
            emb2 = embeddings[j].reshape(1, -1).astype('float32')
            
            # Compute L2 distance (same as FAISS IndexFlatL2)
            distance = np.linalg.norm(emb1 - emb2)
            distances.append(distance)
            
            print(f"Capture {i+1} vs Capture {j+1}: {distance:.6f}")
    
    # Statistics
    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)
    print(f"Min distance: {min(distances):.6f}")
    print(f"Max distance: {max(distances):.6f}")
    print(f"Mean distance: {np.mean(distances):.6f}")
    print(f"Std deviation: {np.std(distances):.6f}")
    
    print(f"\nCurrent threshold: {config.FACE_MATCH_THRESHOLD}")
    
    if max(distances) < config.FACE_MATCH_THRESHOLD:
        print(f"✓ All same-person distances < threshold")
    else:
        print(f"✗ WARNING: Max same-person distance ({max(distances):.6f}) >= threshold ({config.FACE_MATCH_THRESHOLD})")
        print(f"  This could cause false negatives (failing to recognize same person)")
    
    print("\n" + "=" * 80)
    print("NEXT STEP: Test with DIFFERENT person")
    print("=" * 80)
    print("To validate threshold, we need:")
    print(f"1. Max same-person distance: {max(distances):.6f} (measured)")
    print("2. Min different-person distance: ??? (needs second person)")
    print()
    print("Threshold should be between these two values.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
