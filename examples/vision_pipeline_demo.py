"""Vision pipeline integration demo.

Demonstrates the full 5-stage vision cascade running in real-time:
- Video capture
- Motion gate filter
- YOLO pose detection
- ByteTrack tracking
- Gesture recognition + Face identification

Press Ctrl+C to stop.
"""

import sys
import time
import signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import pipeline
from robot_assistant.events import bus
from robot_assistant.events.schemas import (
    GestureDetectedEvent,
    IdentityResolvedEvent,
    TrackLostEvent
)


# Event handlers for demonstration
def on_gesture_detected(event: GestureDetectedEvent):
    """Handle GESTURE_DETECTED events."""
    print(f"\n🖐️  GESTURE: {event['gesture']} from track {event['track_id']}")


def on_identity_resolved(event: IdentityResolvedEvent):
    """Handle IDENTITY_RESOLVED events."""
    print(f"\n👤 IDENTITY: track {event['track_id']} → "
          f"embedding_id {event['embedding_id']} "
          f"({event['status']}, name={event.get('name', 'N/A')})")


def on_track_lost(event: TrackLostEvent):
    """Handle TRACK_LOST events."""
    print(f"\n👋 TRACK LOST: track {event['track_id']} "
          f"(embedding_id {event['embedding_id']})")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\nStopping pipeline...")
    pipeline.stop_pipeline(timeout=10.0)
    print("Pipeline stopped. Exiting.")
    sys.exit(0)


def main():
    print("=" * 80)
    print("VISION PIPELINE DEMO")
    print("=" * 80)
    print()
    print("This demo runs the complete 5-stage vision pipeline:")
    print("  1. Video capture from webcam")
    print("  2. Motion gate (skips YOLO on static frames)")
    print("  3. YOLO pose detection (every 5th frame)")
    print("  4. ByteTrack tracking (stable IDs across occlusion)")
    print("  5. Gesture recognition + Face identification")
    print()
    print("Events will be printed to console as they occur:")
    print("  🖐️  GESTURE_DETECTED - when you raise your hand")
    print("  👤 IDENTITY_RESOLVED - first time each face is seen")
    print("  👋 TRACK_LOST - when person leaves frame for >30 frames")
    print()
    print("Position yourself in front of webcam and raise your hand!")
    print("Press Ctrl+C to stop.")
    print()
    
    # Register signal handler for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Subscribe to events
    bus.subscribe('GESTURE_DETECTED', on_gesture_detected)
    bus.subscribe('IDENTITY_RESOLVED', on_identity_resolved)
    bus.subscribe('TRACK_LOST', on_track_lost)
    
    try:
        # Start pipeline in background thread
        if pipeline.start_pipeline(camera_index=0):
            print("✓ Pipeline started successfully")
            print("-" * 80)
            print()
            
            # Keep main thread alive
            while pipeline.is_pipeline_running():
                time.sleep(0.5)
        else:
            print("✗ Failed to start pipeline (already running?)")
            return 1
    
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # Cleanup
        pipeline.stop_pipeline(timeout=5.0)
        bus._subscribers.clear()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
