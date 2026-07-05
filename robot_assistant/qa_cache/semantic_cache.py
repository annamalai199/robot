"""Semantic cache using FAISS vector similarity search.

Part of the 3-tier cache system (exact → semantic → entity-gated). Finds near-
duplicate questions using sentence embeddings and cosine similarity.

Key Features:
- sentence-transformers all-MiniLM-L6-v2 (384-dim embeddings)
- FAISS IndexFlatIP for cosine similarity (inner product with normalized vectors)
- Returns candidates above configurable threshold (0.92 from config)
- Stores original question text + answer + data_version alongside embeddings
- In-memory FAISS index (fast, no persistence needed for current scope)
- Latency target: <20ms (embedding generation + FAISS search)

Design Rationale (from Section 6):
Semantic cache catches paraphrases and near-duplicates that exact match misses.
Example: "What's the HOD's name?" and "Who is the HOD?" should hit the same cache
entry even though text differs. Cosine similarity > 0.92 indicates semantic equivalence.

CRITICAL: Semantic cache returns CANDIDATES only. The Cache Manager (Task 1.11)
must apply the entity gate to prevent wrong-person/wrong-subject answers when
two questions are semantically similar but factually different.

Example Entity Gate Scenario:
- "Who is the HOD?" (cached) vs "Who is the placement officer?" (query)
- Cosine similarity: ~0.95 (very similar!)
- But entities differ: subject='hod' vs subject='placement'
- Entity gate blocks cache hit, forcing LLM re-generation with correct answer
"""

import logging
import time
import numpy as np
from typing import Optional
from pathlib import Path

try:
    import faiss
except ImportError:
    raise ImportError(
        "FAISS not installed. Install with: pip install faiss-cpu (or faiss-gpu)"
    )

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise ImportError(
        "sentence-transformers not installed. Install with: pip install sentence-transformers"
    )

from robot_assistant.config import config

logger = logging.getLogger(__name__)

# Global embedding model and FAISS index
_model: Optional[SentenceTransformer] = None
_index: Optional[faiss.IndexFlatIP] = None

# Parallel arrays for metadata (question text, answer, data_version)
# Index i in FAISS corresponds to index i in these lists
_questions: list[str] = []
_answers: list[str] = []
_data_versions: list[int] = []


def _get_model() -> SentenceTransformer:
    """Get or load the sentence embedding model.
    
    Returns:
        Loaded SentenceTransformer model (all-MiniLM-L6-v2).
    """
    global _model
    
    if _model is None:
        logger.info("Loading sentence-transformers model: all-MiniLM-L6-v2")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Model loaded successfully")
    
    return _model


def _get_index() -> faiss.IndexFlatIP:
    """Get or create the FAISS index.
    
    Returns:
        FAISS IndexFlatIP for cosine similarity (384 dimensions).
    """
    global _index
    
    if _index is None:
        # IndexFlatIP uses inner product (equivalent to cosine similarity for normalized vectors)
        # Dimension: 384 (all-MiniLM-L6-v2 embedding size)
        _index = faiss.IndexFlatIP(384)
        logger.info("Created FAISS IndexFlatIP (384-dim) for semantic cache")
    
    return _index


def embed_question(question: str) -> np.ndarray:
    """Generate embedding for a question.
    
    Args:
        question: Question text to embed.
    
    Returns:
        384-dim numpy array (L2-normalized for cosine similarity).
    
    Latency: ~15-20ms on laptop CPU for all-MiniLM-L6-v2.
    
    Example:
        >>> emb = embed_question("What is the HOD's name?")
        >>> emb.shape
        (384,)
        >>> np.isclose(np.linalg.norm(emb), 1.0)  # Normalized
        True
    """
    start_time = time.time()
    
    model = _get_model()
    
    # Generate embedding (returns numpy array)
    embedding = model.encode(question, convert_to_numpy=True)
    
    # Normalize for cosine similarity (FAISS IndexFlatIP uses inner product)
    # For normalized vectors: inner_product(a, b) = cosine_similarity(a, b)
    embedding = embedding / np.linalg.norm(embedding)
    
    latency_ms = (time.time() - start_time) * 1000
    logger.debug(f"Embedded question in {latency_ms:.2f}ms: '{question[:50]}...'")
    
    return embedding


def search(question_embedding: np.ndarray, threshold: float = None) -> list[dict]:
    """Search for similar questions in the semantic cache.
    
    Args:
        question_embedding: 384-dim numpy array (L2-normalized).
        threshold: Minimum cosine similarity (default: config.SEMANTIC_CACHE_THRESHOLD).
    
    Returns:
        List of candidate dicts with keys:
            - 'question': Original cached question text
            - 'answer': Cached answer text
            - 'data_version': Data version when cached
            - 'similarity': Cosine similarity score (0.0 to 1.0)
        
        Sorted by similarity (highest first).
        Empty list if no candidates above threshold.
    
    Latency: <5ms for search in typical cache size (<100 questions).
    
    Example:
        >>> emb = embed_question("Who is the HOD?")
        >>> candidates = search(emb, threshold=0.92)
        >>> if candidates:
        ...     print(f"Found {len(candidates)} similar questions")
        ...     print(f"Best match: {candidates[0]['question']} (sim={candidates[0]['similarity']:.3f})")
    """
    if threshold is None:
        threshold = config.SEMANTIC_CACHE_THRESHOLD
    
    start_time = time.time()
    
    index = _get_index()
    
    # Check if index is empty
    if index.ntotal == 0:
        logger.debug("Semantic cache empty, no candidates")
        return []
    
    # Search FAISS (k=5: return up to 5 nearest neighbors)
    # Returns: distances (inner products), indices (positions in index)
    k = min(5, index.ntotal)  # Can't request more than we have
    
    # FAISS expects 2D array: (num_queries, embedding_dim)
    query = question_embedding.reshape(1, -1).astype('float32')
    
    distances, indices = index.search(query, k)
    
    # Build candidate list
    candidates = []
    
    for dist, idx in zip(distances[0], indices[0]):
        # dist is inner product (cosine similarity for normalized vectors)
        similarity = float(dist)
        
        # Filter by threshold
        if similarity < threshold:
            continue
        
        # Check if index valid (FAISS returns -1 for unfilled slots)
        if idx < 0 or idx >= len(_questions):
            continue
        
        candidates.append({
            'question': _questions[idx],
            'answer': _answers[idx],
            'data_version': _data_versions[idx],
            'similarity': similarity
        })
    
    latency_ms = (time.time() - start_time) * 1000
    logger.debug(f"Semantic search found {len(candidates)} candidates in {latency_ms:.2f}ms")
    
    # Sort by similarity (highest first)
    candidates.sort(key=lambda c: c['similarity'], reverse=True)
    
    return candidates


def add(question: str, answer: str, data_version: int) -> None:
    """Add a question-answer pair to the semantic cache.
    
    Args:
        question: Question text (will be embedded).
        answer: Answer text.
        data_version: Data version tag (from current refresh cycle).
    
    Side Effects:
        - Embeds question using sentence-transformers
        - Adds embedding to FAISS index
        - Appends metadata to parallel arrays
    
    Example:
        >>> add("What's the HOD's name?", "Dr. Rajesh Kumar", data_version=1)
        >>> add("Who is the HOD?", "Dr. Rajesh Kumar", data_version=1)
        # These two will have high cosine similarity
    """
    # Embed question
    embedding = embed_question(question)
    
    # Add to FAISS (expects 2D array)
    index = _get_index()
    index.add(embedding.reshape(1, -1).astype('float32'))
    
    # Add metadata (must stay in sync with FAISS index)
    _questions.append(question)
    _answers.append(answer)
    _data_versions.append(data_version)
    
    logger.debug(f"Added to semantic cache: '{question[:50]}...' (v{data_version})")


def clear() -> None:
    """Clear the semantic cache (for testing/reset).
    
    Side Effects:
        - Clears FAISS index
        - Clears metadata arrays
    """
    global _index, _questions, _answers, _data_versions
    
    _index = None  # Will be recreated on next access
    _questions.clear()
    _answers.clear()
    _data_versions.clear()
    
    logger.debug("Semantic cache cleared")


def get_cache_size() -> int:
    """Get the number of questions in the semantic cache.
    
    Returns:
        Count of cached question-answer pairs.
    """
    return len(_questions)


def get_cache_stats() -> dict:
    """Get semantic cache statistics for monitoring/debugging.
    
    Returns:
        Dict with cache size and per-version counts.
    """
    version_counts = {}
    for v in _data_versions:
        version_counts[v] = version_counts.get(v, 0) + 1
    
    return {
        'total_entries': len(_questions),
        'entries_by_version': version_counts,
        'embedding_dim': 384,
        'model': 'all-MiniLM-L6-v2'
    }
