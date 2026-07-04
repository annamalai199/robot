"""Tests for exact-match cache with data version tracking.

Critical test cases:
1. Exact match hit (same normalized question)
2. Normalization (case, whitespace, punctuation)
3. Cache miss on unseen question
4. Data version mismatch (CRITICAL - cache staleness after refresh)
5. Data version file persistence and reload
"""

import pytest
import time
from pathlib import Path

from robot_assistant.qa_cache import exact_cache
from robot_assistant.config import config


@pytest.fixture(autouse=True)
def reset_cache():
    """Clear cache and reset data version before each test."""
    exact_cache.clear()
    exact_cache.set_data_version(1)
    yield
    exact_cache.clear()
    
    # Clean up test version file if it exists
    version_path = Path(config.DATA_VERSION_PATH)
    if version_path.exists():
        try:
            version_path.unlink()
        except:
            pass


# =============================================================================
# EXACT MATCH TESTS
# =============================================================================

def test_exact_match_hit():
    """Test that exact match returns cached answer."""
    question = "What's my attendance?"
    answer = "Your attendance is 85%"
    
    # Store in cache
    exact_cache.put(question, answer, data_version=1)
    
    # Retrieve - should hit
    result = exact_cache.get(question)
    
    assert result is not None
    assert result["answer"] == answer
    assert result["data_version"] == 1


def test_cache_miss_on_unseen_question():
    """Test that unseen question returns None (cache miss)."""
    # Cache one question
    exact_cache.put("What's my attendance?", "85%", data_version=1)
    
    # Ask different question - should miss
    result = exact_cache.get("What's the schedule?")
    
    assert result is None


def test_empty_cache_returns_none():
    """Test that empty cache returns None for any question."""
    result = exact_cache.get("Any question")
    
    assert result is None


# =============================================================================
# NORMALIZATION TESTS (Critical for consistency)
# =============================================================================

def test_case_insensitive_matching():
    """Test that different casing hits same cache entry."""
    # Store with lowercase
    exact_cache.put("what's my attendance?", "85%", data_version=1)
    
    # Query with different casing - should hit
    assert exact_cache.get("What's my attendance?") is not None
    assert exact_cache.get("WHAT'S MY ATTENDANCE?") is not None
    assert exact_cache.get("WhAt'S mY aTtEnDaNcE?") is not None


def test_whitespace_normalization():
    """Test that different whitespace hits same cache entry."""
    # Store with normal spacing
    exact_cache.put("What is the schedule?", "Monday 2-5 PM", data_version=1)
    
    # Query with different whitespace - should hit
    assert exact_cache.get("What is the schedule?") is not None
    assert exact_cache.get("  What is the schedule?  ") is not None
    assert exact_cache.get("What  is   the    schedule?") is not None


def test_punctuation_normalization():
    """Test that trailing punctuation doesn't affect matching."""
    # Store with question mark
    exact_cache.put("What's my attendance?", "85%", data_version=1)
    
    # Query with different punctuation - should hit
    assert exact_cache.get("What's my attendance") is not None
    assert exact_cache.get("What's my attendance?") is not None
    assert exact_cache.get("What's my attendance!") is not None
    assert exact_cache.get("What's my attendance.") is not None


def test_combined_normalization():
    """Test that case + whitespace + punctuation all normalized together."""
    # Store with one format
    exact_cache.put("what is the hod's name", "Dr. Rajesh Kumar", data_version=1)
    
    # Query with completely different format - should hit
    result = exact_cache.get("  WHAT   IS  THE   HOD'S  NAME???  ")
    
    assert result is not None
    assert result["answer"] == "Dr. Rajesh Kumar"


def test_normalize_question_function():
    """Test normalize_question function directly."""
    # Case normalization
    assert exact_cache.normalize_question("Hello") == "hello"
    assert exact_cache.normalize_question("HELLO") == "hello"
    
    # Whitespace normalization
    assert exact_cache.normalize_question("  hello  ") == "hello"
    assert exact_cache.normalize_question("hello   world") == "hello world"
    
    # Punctuation removal
    assert exact_cache.normalize_question("hello?") == "hello"
    assert exact_cache.normalize_question("hello!") == "hello"
    assert exact_cache.normalize_question("hello.") == "hello"
    assert exact_cache.normalize_question("hello...") == "hello"
    
    # Combined
    assert exact_cache.normalize_question("  HELLO  WORLD!!!  ") == "hello world"


# =============================================================================
# DATA VERSION TESTS (CRITICAL - prevents stale data)
# =============================================================================

def test_data_version_mismatch_returns_none():
    """Test that cached entry with old version returns None (cache miss).
    
    This is CRITICAL: After nightly CrewAI refresh, old cache entries must
    not be served. They should be treated as misses, forcing LLM re-generation.
    """
    question = "What's my attendance?"
    
    # Cache answer with version 1
    exact_cache.set_data_version(1)
    exact_cache.put(question, "85%", data_version=1)
    
    # Verify it hits with version 1
    assert exact_cache.get(question) is not None
    
    # Simulate nightly refresh - increment version
    exact_cache.set_data_version(2)
    
    # Same question should now MISS (stale data)
    result = exact_cache.get(question)
    assert result is None


def test_mixed_versions_in_cache():
    """Test that cache correctly handles mixed version entries."""
    # Set version 1, cache some entries
    exact_cache.set_data_version(1)
    exact_cache.put("Question 1", "Answer 1", data_version=1)
    exact_cache.put("Question 2", "Answer 2", data_version=1)
    
    # Set version 2, cache new entries
    exact_cache.set_data_version(2)
    exact_cache.put("Question 3", "Answer 3", data_version=2)
    exact_cache.put("Question 4", "Answer 4", data_version=2)
    
    # Version 1 entries should MISS
    assert exact_cache.get("Question 1") is None
    assert exact_cache.get("Question 2") is None
    
    # Version 2 entries should HIT
    assert exact_cache.get("Question 3") is not None
    assert exact_cache.get("Question 4") is not None


def test_set_and_get_data_version():
    """Test data version getter and setter."""
    # Initial version
    assert exact_cache.get_data_version() == 1
    
    # Update version
    exact_cache.set_data_version(5)
    assert exact_cache.get_data_version() == 5
    
    # Update again
    exact_cache.set_data_version(10)
    assert exact_cache.get_data_version() == 10


def test_put_with_current_version():
    """Test that put with current version allows retrieval."""
    exact_cache.set_data_version(3)
    
    # Cache with current version
    exact_cache.put("Question", "Answer", data_version=3)
    
    # Should hit
    result = exact_cache.get("Question")
    assert result is not None
    assert result["data_version"] == 3


def test_version_mismatch_critical_regression():
    """CRITICAL REGRESSION TEST: Old version must not serve stale data.
    
    This test ensures the whole reason data_version exists works correctly:
    After nightly CrewAI refresh, cache must go stale, not silently serve
    pre-refresh answers.
    """
    # Day 1: Cache some answers with version 1
    exact_cache.set_data_version(1)
    exact_cache.put("What are the lab hours?", "Monday 2-5 PM", data_version=1)
    exact_cache.put("Who is the HOD?", "Dr. Rajesh Kumar", data_version=1)
    
    # Verify they hit on day 1
    assert exact_cache.get("What are the lab hours?")["answer"] == "Monday 2-5 PM"
    assert exact_cache.get("Who is the HOD?")["answer"] == "Dr. Rajesh Kumar"
    
    # Night: CrewAI refresh happens, version increments
    exact_cache.set_data_version(2)
    
    # Day 2: Same questions should MISS (force LLM re-generation with fresh data)
    assert exact_cache.get("What are the lab hours?") is None
    assert exact_cache.get("Who is the HOD?") is None
    
    # Day 2: New cache entries with version 2
    exact_cache.put("What are the lab hours?", "Monday 3-6 PM", data_version=2)  # Schedule changed
    exact_cache.put("Who is the HOD?", "Dr. Anitha Reddy", data_version=2)  # HOD changed
    
    # Day 2: New entries should hit
    assert exact_cache.get("What are the lab hours?")["answer"] == "Monday 3-6 PM"
    assert exact_cache.get("Who is the HOD?")["answer"] == "Dr. Anitha Reddy"


# =============================================================================
# CACHE MANAGEMENT TESTS
# =============================================================================

def test_clear_empties_cache():
    """Test that clear() removes all entries."""
    # Add entries
    exact_cache.put("Question 1", "Answer 1", data_version=1)
    exact_cache.put("Question 2", "Answer 2", data_version=1)
    
    assert exact_cache.get_cache_size() == 2
    
    # Clear
    exact_cache.clear()
    
    assert exact_cache.get_cache_size() == 0
    assert exact_cache.get("Question 1") is None
    assert exact_cache.get("Question 2") is None


def test_clear_does_not_reset_version():
    """Test that clear() doesn't reset data version."""
    exact_cache.set_data_version(5)
    
    # Add and clear
    exact_cache.put("Question", "Answer", data_version=5)
    exact_cache.clear()
    
    # Version should still be 5
    assert exact_cache.get_data_version() == 5


def test_get_cache_size():
    """Test cache size tracking."""
    assert exact_cache.get_cache_size() == 0
    
    exact_cache.put("Q1", "A1", 1)
    assert exact_cache.get_cache_size() == 1
    
    exact_cache.put("Q2", "A2", 1)
    assert exact_cache.get_cache_size() == 2
    
    # Overwrite doesn't increase size
    exact_cache.put("Q1", "A1 updated", 1)
    assert exact_cache.get_cache_size() == 2


def test_get_cache_stats():
    """Test cache statistics reporting."""
    exact_cache.set_data_version(1)
    
    # Empty cache
    stats = exact_cache.get_cache_stats()
    assert stats["total_entries"] == 0
    assert stats["current_version"] == 1
    
    # Add some entries
    exact_cache.put("Q1", "A1", 1)
    exact_cache.put("Q2", "A2", 1)
    exact_cache.set_data_version(2)
    exact_cache.put("Q3", "A3", 2)
    
    stats = exact_cache.get_cache_stats()
    assert stats["total_entries"] == 3
    assert stats["current_version"] == 2
    assert stats["entries_by_version"][1] == 2
    assert stats["entries_by_version"][2] == 1


def test_overwrite_existing_entry():
    """Test that putting same question overwrites previous entry."""
    question = "What's my attendance?"
    
    # Initial entry
    exact_cache.put(question, "85%", data_version=1)
    assert exact_cache.get(question)["answer"] == "85%"
    
    # Overwrite
    exact_cache.put(question, "90%", data_version=1)
    assert exact_cache.get(question)["answer"] == "90%"
    
    # Size should still be 1 (overwrite, not add)
    assert exact_cache.get_cache_size() == 1


# =============================================================================
# LATENCY TESTS
# =============================================================================

def test_latency_target_under_5ms():
    """Test that cache operations meet <5ms latency target.
    
    Target from design.md Section 8: Exact-match cache should be <5ms.
    """
    # Populate cache with some entries
    for i in range(100):
        exact_cache.put(f"Question {i}", f"Answer {i}", data_version=1)
    
    # Measure get() latency
    latencies = []
    for i in range(100):
        start = time.time()
        exact_cache.get(f"Question {i}")
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)
    
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    
    # Should be well under 5ms (likely <1ms for dict lookup)
    assert avg_latency < 5.0, f"Average latency {avg_latency:.2f}ms exceeds 5ms target"
    assert max_latency < 10.0, f"Max latency {max_latency:.2f}ms too high"


def test_put_latency():
    """Test that put() is also fast (not a bottleneck)."""
    latencies = []
    
    for i in range(100):
        start = time.time()
        exact_cache.put(f"Question {i}", f"Answer {i}", data_version=1)
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)
    
    avg_latency = sum(latencies) / len(latencies)
    
    # Put should also be fast (dict assignment)
    assert avg_latency < 5.0, f"Put latency {avg_latency:.2f}ms exceeds 5ms"


# =============================================================================
# EDGE CASES
# =============================================================================

def test_empty_question():
    """Test that empty question doesn't crash."""
    exact_cache.put("", "Empty answer", data_version=1)
    result = exact_cache.get("")
    
    assert result is not None
    assert result["answer"] == "Empty answer"


def test_very_long_question():
    """Test that very long questions work correctly."""
    long_question = "What is " + "the " * 100 + "answer?"
    
    exact_cache.put(long_question, "The answer", data_version=1)
    result = exact_cache.get(long_question)
    
    assert result is not None
    assert result["answer"] == "The answer"


def test_special_characters_in_question():
    """Test that special characters are preserved (except trailing punctuation)."""
    question = "What's the @#$% attendance for user_123?"
    
    exact_cache.put(question, "85%", data_version=1)
    
    # Should normalize to remove trailing ? but keep rest
    result = exact_cache.get("What's the @#$% attendance for user_123")
    assert result is not None


def test_unicode_characters():
    """Test that Unicode characters work correctly."""
    question = "Who is the HOD? 你好"
    
    exact_cache.put(question, "Dr. Rajesh Kumar", data_version=1)
    result = exact_cache.get(question)
    
    assert result is not None


# =============================================================================
# FILE-BASED VERSION TRACKING TESTS (CRITICAL)
# =============================================================================

def test_set_data_version_writes_to_file():
    """Test that set_data_version() writes to data/data_version.txt."""
    version_path = Path(config.DATA_VERSION_PATH)
    
    # Set version
    exact_cache.set_data_version(5)
    
    # File should exist and contain "5"
    assert version_path.exists()
    content = version_path.read_text().strip()
    assert content == "5"


def test_reload_data_version_reads_from_file():
    """Test that reload_data_version() reads from file.
    
    CRITICAL: When CrewAI updates data/data_version.txt, cache must see it.
    """
    version_path = Path(config.DATA_VERSION_PATH)
    
    # Start with version 1
    exact_cache.set_data_version(1)
    assert exact_cache.get_data_version() == 1
    
    # Simulate CrewAI updating the file directly
    version_path.parent.mkdir(parents=True, exist_ok=True)
    version_path.write_text("3")
    
    # Reload should pick up the new version
    new_version = exact_cache.reload_data_version()
    
    assert new_version == 3
    assert exact_cache.get_data_version() == 3


def test_initial_load_from_file():
    """Test that module loads initial version from file if it exists."""
    version_path = Path(config.DATA_VERSION_PATH)
    
    # Create file with version 7
    version_path.parent.mkdir(parents=True, exist_ok=True)
    version_path.write_text("7")
    
    # Reload module state
    exact_cache._current_data_version = exact_cache._load_data_version()
    
    assert exact_cache.get_data_version() == 7


def test_cache_staleness_after_crewai_refresh():
    """CRITICAL INTEGRATION TEST: Cache goes stale after CrewAI bumps version file.
    
    This simulates the real workflow:
    1. Cache has entries with version 1
    2. CrewAI runs nightly refresh, writes version 2 to file
    3. Cache reloads version from file
    4. All v1 entries should now be stale (return None)
    """
    # Day 1: Cache some answers with version 1
    exact_cache.set_data_version(1)
    exact_cache.put("What are the lab hours?", "Monday 2-5 PM", data_version=1)
    exact_cache.put("Who is the HOD?", "Dr. Rajesh Kumar", data_version=1)
    
    # Verify cache hits
    assert exact_cache.get("What are the lab hours?") is not None
    assert exact_cache.get("Who is the HOD?") is not None
    
    # Night: CrewAI runs refresh, bumps version file
    version_path = Path(config.DATA_VERSION_PATH)
    version_path.write_text("2")
    
    # Morning: Cache reloads version from file
    exact_cache.reload_data_version()
    
    # All v1 entries should now be STALE (return None)
    assert exact_cache.get("What are the lab hours?") is None
    assert exact_cache.get("Who is the HOD?") is None
    
    # New queries with v2 will cache-miss, hit LLM, write back with v2
    exact_cache.put("What are the lab hours?", "Monday 3-6 PM", data_version=2)
    
    # v2 entries should hit
    assert exact_cache.get("What are the lab hours?")["answer"] == "Monday 3-6 PM"


def test_normalize_question_uses_shared_function():
    """Test that normalize_question uses intents.normalize_text (shared implementation).
    
    This ensures normalization can't silently drift between intents and cache.
    """
    from robot_assistant.decision_engine.intents import normalize_text
    
    test_cases = [
        "Hello World",
        "  WHAT IS THE  SCHEDULE?  ",
        "Thanks!!!",
        "bye.",
    ]
    
    for test_input in test_cases:
        # Both should produce identical output
        cache_normalized = exact_cache.normalize_question(test_input)
        intents_normalized = normalize_text(test_input)
        
        assert cache_normalized == intents_normalized, \
            f"Normalization mismatch: cache={cache_normalized}, intents={intents_normalized}"
