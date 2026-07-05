"""Measure semantic cache latency with model pre-loaded.

Isolates embedding generation and search latency to verify budget numbers.
"""

import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.qa_cache import semantic_cache

def measure_embedding_latency(iterations=50):
    """Measure embedding generation latency with model pre-loaded."""
    print("Pre-loading sentence-transformers model...")
    # Force model load
    _ = semantic_cache.embed_question("warmup")
    print("Model loaded.\n")
    
    questions = [
        "What is the HOD's name?",
        "Where is the library located?",
        "Who is the placement officer?",
        "What are the canteen timings?",
        "How do I access the WiFi?",
    ]
    
    print(f"Measuring embedding latency over {iterations} iterations...")
    latencies = []
    
    for i in range(iterations):
        question = questions[i % len(questions)]
        
        start = time.time()
        emb = semantic_cache.embed_question(question)
        latency_ms = (time.time() - start) * 1000
        
        latencies.append(latency_ms)
    
    avg = sum(latencies) / len(latencies)
    p50 = sorted(latencies)[len(latencies) // 2]
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    min_lat = min(latencies)
    max_lat = max(latencies)
    
    print(f"Embedding Latency:")
    print(f"  Average: {avg:.2f}ms")
    print(f"  p50:     {p50:.2f}ms")
    print(f"  p95:     {p95:.2f}ms")
    print(f"  Min:     {min_lat:.2f}ms")
    print(f"  Max:     {max_lat:.2f}ms")
    
    return avg, p50, p95


def measure_search_latency(iterations=50):
    """Measure FAISS search latency with cache populated."""
    print("\nPre-populating cache with 20 entries...")
    semantic_cache.clear()
    
    for i in range(20):
        semantic_cache.add(f"Question {i}", f"Answer {i}", data_version=1)
    
    print(f"Cache populated with {semantic_cache.get_cache_size()} entries.\n")
    
    # Pre-generate embeddings to isolate search time
    print(f"Measuring FAISS search latency over {iterations} iterations...")
    embeddings = []
    for i in range(10):
        embeddings.append(semantic_cache.embed_question(f"Question {i}"))
    
    latencies = []
    
    for i in range(iterations):
        emb = embeddings[i % len(embeddings)]
        
        start = time.time()
        candidates = semantic_cache.search(emb, threshold=0.92)
        latency_ms = (time.time() - start) * 1000
        
        latencies.append(latency_ms)
    
    avg = sum(latencies) / len(latencies)
    p50 = sorted(latencies)[len(latencies) // 2]
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    min_lat = min(latencies)
    max_lat = max(latencies)
    
    print(f"FAISS Search Latency:")
    print(f"  Average: {avg:.2f}ms")
    print(f"  p50:     {p50:.2f}ms")
    print(f"  p95:     {p95:.2f}ms")
    print(f"  Min:     {min_lat:.2f}ms")
    print(f"  Max:     {max_lat:.2f}ms")
    
    return avg, p50, p95


def measure_total_semantic_cache_hit(iterations=50):
    """Measure total semantic cache hit time (embed + search, no entity gate)."""
    print("\nMeasuring TOTAL semantic cache hit (embed + search)...")
    print(f"Iterations: {iterations}\n")
    
    # Pre-load model and populate cache
    _ = semantic_cache.embed_question("warmup")
    semantic_cache.clear()
    for i in range(20):
        semantic_cache.add(f"Question {i}", f"Answer {i}", data_version=1)
    
    questions = [f"Question {i}" for i in range(10)]
    latencies = []
    
    for i in range(iterations):
        question = questions[i % len(questions)]
        
        start = time.time()
        # This is what Cache Manager will do
        emb = semantic_cache.embed_question(question)
        candidates = semantic_cache.search(emb, threshold=0.92)
        latency_ms = (time.time() - start) * 1000
        
        latencies.append(latency_ms)
    
    avg = sum(latencies) / len(latencies)
    p50 = sorted(latencies)[len(latencies) // 2]
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    min_lat = min(latencies)
    max_lat = max(latencies)
    
    print(f"Total Semantic Cache Hit (embed + search):")
    print(f"  Average: {avg:.2f}ms")
    print(f"  p50:     {p50:.2f}ms")
    print(f"  p95:     {p95:.2f}ms")
    print(f"  Min:     {min_lat:.2f}ms")
    print(f"  Max:     {max_lat:.2f}ms")
    
    return avg, p50, p95


if __name__ == "__main__":
    print("=" * 70)
    print("Semantic Cache Latency Measurement")
    print("=" * 70)
    print()
    
    # Measure components
    embed_avg, embed_p50, embed_p95 = measure_embedding_latency(iterations=100)
    search_avg, search_p50, search_p95 = measure_search_latency(iterations=100)
    
    # Measure total
    total_avg, total_p50, total_p95 = measure_total_semantic_cache_hit(iterations=100)
    
    # Entity gate estimate (from design doc)
    entity_gate_latency = 2.0  # <2ms per design
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Embedding (avg):         {embed_avg:.2f}ms")
    print(f"FAISS search (avg):      {search_avg:.2f}ms")
    print(f"Entity gate (estimate):  {entity_gate_latency:.2f}ms")
    print(f"---")
    print(f"Total (measured):        {total_avg:.2f}ms")
    print(f"Total + entity gate:     {total_avg + entity_gate_latency:.2f}ms")
    print()
    print(f"Design budget (laptop):  20ms")
    print(f"Actual (p50):            {total_p50 + entity_gate_latency:.2f}ms")
    print(f"Actual (p95):            {total_p95 + entity_gate_latency:.2f}ms")
    print()
    
    if total_p95 + entity_gate_latency > 20:
        print("⚠️  BUDGET EXCEEDED: Measured p95 exceeds 20ms laptop target")
        recommended = int((total_p95 + entity_gate_latency) / 5) * 5 + 5  # Round up to nearest 5
        print(f"   Recommended budget: <{recommended}ms (laptop)")
    else:
        print("✅ BUDGET MET: Within 20ms laptop target")
