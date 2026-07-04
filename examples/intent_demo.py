"""Demonstration of deterministic intent handler.

Shows how STT transcripts with varying casing, whitespace, and punctuation
are normalized and matched to known intents.

NOTE: As of Task 1.7, intents.py returns text only - the Decision Engine
(engine.py) is responsible for publishing RESPONSE events. This demo now
shows the intent handler as a standalone component for testing/debugging.
For full system behavior with RESPONSE events, use the Decision Engine.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.decision_engine import intents


def main():
    """Demo intent handler with real-world STT variations."""
    
    print("=" * 70)
    print("Deterministic Intent Handler Demo")
    print("=" * 70)
    print("\nℹ️  NOTE: This demo shows intents.py as a standalone component.")
    print("   In the full system, the Decision Engine (engine.py) subscribes to")
    print("   TEXT_INPUT events and publishes RESPONSE events based on intent results.")
    print("   This demo calls get_intent_response() directly for testing.")
    
    # Test cases simulating real STT transcripts
    print("\n" + "=" * 70)
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
            print(f"   (Decision Engine would publish RESPONSE event with path='deterministic')")
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
    
    unknown_count = 0
    for test_input in unknown_cases:
        print(f"\n🎤 User says: \"{test_input}\"")
        response = intents.get_intent_response(test_input)
        if response:
            print(f"✓ Intent matched: \"{response}\"")
        else:
            print(f"✗ No match → Decision Engine will try cache/LLM next")
            unknown_count += 1
    
    print(f"\n📊 Unknown intents: {unknown_count}/{len(unknown_cases)}")
    print("   (These would fallthrough to Path B: Cache or Path C: LLM)")
    
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
    
    # Test latency
    print("\n\n" + "=" * 70)
    print("Scenario 4: Latency measurement")
    print("=" * 70)
    
    import time
    latencies = []
    test_inputs = ["hi", "thanks", "help", "bye"] * 25  # 100 lookups
    
    for test_input in test_inputs:
        start = time.time()
        intents.get_intent_response(test_input)
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)
    
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    
    print(f"\n📊 Performed {len(latencies)} intent lookups")
    print(f"📈 Average latency: {avg_latency:.3f}ms")
    print(f"📈 Maximum latency: {max_latency:.3f}ms")
    print(f"🎯 Target: <5ms (deterministic path should be instant)")
    
    if avg_latency < 5:
        print("✅ PASS: Meets <5ms latency target")
    else:
        print("⚠️  WARNING: Exceeds 5ms latency target")
    
    # Summary
    print("\n\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"\n🎯 Intent handler provides deterministic responses (Path A)")
    print(f"📊 Returns text for known intents, None for unknown")
    print(f"⚡ Ultra-low latency: <5ms for instant responses")
    print(f"\nℹ️  Integration: Decision Engine calls this from Path A,")
    print(f"   then tries cache (Path B) and LLM (Path C) if None returned.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
