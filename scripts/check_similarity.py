"""Check semantic similarity between question pairs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.qa_cache import semantic_cache
import numpy as np

pairs = [
    ("What is the HOD's name?", "Who is the HOD?"),
    ("Library location?", "Could you tell me where the library is located?"),
    ("What is the HOD's name?", "Tell me the name of the HOD"),
    ("Who is the HOD?", "What is the HOD's name?"),
]

print("Semantic Similarity Check")
print("=" * 70)

for q1, q2 in pairs:
    emb1 = semantic_cache.embed_question(q1)
    emb2 = semantic_cache.embed_question(q2)
    
    # Cosine similarity (inner product for normalized vectors)
    similarity = float(np.dot(emb1, emb2))
    
    print(f"\nQ1: {q1}")
    print(f"Q2: {q2}")
    print(f"Similarity: {similarity:.4f}")
    print(f"Above 0.92 threshold: {similarity > 0.92}")
