"""Real-time smoke test for vision pipeline modules.

Tests capture -> motion_gate -> detector -> tracker with actual webcam feed.
This validates real YOLO/ByteTrack integration that mocked tests cannot catch.
"""

import cv2
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import capture, motion_gate, detector, tracker
from robot_assistant.config import config


def main():
    print("=" * 80)
    print("VISION PIPELINE SMOKE TEST")
    print("=" * 80)
    print()
    print("This test runs actual webcam feed through:")
    print("  1. capture.get_frame_generator() - video capture")
    print("  2. motion_gate.has_motion() - frame difference detection")
    print("  3. detector.detect_poses() - YOLO11n-pose inference")
    print("  4. tracker.update() - ByteTrack tracking")
    print()
    print("Duration: 15 seconds")
    print("Position yourself in front of webcam, move around to trigger motion")
    print()
    input("Press Enter to start...")
    print()
    
    # Check camera available
    if not capture.check_camera_available():
        print("ERROR: No webcam found")
        return 1
    
    print("Opening webcam...")
    
    try:
        # Get frame generator
        frame_gen = capture.get_frame_generator()
        
        # Initialize state
        prev_frame = None
        frame_count = 0
        motion_detected_count = 0
        yolo_run_count = 0
        people_detected_total = 0
        tracks_seen = set()
        
        start_time = time.time()
        duration = 15  # seconds
        
        print("Recording started...")
        print("-" * 80)
        
        for frame in frame_gen:
            frame_count += 1
            elapsed = time.time() - start_time
            
            # Stop after duration
            if elapsed > duration:
                break
            
            # Motion gate (skip first frame)
            if prev_frame is not None:
                has_motion_result = motion_gate.has_motion(frame, prev_frame)
                
                if has_motion_result:
                    motion_detected_count += 1
                    motion_status = "MOTION"
                else:
                    motion_status = "static"
            else:
                has_motion_result = True  # First frame always processes
                motion_status = "MOTION (first frame)"
            
            # YOLO detection (every Kth frame if motion)
            detections = []
            if has_motion_result and frame_count % config.YOLO_FRAME_INTERVAL_K == 0:
                yolo_run_count += 1
                detections = detector.detect_poses(frame, conf_threshold=0.5)
                people_detected_total += len(detections)
                
                print(f"Frame {frame_count:3d} ({elapsed:.1f}s): {motion_status:20s} | "
                      f"YOLO: {len(detections)} person(s) detected")
                
                for i, det in enumerate(detections):
                    bbox = det['bbox']
                    conf = det['confidence']
                    print(f"  Person {i+1}: bbox=[{bbox[0]:.0f}, {bbox[1]:.0f}, "
                          f"{bbox[2]:.0f}, {bbox[3]:.0f}], conf={conf:.2f}")
            else:
                if frame_count % 10 == 0:  # Print status every 10 frames
                    print(f"Frame {frame_count:3d} ({elapsed:.1f}s): {motion_status:20s} | "
                          f"YOLO: skipped")
            
            # Tracking (run on frames where YOLO ran)
            if detections:
                tracked = tracker.update(frame, conf_threshold=0.5)
                
                for obj in tracked:
                    track_id = obj['track_id']
                    tracks_seen.add(track_id)
                    bbox = obj['bbox']
                    keypoints = obj['keypoints']
                    
                    # Check keypoint validity (at least some visible)
                    visible_kpts = sum(1 for kpt in keypoints if kpt[2] > 0.5)
                    
                    print(f"    Track {track_id}: bbox=[{bbox[0]:.0f}, {bbox[1]:.0f}, "
                          f"{bbox[2]:.0f}, {bbox[3]:.0f}], keypoints={visible_kpts}/17 visible")
            
            prev_frame = frame
            
            # Display frame (optional visualization)
            # cv2.imshow('Vision Pipeline Test', frame)
            # if cv2.waitKey(1) & 0xFF == ord('q'):
            #     break
        
        # cv2.destroyAllWindows()
        
        # Summary
        print()
        print("=" * 80)
        print("SMOKE TEST SUMMARY")
        print("=" * 80)
        print(f"Total frames processed: {frame_count}")
        print(f"Duration: {elapsed:.1f}s")
        print(f"Average FPS: {frame_count / elapsed:.1f}")
        print()
        print(f"Motion detected: {motion_detected_count}/{frame_count} frames "
              f"({100*motion_detected_count/frame_count:.1f}%)")
        print(f"YOLO runs: {yolo_run_count} (expected: {frame_count // config.YOLO_FRAME_INTERVAL_K})")
        print(f"People detections (total): {people_detected_total}")
        print(f"Unique track IDs seen: {len(tracks_seen)} - {sorted(tracks_seen)}")
        print()
        
        # Validation checks
        errors = []
        
        if frame_count < 100:
            errors.append(f"Too few frames ({frame_count} < 100) - webcam may have issues")
        
        if motion_detected_count == 0:
            errors.append("No motion detected - motion_gate may be broken or you didn't move")
        
        if yolo_run_count == 0:
            errors.append("YOLO never ran - detector may be broken or no motion detected")
        
        if people_detected_total == 0 and motion_detected_count > 0:
            errors.append("Motion detected but no people found - you may not be visible to camera")
        
        if len(tracks_seen) == 0 and people_detected_total > 0:
            errors.append("People detected but no tracks assigned - tracker may be broken")
        
        if errors:
            print("⚠ WARNINGS:")
            for err in errors:
                print(f"  - {err}")
            print()
        
        # Overall result
        if yolo_run_count > 0 and len(tracks_seen) > 0:
            print("✓ SMOKE TEST PASSED")
            print("  All modules working: capture, motion_gate, detector, tracker")
            print()
            print("Notes:")
            print("  - Mocked unit tests verify logic correctness")
            print("  - This smoke test verifies real hardware/model integration")
            print("  - Both are necessary for confidence in the implementation")
            return 0
        else:
            print("✗ SMOKE TEST FAILED")
            print("  One or more modules did not produce expected output")
            return 1
    
    except Exception as e:
        print()
        print("=" * 80)
        print("✗ SMOKE TEST FAILED WITH EXCEPTION")
        print("=" * 80)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
