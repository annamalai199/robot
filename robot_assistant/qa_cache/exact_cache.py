"""Exact-match cache for QA pairs with data version tracking.

Hash-based O(1) lookup for exact question text matches. Part of the 3-tier
cache system (exact → semantic → entity-gated).

Key Features:
- Question text normalization (shared with intents.py for consistency)
- data_version tagging to invalidate cache after nightly CrewAI refresh
- Reads data_version from data/data_version.txt (synced with CrewAI refresh)
- In-memory dict (fast, no persistence needed for current scope)
- Latency target: <5ms (simple dict lookup)

Design Rationale (from Section 6):
Cache entries must go stale after the nightly CrewAI refresh, not silently
serve pre-refresh answers. data_version field enables this - if stored version
doesn't match current version, treat as cache miss.

CRITICAL: data_version must be read from data/data_version.txt so that when
CrewAI (Task 6.1) bumps the version file, the cache sees it and treats all
old entries as stale. Without this connection, stale answers would pass the
version check forever.

MAIN LOOP REQUIREMENT (Task 4.5):
The main application loop must call reload_data_version() periodically
(e.g., once per minute) to detect when CrewAI has updated data/data_version.txt.
CrewAI is an offline job that can't reach into running Python process memory,
so without periodic reload, the cache will serve against its stale in-memory
version until app restart, even though the file is correctly updated.

Example main loop integration:
    last_version_check = time.time()
    while True:
        # ... normal event processing ...
        
        # Check for version updates once per minute
        if time.time() - last_version_check > 60:
            exact_cache.reload_data_version()
            last_version_check = time.time()
"""

import logging
import time
from typing import Optional
from pathlib import Path

from robot_assistant.config import config
from robot_assistant.decision_engine.intents import normalize_text

logger = logging.getLogger(__name__)

# In-memory cache: normalized_question -> cache_entry
# cache_entry = {"answer": str, "data_version": int, "timestamp": float}
_cache: dict[str, dict] = {}

# Current data version - loaded from data/data_version.txt
_current_data_version: Optional[int] = None


def _load_data_version() -> int:
    """Load data version from file.
    
    Returns:
        Data version integer from data/data_version.txt, or 1 if file doesn't exist.
    """
    version_path = Path(config.DATA_VERSION_PATH)
    
    try:
        if version_path.exists():
            version_str = version_path.read_text().strip()
            version = int(version_str)
            logger.debug(f"Loaded data version {version} from {version_path}")
            return version
        else:
            logger.warning(f"Data version file not found at {version_path}, defaulting to 1")
            return 1
    except (ValueError, IOError) as e:
        logger.error(f"Failed to read data version from {version_path}: {e}, defaulting to 1")
        return 1


def _save_data_version(version: int) -> None:
    """Save data version to file.
    
    Args:
        version: Data version to write to data/data_version.txt.
    """
    version_path = Path(config.DATA_VERSION_PATH)
    
    try:
        # Ensure directory exists
        version_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write version
        version_path.write_text(str(version))
        logger.debug(f"Saved data version {version} to {version_path}")
    except IOError as e:
        logger.error(f"Failed to write data version to {version_path}: {e}")


# Load initial data version from file
_current_data_version = _load_data_version()


def normalize_question(question: str) -> str:
    """Normalize question text for consistent cache lookup.
    
    Uses the same normalization function as intents.py (normalize_text):
    - Lowercase for case-insensitive matching
    - Strip leading/trailing whitespace
    - Remove trailing punctuation (?, !, .)
    - Collapse multiple spaces to single space
    
    Args:
        question: Raw question text from user.
    
    Returns:
        Normalized question text for cache key.
    
    Examples:
        "What's my attendance?" -> "what's my attendance"
        "  WHAT IS  the  schedule?  " -> "what is the schedule"
    """
    # Use shared normalization from intents.py
    return normalize_text(question)


def get(question: str) -> Optional[dict]:
    """Check exact-match cache for a question.
    
    Args:
        question: User's question text (will be normalized).
    
    Returns:
        Dict with 'answer' and 'data_version' if cache hit with matching version,
        None if cache miss or version mismatch.
        
    Cache Hit Conditions:
        1. Normalized question exists in cache, AND
        2. Cached data_version matches current data_version
        
    Cache Miss Conditions:
        - Question never seen before, OR
        - Cached data_version doesn't match current version (stale data)
    
    Latency: Target <5ms (simple dict lookup)
    
    Example:
        >>> set_data_version(1)
        >>> put("What's my attendance?", "85%", 1)
        >>> get("What's my attendance?")  # Case-insensitive
        {"answer": "85%", "data_version": 1}
        >>> get("WHAT'S MY ATTENDANCE?")  # Normalized match
        {"answer": "85%", "data_version": 1}
        >>> set_data_version(2)  # Nightly refresh
        >>> get("What's my attendance?")  # Version mismatch
        None
    """
    start_time = time.time()
    
    # Normalize question for lookup
    normalized = normalize_question(question)
    
    # Check if question exists in cache
    if normalized not in _cache:
        latency_ms = (time.time() - start_time) * 1000
        logger.debug(f"Cache MISS (not found): '{normalized}' ({latency_ms:.2f}ms)")
        return None
    
    # Question exists - check data version
    entry = _cache[normalized]
    cached_version = entry["data_version"]
    
    if cached_version != _current_data_version:
        # Data version mismatch - treat as miss (stale data)
        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Cache MISS (stale version): '{normalized}' "
            f"(cached v{cached_version} != current v{_current_data_version}) "
            f"({latency_ms:.2f}ms)"
        )
        return None
    
    # Cache hit - return answer
    latency_ms = (time.time() - start_time) * 1000
    logger.info(f"Cache HIT: '{normalized}' ({latency_ms:.2f}ms)")
    
    return {
        "answer": entry["answer"],
        "data_version": entry["data_version"]
    }


def put(question: str, answer: str, data_version: int) -> None:
    """Store a QA pair in the exact-match cache.
    
    Args:
        question: User's question text (will be normalized).
        answer: Answer text to cache.
        data_version: Data version tag (from current nightly refresh cycle).
    
    Side Effects:
        Stores normalized question -> answer + data_version in cache.
        Overwrites existing entry if question already cached.
    
    Example:
        >>> put("What's the HOD's name?", "Dr. Rajesh Kumar", 1)
        >>> put("WHAT'S THE HOD'S NAME?", "Dr. Rajesh Kumar", 1)  # Same after normalization
    """
    normalized = normalize_question(question)
    
    _cache[normalized] = {
        "answer": answer,
        "data_version": data_version,
        "timestamp": time.time()
    }
    
    logger.debug(f"Cached: '{normalized}' (v{data_version})")


def set_data_version(version: int) -> None:
    """Set the current data version (called after nightly CrewAI refresh).
    
    Args:
        version: New data version number (incrementing integer).
    
    Side Effects:
        Updates global _current_data_version.
        Writes version to data/data_version.txt (synced with CrewAI).
        All cache entries with older versions will be treated as misses.
    
    Example:
        >>> set_data_version(1)  # Initial startup
        >>> # ... cache gets populated ...
        >>> set_data_version(2)  # After nightly refresh
        >>> # All v1 entries now return None (stale)
    """
    global _current_data_version
    old_version = _current_data_version
    _current_data_version = version
    
    # Write to file so CrewAI and cache stay synced
    _save_data_version(version)
    
    logger.info(f"Data version updated: v{old_version} -> v{version}")


def get_data_version() -> int:
    """Get the current data version.
    
    Returns:
        Current data version number.
    """
    return _current_data_version


def reload_data_version() -> int:
    """Reload data version from file (after external update by CrewAI).
    
    Call this when CrewAI (Task 6.1) updates data/data_version.txt after
    its nightly refresh. This ensures the cache sees the new version and
    treats all old entries as stale.
    
    Returns:
        New data version number loaded from file.
    
    Example:
        >>> # CrewAI runs nightly refresh, bumps data/data_version.txt: 1 -> 2
        >>> reload_data_version()  # Cache now knows about version 2
        2
        >>> # All v1 cache entries now treated as stale
    """
    global _current_data_version
    old_version = _current_data_version
    _current_data_version = _load_data_version()
    
    if _current_data_version != old_version:
        logger.info(f"Reloaded data version from file: v{old_version} -> v{_current_data_version}")
    
    return _current_data_version


def clear() -> None:
    """Clear all cached entries (for testing/reset).
    
    Side Effects:
        Empties the in-memory cache dict.
        Does NOT reset data version.
    """
    _cache.clear()
    logger.debug("Cache cleared")


def get_cache_size() -> int:
    """Get the number of entries in cache.
    
    Returns:
        Count of cached QA pairs (includes stale versions).
    """
    return len(_cache)


def get_cache_stats() -> dict:
    """Get cache statistics for monitoring/debugging.
    
    Returns:
        Dict with cache size, current version, and per-version counts.
    """
    version_counts = {}
    for entry in _cache.values():
        v = entry["data_version"]
        version_counts[v] = version_counts.get(v, 0) + 1
    
    return {
        "total_entries": len(_cache),
        "current_version": _current_data_version,
        "entries_by_version": version_counts
    }
