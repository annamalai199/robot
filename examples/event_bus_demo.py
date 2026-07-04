"""Event Bus Demonstration Script.

This shows how the event bus connects different components in the robot assistant.
Run this to see event-driven communication in action.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.events import (
    subscribe,
    publish,
    set_debug_logging,
    GestureDetectedEvent,
    IdentityResolvedEvent,
    ActionEvent,
    ActionBlockedEvent,
    ResponseEvent,
)


def main():
    """Demonstrate event bus with simulated components."""
    
    print("=" * 70)
    print("Event Bus Demonstration")
    print("=" * 70)
    
    # Enable debug logging to see all events
    set_debug_logging(True)
    
    # Simulate Decision Engine
    def decision_engine_gesture_handler(event: GestureDetectedEvent):
        print(f"\n[Decision Engine] Received gesture: {event['gesture']}")
        print(f"[Decision Engine] Converting to action for track {event['track_id']}")
        
        # Emit ACTION event
        action: ActionEvent = {
            "event": "ACTION",
            "action": "HANDSHAKE",
            "track_id": event["track_id"]
        }
        publish(action)
    
    # Simulate SafetyGate
    def safety_gate_handler(event: ActionEvent):
        print(f"\n[SafetyGate] Checking action: {event['action']}")
        
        # Simulate distance check (no real sensor yet)
        distance_cm = None  # Laptop phase - no sensor
        
        if distance_cm is None:
            print(f"[SafetyGate] ✓ Simulated phase - allowing action (logged)")
            # In real implementation, would publish SERVO_COMMAND here
        else:
            # Would check actual distance
            pass
    
    # Simulate Session State Store
    def session_state_handler(event: IdentityResolvedEvent):
        print(f"\n[Session State] Identity resolved: {event['embedding_id']}")
        print(f"[Session State] Status: {event['status']}")
        
        if event["status"] == "known" and event["name"]:
            print(f"[Session State] Known person: {event['name']}")
            state = "GREETED"
        elif event["status"] == "new":
            print(f"[Session State] New person - registering")
            state = "NEW"
        else:
            state = "GREETED"
        
        # Would publish SESSION_STATE event here
        print(f"[Session State] State: {state}")
    
    # Simulate TTS output
    def tts_handler(event: ResponseEvent):
        print(f"\n[TTS] Speaking: \"{event['text']}\"")
        print(f"[TTS] Response path: {event['path']} (latency: {event['latency_ms']:.1f}ms)")
    
    # Subscribe all handlers
    print("\n📡 Subscribing components to event bus...")
    subscribe("GESTURE_DETECTED", decision_engine_gesture_handler)
    subscribe("ACTION", safety_gate_handler)
    subscribe("IDENTITY_RESOLVED", session_state_handler)
    subscribe("RESPONSE", tts_handler)
    
    print("✓ All components subscribed\n")
    
    # Scenario 1: Hand raise gesture
    print("\n" + "=" * 70)
    print("Scenario 1: Hand Raise Gesture → Handshake Action")
    print("=" * 70)
    
    gesture: GestureDetectedEvent = {
        "event": "GESTURE_DETECTED",
        "gesture": "HAND_RAISED",
        "track_id": "T1"
    }
    
    print("\n🤚 [Vision] Publishing: GESTURE_DETECTED (hand raised)")
    publish(gesture)
    
    # Scenario 2: Known person identified
    print("\n" + "=" * 70)
    print("Scenario 2: Known Person Identified")
    print("=" * 70)
    
    identity: IdentityResolvedEvent = {
        "event": "IDENTITY_RESOLVED",
        "track_id": "T1",
        "embedding_id": "E0042",
        "status": "known",
        "name": "Annamalai",
        "confidence": 0.91
    }
    
    print("\n👤 [Vision] Publishing: IDENTITY_RESOLVED (known person)")
    publish(identity)
    
    # Scenario 3: New person identified
    print("\n" + "=" * 70)
    print("Scenario 3: New Person Identified")
    print("=" * 70)
    
    new_identity: IdentityResolvedEvent = {
        "event": "IDENTITY_RESOLVED",
        "track_id": "T2",
        "embedding_id": "U1720051234",
        "status": "new",
        "name": None,
        "confidence": None
    }
    
    print("\n🆕 [Vision] Publishing: IDENTITY_RESOLVED (new person)")
    publish(new_identity)
    
    # Scenario 4: Response generated
    print("\n" + "=" * 70)
    print("Scenario 4: Response Generated from Cache")
    print("=" * 70)
    
    response: ResponseEvent = {
        "event": "RESPONSE",
        "text": "Lab hours are Monday 2-5 PM and Wednesday 10 AM-1 PM.",
        "path": "cache",
        "latency_ms": 23.5
    }
    
    print("\n💬 [Decision Engine] Publishing: RESPONSE (from cache)")
    publish(response)
    
    # Summary
    print("\n" + "=" * 70)
    print("Demo Complete")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("✓ Event bus connects components via publish/subscribe")
    print("✓ Multiple components can listen to the same event (fan-out)")
    print("✓ Components are loosely coupled (don't import each other)")
    print("✓ Events flow through the system asynchronously")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
