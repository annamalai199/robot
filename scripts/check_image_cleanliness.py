"""Quick check if test images are clean (single-subject) or crowded.

Runs InsightFace detection and reports how many faces are detected.
Use this to verify images are suitable for embedding separation testing.
"""

import cv2
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import face_id


def check_image(image_path):
    """Check how many faces are detected in an image."""
    print(f"\n{'='*60}")
    print(f"Checking: {image_path.name}")
    print(f"{'='*60}")
    
    # Load image
    frame = cv2.imread(str(image_path))
    if frame is None:
        print(f"ERROR: Could not load image")
        return False
    
    print(f"Image size: {frame.shape[1]}x{frame.shape[0]}")
    
    # Detect faces
    face_app = face_id._get_face_app()
    faces = face_app.get(frame)
    
    print(f"Faces detected: {len(faces)}")
    
    if len(faces) == 0:
        print("⚠ NO FACES - image may not be suitable")
        return False
    elif len(faces) == 1:
        print("✓ CLEAN - single face detected (ideal for testing)")
        face = faces[0]
        print(f"  Face bbox: {face.bbox}")
        return True
    else:
        print(f"✗ CROWDED - {len(faces)} faces detected")
        print("  This image has ambiguity - crop to single subject or retake")
        print("  Detected faces:")
        for i, face in enumerate(faces):
            print(f"    Face {i}: bbox={face.bbox}")
        return False


def main():
    print("=" * 80)
    print("IMAGE CLEANLINESS CHECKER")
    print("=" * 80)
    print()
    print("This script checks if images are suitable for embedding separation testing.")
    print("Ideal: 1 face detected (clean single-subject)")
    print("Problem: 2+ faces detected (crowded, ambiguous)")
    print()
    
    # Check test_images directory
    test_dir = Path(__file__).parent.parent / 'robot_assistant' / 'data' / 'test_images'
    
    if not test_dir.exists():
        print(f"Directory not found: {test_dir}")
        print("No test images to check.")
        return 0
    
    # Find all image files
    image_files = list(test_dir.glob("*.jpg")) + list(test_dir.glob("*.png"))
    
    if len(image_files) == 0:
        print(f"No images found in: {test_dir}")
        return 0
    
    print(f"Found {len(image_files)} image(s) to check:")
    for img in image_files:
        print(f"  - {img.name}")
    print()
    
    # Check each image
    results = []
    for img_path in image_files:
        is_clean = check_image(img_path)
        results.append((img_path.name, is_clean))
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    clean_count = sum(1 for _, is_clean in results if is_clean)
    crowded_count = len([r for r in results if not r[1] and r[0] not in ['ERROR']])
    
    print(f"Clean (1 face):   {clean_count}")
    print(f"Crowded (2+ faces): {crowded_count}")
    print()
    
    if clean_count >= 2:
        print("✓ You have enough clean images for different-person testing")
        print(f"  Ready to run: python scripts\\test_different_person.py")
    else:
        print("⚠ Need at least 2 clean single-subject images")
        print("  Options:")
        print("  1. Crop existing images to remove background people")
        print("  2. Capture new photos with empty/simple background")
        print("  3. Use Mode 3 in test_different_person.py (webcam + 1-2 photos)")
    
    print()
    print("See TESTING_INSTRUCTIONS_CLEAN_IMAGES.md for details")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
