"""Test different-person discrimination with static images.

Downloads/loads photos of genuinely different people and measures
L2 distances to validate that the threshold separates different identities.
"""

import cv2
import numpy as np
import sys
import logging
from pathlib import Path
import urllib.request

sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s - %(name)s - %(message)s'
)

from robot_assistant.vision import detector, face_id
from robot_assistant.config import config


def download_test_image(url, save_path):
    """Download an image from URL."""
    print(f"Downloading from {url}...")
    try:
        urllib.request.urlretrieve(url, save_path)
        print(f"Saved to {save_path}")
        return True
    except Exception as e:
        print(f"ERROR downloading: {e}")
        return False


def process_image(image_path, person_label):
    """Process an image through the full pipeline."""
    print(f"\n{'='*60}")
    print(f"Processing {person_label}: {image_path}")
    print(f"{'='*60}")
    
    # Load image
    frame = cv2.imread(str(image_path))
    if frame is None:
        print(f"ERROR: Could not load {image_path}")
        return None
    
    print(f"Image loaded: {frame.shape}")
    
    # Detect person bbox with YOLO
    detections = detector.detect_poses(frame, conf_threshold=0.3)  # Lower threshold for photos
    
    if len(detections) == 0:
        print("ERROR: No person detected")
        return None
    
    bbox = detections[0]['bbox']
    print(f"YOLO bbox: {bbox}")
    
    # Get embedding via identify_face
    track_id = f"PHOTO_{person_label}"
    result = face_id.identify_face(frame, bbox, track_id)
    
    if result is None:
        print("ERROR: No face identified")
        return None
    
    print(f"Result: {result['embedding_id']}, status={result['status']}")
    if result['confidence'] is not None:
        distance = (1.0 - result['confidence']) * config.FACE_MATCH_THRESHOLD
        print(f"  Match to existing: distance={distance:.6f}, confidence={result['confidence']:.4f}")
    
    # Extract raw embedding for pairwise comparison using SAME selection logic
    face_app = face_id._get_face_app()
    faces = face_app.get(frame)
    
    print(f"InsightFace detected {len(faces)} face(s) for pairwise comparison")
    for idx, f in enumerate(faces):
        print(f"  Face {idx}: bbox={f.bbox}")
    
    if len(faces) == 0:
        print("ERROR: InsightFace found no faces")
        return None
    
    # Use SHARED face selection function (not duplicated logic!)
    selected_face = face_id._select_face_for_bbox(faces, bbox)
    
    if selected_face is None:
        print("ERROR: No face selected by overlap logic")
        return None
    
    # Find which face was selected for logging
    sorted_faces = sorted(faces, key=lambda f: f.bbox[0])
    selected_idx = None
    for idx, f in enumerate(sorted_faces):
        if f is selected_face:
            selected_idx = idx
            break
    
    print(f"Selected face {selected_idx} for pairwise comparison: bbox={selected_face.bbox}")
    
    # Normalize embedding (same as identify_face does)
    embedding = selected_face.embedding
    embedding = embedding / np.linalg.norm(embedding)
    
    return {
        'label': person_label,
        'path': image_path,
        'result': result,
        'embedding': embedding
    }


def compute_distance(emb1, emb2):
    """Compute L2 distance between two embeddings."""
    e1 = emb1.reshape(1, -1).astype('float32')
    e2 = emb2.reshape(1, -1).astype('float32')
    return np.linalg.norm(e1 - e2)


def main():
    print("=" * 80)
    print("DIFFERENT-PERSON DISCRIMINATION TEST")
    print("=" * 80)
    print()
    print("This test uses static photos of different people to measure")
    print("separation between different identities.")
    print()
    
    # Create test images directory
    test_dir = Path(__file__).parent.parent / 'robot_assistant' / 'data' / 'test_images'
    test_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Test images will be saved to: {test_dir}")
    print()
    
    # Option 1: Use existing images if available
    print("Options:")
    print("1. Use your own images (place JPG files in data/test_images/)")
    print("2. Download sample face images from a URL")
    print("3. Use webcam to capture Person A, then use photos for Person B/C")
    print()
    
    mode = input("Choose mode (1/2/3): ").strip()
    
    if mode == "1":
        # Use existing images
        print("\nLooking for images in test_images/...")
        image_files = list(test_dir.glob("*.jpg")) + list(test_dir.glob("*.png"))
        
        if len(image_files) < 2:
            print(f"ERROR: Need at least 2 images, found {len(image_files)}")
            print(f"Place images in: {test_dir}")
            return 1
        
        print(f"Found {len(image_files)} images:")
        for img in image_files:
            print(f"  - {img.name}")
        
    elif mode == "2":
        # Download sample images
        print("\nYou can provide URLs to download, or use default celebrity photos.")
        print("Example URLs (publicly available):")
        print("  - Wikipedia portraits")
        print("  - Public domain celebrity photos")
        print("  - Stock photo sites with clear license")
        print()
        
        urls = []
        print("Enter image URLs (or press Enter to skip):")
        for i in range(3):
            url = input(f"  URL {i+1}: ").strip()
            if url:
                urls.append(url)
            else:
                break
        
        if len(urls) < 2:
            print("Need at least 2 URLs for different-person test")
            return 1
        
        # Download images
        image_files = []
        for i, url in enumerate(urls):
            save_path = test_dir / f"person_{chr(65+i)}.jpg"
            if download_test_image(url, save_path):
                image_files.append(save_path)
        
        if len(image_files) < 2:
            print("Failed to download enough images")
            return 1
            
    elif mode == "3":
        # Capture Person A from webcam, then use photos for others
        print("\nFirst, capture Person A from webcam...")
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("ERROR: Cannot open webcam")
            return 1
        
        print("Position face, press SPACE to capture Person A")
        
        frame_a = None
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            cv2.imshow('Capture Person A', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):
                frame_a = frame.copy()
                cv2.imwrite(str(test_dir / 'person_A.jpg'), frame_a)
                print("Person A captured and saved")
                break
            elif key == ord('q'):
                cap.release()
                cv2.destroyAllWindows()
                return 1
        
        cap.release()
        cv2.destroyAllWindows()
        
        print("\nNow provide photos of different people (Person B, C, etc.)")
        print(f"Place JPG files in: {test_dir}")
        input("Press Enter when ready...")
        
        image_files = list(test_dir.glob("*.jpg")) + list(test_dir.glob("*.png"))
        
        if len(image_files) < 2:
            print(f"ERROR: Need at least 2 images total, found {len(image_files)}")
            return 1
    
    else:
        print("Invalid mode")
        return 1
    
    # Clear FAISS index to start fresh
    print("\nClearing FAISS index...")
    face_id.clear_index()
    face_id.reset()
    
    # Process all images
    print("\n" + "=" * 80)
    print("PROCESSING ALL IMAGES")
    print("=" * 80)
    
    results = []
    for img_path in image_files[:5]:  # Limit to 5 images
        result = process_image(img_path, img_path.stem)
        if result:
            results.append(result)
            face_id.reset()  # Clear track cache between images
    
    if len(results) < 2:
        print("\nERROR: Need at least 2 successful processed images")
        return 1
    
    # Compute all pairwise distances
    print("\n" + "=" * 80)
    print("PAIRWISE L2 DISTANCES")
    print("=" * 80)
    
    distances = []
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            label_i = results[i]['label']
            label_j = results[j]['label']
            
            distance = compute_distance(results[i]['embedding'], results[j]['embedding'])
            distances.append({
                'pair': f"{label_i} vs {label_j}",
                'distance': distance
            })
            
            print(f"{label_i:15s} vs {label_j:15s}: {distance:.6f}")
    
    # Analysis
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    
    all_dists = [d['distance'] for d in distances]
    print(f"Min distance: {min(all_dists):.6f}")
    print(f"Max distance: {max(all_dists):.6f}")
    print(f"Mean distance: {np.mean(all_dists):.6f}")
    
    print(f"\nCurrent threshold: {config.FACE_MATCH_THRESHOLD}")
    print()
    
    # Check if any distances are below threshold (false positives)
    false_positives = [d for d in distances if d['distance'] < config.FACE_MATCH_THRESHOLD]
    
    if false_positives:
        print("⚠ WARNING: Some different-person pairs matched (FALSE POSITIVES):")
        for fp in false_positives:
            print(f"  {fp['pair']}: distance={fp['distance']:.6f} < threshold")
        print()
        print("This means the threshold is TOO LOOSE.")
        print(f"Suggested threshold: {min(all_dists) * 0.95:.2f} (just below min different-person distance)")
    else:
        print("✓ All different-person pairs have distance >= threshold")
        print(f"  Min different-person distance: {min(all_dists):.6f}")
        print(f"  Threshold: {config.FACE_MATCH_THRESHOLD}")
        print(f"  Margin: {min(all_dists) - config.FACE_MATCH_THRESHOLD:.6f}")
    
    print("\n" + "=" * 80)
    print("NEXT STEP: Combine with same-person variance data")
    print("=" * 80)
    print("Run test_same_person_variance.py to get max same-person distance.")
    print("Then set threshold between max(same-person) and min(different-person).")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
