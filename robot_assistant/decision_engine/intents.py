"""Deterministic intent handler for instant text responses.

This module handles common greetings, thanks, and help requests with canned responses.
No LLM call needed - instant response (< 5ms latency target).

Path A in the Decision Engine's 3-way routing:
- A) Deterministic intent → instant, no LLM
- B) Cached question → fast semantic cache
- C) Novel question → LangGraph + LLM

This module handles ONLY text intents. Gesture-to-action mapping is separate
(gesture_actions.py) and should not be coupled here.
"""

import logging
import time
from typing import Optional

from robot_assistant.config import config
from robot_assistant.events import publish, ResponseEvent

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize text for intent matching.
    
    STT transcripts come with inconsistent casing, extra whitespace,
    and sometimes trailing punctuation. Normalize for reliable matching.
    
    Args:
        text: Raw input text (possibly from voice STT).
    
    Returns:
        Normalized text: lowercase, stripped, single spaces, no trailing punctuation.
    
    Examples:
        "  Hello!  " -> "hello"
        "THANK YOU." -> "thank you"
        "what   can you do?" -> "what can you do"
    """
    # Lowercase
    text = text.lower()
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # Remove trailing punctuation (STT often adds periods, question marks)
    while text and text[-1] in ".,!?;:":
        text = text[:-1]
    
    # Collapse multiple spaces to single space
    text = " ".join(text.split())
    
    return text


def get_intent_response(text: str) -> Optional[str]:
    """Check if text matches a known deterministic intent and return response.
    
    Args:
        text: User input text (from voice STT or keyboard).
    
    Returns:
        Response text if intent is known, None if unknown (caller should try cache/LLM).
        
    Side Effects:
        If a known intent is matched, publishes a RESPONSE event with path="deterministic".
    
    Example:
        >>> get_intent_response("Hi")
        "Hello! How can I help you today?"
        
        >>> get_intent_response("What's my attendance?")  # Unknown intent
        None
    """
    start_time = time.time()
    
    # Normalize for case-insensitive matching
    normalized = normalize_text(text)
    
    # Check against known intents from config
    response_text = config.INTENT_RESPONSES.get(normalized)
    
    if response_text is None:
        # Unknown intent - return None so caller can try cache/LLM
        logger.debug(f"Unknown intent: '{normalized}' (original: '{text}')")
        return None
    
    # Known intent - publish RESPONSE event
    latency_ms = (time.time() - start_time) * 1000
    
    response_event: ResponseEvent = {
        "event": "RESPONSE",
        "text": response_text,
        "path": "deterministic",
        "latency_ms": latency_ms
    }
    
    publish(response_event)
    
    logger.info(f"Deterministic intent matched: '{normalized}' -> '{response_text}' ({latency_ms:.2f}ms)")
    
    return response_text


def add_intent(text: str, response: str) -> None:
    """Add a new intent to the runtime table.
    
    Useful for testing or dynamic intent addition (not used in main flow).
    
    Args:
        text: Intent text (will be normalized before storing).
        response: Response text to return for this intent.
    """
    normalized = normalize_text(text)
    config.INTENT_RESPONSES[normalized] = response
    logger.info(f"Added intent: '{normalized}' -> '{response}'")


def remove_intent(text: str) -> bool:
    """Remove an intent from the runtime table.
    
    Args:
        text: Intent text to remove (will be normalized).
    
    Returns:
        True if intent was found and removed, False otherwise.
    """
    normalized = normalize_text(text)
    if normalized in config.INTENT_RESPONSES:
        del config.INTENT_RESPONSES[normalized]
        logger.info(f"Removed intent: '{normalized}'")
        return True
    return False


def get_all_intents() -> dict[str, str]:
    """Get all registered intents and their responses.
    
    Returns:
        Dict mapping normalized intent text to response text.
    """
    return dict(config.INTENT_RESPONSES)
