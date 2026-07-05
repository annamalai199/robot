"""Live integration test for LangGraph with real Ollama.

Tests the full reasoning graph end-to-end with actual Ollama LLM,
real database, and cache write-back verification.
"""

import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.reasoning import graph
from robot_assistant.qa_cache import cache_manager


def main():
    """Run live integration test."""
    print("=" * 70)
    print("LIVE INTEGRATION TEST: LangGraph with Real Ollama")
    print("=" * 70)
    print()
    
    # Test question
    question = "Who is the HOD?"
    print(f"Test Question: {question}")
    print()
    
    # Get cache stats BEFORE
    print("-" * 70)
    print("BEFORE: Cache Stats")
    print("-" * 70)
    stats_before = cache_manager.get_cache_stats()
    print(f"Exact cache: {stats_before['exact']['total_entries']} entries")
    print(f"Semantic cache: {stats_before['semantic']['total_entries']} entries")
    print(f"Data version: {stats_before['data_version']}")
    print()
    
    # Run the reasoning graph with real Ollama
    print("-" * 70)
    print("RUNNING: LangGraph Reasoning (with real Ollama)")
    print("-" * 70)
    print("This will:")
    print("1. Call MCP Memory Server (real SQLite query)")
    print("2. Call Ollama LLM (gemma2:2b)")
    print("3. Write result to cache")
    print()
    
    try:
        result = graph.run_reasoning_graph(question)
        
        print("✅ SUCCESS")
        print()
        print("-" * 70)
        print("RESULT:")
        print("-" * 70)
        print(f"Answer: {result['answer']}")
        print(f"Cache Written: {result['cache_written']}")
        print(f"MCP Confidence: {result['mcp_confidence']}")
        print(f"Error: {result['error']}")
        print()
        
        # Get cache stats AFTER
        print("-" * 70)
        print("AFTER: Cache Stats")
        print("-" * 70)
        stats_after = cache_manager.get_cache_stats()
        print(f"Exact cache: {stats_after['exact']['total_entries']} entries")
        print(f"Semantic cache: {stats_after['semantic']['total_entries']} entries")
        print(f"Data version: {stats_after['data_version']}")
        print()
        
        # Verify cache write
        print("-" * 70)
        print("VERIFICATION:")
        print("-" * 70)
        
        if result['cache_written']:
            # Check if exact cache size increased
            exact_increased = stats_after['exact']['total_entries'] > stats_before['exact']['total_entries']
            semantic_increased = stats_after['semantic']['total_entries'] > stats_before['semantic']['total_entries']
            
            print(f"✅ Exact cache increased: {exact_increased} ({stats_before['exact']['total_entries']} → {stats_after['exact']['total_entries']})")
            print(f"✅ Semantic cache increased: {semantic_increased} ({stats_before['semantic']['total_entries']} → {stats_after['semantic']['total_entries']})")
            
            # Try to retrieve from cache
            print()
            print("Testing cache hit on same question...")
            cached_result = cache_manager.check_cache(question)
            if cached_result:
                print(f"✅ Cache hit successful!")
                print(f"   Cached answer: {cached_result['answer']}")
                print(f"   Source: {cached_result.get('source', 'unknown')}")
            else:
                print("❌ Cache hit failed (unexpected)")
        else:
            print(f"⚠️  Cache write reported as False")
            if result['error']:
                print(f"   Reason: {result['error']}")
        
        print()
        print("=" * 70)
        print("TEST COMPLETE")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        print()
        print("Possible issues:")
        print("- Is Ollama running? (ollama serve)")
        print("- Is gemma2:2b model pulled? (ollama pull gemma2:2b)")
        print("- Is the database initialized? (python scripts/init_memory_db.py)")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
