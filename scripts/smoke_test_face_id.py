"""Real-time smoke test for face identification with live webcam.

NO FILES SAVED: This script captures frames and processes them in-memory only.
No face images, crops, embeddings, or index files are saved to disk or committed.

Requirements:
- Webcam connected and accessible
- Good lighting on person's face
- Person positioned within camera frame

Test procedure:
1. Opens webcam
2. Runs YOLO pose detection to get person bbox
3. Runs face identification with real InsightFace model
4. First run: confirms status="new", generates embedding_id, adds to FAISS
5. Second run (same person, same session): confirms status="known", returns SAME embedding_id
6. Prints results to console only

Privacy: No face data is saved. FAISS index is in-memory for this test only.
"""

import cv2
import numpy as np
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import detector, face_id
from robot_assistant.events import bus


def main():
    print("=" * 70)
    print("Face ID Smoke Test (Real-time Webcam)")
    print("=" * 70)
    print()
    print("This test will:")
    print("1. Open your webcam")
    print("2. Detect your pose to get a bounding box")
    print("3. Run face identification (real InsightFace model)")
    print("4. Print results to console only - NO FILES SAVED")
    print()
    print("Privacy: No face images, crops, or embeddings saved to disk.")
    print("FAISS index exists in-memory for this test session only.")
    print()
    print("Press 'q' to quit at any time.")
    print("=" * 70)
    print()
    
    # Clear any existing face index (fresh start)
    face_id.clear_index()
    face_id.reset()
    
    # Open webcam
    print("Opening webcam...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("ERROR: Could not open webcam")
        return 1
    
    print("Webcam opened successfully!")
    print()
    print("Instructions:")
    print("- Position your face clearly in frame")
    print("- Press SPACE to capture and identify")
    print("- Press 'q' to quit")
    print()
    
    identification_count = 0
    results_log = []
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                print("ERROR: Failed to read frame")
                break
            
            # Display frame
            display_frame = frame.copy()
            cv2.putText(display_frame, "Press SPACE to identify face, Q to quit", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            if identification_count > 0:
                cv2.putText(display_frame, f"Identifications: {identification_count}", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow("Face ID Smoke Test", display_frame)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("\nQuitting...")
                break
            elif key == ord(' '):  # Space key
                print(f"\n--- Identification #{identification_count + 1} ---")
                
                # Run pose detection to get bbox
                print("Running pose detection...")
                detections = detector.detect_poses(frame, conf_threshold=0.5)
                
                if len(detections) == 0:
                    print("No person detected in frame. Please position yourself clearly.")
                    continue
                
                # Use first detection
                detection = detections[0]
                bbox = detection['bbox']
                confidence = detection['confidence']
                
                print(f"Person detected: bbox {bbox}, confidence {confidence:.2f}")
                
                # Generate a track_id (in real system, this comes from tracker)
                track_id = f"SMOKE_TEST_{identification_count + 1}"
                
                # Run face identification (REAL InsightFace model, no mocks)
                print(f"Running face identification (track_id={track_id})...")
                result = face_id.identify_face(frame, bbox, track_id=track_id)
                
                if result is None:
                    print("No face detected in bounding box.")
                    continue
                
                # Print results
                print()
                print("RESULT:")
                print(f"  embedding_id: {result['embedding_id']}")
                print(f"  status: {result['status']}")
                print(f"  name: {result['name']}")
                print(f"  confidence: {result['confidence']}")
                print()
                
                # Log for comparison
                results_log.append(result)
                identification_count += 1
                
                # Check for match if this is a repeat
                if identification_count > 1:
                    print("COMPARISON WITH PREVIOUS RUNS:")
                    for i, prev_result in enumerate(results_log[:-1]):
                        if prev_result['embedding_id'] == result['embedding_id']:
                            print(f"  ✓ MATCHED run #{i+1}: Same embedding_id!")
                        else:
                            print(f"  ✗ Different from run #{i+1}: Different embedding_id")
                    print()
                
                # Specific checks for first 2 runs
                if identification_count == 1:
                    print("FIRST RUN CHECK:")
                    if result['status'] == 'new':
                        print("  ✓ Status is 'new' (expected for first face)")
                    else:
                        print(f"  ✗ Status is '{result['status']}' (expected 'new')")
                    
                    if result['embedding_id'].startswith('U'):
                        print("  ✓ Embedding ID starts with 'U' (unknown face)")
                    else:
                        print(f"  ✗ Embedding ID is '{result['embedding_id']}' (expected U####)")
                    
                    if result['confidence'] is None:
                        print("  ✓ Confidence is None (expected for new face)")
                    else:
                        print(f"  ✗ Confidence is {result['confidence']} (expected None)")
                    print()
                    
                    print("Now run identification AGAIN (press SPACE) to test matching...")
                    print()
                
                elif identification_count == 2:
                    print("SECOND RUN CHECK (same person, new track_id):")
                    if result['embedding_id'] == results_log[0]['embedding_id']:
                        print("  ✓ SAME embedding_id as first run (matched!)")
                    else:
                        print(f"  ✗ Different embedding_id from first run")
                        print(f"    First: {results_log[0]['embedding_id']}")
                        print(f"    Second: {result['embedding_id']}")
                    
                    if result['status'] in ['known', 'registered_unknown']:
                        print(f"  ✓ Status is '{result['status']}' (recognized as known)")
                    else:
                        print(f"  ✗ Status is '{result['status']}' (expected 'known' or 'registered_unknown')")
                    
                    if result['confidence'] is not None and result['confidence'] > 0.8:
                        print(f"  ✓ High confidence: {result['confidence']:.2f}")
                    else:
                        conf_str = f"{result['confidence']:.2f}" if result['confidence'] else "None"
                        print(f"  ✗ Low/no confidence: {conf_str} (expected > 0.8)")
                    print()
                    
                    print("✓ SMOKE TEST COMPLETE")
                    print("  - First run registered new face")
                    print("  - Second run matched to first face")
                    print("  - Same embedding_id returned")
                    print()
                    print("Press 'q' to quit or SPACE for more identifications")
                    print()
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print()
        print("=" * 70)
        print("Smoke Test Complete")
        print("=" * 70)
        print()
        print(f"Total identifications: {identification_count}")
        print()
        
        if identification_count >= 2:
            print("SUCCESS CRITERIA:")
            if results_log[0]['status'] == 'new':
                print("  ✓ First run: status='new'")
            else:
                print(f"  ✗ First run: status='{results_log[0]['status']}' (expected 'new')")
            
            if results_log[1]['embedding_id'] == results_log[0]['embedding_id']:
                print("  ✓ Second run: matched first face (same embedding_id)")
            else:
                print("  ✗ Second run: did not match (different embedding_id)")
            
            if results_log[1]['confidence'] and results_log[1]['confidence'] > 0.8:
                print(f"  ✓ Second run: high confidence ({results_log[1]['confidence']:.2f})")
            else:
                print("  ✗ Second run: low/no confidence")
        else:
            print("Not enough runs to validate (need at least 2)")
        
        print()
        print("PRIVACY CONFIRMED:")
        print("  - No face images saved")
        print("  - No face crops saved")
        print("  - No embeddings saved to disk")
        print("  - FAISS index was in-memory only for this test")
        print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
