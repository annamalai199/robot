"""Test 3 JPG photos of different people - modality-controlled test.

Uses ONLY JPG files (no webcam mixing) to avoid confounding:
- "Different person" with "different capture pipeline"

Tests:
1. Determinism: Same image processed twice → distance ~0.0
2. Different-person separation: All 3 pairwise distances
3. Comparison with same-person variance from webcam tests

Uses the SAME preprocessing path as identify_face() in production.
"""

import cv2
import numpy as np
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)

from robot_assistant.vision import detector, face_id
from robot_assistant.config import config


def process_image_production_path(image_path, label):
    """Process image using EXACT same path as identify_face() in production.
    
    Returns dict with:
    - label: image identifier
    - frame: the loaded frame
    - yolo_bbox: YOLO detected person bbox
    - faces_detected: number of faces InsightFace found
    - selected_face_bbox: bbox of face selected for this person
    - embedding: normalized 512-dim embedding
    """
    print(f"\n{'='*70}")
    print(f"Processing: {label}")
    print(f"{'='*70}")
    
    # Load image
    frame = cv2.imread(str(image_path))
    if frame is None:
        print(f"ERROR: Could not load {image_path}")
        return None
    
    print(f"Image loaded: {frame.shape[1]}x{frame.shape[0]} (WxH)")
    
    # Step 1: YOLO detection (same as production)
    detections = detector.detect_poses(frame, conf_threshold=0.3)
    
    if len(detections) == 0:
        print("ERROR: No person detected by YOLO")
        return None
    
    yolo_bbox = detections[0]['bbox']
    print(f"YOLO bbox: [{yolo_bbox[0]:.1f}, {yolo_bbox[1]:.1f}, {yolo_bbox[2]:.1f}, {yolo_bbox[3]:.1f}]")
    
    # Step 2: InsightFace on FULL FRAME (same as production)
    face_app = face_id._get_face_app()
    faces = face_app.get(frame)  # Full frame, not cropped
    
    print(f"InsightFace detected: {len(faces)} face(s)")
    for idx, f in enumerate(faces):
        print(f"  Face {idx}: bbox=[{f.bbox[0]:.1f}, {f.bbox[1]:.1f}, {f.bbox[2]:.1f}, {f.bbox[3]:.1f}]")
    
    if len(faces) == 0:
        print("ERROR: No face detected by InsightFace")
        return None
    
    # Step 3: Select face using SHARED function (same as production)
    selected_face = face_id._select_face_for_bbox(faces, yolo_bbox)
    
    if selected_face is None:
        print("ERROR: No face selected by overlap logic")
        return None
    
    # Find which face was selected
    sorted_faces = sorted(faces, key=lambda f: f.bbox[0])
    selected_idx = None
    for idx, f in enumerate(sorted_faces):
        if f is selected_face:
            selected_idx = idx
            break
    
    print(f"Selected: Face {selected_idx}")
    print(f"Selected bbox: [{selected_face.bbox[0]:.1f}, {selected_face.bbox[1]:.1f}, {selected_face.bbox[2]:.1f}, {selected_face.bbox[3]:.1f}]")
    
    # Step 4: Normalize embedding (same as production)
    embedding = selected_face.embedding
    embedding = embedding / np.linalg.norm(embedding)
    
    return {
        'label': label,
        'frame': frame,
        'yolo_bbox': yolo_bbox,
        'faces_detected': len(faces),
        'selected_face_bbox': selected_face.bbox,
        'embedding': embedding
    }


def compute_distance(emb1, emb2):
    """Compute L2 distance between two embeddings."""
    e1 = emb1.reshape(1, -1).astype('float32')
    e2 = emb2.reshape(1, -1).astype('float32')
    return np.linalg.norm(e1 - e2)


def main():
    print("=" * 80)
    print("MODALITY-CONTROLLED TEST: 3 JPG Photos Only")
    print("=" * 80)
    print()
    print("This test uses ONLY JPG files (no webcam mixing)")
    print("to avoid confounding 'different person' with 'different capture pipeline'")
    print()
    print("Uses SAME preprocessing path as identify_face() in production:")
    print("  1. YOLO detects person bbox")
    print("  2. InsightFace processes FULL FRAME")
    print("  3. Select face using bbox overlap")
    print("  4. Normalize embedding")
    print()
    
    # Find JPG files
    test_dir = Path(__file__).parent.parent / 'robot_assistant' / 'data' / 'test_images'
    
    if not test_dir.exists():
        print(f"ERROR: Directory not found: {test_dir}")
        return 1
    
    jpg_files = list(test_dir.glob("*.jpg")) + list(test_dir.glob("*.JPG"))
    
    # Filter to specific files we want
    target_files = [
        'person_A.jpg',
        'WIN_20260706_10_58_33_Pro.jpg',
        'WIN_20260706_10_59_11_Pro.jpg',
        'WIN_20260706_11_37_54_Pro.jpg'
    ]
    
    jpg_files_filtered = []
    for target in target_files:
        matching = [f for f in jpg_files if f.name == target]
        if matching:
            jpg_files_filtered.append(matching[0])
    
    if len(jpg_files_filtered) < 4:
        print(f"ERROR: Need 4 specific JPG files, found {len(jpg_files_filtered)}")
        print("Required files:")
        for target in target_files:
            found = any(f.name == target for f in jpg_files_filtered)
            status = "✓" if found else "✗"
            print(f"  {status} {target}")
        print()
        print(f"Place files in: {test_dir}")
        return 1
    
    jpg_files = jpg_files_filtered
    
    print(f"Found {len(jpg_files)} JPG file(s):")
    for f in jpg_files:
        print(f"  - {f.name}")
    print()
    
    # ========================================================================
    # TEST 1: DETERMINISM CHECK
    # ========================================================================
    print("=" * 80)
    print("TEST 1: DETERMINISM CHECK (Critical - must pass first)")
    print("=" * 80)
    print()
    print("Processing same image TWICE to verify determinism...")
    print()
    
    test_image = jpg_files[0]
    
    result1 = process_image_production_path(test_image, f"{test_image.stem}_run1")
    if result1 is None:
        return 1
    
    result2 = process_image_production_path(test_image, f"{test_image.stem}_run2")
    if result2 is None:
        return 1
    
    determinism_distance = compute_distance(result1['embedding'], result2['embedding'])
    
    print()
    print("=" * 80)
    print("DETERMINISM RESULT")
    print("=" * 80)
    print(f"Same image processed twice:")
    print(f"  Distance: {determinism_distance:.10f}")
    print()
    
    if determinism_distance < 0.001:
        print("✓ DETERMINISM VERIFIED (distance < 0.001)")
        print("  Pipeline is deterministic - safe to proceed")
    elif determinism_distance < 0.01:
        print("⚠ MINOR VARIANCE (0.001 < distance < 0.01)")
        print("  Acceptable but investigate if this increases")
    else:
        print("✗ NONDETERMINISM BUG DETECTED (distance >= 0.01)")
        print("  STOP: Fix nondeterminism before trusting any other results")
        print()
        print("The bug from earlier has NOT been fully fixed.")
        print("Do not proceed with threshold validation until this is resolved.")
        return 1
    
    print()
    
    # ========================================================================
    # TEST 2: DIFFERENT-PERSON DISTANCES
    # ========================================================================
    print("=" * 80)
    print("TEST 2: DIFFERENT-PERSON DISTANCES")
    print("=" * 80)
    print()
    
    # Process all 3 images
    results = []
    for jpg_file in jpg_files:
        result = process_image_production_path(jpg_file, jpg_file.stem)
        if result is None:
            print(f"ERROR: Failed to process {jpg_file.name}")
            return 1
        results.append(result)
    
    # Compute all pairwise distances
    print()
    print("=" * 80)
    print("PAIRWISE L2 DISTANCES (All 6 pairs from 4 images)")
    print("=" * 80)
    
    distances = []
    distance_pairs = []
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            dist = compute_distance(results[i]['embedding'], results[j]['embedding'])
            distances.append(dist)
            distance_pairs.append({
                'i': i,
                'j': j,
                'label_i': results[i]['label'],
                'label_j': results[j]['label'],
                'distance': dist
            })
            print(f"{results[i]['label']:30s} vs {results[j]['label']:30s}: {dist:.6f}")
    
    # Statistics
    print()
    print("=" * 80)
    print("DIFFERENT-PERSON STATISTICS (All 6 pairs)")
    print("=" * 80)
    print(f"Min distance: {min(distances):.6f}")
    print(f"Max distance: {max(distances):.6f}")
    print(f"Mean distance: {np.mean(distances):.6f}")
    print(f"Std deviation: {np.std(distances):.6f}")
    
    # ========================================================================
    # TEST 3: HOLDOUT VALIDATION
    # ========================================================================
    print()
    print("=" * 80)
    print("HOLDOUT VALIDATION")
    print("=" * 80)
    print()
    print("Holdout pair: person_A vs WIN_20260706_11_37_54_Pro")
    print("This pair will NOT be used to calculate the threshold.")
    print()
    
    # Find holdout pair
    holdout_pair = None
    training_distances = []
    
    for pair in distance_pairs:
        is_holdout = (
            ('person_A' in pair['label_i'] and 'WIN_20260706_11_37_54_Pro' in pair['label_j']) or
            ('person_A' in pair['label_j'] and 'WIN_20260706_11_37_54_Pro' in pair['label_i'])
        )
        
        if is_holdout:
            holdout_pair = pair
        else:
            training_distances.append(pair['distance'])
    
    if holdout_pair is None:
        print("ERROR: Could not find holdout pair")
        return 1
    
    print(f"Holdout distance: {holdout_pair['distance']:.6f}")
    print()
    print("Training pairs (5 remaining):")
    for pair in distance_pairs:
        if pair != holdout_pair:
            print(f"  {pair['label_i']:30s} vs {pair['label_j']:30s}: {pair['distance']:.6f}")
    print()
    print(f"Training set min: {min(training_distances):.6f}")
    print(f"Training set max: {max(training_distances):.6f}")
    print(f"Training set mean: {np.mean(training_distances):.6f}")
    
    # ========================================================================
    # TEST 4: COMPARISON WITH SAME-PERSON VARIANCE
    # ========================================================================
    print()
    print("=" * 80)
    print("THRESHOLD CALCULATION (Using Training Set Only)")
    print("=" * 80)
    print()
    print("From earlier webcam-only test_same_person_variance.py:")
    print("  Same-person range: 0.82 - 0.97 (best run: 0.819-0.969)")
    print()
    print("From this test (JPG photos, training set only):")
    print(f"  Different-person range: {min(training_distances):.2f} - {max(training_distances):.2f}")
    print()
    
    # Check for overlap
    same_person_max = 0.97  # From earlier test
    different_person_min_training = min(training_distances)
    
    if different_person_min_training > same_person_max:
        gap = different_person_min_training - same_person_max
        print(f"✓ CLEAN SEPARATION (training set)")
        print(f"  Gap between ranges: {gap:.2f}")
        print(f"  Different-person min ({different_person_min_training:.2f}) > Same-person max ({same_person_max:.2f})")
        print()
        print(f"Evidence-based threshold (from training set):")
        threshold = (same_person_max + different_person_min_training) / 2
        print(f"  Midpoint: {threshold:.2f}")
        margin = min(threshold - same_person_max, different_person_min_training - threshold)
        print(f"  Safety margin: ±{margin:.2f}")
    else:
        overlap = same_person_max - different_person_min_training
        print(f"✗ RANGES OVERLAP")
        print(f"  Overlap: {overlap:.2f}")
        print(f"  Same-person max ({same_person_max:.2f}) >= Different-person min ({different_person_min_training:.2f})")
        threshold = None
    
    # ========================================================================
    # TEST 5: HOLDOUT VALIDATION CHECK
    # ========================================================================
    print()
    print("=" * 80)
    print("HOLDOUT VALIDATION CHECK")
    print("=" * 80)
    print()
    
    if threshold is not None:
        print(f"Threshold (from training set): {threshold:.2f}")
        print(f"Holdout pair distance: {holdout_pair['distance']:.6f}")
        print(f"Holdout pair: {holdout_pair['label_i']} vs {holdout_pair['label_j']}")
        print()
        
        if holdout_pair['distance'] > threshold:
            margin_holdout = holdout_pair['distance'] - threshold
            print(f"✓ HOLDOUT PASSES")
            print(f"  Holdout distance ({holdout_pair['distance']:.2f}) > threshold ({threshold:.2f})")
            print(f"  Margin: {margin_holdout:.2f}")
            print()
            print("The held-out pair is correctly classified as different-person.")
            print("Threshold generalizes to unseen data.")
        else:
            shortfall = threshold - holdout_pair['distance']
            print(f"✗ HOLDOUT FAILS")
            print(f"  Holdout distance ({holdout_pair['distance']:.2f}) <= threshold ({threshold:.2f})")
            print(f"  Shortfall: {shortfall:.2f}")
            print()
            print("The held-out pair would be misclassified as same-person!")
            print("Threshold does NOT generalize - may be overfitting.")
    else:
        print("Cannot validate holdout - ranges overlap, no threshold calculated")
    
    # ========================================================================
    # FINAL COMPARISON WITH ALL DATA
    # ========================================================================
    # ========================================================================
    # FINAL COMPARISON WITH ALL DATA
    # ========================================================================
    print()
    print("=" * 80)
    print("FINAL SUMMARY - ALL DATA")
    print("=" * 80)
    print()
    print("All 6 pairwise distances:")
    for pair in distance_pairs:
        marker = " [HOLDOUT]" if pair == holdout_pair else ""
        print(f"  {pair['label_i']:30s} vs {pair['label_j']:30s}: {pair['distance']:.6f}{marker}")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✓ Determinism: {determinism_distance:.10f} (same image twice)")
    print(f"  Same-person range (webcam): 0.82 - 0.97")
    print(f"  Different-person all pairs (JPG): {min(distances):.2f} - {max(distances):.2f}")
    print(f"  Different-person training only: {min(training_distances):.2f} - {max(training_distances):.2f}")
    
    if threshold is not None:
        print(f"  Threshold from training: {threshold:.2f}")
        if holdout_pair['distance'] > threshold:
            print(f"  Holdout validation: PASS")
        else:
            print(f"  Holdout validation: FAIL")
        print(f"  Status: Clean separation, threshold calculable")
    else:
        print(f"  Status: Overlap detected, need tradeoff analysis")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
