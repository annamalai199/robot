"""QA Cache - Multi-tier caching system for question answering.

Three-tier cache with entity gating:
1. Exact-match cache (Task 1.8) - O(1) hash lookup
2. Semantic cache (Task 1.10) - FAISS vector similarity
3. Entity gate (Task 1.9) - Prevents wrong-but-similar answers

Design from Section 4 of design.md.
"""

from robot_assistant.qa_cache.exact_cache import (
    get,
    put,
    set_data_version,
    get_data_version,
    reload_data_version,
    clear,
    get_cache_size,
    get_cache_stats,
    normalize_question,
)

from robot_assistant.qa_cache.entity_extractor import (
    extract_entities,
    entities_match,
    add_subject_pattern,
    get_subject_patterns,
)

__all__ = [
    # Exact cache
    "get",
    "put",
    "set_data_version",
    "get_data_version",
    "reload_data_version",
    "clear",
    "get_cache_size",
    "get_cache_stats",
    "normalize_question",
    # Entity extractor
    "extract_entities",
    "entities_match",
    "add_subject_pattern",
    "get_subject_patterns",
]
