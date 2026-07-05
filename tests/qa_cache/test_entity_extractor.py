"""Tests for entity extraction (subject/person).

Critical test cases:
1. Subject extraction (hod, library, canteen, placement, etc.)
2. Person extraction (capitalized words, stopword filtering)
3. Both subject and person in same question
4. Neither subject nor person (graceful None returns)
5. HOD vs placement officer (critical regression - entity gate justification)
"""

import pytest

from robot_assistant.qa_cache import entity_extractor


# =============================================================================
# SUBJECT EXTRACTION TESTS
# =============================================================================

def test_subject_extraction_hod():
    """Test that 'hod' is extracted as subject."""
    result = entity_extractor.extract_entities("Who is the HOD?")
    
    assert result["subject"] == "hod"
    assert result["person"] is None


def test_subject_extraction_library():
    """Test that 'library' is extracted as subject."""
    result = entity_extractor.extract_entities("Where is the library?")
    
    assert result["subject"] == "library"


def test_subject_extraction_canteen():
    """Test that 'canteen' is extracted as subject."""
    result = entity_extractor.extract_entities("What does the canteen serve?")
    
    assert result["subject"] == "canteen"


def test_subject_extraction_placement():
    """Test that 'placement' is extracted as subject."""
    result = entity_extractor.extract_entities("Where is the placement cell?")
    
    assert result["subject"] == "placement"


def test_subject_extraction_case_insensitive():
    """Test that subject extraction is case-insensitive."""
    # All should extract 'library'
    assert entity_extractor.extract_entities("LIBRARY location?")["subject"] == "library"
    assert entity_extractor.extract_entities("Library rules?")["subject"] == "library"
    assert entity_extractor.extract_entities("library hours?")["subject"] == "library"


def test_subject_extraction_multiple_subjects():
    """Test that first matching subject is extracted."""
    # Has both 'library' and 'canteen'
    result = entity_extractor.extract_entities("Is the library near the canteen?")
    
    # Should extract first match (library appears first)
    assert result["subject"] == "library"


def test_subject_extraction_facilities():
    """Test extraction of various facility subjects."""
    facilities = [
        ("Where is the hostel?", "hostel"),
        ("What lab equipment is available?", "lab"),
        ("Department location?", "department"),
        ("Helpdesk number?", "helpdesk"),
        ("Sports facilities?", "sports"),
        ("Parking info?", "parking"),
        ("Auditorium capacity?", "auditorium"),
        ("WiFi access?", "wifi"),
    ]
    
    for question, expected_subject in facilities:
        result = entity_extractor.extract_entities(question)
        assert result["subject"] == expected_subject, f"Failed for: {question}"


# =============================================================================
# PERSON EXTRACTION TESTS
# =============================================================================

def test_person_extraction_dr_title():
    """Test that 'Dr.' is extracted as person (capitalized, not stopword)."""
    result = entity_extractor.extract_entities("What does Dr. Kumar teach?")
    
    assert result["person"] == "Dr"  # Period stripped for stopword check
    assert result["subject"] is None


def test_person_extraction_possessive_s_stripped():
    """Test that possessive 's is stripped before stopword check.
    
    CRITICAL REGRESSION TEST: "HOD's" must be treated as "HOD" (a stopword),
    not as a person name. Without stripping possessive 's, "HOD's" would be
    extracted as a person, causing false entity mismatches in cache manager.
    
    Bug history: Initially "What is the HOD's name?" extracted person="HOD's",
    while "Tell me the HOD's name" extracted person=None, causing cache misses
    for legitimate paraphrases. Fixed by stripping possessive 's before stopword check.
    """
    result = entity_extractor.extract_entities("What is the HOD's name?")
    
    # "HOD's" should be stripped to "HOD", which is in stopwords
    assert result["person"] is None  # Not "HOD's"
    assert result["subject"] == "hod"
    
    # Also test with other possessive patterns
    result2 = entity_extractor.extract_entities("Tell me the HOD's email")
    assert result2["person"] is None
    
    result3 = entity_extractor.extract_entities("What is the library's location?")
    assert result3["person"] is None
    assert result3["subject"] == "library"


def test_person_extraction_prof_title():
    """Test that 'Prof.' is extracted as person."""
    result = entity_extractor.extract_entities("Where is Prof. Raman?")
    
    assert result["person"] == "Prof"  # Period stripped


def test_person_extraction_full_name():
    """Test that first capitalized name is extracted."""
    result = entity_extractor.extract_entities("Is Rajesh Kumar the HOD?")
    
    # Should extract 'Rajesh' (first capitalized, not stopword)
    assert result["person"] == "Rajesh"


def test_person_extraction_stops_word_filtering():
    """Test that capitalized stopwords are NOT extracted as person."""
    # 'What' is capitalized but is a stopword
    result = entity_extractor.extract_entities("What is the library location?")
    
    assert result["person"] is None


def test_person_extraction_with_punctuation():
    """Test that trailing punctuation is stripped before stopword check."""
    # 'Dr.' has period but should still be extracted (not a stopword)
    result = entity_extractor.extract_entities("Ask Dr. about it")
    
    assert result["person"] == "Dr"  # Period stripped


# =============================================================================
# COMBINED EXTRACTION TESTS
# =============================================================================

def test_both_subject_and_person():
    """Test extraction when both subject and person are present."""
    result = entity_extractor.extract_entities("Is Dr. Kumar the HOD?")
    
    assert result["subject"] == "hod"
    assert result["person"] == "Dr"  # Period stripped


def test_neither_subject_nor_person():
    """Test that both return None gracefully for unrelated question.
    
    CRITICAL: Must not raise error, return None for missing entities.
    """
    result = entity_extractor.extract_entities("Hi there")
    
    assert result["subject"] is None
    assert result["person"] is None


def test_greeting_returns_none():
    """Test that greetings don't extract spurious entities."""
    greetings = [
        "hello",
        "hi",
        "good morning",
        "thanks",
        "bye",
    ]
    
    for greeting in greetings:
        result = entity_extractor.extract_entities(greeting)
        assert result["subject"] is None
        assert result["person"] is None


# =============================================================================
# CRITICAL REGRESSION TEST (Entity Gate Justification)
# =============================================================================

def test_hod_vs_placement_officer_different_subjects():
    """CRITICAL: 'HOD' and 'placement officer' extract different entities.
    
    This is the core justification for the entity gate:
    - "Who is the HOD?" and "Who is the placement officer?" have high
      semantic similarity (~0.90+) but completely different correct answers.
    - Entity extraction must catch that they ask about different roles/subjects.
    - This prevents cache hit on wrong person.
    """
    hod_entities = entity_extractor.extract_entities("Who is the HOD?")
    placement_entities = entity_extractor.extract_entities("Who is the placement officer?")
    
    # HOD should extract 'hod' subject
    assert hod_entities["subject"] == "hod"
    assert hod_entities["person"] is None
    
    # Placement officer should extract 'placement' and 'officer' subjects
    # First match wins, so should get 'placement'
    assert placement_entities["subject"] == "placement"
    # 'Who' is stopword, so no person extracted
    assert placement_entities["person"] is None
    
    # CRITICAL: Subjects are DIFFERENT
    assert hod_entities["subject"] != placement_entities["subject"]
    
    # Use entities_match to confirm they don't match (entity gate blocks cache hit)
    assert not entity_extractor.entities_match(hod_entities, placement_entities)


def test_library_vs_canteen_different_subjects():
    """Test that different facility questions extract different subjects."""
    library_entities = entity_extractor.extract_entities("Where is the library?")
    canteen_entities = entity_extractor.extract_entities("Where is the canteen?")
    
    assert library_entities["subject"] == "library"
    assert canteen_entities["subject"] == "canteen"
    
    # Different subjects - should not match
    assert not entity_extractor.entities_match(library_entities, canteen_entities)


# =============================================================================
# ENTITIES_MATCH TESTS (Cache Gating Logic)
# =============================================================================

def test_entities_match_identical():
    """Test that identical entities match."""
    e1 = {"subject": "hod", "person": None}
    e2 = {"subject": "hod", "person": None}
    
    assert entity_extractor.entities_match(e1, e2)


def test_entities_match_both_none():
    """Test that both-None entities match."""
    e1 = {"subject": None, "person": None}
    e2 = {"subject": None, "person": None}
    
    assert entity_extractor.entities_match(e1, e2)


def test_entities_no_match_different_subject():
    """Test that different subjects don't match."""
    e1 = {"subject": "hod", "person": None}
    e2 = {"subject": "placement", "person": None}
    
    assert not entity_extractor.entities_match(e1, e2)


def test_entities_no_match_different_person():
    """Test that different persons don't match."""
    e1 = {"subject": None, "person": "Dr."}
    e2 = {"subject": None, "person": "Prof."}
    
    assert not entity_extractor.entities_match(e1, e2)


def test_entities_no_match_one_none_one_value():
    """Test that None vs value doesn't match (asymmetry)."""
    e1 = {"subject": "hod", "person": None}
    e2 = {"subject": None, "person": None}
    
    # e1 has 'hod' subject, e2 has None - don't match
    assert not entity_extractor.entities_match(e1, e2)


def test_entities_match_case_insensitive():
    """Test that entity matching is case-insensitive."""
    e1 = {"subject": "HOD", "person": "Dr."}
    e2 = {"subject": "hod", "person": "dr."}
    
    assert entity_extractor.entities_match(e1, e2)


def test_entities_match_both_have_values():
    """Test matching when both have subject and person."""
    e1 = {"subject": "hod", "person": "Dr."}
    e2 = {"subject": "hod", "person": "Dr."}
    
    assert entity_extractor.entities_match(e1, e2)


def test_entities_no_match_subject_matches_person_differs():
    """Test that both must match for overall match."""
    e1 = {"subject": "hod", "person": "Dr."}
    e2 = {"subject": "hod", "person": "Prof."}
    
    # Subject matches but person differs - overall no match
    assert not entity_extractor.entities_match(e1, e2)


# =============================================================================
# EDGE CASES
# =============================================================================

def test_empty_string():
    """Test that empty string returns None for both."""
    result = entity_extractor.extract_entities("")
    
    assert result["subject"] is None
    assert result["person"] is None


def test_only_stopwords():
    """Test that question with only stopwords returns None."""
    result = entity_extractor.extract_entities("What is the of and?")
    
    assert result["subject"] is None
    assert result["person"] is None


def test_very_long_question():
    """Test that very long question still extracts correctly."""
    long_q = "I was wondering if you could possibly tell me where the library is located?"
    result = entity_extractor.extract_entities(long_q)
    
    assert result["subject"] == "library"


def test_special_characters():
    """Test that special characters don't break extraction."""
    result = entity_extractor.extract_entities("Where's the library @#$%?")
    
    assert result["subject"] == "library"


def test_unicode_characters():
    """Test that Unicode characters are handled."""
    result = entity_extractor.extract_entities("Where is the library? 你好")
    
    assert result["subject"] == "library"


# =============================================================================
# RUNTIME EXTENSION TESTS
# =============================================================================

def test_add_subject_pattern():
    """Test adding new subject pattern at runtime."""
    # Get original pattern
    original = entity_extractor.get_subject_patterns()
    
    # Add new pattern
    entity_extractor.add_subject_pattern("gym")
    
    # Should now extract 'gym'
    result = entity_extractor.extract_entities("Where is the gym?")
    assert result["subject"] == "gym"
    
    # Restore original (for test isolation)
    entity_extractor.SUBJECT_PATTERNS = original


def test_get_subject_patterns():
    """Test getting current subject patterns."""
    patterns = entity_extractor.get_subject_patterns()
    
    assert isinstance(patterns, str)
    assert "hod" in patterns
    assert "library" in patterns
    assert "canteen" in patterns


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

def test_extraction_latency():
    """Test that extraction meets <2ms latency target."""
    import time
    
    questions = [
        "Who is the HOD?",
        "Where is the library?",
        "What does the canteen serve?",
        "Is Dr. Kumar the HOD?",
    ] * 25  # 100 extractions
    
    latencies = []
    for question in questions:
        start = time.time()
        entity_extractor.extract_entities(question)
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)
    
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    
    # Target: <2ms from design doc
    assert avg_latency < 2.0, f"Average latency {avg_latency:.2f}ms exceeds 2ms target"
    assert max_latency < 5.0, f"Max latency {max_latency:.2f}ms too high"
