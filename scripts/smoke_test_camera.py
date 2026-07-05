"""Smoke test for video capture.

Tests that get_frame_generator() works correctly:
- Opens camera successfully
- Yields non-empty numpy arrays
- Frames have sane shape (height, width, 3 channels BGR)
- Can capture multiple frames
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from robot_assistant.vision.capture import get_frame_generator, check_camera_available, list_available_cameras


def smoke_test_camera():
    """Run smoke test on camera capture."""
    print("=" * 60)
    print("CAMERA SMOKE TEST")
    print("=" * 60)
    
    # Check available cameras
    print("\n1. Checking available cameras...")
    available = list_available_cameras()
    
    if not available:
        print("❌ No cameras found! Test cannot proceed.")
        print("   Make sure a webcam is connected and not in use.")
        return False
    
    print(f"✓ Found {len(available)} camera(s): {available}")
    camera_idx = available[0]
    
    # Check primary camera explicitly
    print(f"\n2. Checking camera {camera_idx}...")
    if not check_camera_available(camera_idx):
        print(f"❌ Camera {camera_idx} is not available!")
        return False
    
    print(f"✓ Camera {camera_idx} is available")
    
    # Test frame capture
    print(f"\n3. Capturing frames from camera {camera_idx}...")
    try:
        gen = get_frame_generator(camera_idx)
        
        # Capture first few frames
        frames_to_test = 5
        captured_frames = []
        
        for i in range(frames_to_test):
            frame = next(gen)
            captured_frames.append(frame)
            print(f"   Frame {i+1}: shape={frame.shape}, dtype={frame.dtype}, "
                  f"min={frame.min()}, max={frame.max()}, mean={frame.mean():.1f}")
        
        # Stop generator
        gen.close()
        
        # Validate frames
        print("\n4. Validating frames...")
        
        for i, frame in enumerate(captured_frames):
            # Check it's a numpy array
            if not hasattr(frame, 'shape'):
                print(f"❌ Frame {i+1} is not a numpy array!")
                return False
            
            # Check shape is valid (height, width, 3)
            if len(frame.shape) != 3:
                print(f"❌ Frame {i+1} has invalid shape {frame.shape} (expected 3D array)!")
                return False
            
            height, width, channels = frame.shape
            
            if channels != 3:
                print(f"❌ Frame {i+1} has {channels} channels (expected 3 for BGR)!")
                return False
            
            # Check dimensions are reasonable (at least 320x240, at most 4K)
            if width < 320 or height < 240:
                print(f"❌ Frame {i+1} resolution too small: {width}x{height}")
                return False
            
            if width > 4096 or height > 4096:
                print(f"❌ Frame {i+1} resolution suspiciously large: {width}x{height}")
                return False
            
            # Check pixel values are in valid range [0, 255]
            if frame.min() < 0 or frame.max() > 255:
                print(f"❌ Frame {i+1} has invalid pixel values (min={frame.min()}, max={frame.max()})!")
                return False
            
            # Check dtype is uint8
            if frame.dtype != 'uint8':
                print(f"❌ Frame {i+1} has wrong dtype {frame.dtype} (expected uint8)!")
                return False
        
        # All frames valid
        print(f"✓ All {frames_to_test} frames are valid")
        
        # Test camera handle cleanup
        print(f"\n5. Verifying camera handle cleanup...")
        print(f"   Generator closed, forcing garbage collection...")
        import gc
        gc.collect()  # Force cleanup of any lingering references
        
        # Try to open camera again - should succeed if handle was properly released
        import cv2
        test_cap = cv2.VideoCapture(camera_idx)
        if not test_cap.isOpened():
            print(f"❌ Camera handle was not released! Cannot reopen camera {camera_idx}.")
            print(f"   This means capture.py has a resource leak.")
            return False
        
        # Try to read a frame to confirm it's actually working
        ret, test_frame = test_cap.read()
        test_cap.release()
        
        if not ret:
            print(f"❌ Camera reopened but cannot read frames!")
            return False
        
        print(f"✓ Camera handle properly released - camera can be reopened")
        
        # Summary
        first_frame = captured_frames[0]
        h, w, c = first_frame.shape
        print(f"\n6. Summary:")
        print(f"   Resolution: {w}x{h}")
        print(f"   Channels: {c} (BGR)")
        print(f"   Dtype: {first_frame.dtype}")
        print(f"   Frames captured: {frames_to_test}")
        print(f"   Handle cleanup: verified")
        
        print("\n" + "=" * 60)
        print("✓ SMOKE TEST PASSED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Error during capture: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = smoke_test_camera()
    sys.exit(0 if success else 1)
