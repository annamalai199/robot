"""Demonstration of deterministic intent handler.

Shows how STT transcripts with varying casing, whitespace, and punctuation
are normalized and matched to known intents.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.decision_engine import intents
from robot_assistant.events import bus, subscribe


def main():
    """Demo intent handler with real-world STT variations."""
    
    print("=" * 70)
    print("Deterministic Intent Handler Demo")
    print("=" * 70)
    
    # Subscribe to RESPONSE events
    responses_received = []
    
    def response_handler(event):
        responses_received.append(event)
        print(f"\n📨 [RESPONSE Event]")
        print(f"   Text: \"{event['text']}\"")
        print(f"   Path: {event['path']}")
        print(f"   Latency: {event['latency_ms']:.2f}ms")
    
    subscribe("RESPONSE", response_handler)
    
    print("\n✅ Subscribed to RESPONSE events\n")
    
    # Test cases simulating real STT transcripts
    print("=" * 70)
    print("Scenario 1: Greeting with variations")
    print("=" * 70)
    
    test_cases_greetings = [
        "hi",          # Clean
        "Hi",          # Uppercase
        "HI!",         # Uppercase + punctuation
        "  hello  ",   # Extra whitespace
        "Hello.",      # Capitalized + period
    ]
    
    for test_input in test_cases_greetings:
        print(f"\n🎤 User says: \"{test_input}\"")
        response = intents.get_intent_response(test_input)
        if response:
            print(f"✓ Intent matched: \"{response}\"")
        else:
            print(f"✗ No match (would try cache/LLM)")
    
    # Test unknown intents (fallthrough)
    print("\n\n" + "=" * 70)
    print("Scenario 2: Unknown intents (fallthrough to cache/LLM)")
    print("=" * 70)
    
    unknown_cases = [
        "What's my attendance today?",
        "Who is the HOD?",
        "Tell me about the lab hours",
    ]
    
    before_count = len(responses_received)
    
    for test_input in unknown_cases:
        print(f"\n🎤 User says: \"{test_input}\"")
        response = intents.get_intent_response(test_input)
        if response:
            print(f"✓ Intent matched: \"{response}\"")
        else:
            print(f"✗ No match → fallthrough to cache/LLM")
    
    after_count = len(responses_received)
    print(f"\n📊 Unknown intents: {len(unknown_cases)}, RESPONSE events: {after_count - before_count}")
    print("   (Should be 0 events for unknown intents)")
    
    # Test normalization edge cases
    print("\n\n" + "=" * 70)
    print("Scenario 3: Normalization edge cases")
    print("=" * 70)
    
    edge_cases = [
        ("THANK   YOU!!!", "Multiple spaces + punctuation + caps"),
        ("what can you do?", "Question with question mark"),
        ("  bye  .", "Leading/trailing spaces + period"),
    ]
    
    for test_input, description in edge_cases:
        print(f"\n🎤 User says: \"{test_input}\"")
        print(f"   ({description})")
        response = intents.get_intent_response(test_input)
        if response:
            print(f"✓ Intent matched: \"{response}\"")
        else:
            print(f"✗ No match")
    
    # Summary
    print("\n\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"\n📊 Total RESPONSE events published: {len(responses_received)}")
    print(f"📈 Average latency: {sum(r['latency_ms'] for r in responses_received) / len(responses_received):.2f}ms")
    print(f"🎯 All responses via path='deterministic' (no LLM calls)")
    print(f"\nℹ️  Unknown intents return None → Decision Engine tries cache/LLM next")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
