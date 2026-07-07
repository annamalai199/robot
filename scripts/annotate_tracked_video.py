"""Annotate video with YOLO bounding boxes and track IDs for visual verification.

Runs tracker.update() on each frame and draws:
- Bounding boxes around each detected person
- Track ID number above each bbox
- Frame number in top-left corner

Outputs annotated video file for visual inspection of track ID consistency.
"""

import cv2
import sys
import argparse
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import tracker
from robot_assistant.config import config


def draw_tracked_objects(frame, tracked_objects, frame_num):
    """Draw bounding boxes and track IDs on frame.
    
    Args:
        frame: BGR frame to annotate
        tracked_objects: List of tracked objects from tracker.update()
        frame_num: Current frame number
    
    Returns:
        Annotated frame
    """
    annotated = frame.copy()
    
    # Draw frame number in top-left
    cv2.putText(annotated, f"Frame {frame_num}", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Draw each tracked object
    for obj in tracked_objects:
        track_id = obj['track_id']
        bbox = obj['bbox']
        x1, y1, x2, y2 = map(int, bbox)
        
        # Choose color based on track ID (different color per ID)
        colors = [
            (0, 255, 0),    # Green for track 1
            (255, 0, 0),    # Blue for track 2
            (0, 0, 255),    # Red for track 3
            (255, 255, 0),  # Cyan for track 4
            (255, 0, 255),  # Magenta for track 5
        ]
        color = colors[(track_id - 1) % len(colors)]
        
        # Draw bounding box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
        
        # Draw track ID label with background
        label = f"ID: {track_id}"
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
        label_w, label_h = label_size
        
        # Draw filled rectangle behind text
        cv2.rectangle(annotated, 
                     (x1, y1 - label_h - 10), 
                     (x1 + label_w + 10, y1),
                     color, -1)
        
        # Draw text
        cv2.putText(annotated, label, (x1 + 5, y1 - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    
    # Draw track count in top-right
    track_count_text = f"Tracks: {len(tracked_objects)}"
    cv2.putText(annotated, track_count_text, (annotated.shape[1] - 200, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    return annotated


def main():
    parser = argparse.ArgumentParser(
        description='Annotate video with track IDs for visual verification'
    )
    parser.add_argument('input', type=str, help='Input video path')
    parser.add_argument('output', type=str, help='Output annotated video path')
    parser.add_argument('--conf', type=float, default=0.5,
                       help='Detection confidence threshold (default: 0.5)')
    parser.add_argument('--preview', action='store_true',
                       help='Show live preview while processing')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    print("=" * 80)
    print("VIDEO TRACK ANNOTATION")
    print("=" * 80)
    print()
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Confidence threshold: {args.conf}")
    print()
    
    # Check input exists
    if not input_path.exists():
        print(f"✗ Input video not found: {input_path}")
        return 1
    
    # Open input video
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        print(f"✗ Failed to open input video: {input_path}")
        return 1
    
    # Get video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count_total / fps
    
    print(f"Video: {width}x{height} @ {fps:.1f} FPS")
    print(f"Duration: {duration:.1f}s ({frame_count_total} frames)")
    print()
    
    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Setup video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    
    if not out.isOpened():
        print(f"✗ Failed to open video writer: {output_path}")
        cap.release()
        return 1
    
    print("-" * 80)
    print("PROCESSING...")
    print("-" * 80)
    print()
    
    frame_num = 0
    track_id_history = set()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_num += 1
            
            # Show progress
            if frame_num % 50 == 0:
                print(f"  Frame {frame_num}/{frame_count_total} ({100*frame_num/frame_count_total:.1f}%)")
            
            # Run tracker (runs YOLO internally every K frames)
            run_yolo = (frame_num % config.YOLO_FRAME_INTERVAL_K == 0)
            
            if run_yolo:
                tracked_objects = tracker.update(frame, conf_threshold=args.conf)
                
                # Record track IDs seen
                for obj in tracked_objects:
                    track_id = obj['track_id']
                    if track_id not in track_id_history:
                        print(f"  [NEW TRACK] Frame {frame_num}: track_id={track_id}")
                        track_id_history.add(track_id)
            else:
                # No YOLO this frame - use empty list (no annotations)
                tracked_objects = []
            
            # Annotate frame
            annotated = draw_tracked_objects(frame, tracked_objects, frame_num)
            
            # Write to output
            out.write(annotated)
            
            # Show preview if requested
            if args.preview:
                cv2.imshow('Annotated Video (press q to stop)', annotated)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\n⚠ Stopped by user")
                    break
    
    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")
    
    finally:
        cap.release()
        out.release()
        if args.preview:
            cv2.destroyAllWindows()
        
        print()
        print("=" * 80)
        print("ANNOTATION COMPLETE")
        print("=" * 80)
        print()
        print(f"Processed: {frame_num} frames")
        print(f"Unique track IDs seen: {sorted(track_id_history)}")
        print()
        
        # Verify output file
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"✓ Output saved: {output_path}")
            print(f"  Size: {size_mb:.1f} MB")
            print()
            print("NEXT STEPS:")
            print("1. Play the annotated video")
            print("2. Watch the crossing segment carefully")
            print("3. Verify track IDs stay consistent:")
            print("   ✓ GOOD: Person A stays 'ID: 1', Person B stays 'ID: 2'")
            print("   ✗ BAD: IDs swap (Person A becomes 'ID: 2', Person B becomes 'ID: 1')")
            print()
            print(f"Track IDs detected: {sorted(track_id_history)}")
            if len(track_id_history) >= 2:
                print("✓ Multiple tracks found - crossing validation possible")
            else:
                print("⚠ Only single track found - may be single-person video")
        else:
            print("✗ Output file not created")
            return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
