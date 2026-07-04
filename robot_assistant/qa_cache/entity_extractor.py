"""Entity extraction for cache gating.

Extracts subject and person entities from questions to prevent semantically
similar but factually different questions from hitting the same cache entry.

Design Decision (Section 6):
Regex-based extraction is sufficient for templated college questions, faster
than spaCy (<2ms vs 15-30ms), and simpler to maintain. The entity gate only
needs binary matching (entities exist and match), not complex NER relationships.

Example: "Who is the HOD?" and "Who is the placement officer?" have high cosine
similarity (~0.90+) but different correct answers. Entity extraction catches
that they ask about different people, preventing wrong cache hits.

No date extraction: All memory facts are static/non-temporal (people, facilities,
general info). No schedules, exams, or time-sensitive data in current scope.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Subject patterns matching facility/general/person categories
# Matches topics present in memory.db: hod, library, canteen, placement, etc.
SUBJECT_PATTERNS = r'\b(hod|library|canteen|placement|hostel|lab|department|helpdesk|sports|parking|auditorium|wifi|principal|advisor|instructor|officer|facilities|dress|code)\b'

# Common stopwords to filter out when detecting person names
# Includes question words, common sentence starters, and short words often capitalized
STOPWORDS = {
    'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'should', 'could', 'can', 'may', 'might', 'must',
    'what', 'which', 'who', 'whom', 'whose', 'where', 'when',
    'why', 'how', 'a', 'an', 'and', 'or', 'but', 'if', 'then',
    'my', 'your', 'his', 'her', 'its', 'our', 'their',
    'about', 'for', 'with', 'from', 'to', 'in', 'on', 'at',
    'of', 'by', 'as', 'into', 'through', 'during', 'before', 'after',
    # Add common sentence starters and greetings
    'hi', 'hello', 'hey', 'thanks', 'bye', 'goodbye', 'please',
    'ask', 'tell', 'show', 'give', 'get', 'take', 'make', 'find',
    # Add acronyms/abbreviations that might be capitalized but aren't person names
    'hod', 'cse', 'it', 'ai', 'ml', 'phd', 'mba', 'btech', 'mtech'
}


def extract_entities(question: str) -> dict:
    """Extract subject and person entities from a question.
    
    Args:
        question: User's question text.
    
    Returns:
        Dict with 'subject' and 'person' keys.
        Both values are None if not detected (graceful, not error).
        
    Entity Extraction Logic:
        - Subject: Regex match against SUBJECT_PATTERNS (hod, library, canteen, etc.)
        - Person: First capitalized word not in STOPWORDS (simple heuristic)
        
    Examples:
        >>> extract_entities("Who is the HOD?")
        {"subject": "hod", "person": None}
        
        >>> extract_entities("Where is the library?")
        {"subject": "library", "person": None}
        
        >>> extract_entities("What does Dr. Kumar teach?")
        {"subject": None, "person": "Dr."}
        
        >>> extract_entities("Hi there")
        {"subject": None, "person": None}
    
    Latency: <2ms (simple regex + string split)
    """
    # Normalize for case-insensitive matching
    text_lower = question.lower()
    
    # Subject extraction - regex match
    subject_match = re.search(SUBJECT_PATTERNS, text_lower, re.IGNORECASE)
    subject = subject_match.group() if subject_match else None
    
    # Person extraction - capitalized words not in stopwords
    # Uses original casing for better person detection
    words = question.split()
    person = None
    
    for word in words:
        # Check if word starts with uppercase and is not a stopword
        if word and word[0].isupper():
            # Remove trailing punctuation for stopword check
            word_clean = word.rstrip('.,!?;:')
            if word_clean.lower() not in STOPWORDS:
                person = word_clean
                break  # Take first match
    
    logger.debug(f"Extracted entities from '{question[:50]}...': subject={subject}, person={person}")
    
    return {
        "subject": subject,
        "person": person
    }


def add_subject_pattern(pattern: str) -> None:
    """Add a new subject pattern to the regex (for runtime extension).
    
    Args:
        pattern: Subject keyword to add (e.g., "hostel", "gym").
    
    Side Effects:
        Updates global SUBJECT_PATTERNS regex.
    
    Note: For testing/demo only. Production should update SUBJECT_PATTERNS constant.
    """
    global SUBJECT_PATTERNS
    
    # Remove closing )\b and add new pattern
    patterns_list = SUBJECT_PATTERNS[3:-3].split('|')  # Strip \b( and )\b
    if pattern not in patterns_list:
        patterns_list.append(pattern)
        SUBJECT_PATTERNS = r'\b(' + '|'.join(patterns_list) + r')\b'
        logger.info(f"Added subject pattern: '{pattern}'")


def entities_match(entities1: dict, entities2: dict) -> bool:
    """Check if two entity dicts match (for cache gating).
    
    Args:
        entities1: First entity dict from extract_entities().
        entities2: Second entity dict from extract_entities().
    
    Returns:
        True if entities match (both subjects and persons match), False otherwise.
        
    Matching Logic:
        - If both have None for a key, that key matches
        - If one has None and other has a value, they DON'T match
        - If both have values, they must be equal (case-insensitive)
        
    Examples:
        >>> e1 = {"subject": "hod", "person": None}
        >>> e2 = {"subject": "hod", "person": None}
        >>> entities_match(e1, e2)
        True
        
        >>> e1 = {"subject": "hod", "person": None}
        >>> e2 = {"subject": "placement", "person": None}
        >>> entities_match(e1, e2)
        False
        
        >>> e1 = {"subject": None, "person": "Dr."}
        >>> e2 = {"subject": None, "person": None}
        >>> entities_match(e1, e2)
        False
    
    Use Case:
        Semantic cache finds candidate with high cosine similarity.
        Entity gate checks if entities match before returning hit.
        This prevents "Who is the HOD?" from returning cached answer for
        "Who is the placement officer?" (semantically similar but different person).
    """
    # Check subject match
    subject1 = entities1.get("subject")
    subject2 = entities2.get("subject")
    
    # If both None, they match
    # If one None and other not, they don't match
    # If both have values, compare (case-insensitive)
    if subject1 is None and subject2 is None:
        subject_matches = True
    elif subject1 is None or subject2 is None:
        subject_matches = False
    else:
        subject_matches = subject1.lower() == subject2.lower()
    
    # Check person match (same logic)
    person1 = entities1.get("person")
    person2 = entities2.get("person")
    
    if person1 is None and person2 is None:
        person_matches = True
    elif person1 is None or person2 is None:
        person_matches = False
    else:
        person_matches = person1.lower() == person2.lower()
    
    # Both must match for overall match
    return subject_matches and person_matches


def get_subject_patterns() -> str:
    """Get the current subject patterns regex.
    
    Returns:
        Current SUBJECT_PATTERNS regex string.
    """
    return SUBJECT_PATTERNS
