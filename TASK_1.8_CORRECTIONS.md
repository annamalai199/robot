# Task 1.8 Critical Corrections Applied

## Summary
Two critical architectural issues were identified and fixed before proceeding to Task 1.9:

1. **Data version disconnection** - Cache wasn't reading/writing data/data_version.txt
2. **Normalize function duplication** - Reimplemented instead of sharing intents.normalize_text()

Both fixes are now complete with comprehensive test coverage.

---

## Issue 1: Data Version File Disconnection ❌ → ✅

### Problem Identified
The initial implementation had `_current_data_version` as an in-memory counter starting at 1, completely **disconnected from data/data_version.txt**. 

**Why this breaks the system:**
1. CrewAI (Task 6.1) will bump `data/data_version.txt` after nightly refresh: 1 → 2
2. Cache never reads the file, so `_current_data_version` stays at 1
3. All cache entries with version 1 continue to pass the version check
4. **Stale answers served forever** (defeats entire purpose of data_version)

### Fix Applied

#### Code Changes:
```python
# Before (BROKEN):
_current_data_version: int = 1  # Hardcoded, never reads file

# After (FIXED):
_current_data_version: Optional[int] = None

def _load_data_version() -> int:
    """Load data version from data/data_version.txt"""
    version_path = Path(config.DATA_VERSION_PATH)
    if version_path.exists():
        return int(version_path.read_text().strip())
    return 1

def _save_data_version(version: int) -> None:
    """Save data version to data/data_version.txt"""
    version_path = Path(config.DATA_VERSION_PATH)
    version_path.parent.mkdir(parents=True, exist_ok=True)
    version_path.write_text(str(version))

# Module init: Load from file
_current_data_version = _load_data_version()
```

#### New Functions:
1. **`_load_data_version()`** - Read version from file (used on module load)
2. **`_save_data_version(version)`** - Write version to file (used by set_data_version)
3. **`reload_data_version()`** - PUBLIC: Reload from file after external update

#### Updated Functions:
- **`set_data_version(version)`** - Now calls `_save_data_version()` to persist to file

### Test Coverage Added
```python
def test_set_data_version_writes_to_file():
    """Verify set_data_version() persists to data/data_version.txt"""

def test_reload_data_version_reads_from_file():
    """Verify reload_data_version() picks up external file changes"""

def test_initial_load_from_file():
    """Verify module loads initial version from file if it exists"""

def test_cache_staleness_after_crewai_refresh():
    """CRITICAL INTEGRATION TEST: Simulates real CrewAI workflow
    
    1. Cache has entries with version 1
    2. CrewAI writes version 2 to file
    3. Cache reloads version from file
    4. All v1 entries should be stale (return None)
    """
```

### Real Workflow (Now Correct)
```python
# Application startup
# → exact_cache.py loads: _current_data_version = _load_data_version()
# → Reads data/data_version.txt: "1"

# Day operations: Cache writes with v1
exact_cache.put("Lab hours?", "Monday 2-5 PM", data_version=1)

# Night: CrewAI runs refresh
# → crewai_client.py writes data/data_version.txt: "2"

# Morning: Application still running, cache reloads
exact_cache.reload_data_version()
# → Reads data/data_version.txt: "2"
# → _current_data_version = 2

# Now all v1 cache entries return None (stale) ✅
exact_cache.get("Lab hours?") → None
```

---

## Issue 2: Normalize Function Duplication ❌ → ✅

### Problem Identified
`exact_cache.normalize_question()` **reimplemented** the same logic as `intents.normalize_text()`:

```python
# intents.py
def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.strip()
    while text and text[-1] in ".,!?;:":
        text = text[:-1]
    text = " ".join(text.split())
    return text

# exact_cache.py (DUPLICATE!)
def normalize_question(question: str) -> str:
    text = question.lower()        # Same logic
    text = text.strip()            # Same logic
    while text and text[-1] in ".,!?;:":  # Same logic
        text = text[:-1]
    text = " ".join(text.split())  # Same logic
    return text
```

**Why this is dangerous:**
- Two implementations can **silently drift apart** over time
- If someone updates intents.py normalization, cache normalization won't match
- "hello" might normalize differently in intent vs cache paths
- Hard to spot bugs (logic looks identical initially)

### Fix Applied

#### Code Changes:
```python
# Before (DUPLICATE):
def normalize_question(question: str) -> str:
    text = question.lower()
    text = text.strip()
    # ... 10 more lines of duplicated logic

# After (SHARED):
from robot_assistant.decision_engine.intents import normalize_text

def normalize_question(question: str) -> str:
    """Normalize question text for consistent cache lookup.
    
    Uses the same normalization function as intents.py (normalize_text).
    """
    return normalize_text(question)  # Single source of truth
```

### Test Coverage Added
```python
def test_normalize_question_uses_shared_function():
    """Test that normalize_question uses intents.normalize_text.
    
    Ensures normalization can't silently drift between intents and cache.
    """
    from robot_assistant.decision_engine.intents import normalize_text
    
    test_cases = [
        "Hello World",
        "  WHAT IS THE  SCHEDULE?  ",
        "Thanks!!!",
        "bye.",
    ]
    
    for test_input in test_cases:
        # Both should produce IDENTICAL output
        cache_normalized = exact_cache.normalize_question(test_input)
        intents_normalized = normalize_text(test_input)
        
        assert cache_normalized == intents_normalized
```

### Benefits
✅ Single source of truth - one function, one implementation  
✅ Can't drift apart - changes automatically apply to both paths  
✅ Clearer code - `normalize_question` is now a thin wrapper with clear intent  
✅ Test enforces this - fails if implementations diverge

---

## Verification

### Before Fixes
- ❌ Data version: In-memory counter, never reads/writes file
- ❌ Normalize: Duplicate implementation, can drift
- ⚠️ 205 tests passing (but architectural issues hidden)

### After Fixes
- ✅ Data version: File-based, synced with CrewAI
- ✅ Normalize: Shared function from intents.py
- ✅ 210 tests passing (5 new tests for file-based version + shared normalization)

### New Test Count Breakdown
- 24 original exact cache tests
- 3 new file-based version tests
- 1 new shared normalization test
- 1 new critical integration test (CrewAI workflow simulation)
- **= 29 total exact cache tests**

---

## Impact on Future Tasks

### Task 4.5: Main Application Loop
**CRITICAL DEPENDENCY DOCUMENTED:**
Main loop must call both:
1. `session_state.check_timeouts()` ~1x/second (Task 1.6 requirement)
2. `exact_cache.reload_data_version()` ~1x/minute (Task 1.8 requirement)

Without these periodic calls:
- Greeting timeout won't trigger (identities stuck in NEW state)
- Cache staleness won't detect CrewAI updates (serves stale data indefinitely)

Documentation added to:
- `exact_cache.py` module docstring
- `design.md` Section 4 (QA Cache Layer)
- `tasks.md` Task 4.5 acceptance criteria

### Task 6.1: CrewAI Nightly Refresh
**Before fix:** CrewAI bumps file, cache doesn't know → stale answers forever  
**After fix:** CrewAI bumps file, cache.reload_data_version() sees it → all old entries stale ✅

### Task 1.11: Cache Manager
**Before fix:** Cache and intents normalize differently → inconsistent behavior  
**After fix:** Both use same function → consistent across Path A and Path B ✅

### General Maintenance
**Before fix:** Two places to update normalization logic  
**After fix:** One place (`intents.normalize_text`) updates both ✅

---

## Lessons Learned

1. **Always check file I/O assumptions** - "data_version" implied file-based, but implementation was memory-only
2. **DRY principle matters** - Duplicate logic = silent drift risk
3. **Test the integration, not just the units** - `test_cache_staleness_after_crewai_refresh` caught the real workflow issue
4. **Document architectural dependencies** - Now clear that cache MUST read/write the file

---

**Status:** Both issues fixed and verified ✅  
**Tests:** 210/210 passing (5 new tests)  
**Ready for:** Task 1.9 Entity Extractor
