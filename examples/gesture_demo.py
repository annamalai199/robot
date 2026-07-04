"""Demonstration of gesture-to-action mapping.

Shows how vision pipeline GESTURE_DETECTED events are mapped to ACTION events,
and how unknown gestures are safely ignored (no-op).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.decision_engine import gesture_actions
from robot_assistant.events import bus, subscribe, publish, GestureDetectedEvent


def main():
    """Demo gesture-to-action mapping with synthetic vision events."""
    
    print("=" * 70)
    print("Gesture-to-Action Mapping Demo")
    print("=" * 70)
    
    # Subscribe to ACTION events
    actions_received = []
    
    def action_handler(event):
        actions_received.append(event)
        print(f"\n🤖 [ACTION Event]")
        print(f"   Action: {event['action']}")
        print(f"   Track ID: {event['track_id']}")
    
    subscribe("ACTION", action_handler)
    
    # Start gesture handler (subscribes to GESTURE_DETECTED)
    gesture_actions.start_gesture_handler()
    
    print("\n✅ Gesture handler started (subscribed to GESTURE_DETECTED events)")
    print(f"✅ Subscribed to ACTION events\n")
    
    # Scenario 1: Known gesture
    print("=" * 70)
    print("Scenario 1: Known Gesture (HAND_RAISED)")
    print("=" * 70)
    
    print("\n👁️ [Vision Pipeline] Detected gesture: HAND_RAISED (track T1)")
    
    gesture_event: GestureDetectedEvent = {
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T1"
    }
    publish(gesture_event)
    
    # Scenario 2: Unknown gestures (safe no-op)
    print("\n\n" + "=" * 70)
    print("Scenario 2: Unknown Gestures (Safe No-Op)")
    print("=" * 70)
    
    before_count = len(actions_received)
    
    unknown_gestures = [
        "RANDOM_GESTURE",
        "UNDEFINED_MOTION",
        "WEIRD_POSE",
    ]
    
    for gesture in unknown_gestures:
        print(f"\n👁️ [Vision Pipeline] Detected gesture: {gesture} (track T2)")
        
        gesture_event: GestureDetectedEvent = {
            "event": "GESTURE_DETECTED",
            "gesture": gesture,
            "track_id": "T2"
        }
        publish(gesture_event)
        
        print(f"   ✓ Safely ignored (no ACTION event published)")
    
    after_count = len(actions_received)
    print(f"\n📊 Unknown gestures: {len(unknown_gestures)}, ACTION events: {after_count - before_count}")
    print("   (Should be 0 - unknown gestures produce no actions)")
    
    # Scenario 3: Multiple tracks, same gesture
    print("\n\n" + "=" * 70)
    print("Scenario 3: Multiple Tracks, Same Gesture")
    print("=" * 70)
    
    tracks = ["T3", "T4", "T5"]
    
    for track_id in tracks:
        print(f"\n👁️ [Vision Pipeline] Person {track_id} raises hand")
        
        gesture_event: GestureDetectedEvent = {
            "event": "GESTURE_DETECTED",
            "gesture": "HAND_RAISED",
            "track_id": track_id
        }
        publish(gesture_event)
    
    # Scenario 4: Runtime extensibility
    print("\n\n" + "=" * 70)
    print("Scenario 4: Runtime Extensibility (Add New Gestures)")
    print("=" * 70)
    
    # Add new gesture mapping
    print("\n➕ Adding new gesture: WAVE → WAVE_BACK")
    gesture_actions.add_gesture_mapping("WAVE", "WAVE_BACK")
    
    print("\n👁️ [Vision Pipeline] Detected gesture: WAVE (track T6)")
    
    gesture_event: GestureDetectedEvent = {
        "event": "GESTURE_DETECTED",
        "gesture": "WAVE",
        "track_id": "T6"
    }
    publish(gesture_event)
    
    # Summary
    print("\n\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"\n📊 Total ACTION events published: {len(actions_received)}")
    print(f"\nBreakdown:")
    print(f"  - Scenario 1 (HAND_RAISED): 1 action")
    print(f"  - Scenario 2 (Unknown gestures): 0 actions (safe no-op)")
    print(f"  - Scenario 3 (Multiple tracks): {len(tracks)} actions")
    print(f"  - Scenario 4 (WAVE): 1 action")
    print(f"\n📋 All ACTION events go to SafetyGate next (not built yet)")
    print(f"🎯 Unknown gestures safely ignored → No default actions")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
