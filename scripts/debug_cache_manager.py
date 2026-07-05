"""Debug cache manager behavior."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.qa_cache import cache_manager, entity_extractor, semantic_cache, exact_cache
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

# Clear and reset
cache_manager.clear_cache()
exact_cache.set_data_version(1)

print("="*70)
print("Test 1: 'What is HOD's name?' -> 'Who is the HOD?'")
print("="*70)

# Write
cache_manager.write_cache("What is the HOD's name?", "Dr. Rajesh Kumar")

# Extract entities
e1 = entity_extractor.extract_entities("What is the HOD's name?")
e2 = entity_extractor.extract_entities("Who is the HOD?")
print(f"Cached entities: {e1}")
print(f"Query entities: {e2}")
print(f"Entities match: {entity_extractor.entities_match(e1, e2)}")

# Check semantic similarity
emb = semantic_cache.embed_question("Who is the HOD?")
candidates = semantic_cache.search(emb, threshold=0.92)
print(f"Semantic candidates: {len(candidates)}")
if candidates:
    print(f"  Best match similarity: {candidates[0]['similarity']:.4f}")

# Check cache
result = cache_manager.check_cache("Who is the HOD?")
print(f"Cache result: {result}")

print("\n" + "="*70)
print("Test 2: 'What is HOD's name?' -> 'Tell me the name of the HOD'")
print("="*70)

cache_manager.clear_cache()
exact_cache.set_data_version(1)
cache_manager.write_cache("What is the HOD's name?", "Dr. Rajesh Kumar")

e1 = entity_extractor.extract_entities("What is the HOD's name?")
e2 = entity_extractor.extract_entities("Tell me the name of the HOD")
print(f"Cached entities: {e1}")
print(f"Query entities: {e2}")
print(f"Entities match: {entity_extractor.entities_match(e1, e2)}")

emb = semantic_cache.embed_question("Tell me the name of the HOD")
candidates = semantic_cache.search(emb, threshold=0.92)
print(f"Semantic candidates: {len(candidates)}")
if candidates:
    print(f"  Best match similarity: {candidates[0]['similarity']:.4f}")

result = cache_manager.check_cache("Tell me the name of the HOD")
print(f"Cache result: {result}")
