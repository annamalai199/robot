"""Comprehensive face ID validation with diagnostics.

Tests:
1. Same person: 3+ captures, check distances and consistency
2. Different person: 1+ capture, check distance separation
3. Raw embedding analysis: Check if InsightFace outputs are pre-normalized
4. Bbox diagnostics: Log actual bbox sizes and face crop dimensions
"""

import cv2
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import detector, face_id
from robot_assistant.config import config
from insightface.app import FaceAnalysis


def main():
    print("=" * 80)
    print("COMPREHENSIVE FACE ID VALIDATION")
    print("=" * 80)
    print()
    print("This test will:")
    print("1. Check if InsightFace embeddings are pre-normalized")
    print("2. Test same-person recognition (3+ captures)")
    print("3. Test different-person separation (different face)")
    print("4. Diagnose bbox and crop dimensions for each capture")
    print("5. Calculate optimal threshold based on actual distance distribution")
    print()
    print(f"Current threshold: {config.FACE_MATCH_THRESHOLD}")
    print()
    
    # Clear state
    face_id.clear_index()
    face_id.reset()
    
    # Load InsightFace model
    print("Loading InsightFace model...")
    face_app = FaceAnalysis(name='buffalo_s')
    face_app.prepare(ctx_id=-1, det_size=(640, 640))
    print("Model loaded!")
    print()
    
    # Open webcam
    print("Opening webcam...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open webcam")
        return 1
    print("Webcam opened!")
    print()
    
    # Phase 1: Check InsightFace normalization
    print("=" * 80)
    print("PHASE 1: InsightFace Embedding Normalization Check")
    print("=" * 80)
    print()
    print("Position your face in frame and press SPACE")
    
    frame1 = wait_for_capture(cap, "normalization test")
    if frame1 is None:
        cap.release()
        return 1
    
    detections = detector.detect_poses(frame1, conf_threshold=0.5)
    if len(detections) == 0:
        print("ERROR: No person detected")
        cap.release()
        return 1
    
    bbox = detections[0]['bbox']
    x1, y1, x2, y2 = [int(c) for c in bbox]
    crop = frame1[y1:y2, x1:x2]
    
    faces = face_app.get(crop)
    if len(faces) == 0:
        print("ERROR: No face detected in crop")
        cap.release()
        return 1
    
    raw_embedding = faces[0].embedding
    raw_norm = np.linalg.norm(raw_embedding)
    
    print(f"Raw embedding shape: {raw_embedding.shape}")
    print(f"Raw embedding dtype: {raw_embedding.dtype}")
    print(f"Raw embedding L2 norm: {raw_norm:.6f}")
    print()
    
    if abs(raw_norm - 1.0) < 0.01:
        print("✓ InsightFace outputs ARE pre-normalized (||e|| ≈ 1.0)")
        print("  → Re-normalizing in face_id.py is redundant but harmless")
        print("  → For normalized vectors, L2 distance ∈ [0, √2] ≈ [0, 1.414]")
    else:
        print(f"✗ InsightFace outputs are NOT normalized (||e|| = {raw_norm:.6f})")
        print("  → Normalization in face_id.py is REQUIRED")
        print("  → Without normalization, distances would be scale-dependent")
    print()
    
    # Phase 2: Same person multiple captures
    print("=" * 80)
    print("PHASE 2: Same Person Recognition (Person A)")
    print("=" * 80)
    print()
    
    person_a_results = []
    person_a_embeddings = []
    
    for i in range(3):
        print(f"\n--- Capture {i+1}/3 for Person A ---")
        print("Vary angle/lighting slightly, then press SPACE")
        
        frame = wait_for_capture(cap, f"Person A capture {i+1}")
        if frame is None:
            continue
        
        result, diagnostics = capture_and_diagnose(frame, f"PERSON_A_{i+1}", face_app)
        
        if result:
            person_a_results.append(result)
            person_a_embeddings.append(diagnostics['normalized_embedding'])
            
            print(f"\nResult:")
            print(f"  embedding_id: {result['embedding_id']}")
            print(f"  status: {result['status']}")
            print(f"  confidence: {result['confidence']}")
            if result['confidence'] is not None and 'distance' in diagnostics and diagnostics['distance'] is not None:
                print(f"  L2 distance: {diagnostics['distance']:.4f}")
            
            print(f"\nDiagnostics:")
            print(f"  bbox: {diagnostics['bbox']}")
            print(f"  crop_size: {diagnostics['crop_size']}")
            print(f"  raw_embedding_norm: {diagnostics['raw_norm']:.6f}")
    
    # Analyze same-person distances
    if len(person_a_embeddings) >= 2:
        print("\n" + "=" * 80)
        print("SAME-PERSON DISTANCE ANALYSIS")
        print("=" * 80)
        
        distances_within_person_a = []
        for i in range(len(person_a_embeddings)):
            for j in range(i+1, len(person_a_embeddings)):
                emb_i = person_a_embeddings[i]
                emb_j = person_a_embeddings[j]
                dist = np.linalg.norm(emb_i - emb_j)
                distances_within_person_a.append(dist)
                print(f"  Distance between capture {i+1} and {j+1}: {dist:.4f}")
        
        if distances_within_person_a:
            print(f"\n  Mean same-person distance: {np.mean(distances_within_person_a):.4f}")
            print(f"  Max same-person distance: {np.max(distances_within_person_a):.4f}")
            print(f"  Min same-person distance: {np.min(distances_within_person_a):.4f}")
    
    # Phase 3: Different person
    print("\n" + "=" * 80)
    print("PHASE 3: Different Person Test (Person B)")
    print("=" * 80)
    print()
    print("Have a DIFFERENT person sit in frame (or show photo of different face)")
    print("Press SPACE to capture, or 'q' to skip")
    
    frame_b = wait_for_capture(cap, "Person B", allow_skip=True)
    
    person_b_distance = None
    
    if frame_b is not None:
        result_b, diagnostics_b = capture_and_diagnose(frame_b, "PERSON_B_1", face_app)
        
        if result_b:
            print(f"\nResult:")
            print(f"  embedding_id: {result_b['embedding_id']}")
            print(f"  status: {result_b['status']}")
            print(f"  confidence: {result_b['confidence']}")
            if 'distance' in diagnostics_b:
                person_b_distance = diagnostics_b['distance']
                print(f"  L2 distance to Person A: {person_b_distance:.4f}")
            
            print(f"\nDiagnostics:")
            print(f"  bbox: {diagnostics_b['bbox']}")
            print(f"  crop_size: {diagnostics_b['crop_size']}")
            
            if result_b['embedding_id'] == person_a_results[0]['embedding_id']:
                print("\n  ⚠ WARNING: MATCHED Person A (potential false positive!)")
                if person_b_distance:
                    print(f"     Distance {person_b_distance:.4f} < threshold {config.FACE_MATCH_THRESHOLD}")
            else:
                print("\n  ✓ Correctly identified as different person")
                if person_b_distance:
                    print(f"     Distance {person_b_distance:.4f} >= threshold {config.FACE_MATCH_THRESHOLD}")
    
    # Final analysis
    print("\n" + "=" * 80)
    print("FINAL ANALYSIS")
    print("=" * 80)
    print()
    
    if len(person_a_results) >= 2:
        same_person_distances = [r.get('confidence') for r in person_a_results[1:] if r.get('confidence')]
        if same_person_distances:
            print("Same-person recognition:")
            print(f"  Captures matched: {sum(1 for r in person_a_results[1:] if r['embedding_id'] == person_a_results[0]['embedding_id'])}/{len(person_a_results)-1}")
            print(f"  Confidence range: {min(same_person_distances):.2f} - {max(same_person_distances):.2f}")
    
    if person_b_distance:
        print(f"\nDifferent-person separation:")
        print(f"  L2 distance: {person_b_distance:.4f}")
        print(f"  Current threshold: {config.FACE_MATCH_THRESHOLD}")
        print(f"  Threshold buffer: {person_b_distance - config.FACE_MATCH_THRESHOLD:.4f}")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    if distances_within_person_a and person_b_distance:
        max_same = max(distances_within_person_a)
        min_different = person_b_distance
        
        print(f"Distance ranges observed:")
        print(f"  Same person (max): {max_same:.4f}")
        print(f"  Different person (min): {min_different:.4f}")
        print(f"  Separation gap: {min_different - max_same:.4f}")
        print()
        
        if min_different <= max_same:
            print("⚠ ERROR: No separation! Same-person max >= different-person min")
            print("  → Cannot reliably distinguish same vs different person")
            print("  → Need better lighting, clearer face visibility, or better model")
        else:
            # Recommend threshold in the middle of the gap
            recommended = (max_same + min_different) / 2
            print(f"✓ Clear separation exists")
            print(f"  Recommended threshold: {recommended:.4f}")
            print(f"    (Halfway between max same-person and min different-person)")
            print()
            print(f"  Current threshold: {config.FACE_MATCH_THRESHOLD}")
            if config.FACE_MATCH_THRESHOLD < max_same:
                print(f"  → TOO STRICT (causes false negatives)")
            elif config.FACE_MATCH_THRESHOLD > min_different:
                print(f"  → TOO LOOSE (causes false positives)")
            else:
                print(f"  → Within acceptable range (has {min_different - config.FACE_MATCH_THRESHOLD:.4f} buffer)")
    
    cap.release()
    cv2.destroyAllWindows()
    print()
    print("=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)
    
    return 0


def wait_for_capture(cap, label, allow_skip=False):
    """Wait for user to press SPACE to capture frame."""
    print(f"Position face for {label}, press SPACE (or 'q' to {'skip' if allow_skip else 'quit'})")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("ERROR: Failed to read frame")
            return None
        
        cv2.imshow('Face ID Validation', frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            if allow_skip:
                print("Skipped by user")
                return None
            else:
                print("Quit by user")
                return None
        elif key == ord(' '):
            cv2.destroyAllWindows()
            return frame
    
    return None


def capture_and_diagnose(frame, track_id, face_app):
    """Capture and diagnose face identification with detailed metrics."""
    # Detect pose
    detections = detector.detect_poses(frame, conf_threshold=0.5)
    if len(detections) == 0:
        print("ERROR: No person detected")
        return None, {}
    
    bbox = detections[0]['bbox']
    x1, y1, x2, y2 = [int(c) for c in bbox]
    crop = frame[y1:y2, x1:x2]
    crop_size = (x2-x1, y2-y1)  # width, height
    
    # Get raw embedding for analysis
    faces = face_app.get(crop)
    if len(faces) == 0:
        print("ERROR: No face in crop")
        return None, {}
    
    raw_embedding = faces[0].embedding
    raw_norm = np.linalg.norm(raw_embedding)
    
    # Normalize (same as face_id.py does)
    normalized = raw_embedding / raw_norm
    
    # Run actual face_id
    result = face_id.identify_face(frame, bbox, track_id)
    
    # Get distance if matched
    distance = None
    if result and result['confidence'] is not None:
        # Reverse-engineer distance from confidence formula
        confidence = result['confidence']
        distance = (1.0 - confidence) * config.FACE_MATCH_THRESHOLD
    
    diagnostics = {
        'bbox': bbox,
        'crop_size': crop_size,
        'raw_norm': raw_norm,
        'normalized_embedding': normalized,
        'distance': distance
    }
    
    return result, diagnostics


if __name__ == '__main__':
    sys.exit(main())
