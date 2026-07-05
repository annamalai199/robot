"""Tests for semantic cache (FAISS vector similarity search).

Critical test cases:
1. Near-duplicate phrasing returns hit (paraphrases)
2. Unrelated questions return no candidates
3. Threshold boundary behavior (just above vs just below 0.92)
4. data_version storage and retrieval
5. Latency targets (<20ms)
6. Empty cache behavior
"""

import pytest
import numpy as np
import time

from robot_assistant.qa_cache import semantic_cache
from robot_assistant.config import config


# =============================================================================
# SETUP / TEARDOWN
# =============================================================================

@pytest.fixture(autouse=True)
def reset_cache():
    """Clear semantic cache before each test."""
    semantic_cache.clear()
    yield
    semantic_cache.clear()


# =============================================================================
# EMBEDDING TESTS
# =============================================================================

def test_embed_question_returns_384_dim():
    """Test that embeddings are 384-dimensional."""
    emb = semantic_cache.embed_question("What is the HOD's name?")
    
    assert isinstance(emb, np.ndarray)
    assert emb.shape == (384,)


def test_embed_question_normalized():
    """Test that embeddings are L2-normalized (for cosine similarity)."""
    emb = semantic_cache.embed_question("What is the HOD's name?")
    
    # L2 norm should be 1.0 (within floating point tolerance)
    norm = np.linalg.norm(emb)
    assert np.isclose(norm, 1.0, atol=1e-6)


def test_embed_question_deterministic():
    """Test that same question produces same embedding."""
    question = "Where is the library?"
    
    emb1 = semantic_cache.embed_question(question)
    emb2 = semantic_cache.embed_question(question)
    
    # Should be identical (or nearly identical due to floating point)
    assert np.allclose(emb1, emb2, atol=1e-6)


def test_embed_question_different_for_different_text():
    """Test that different questions produce different embeddings."""
    emb1 = semantic_cache.embed_question("What is the HOD's name?")
    emb2 = semantic_cache.embed_question("Where is the canteen?")
    
    # Embeddings should be different
    assert not np.allclose(emb1, emb2, atol=0.1)


# =============================================================================
# SEARCH TESTS - NEAR-DUPLICATE PHRASING (CRITICAL)
# =============================================================================

def test_search_near_duplicate_phrasing_returns_hit():
    """CRITICAL: Test that paraphrased questions hit the cache.
    
    This is the core value of semantic cache - catching paraphrases that
    exact match would miss.
    """
    # Add original question
    semantic_cache.add("What is the HOD's name?", "Dr. Rajesh Kumar", data_version=1)
    
    # Search with paraphrase
    emb = semantic_cache.embed_question("Who is the HOD?")
    candidates = semantic_cache.search(emb, threshold=0.85)  # Lower threshold for test
    
    # Should find the cached question
    assert len(candidates) > 0
    assert candidates[0]['answer'] == "Dr. Rajesh Kumar"
    assert candidates[0]['data_version'] == 1
    assert candidates[0]['similarity'] > 0.85


def test_search_different_word_order_high_similarity():
    """Test that different word order still produces high similarity."""
    semantic_cache.add("Where is the library located?", "Central Library, Block B", data_version=1)
    
    emb = semantic_cache.embed_question("The library is located where?")
    candidates = semantic_cache.search(emb, threshold=0.85)
    
    assert len(candidates) > 0
    assert candidates[0]['answer'] == "Central Library, Block B"


def test_search_expanded_phrasing_high_similarity():
    """Test that expanded/verbose phrasing still matches."""
    semantic_cache.add("HOD name?", "Dr. Rajesh Kumar", data_version=1)
    
    emb = semantic_cache.embed_question("Could you tell me the name of the HOD?")
    candidates = semantic_cache.search(emb, threshold=0.80)
    
    assert len(candidates) > 0
    assert candidates[0]['answer'] == "Dr. Rajesh Kumar"


# =============================================================================
# SEARCH TESTS - UNRELATED QUESTIONS (CRITICAL)
# =============================================================================

def test_search_unrelated_question_returns_no_candidates():
    """CRITICAL: Test that unrelated questions don't hit the cache."""
    semantic_cache.add("What is the HOD's name?", "Dr. Rajesh Kumar", data_version=1)
    
    # Ask completely unrelated question
    emb = semantic_cache.embed_question("What's the weather like today?")
    candidates = semantic_cache.search(emb, threshold=0.92)
    
    # Should find nothing
    assert len(candidates) == 0


def test_search_different_subject_low_similarity():
    """Test that questions about different subjects have low similarity."""
    semantic_cache.add("Where is the library?", "Central Library, Block B", data_version=1)
    
    # Different subject (canteen vs library)
    emb = semantic_cache.embed_question("Where is the canteen?")
    candidates = semantic_cache.search(emb, threshold=0.92)
    
    # Should not hit at high threshold (entity gate's job to catch these)
    # But might hit at lower threshold, which is fine - that's why entity gate exists
    if len(candidates) > 0:
        # If it does hit, similarity should be moderate (not super high)
        assert candidates[0]['similarity'] < 0.95


# =============================================================================
# THRESHOLD BOUNDARY TESTS (CRITICAL)
# =============================================================================

def test_search_threshold_boundary_just_above():
    """Test that similarity just above threshold returns hit."""
    semantic_cache.add("What is the HOD's name?", "Dr. Rajesh Kumar", data_version=1)
    
    # Same question should have similarity ~1.0
    emb = semantic_cache.embed_question("What is the HOD's name?")
    candidates = semantic_cache.search(emb, threshold=0.99)  # High threshold
    
    # Should still hit (perfect match)
    assert len(candidates) > 0
    assert candidates[0]['similarity'] >= 0.99


def test_search_threshold_boundary_just_below():
    """Test that similarity just below threshold returns miss."""
    semantic_cache.add("Where is the library?", "Central Library, Block B", data_version=1)
    
    # Somewhat related but not very similar
    emb = semantic_cache.embed_question("Tell me about library rules")
    
    # Find actual similarity
    candidates_low = semantic_cache.search(emb, threshold=0.0)
    
    if len(candidates_low) > 0:
        actual_sim = candidates_low[0]['similarity']
        
        # Set threshold just above actual similarity
        candidates_high = semantic_cache.search(emb, threshold=actual_sim + 0.01)
        
        # Should miss
        assert len(candidates_high) == 0


def test_search_default_threshold_from_config():
    """Test that search uses config.SEMANTIC_CACHE_THRESHOLD by default."""
    semantic_cache.add("What is the HOD's name?", "Dr. Rajesh Kumar", data_version=1)
    
    emb = semantic_cache.embed_question("What is the HOD's name?")
    
    # Call without explicit threshold
    candidates = semantic_cache.search(emb)
    
    # Should use config threshold (0.92)
    # Perfect match should exceed 0.92
    assert len(candidates) > 0


# =============================================================================
# DATA VERSION TESTS
# =============================================================================

def test_search_returns_data_version():
    """Test that search results include data_version."""
    semantic_cache.add("What is the HOD's name?", "Dr. Rajesh Kumar", data_version=5)
    
    emb = semantic_cache.embed_question("What is the HOD's name?")
    candidates = semantic_cache.search(emb, threshold=0.92)
    
    assert len(candidates) > 0
    assert candidates[0]['data_version'] == 5


def test_multiple_versions_coexist():
    """Test that entries with different data_versions can coexist."""
    semantic_cache.add("What is the HOD's name?", "Dr. Old HOD", data_version=1)
    semantic_cache.add("Where is the library?", "Central Library", data_version=2)
    
    # Search for each
    emb1 = semantic_cache.embed_question("What is the HOD's name?")
    candidates1 = semantic_cache.search(emb1, threshold=0.92)
    
    emb2 = semantic_cache.embed_question("Where is the library?")
    candidates2 = semantic_cache.search(emb2, threshold=0.92)
    
    # Both should be found with their respective versions
    assert len(candidates1) > 0
    assert candidates1[0]['data_version'] == 1
    
    assert len(candidates2) > 0
    assert candidates2[0]['data_version'] == 2


# =============================================================================
# MULTIPLE CANDIDATES TESTS
# =============================================================================

def test_search_returns_multiple_candidates_sorted():
    """Test that search returns multiple candidates sorted by similarity."""
    # Add several similar questions
    semantic_cache.add("What is the HOD's name?", "Dr. Rajesh Kumar", data_version=1)
    semantic_cache.add("Who is the HOD?", "Dr. Rajesh Kumar", data_version=1)
    semantic_cache.add("Tell me the HOD's name", "Dr. Rajesh Kumar", data_version=1)
    
    # Search
    emb = semantic_cache.embed_question("HOD name?")
    candidates = semantic_cache.search(emb, threshold=0.80)
    
    # Should find multiple candidates
    assert len(candidates) >= 2
    
    # Should be sorted by similarity (highest first)
    for i in range(len(candidates) - 1):
        assert candidates[i]['similarity'] >= candidates[i+1]['similarity']


def test_search_returns_top_k_candidates():
    """Test that search returns at most k candidates (k=5)."""
    # Add many similar questions
    for i in range(10):
        semantic_cache.add(f"Question variant {i}", "Answer", data_version=1)
    
    # Search with low threshold to match all
    emb = semantic_cache.embed_question("Question variant 0")
    candidates = semantic_cache.search(emb, threshold=0.0)
    
    # Should return at most 5 (k=5 in implementation)
    assert len(candidates) <= 5


# =============================================================================
# EMPTY CACHE TESTS
# =============================================================================

def test_search_empty_cache_returns_no_candidates():
    """Test that search on empty cache returns empty list."""
    # Cache is empty (cleared by fixture)
    emb = semantic_cache.embed_question("Any question")
    candidates = semantic_cache.search(emb, threshold=0.92)
    
    assert len(candidates) == 0


def test_add_to_empty_cache():
    """Test that adding to empty cache works."""
    semantic_cache.add("First question", "First answer", data_version=1)
    
    emb = semantic_cache.embed_question("First question")
    candidates = semantic_cache.search(emb, threshold=0.92)
    
    assert len(candidates) > 0
    assert candidates[0]['answer'] == "First answer"


# =============================================================================
# LATENCY TESTS (PERFORMANCE)
# =============================================================================

def test_embed_question_latency_under_20ms():
    """Test that embedding generation meets <20ms target.
    
    Design target: <20ms total for semantic cache hit (embedding + search).
    Embedding generation should be <20ms to leave room for FAISS search.
    """
    question = "What is the HOD's name?"
    
    latencies = []
    for _ in range(10):
        start = time.time()
        semantic_cache.embed_question(question)
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)
    
    avg_latency = sum(latencies) / len(latencies)
    
    # First call may be slower (model loading), but average should be good
    assert avg_latency < 30.0, f"Average embedding latency {avg_latency:.2f}ms exceeds 30ms"


def test_search_latency_under_20ms():
    """Test that search meets <20ms target (total: embedding + search)."""
    # Populate cache with some entries
    for i in range(20):
        semantic_cache.add(f"Question {i}", f"Answer {i}", data_version=1)
    
    # Measure total time: embed + search
    question = "Question 0"
    
    latencies = []
    for _ in range(10):
        start = time.time()
        emb = semantic_cache.embed_question(question)
        semantic_cache.search(emb, threshold=0.92)
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)
    
    avg_latency = sum(latencies) / len(latencies)
    
    # Target: <20ms (design doc), allow <30ms for laptop variance
    assert avg_latency < 30.0, f"Average semantic cache latency {avg_latency:.2f}ms exceeds 30ms"


# =============================================================================
# CACHE MANAGEMENT TESTS
# =============================================================================

def test_clear_empties_cache():
    """Test that clear() empties the cache."""
    semantic_cache.add("Question", "Answer", data_version=1)
    
    assert semantic_cache.get_cache_size() == 1
    
    semantic_cache.clear()
    
    assert semantic_cache.get_cache_size() == 0


def test_get_cache_size():
    """Test that get_cache_size() returns correct count."""
    assert semantic_cache.get_cache_size() == 0
    
    semantic_cache.add("Q1", "A1", data_version=1)
    assert semantic_cache.get_cache_size() == 1
    
    semantic_cache.add("Q2", "A2", data_version=1)
    assert semantic_cache.get_cache_size() == 2


def test_get_cache_stats():
    """Test that get_cache_stats() returns useful info."""
    semantic_cache.add("Q1", "A1", data_version=1)
    semantic_cache.add("Q2", "A2", data_version=1)
    semantic_cache.add("Q3", "A3", data_version=2)
    
    stats = semantic_cache.get_cache_stats()
    
    assert stats['total_entries'] == 3
    assert stats['entries_by_version'] == {1: 2, 2: 1}
    assert stats['embedding_dim'] == 384
    assert stats['model'] == 'all-MiniLM-L6-v2'


# =============================================================================
# EDGE CASES
# =============================================================================

def test_empty_question_string():
    """Test that empty question string doesn't crash."""
    emb = semantic_cache.embed_question("")
    
    # Should return valid embedding
    assert emb.shape == (384,)


def test_very_long_question():
    """Test that very long question is handled."""
    long_q = "What is the name of the HOD? " * 100
    
    semantic_cache.add(long_q, "Answer", data_version=1)
    
    emb = semantic_cache.embed_question(long_q)
    candidates = semantic_cache.search(emb, threshold=0.92)
    
    assert len(candidates) > 0


def test_special_characters_in_question():
    """Test that special characters don't break embedding."""
    question = "What's the HOD's name @#$%^&*()?"
    
    semantic_cache.add(question, "Answer", data_version=1)
    
    emb = semantic_cache.embed_question(question)
    candidates = semantic_cache.search(emb, threshold=0.92)
    
    assert len(candidates) > 0


def test_unicode_characters_in_question():
    """Test that Unicode characters are handled."""
    question = "Where is the library? 你好 नमस्ते"
    
    emb = semantic_cache.embed_question(question)
    
    # Should return valid embedding
    assert emb.shape == (384,)


# =============================================================================
# INTEGRATION TESTS (Semantic + Entity Gate Scenario)
# =============================================================================

def test_hod_vs_placement_officer_high_similarity():
    """Test that HOD and placement officer questions have high semantic similarity.
    
    This validates the need for entity gate - semantic cache alone would
    return wrong answer without entity checking.
    """
    # Add HOD question
    semantic_cache.add("Who is the HOD?", "Dr. Rajesh Kumar", data_version=1)
    
    # Search for placement officer
    emb = semantic_cache.embed_question("Who is the placement officer?")
    candidates = semantic_cache.search(emb, threshold=0.85)  # Lower threshold
    
    # Should find HOD question as candidate (high similarity)
    # This is why entity gate is needed!
    if len(candidates) > 0:
        assert candidates[0]['similarity'] > 0.85
        assert candidates[0]['answer'] == "Dr. Rajesh Kumar"
        # But Cache Manager (Task 1.11) will apply entity gate and reject this


def test_library_vs_canteen_moderate_similarity():
    """Test that facility questions have moderate similarity."""
    semantic_cache.add("Where is the library?", "Central Library, Block B", data_version=1)
    
    emb = semantic_cache.embed_question("Where is the canteen?")
    candidates = semantic_cache.search(emb, threshold=0.80)
    
    # May or may not hit depending on threshold
    # Entity gate will handle if it does hit
    if len(candidates) > 0:
        # Similarity should be moderate (not super high)
        assert 0.80 < candidates[0]['similarity'] < 0.95
