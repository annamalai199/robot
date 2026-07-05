"""Cache Manager - Orchestrates 3-tier cache system with entity gate.

Coordinates exact → semantic → entity-gated flow for question answering cache.
Ensures that semantically similar but factually different questions don't
return wrong answers (e.g., "Who is the HOD?" vs "Who is the placement officer?").

Flow:
1. Check exact cache (fast path, <5ms)
2. On miss, embed question and check semantic cache (<25ms)
3. For each semantic candidate:
   - Extract entities from cached question and query question
   - If entities match AND data_version matches → HIT
   - If entities don't match → SKIP candidate (entity gate blocks wrong answer)
   - If data_version doesn't match → SKIP candidate (stale data)
4. If no valid candidates → MISS (fall through to LLM)

Design Rationale (from Section 6):
The entity gate is critical to prevent semantically similar questions with different
factual answers from hitting the same cache entry. Example:
- "Who is the HOD?" (cached: Dr. Rajesh Kumar)
- "Who is the placement officer?" (query)
- Semantic similarity: ~0.95 (very high!)
- BUT entities differ: subject='hod' vs subject='placement'
- Entity gate blocks → cache MISS → LLM generates correct answer
"""

import logging
import time
from typing import Optional

from robot_assistant.qa_cache import exact_cache
from robot_assistant.qa_cache import semantic_cache
from robot_assistant.qa_cache import entity_extractor
from robot_assistant.config import config

logger = logging.getLogger(__name__)


def check_cache(question: str) -> Optional[dict]:
    """Check 3-tier cache for a question answer.
    
    Args:
        question: User's question text.
    
    Returns:
        Dict with 'answer', 'path', and 'latency_ms' keys if cache hit.
        None if cache miss (fall through to LLM).
        
    Cache Hit Paths:
        - 'exact': Exact text match in hash cache
        - 'semantic': Semantic similarity match with entity gate pass
        
    Cache Miss Conditions:
        - Question never seen before
        - Semantic candidate found but entities don't match (entity gate blocks)
        - Semantic candidate found but data_version stale
        - No semantic candidates above threshold
    
    Example:
        >>> write_cache("What is the HOD's name?", "Dr. Rajesh Kumar")
        >>> result = check_cache("What is the HOD's name?")  # Exact hit
        >>> result['answer']
        "Dr. Rajesh Kumar"
        >>> result['path']
        'exact'
        
        >>> result = check_cache("Who is the HOD?")  # Semantic hit
        >>> result['answer']
        "Dr. Rajesh Kumar"
        >>> result['path']
        'semantic'
        
        >>> result = check_cache("Who is the placement officer?")  # Entity gate blocks
        >>> result
        None
    """
    start_time = time.time()
    
    # TIER 1: Exact cache check (fast path)
    exact_result = exact_cache.get(question)
    
    if exact_result is not None:
        latency_ms = (time.time() - start_time) * 1000
        logger.info(f"Cache HIT (exact): '{question[:50]}...' ({latency_ms:.2f}ms)")
        
        return {
            'answer': exact_result['answer'],
            'path': 'exact',
            'latency_ms': latency_ms
        }
    
    # TIER 2: Semantic cache check
    logger.debug(f"Exact cache miss, trying semantic cache for: '{question[:50]}...'")
    
    # Embed question
    question_embedding = semantic_cache.embed_question(question)
    
    # Search for similar questions
    candidates = semantic_cache.search(
        question_embedding,
        threshold=config.SEMANTIC_CACHE_THRESHOLD
    )
    
    if not candidates:
        latency_ms = (time.time() - start_time) * 1000
        logger.info(f"Cache MISS (no semantic candidates): '{question[:50]}...' ({latency_ms:.2f}ms)")
        return None
    
    # TIER 3: Entity gate
    logger.debug(f"Found {len(candidates)} semantic candidates, applying entity gate")
    
    # Extract entities from query question
    query_entities = entity_extractor.extract_entities(question)
    
    # Current data version for staleness check
    current_version = exact_cache.get_data_version()
    
    # Check each candidate (sorted by similarity, highest first)
    for candidate in candidates:
        cached_question = candidate['question']
        cached_version = candidate['data_version']
        similarity = candidate['similarity']
        
        # Check data version first (fast check)
        if cached_version != current_version:
            logger.debug(
                f"Skipping candidate (stale version): '{cached_question[:50]}...' "
                f"(v{cached_version} != v{current_version})"
            )
            continue
        
        # Extract entities from cached question
        cached_entities = entity_extractor.extract_entities(cached_question)
        
        # Check if entities match
        if entity_extractor.entities_match(query_entities, cached_entities):
            # Entity gate PASS - return hit
            latency_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Cache HIT (semantic): '{question[:50]}...' "
                f"matched '{cached_question[:50]}...' "
                f"(similarity={similarity:.3f}, latency={latency_ms:.2f}ms)"
            )
            
            return {
                'answer': candidate['answer'],
                'path': 'semantic',
                'latency_ms': latency_ms,
                'similarity': similarity,
                'cached_question': cached_question
            }
        else:
            # Entity gate BLOCK - different entities, skip candidate
            logger.info(
                f"Entity gate BLOCKED: '{question[:50]}...' vs '{cached_question[:50]}...' "
                f"(query_entities={query_entities}, cached_entities={cached_entities})"
            )
            continue
    
    # All candidates rejected (entity mismatch or stale version)
    latency_ms = (time.time() - start_time) * 1000
    logger.info(
        f"Cache MISS (all candidates rejected by entity gate): "
        f"'{question[:50]}...' ({latency_ms:.2f}ms)"
    )
    
    return None


def write_cache(question: str, answer: str) -> None:
    """Write a question-answer pair to all cache tiers after LLM generation.
    
    Args:
        question: User's question text.
        answer: LLM-generated answer text.
    
    Side Effects:
        - Writes to exact cache (hash table)
        - Writes to semantic cache (FAISS + metadata)
        - Tags with current data_version
    
    Example:
        >>> # After LLM generates answer
        >>> write_cache("What are the library rules?", "No food/drinks, silence in reading zones")
        >>> # Now future queries can hit cache
    """
    start_time = time.time()
    
    # Get current data version
    data_version = exact_cache.get_data_version()
    
    # Write to exact cache
    exact_cache.put(question, answer, data_version)
    
    # Write to semantic cache
    semantic_cache.add(question, answer, data_version)
    
    latency_ms = (time.time() - start_time) * 1000
    logger.info(
        f"Wrote to cache: '{question[:50]}...' → '{answer[:50]}...' "
        f"(v{data_version}, {latency_ms:.2f}ms)"
    )


def clear_cache() -> None:
    """Clear all cache tiers (for testing/reset).
    
    Side Effects:
        - Clears exact cache
        - Clears semantic cache
        - Does NOT reset data_version
    """
    exact_cache.clear()
    semantic_cache.clear()
    logger.info("All cache tiers cleared")


def get_cache_stats() -> dict:
    """Get statistics from all cache tiers.
    
    Returns:
        Dict with 'exact' and 'semantic' keys containing tier-specific stats.
    """
    return {
        'exact': exact_cache.get_cache_stats(),
        'semantic': semantic_cache.get_cache_stats(),
        'data_version': exact_cache.get_data_version()
    }
