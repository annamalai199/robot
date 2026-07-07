"""Record test video for vision latency benchmark.

Records from webcam with live preview showing elapsed time.
Press 'q' to stop early, or wait for full duration.
"""

import cv2
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import capture


def main():
    parser = argparse.ArgumentParser(description='Record test video for benchmarking')
    parser.add_argument('--duration', type=int, default=60,
                       help='Recording duration in seconds (default: 60)')
    parser.add_argument('--output', type=str, required=True,
                       help='Output video path (e.g., test_videos/video.mp4)')
    parser.add_argument('--fps', type=int, default=30,
                       help='Recording FPS (default: 30)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("TEST VIDEO RECORDING")
    print("=" * 80)
    print()
    print(f"Duration: {args.duration} seconds")
    print(f"Output: {args.output}")
    print(f"FPS: {args.fps}")
    print()
    print("RECORDING REQUIREMENTS:")
    print("  ✓ 1-2 people visible")
    print("  ✓ Hand raise gesture (at least once)")
    print("  ✓ Face clearly visible")
    print("  ✓ CROSSING/OVERLAP segment (5-10 seconds)")
    print()
    print("Controls:")
    print("  - Recording will start automatically after countdown")
    print("  - Press 'q' to stop early")
    print("  - Video preview shows elapsed time")
    print()
    
    # Check camera
    if not capture.check_camera_available():
        print("✗ No webcam found")
        return 1
    
    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Open camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("✗ Failed to open camera")
        return 1
    
    # Get camera properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Camera: {width}x{height} @ {actual_fps:.1f} FPS")
    print()
    
    # Setup video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, args.fps, (width, height))
    
    if not out.isOpened():
        print("✗ Failed to open video writer")
        cap.release()
        return 1
    
    print("Ready to record!")
    print()
    
    # Countdown
    for i in range(3, 0, -1):
        print(f"Starting in {i}...")
        time.sleep(1)
    
    print()
    print("=" * 80)
    print("🔴 RECORDING")
    print("=" * 80)
    print()
    
    start_time = time.time()
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("✗ Failed to read frame")
                break
            
            elapsed = time.time() - start_time
            
            # Check if duration reached
            if elapsed >= args.duration:
                print(f"\n✓ Duration reached: {elapsed:.1f}s")
                break
            
            # Add elapsed time overlay
            time_text = f"{elapsed:.1f}s / {args.duration}s"
            cv2.putText(frame, time_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Write frame
            out.write(frame)
            frame_count += 1
            
            # Show preview
            cv2.imshow('Recording (press q to stop)', frame)
            
            # Check for early stop
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print(f"\n⚠ Stopped early at {elapsed:.1f}s")
                break
            
            # Progress indicator every 5 seconds
            if int(elapsed) % 5 == 0 and int(elapsed) > 0:
                if frame_count % int(actual_fps * 5) < 2:  # Print once per 5-second mark
                    print(f"  {int(elapsed)}s...")
    
    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")
    
    finally:
        # Cleanup
        elapsed_total = time.time() - start_time
        cap.release()
        out.release()
        cv2.destroyAllWindows()
        
        print()
        print("=" * 80)
        print("RECORDING COMPLETE")
        print("=" * 80)
        print()
        print(f"Duration: {elapsed_total:.1f}s")
        print(f"Frames: {frame_count}")
        print(f"Average FPS: {frame_count / elapsed_total:.1f}")
        print(f"Output: {output_path}")
        print()
        
        # Verify file exists
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"✓ File saved: {size_mb:.1f} MB")
            print()
            print("NEXT STEPS:")
            print("1. Play the video to verify quality")
            print("2. Check requirements:")
            print("   - Hand raise visible?")
            print("   - Face visible?")
            print("   - Crossing/overlap segment clear?")
            print("3. If good, proceed to run bench_latency.py")
            print("4. If bad, record again")
        else:
            print("✗ File not saved - recording may have failed")
            return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
