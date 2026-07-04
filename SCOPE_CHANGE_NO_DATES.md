# Scope Change: Remove Date-Sensitive Q&A

## Summary
Removed all date/calendar-based and schedule-related Q&A from the system. The robot now answers only general, static questions about people, facilities, and college information - no temporal/date-sensitive data.

## Rationale
- **Simplifies system:** No date parsing, no "today vs yesterday" logic
- **Reduces complexity:** Entity extractor drops entire date extraction module
- **Better fit for demo:** Static facts don't go stale, cache works indefinitely
- **Cleaner testing:** No need to mock/freeze time for tests

## Changes Applied

### 1. ✅ Task 1.9: Entity Extractor (Updated Before Implementation)
**Before:** `extract_entities() -> {"date": ..., "subject": ..., "person": ...}`  
**After:** `extract_entities() -> {"subject": ..., "person": ...}`

**Removed:**
- Date key entirely
- dateparser dependency
- DATE_PATTERNS regex
- "today", "yesterday", "tomorrow" parsing logic

**Kept:**
- Subject extraction (hod, library, canteen, placement, hostel, lab, etc.)
- Person extraction (capitalized words, stopword filtering)

### 2. ✅ Memory Facts (data/memory.db) - Regenerated
**Before (20 facts):**
- People: 5 facts (kept)
- **Schedule: 10 facts** (removed: lab hours, exam dates, deadlines, holidays, career fair)
- General: 5 facts (kept, updated)

**After (20 facts):**
- People: 5 facts (unchanged - faculty and staff)
- **Facilities: 10 facts** (new: library location/rules, canteen location/offerings, sports, parking, department location, auditorium, placement cell, lab equipment)
- General: 5 facts (updated: helpdesk, wifi, dress code, hostel info, college website)

**Key Changes:**
```
REMOVED schedule category:
- lab_hours_monday, lab_hours_wednesday
- office_hours_hod, library_hours
- exam_schedule, semester_start, class_timings
- project_deadline, holiday_next, career_fair

REMOVED date-sensitive general facts:
- canteen_menu_today (replaced with canteen_offerings - static menu types)

ADDED facilities category:
- library_rules, canteen_location, sports_facilities
- parking_info, auditorium_capacity
- All static, non-temporal information
```

### 3. ✅ design.md Entity Gate Example
**Before:** "attendance today" vs "attendance yesterday" (different date entity)  
**After:** "Who is the HOD?" vs "Who is the placement officer?" (different person entity)

**New Justification:**
Semantic similarity alone is dangerous - these two questions have high cosine similarity (~0.90+) but completely different correct answers. Entity gate prevents returning "Dr. Rajesh Kumar" (HOD) when asked about the placement officer.

### 4. ✅ config.py Updates

#### INTENT_RESPONSES:
```python
# Before:
"help": "I can answer questions about schedules, people, and general information..."

# After:
"help": "I can answer questions about people, facilities, and general college information..."
```

#### CACHE_TTL_SECONDS Comment:
```python
# Added note:
# All current memory facts are static/non-temporal (people, facilities, general info).
# No date-sensitive data (attendance, schedules, exams) in current scope.
# TTL mechanism stays available but unused - all facts can use CACHE_INDEFINITE policy.
```

### 5. ✅ tasks.md Updates

#### Task 1.9 Acceptance Criteria:
```markdown
# Before:
- Returns dict with keys: date, subject, person (all optional)
- Date extraction: "today", "yesterday", "tomorrow", explicit dates
- Tests today/yesterday distinction

# After:
- Returns dict with keys: subject, person (both optional, None if not found)
- No date extraction (no dateparser dependency) - all data is non-temporal
- Tests different subject/person extraction
```

#### Task 1.11 (Cache Manager) Regression Test:
```markdown
# Before:
- "attendance today" cached, then "attendance yesterday" asked → MISS

# After:
- "Who is the HOD?" cached, then "Who is the placement officer?" asked → MISS
  (entity gate prevents wrong-person answer)
```

#### Task 4.3 (E2E Cache Hit Test) Critical Regression:
```markdown
# Before:
- Asks "attendance today", then "attendance yesterday"
- Asserts entity gate prevented wrong cache hit

# After:
- Asks "Who is the HOD?", then "Who is the placement officer?"
- Asserts entity gate prevented wrong-person cache hit
  (semantically similar but different person)
```

### 6. ✅ Seed Script (scripts/init_memory_db.py)
**Module Docstring Updated:**
```python
# Before:
"""Creates memory.db with 20 college-contextual facts across 3 categories:
- People (5 facts)
- Schedule (10 facts)
- General (5 facts)
"""

# After:
"""Creates memory.db with 20 college-contextual facts across 3 categories:
- People (5 facts) - Faculty and staff information
- Facilities (10 facts) - Locations, resources, services, equipment
- General (5 facts) - Policies, contact info, general college info

Note: No date-sensitive or schedule-based facts. All information is static
and non-temporal, suitable for indefinite caching.
"""
```

## Verification

### Database Verified:
```
✓ Tables: identities, memories, metadata
✓ Total: 20 facts

Categories:
  facility  : 10 facts ✅
  general   : 5 facts ✅
  person    : 5 facts ✅

✓ Data version: 1
```

### All Tests Passing:
```
210/210 tests PASSED ✅
```

## Impact on Future Tasks

### Task 1.9 (Next): Entity Extractor
**Simplified scope:**
- Only extract subject and person
- No dateparser dependency
- No DATE_PATTERNS regex
- Cleaner, simpler implementation

### Task 1.11: Cache Manager
**Updated regression test:**
- Use "HOD vs placement officer" instead of "today vs yesterday"
- Entity gate still validates (person mismatch instead of date mismatch)
- Same protection mechanism, different example

### Task 4.3: E2E Cache Hit Test
**Updated integration test:**
- Same test structure, different questions
- Validates entity gate prevents wrong-person answers
- More realistic college Q&A scenario

### Task 6.1: CrewAI Nightly Refresh
**Simplified:**
- No schedule updates needed
- No date-based fact rotation
- Refresh only for static fact corrections/updates
- Can run less frequently if needed

## What Stays the Same

✅ **Entity gate mechanism** - Still needed to prevent wrong-person/wrong-subject answers  
✅ **Cache architecture** - Exact → Semantic → Entity-gated flow unchanged  
✅ **data_version tracking** - Still needed for fact updates/corrections  
✅ **CACHE_TTL mechanism** - Reserved for future if date-sensitive data added  
✅ **Test count** - Still 210 tests, just with updated assertions  

## Dependencies Removed

❌ **dateparser** - No longer needed (was planned for Task 1.9)  
❌ **Date normalization logic** - Not implemented  
❌ **Time-sensitive cache policy** - Not actively used (can stay indefinite)  

---

**Status:** All 6 updates complete and verified ✅  
**Tests:** 210/210 passing  
**Database:** Regenerated with 20 static facts  
**Ready for:** Task 1.9 Entity Extractor (simplified, no-date version)
