"""Decision Engine Router - Main 3-way routing logic.

This is the central coordinator that routes inputs through three decision paths:
- Path A: Deterministic (intents.py, gesture_actions.py) - <5ms
- Path B: QA Cache (exact + semantic + entity-gated) - <35ms
- Path C: LLM Reasoning (LangGraph + MCP + Ollama) - 1-3s

Routes are tried in order A → B → C, taking the first non-None result.

Key Responsibilities (Section 2 of design doc):
1. Subscribe to IDENTITY_RESOLVED and TEXT_INPUT events
2. Manage greeting flow via session_state (NEW → GREETING_INITIATED → GREETING_DELIVERED)
3. Route text questions through Path A/B/C
4. Publish RESPONSE events with path metadata
5. Does NOT re-implement SafetyGate logic (SafetyGate subscribes to ACTION directly)

Event Flow:
    IDENTITY_RESOLVED → check session state → generate greeting if NEW/RETURNED
    TEXT_INPUT → try Path A → try Path B → try Path C → publish RESPONSE
    
Design Note: SafetyGate (Task 1.5) already subscribes to ACTION events directly from
gesture_actions.py (Task 1.4). Decision Engine does not need to call SafetyGate or
re-publish ACTION events - that would be redundant.
"""

import logging
import time
from typing import Optional

from robot_assistant.events import (
    subscribe,
    publish,
    IdentityResolvedEvent,
    TextInputEvent,
    ResponseEvent,
    GreetingInitiatedEvent,
    GreetingDeliveredEvent,
)
from robot_assistant.session_state import (
    get_state,
    update_identity_state,
)
from robot_assistant.decision_engine.intents import get_intent_response

logger = logging.getLogger(__name__)


# =============================================================================
# STUB DEPENDENCIES (to be replaced by real implementations in later tasks)
# =============================================================================

def _stub_tts_synthesize(text: str) -> bool:
    """STUB for Task 2.3: Text-to-Speech synthesis.
    
    Real implementation will use Piper for local TTS synthesis and playback.
    For now, just simulate success.
    
    Args:
        text: Text to synthesize and speak.
    
    Returns:
        True if synthesis succeeded, False if TTS failed.
    
    TODO: Replace with actual TTS call in Task 2.3
    """
    logger.debug(f"[STUB] TTS synthesizing: '{text[:50]}...'")
    return True  # Simulate success


def _stub_cache_check(question: str) -> Optional[dict]:
    """STUB for Task 1.11: Cache Manager check.
    
    Real implementation will check exact cache, then semantic cache with entity gating.
    For now, always return None (cache miss).
    
    Args:
        question: User's question text.
    
    Returns:
        Dict with 'answer' and 'metadata' if cache hit, None if miss.
    
    TODO: Replace with actual cache_manager.check_cache() in Task 1.11
    """
    logger.debug(f"[STUB] Cache check: '{question[:50]}...' -> MISS")
    return None  # Simulate cache miss


def _stub_llm_generate(question: str) -> Optional[str]:
    """STUB for Task 1.14: LangGraph reasoning with LLM.
    
    Real implementation will use LangGraph with Ollama LLM and MCP memory tool.
    For now, return a placeholder answer.
    
    Args:
        question: User's question text.
    
    Returns:
        Generated answer string, or None if LLM generation failed.
    
    TODO: Replace with actual reasoning/graph.py call in Task 1.14
    """
    logger.debug(f"[STUB] LLM generating for: '{question[:50]}...'")
    return f"[LLM STUB] I would answer: {question}"


# =============================================================================
# GREETING MANAGEMENT
# =============================================================================

def _generate_greeting(identity_event: IdentityResolvedEvent, session_state_dict: dict) -> str:
    """Generate appropriate greeting based on identity status and session state.
    
    Args:
        identity_event: IDENTITY_RESOLVED event with identity info.
        session_state_dict: Current session state from get_state().
    
    Returns:
        Greeting text string.
    
    Greeting Logic:
        NEW + name known: "Hello, [name]! I'm your assistant."
        NEW + name unknown: "Hello! I don't believe we've met. I'm your assistant."
        RETURNED + name known: "Welcome back, [name]!"
        RETURNED + name unknown: "Welcome back! How can I help you?"
    """
    state = session_state_dict["state"]
    name = identity_event.get("name")
    status = identity_event["status"]
    
    if state == "NEW":
        if name:
            return f"Hello, {name}! I'm your assistant. How can I help you?"
        else:
            return "Hello! I don't believe we've met. I'm your assistant. How can I help you?"
    
    elif state == "RETURNED":
        if name:
            return f"Welcome back, {name}! How can I help you?"
        else:
            return "Welcome back! How can I help you?"
    
    # GREETED or other states - no greeting needed
    return ""


def _handle_identity_resolved(event: IdentityResolvedEvent) -> None:
    """Handle IDENTITY_RESOLVED event - manage greeting flow.
    
    Args:
        event: IDENTITY_RESOLVED event with embedding_id, track_id, status, name.
    
    Greeting Flow:
        1. Update session state (may transition AWAY → RETURNED)
        2. Check resulting state
        3. If NEW: Publish GREETING_INITIATED, call TTS, publish GREETING_DELIVERED
        4. If RETURNED: Call TTS for "welcome back" (no GREETING_DELIVERED)
        5. Other states: No greeting needed
    
    Notes:
        - GREETING_DELIVERED only published for NEW → GREETED transition
        - RETURNED state gets "welcome back" but no GREETING_DELIVERED (no state change)
        - TTS failure for NEW state is handled by 5-second timeout in session_state
    """
    embedding_id = event["embedding_id"]
    track_id = event["track_id"]
    
    # Update session state (AWAY → RETURNED happens here)
    new_state = update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id)
    
    # Get full state dict for greeting generation
    state_dict = get_state(embedding_id)
    if state_dict is None:
        logger.error(f"State dict is None after update for {embedding_id}")
        return
    
    current_state = state_dict["state"]
    
    # Generate and deliver greeting based on state
    if current_state == "NEW":
        # First time meeting - full greeting flow with state transition
        greeting = _generate_greeting(event, state_dict)
        
        logger.info(f"Greeting NEW identity {embedding_id} (track {track_id})")
        
        # Publish GREETING_INITIATED (starts timeout timer)
        greeting_initiated: GreetingInitiatedEvent = {
            "event": "GREETING_INITIATED",
            "embedding_id": embedding_id,
            "track_id": track_id,
        }
        publish(greeting_initiated)
        update_identity_state(embedding_id, "GREETING_INITIATED", track_id)
        
        # Call TTS (stub for now)
        tts_success = _stub_tts_synthesize(greeting)
        
        if tts_success:
            # TTS succeeded - publish GREETING_DELIVERED to transition NEW → GREETED
            greeting_delivered: GreetingDeliveredEvent = {
                "event": "GREETING_DELIVERED",
                "embedding_id": embedding_id,
                "track_id": track_id,
            }
            publish(greeting_delivered)
            update_identity_state(embedding_id, "GREETING_DELIVERED", track_id)
            logger.info(f"Greeting delivered successfully for {embedding_id}")
        else:
            # TTS failed - timeout will auto-transition after 5 seconds
            logger.warning(f"TTS failed for {embedding_id}, timeout will handle transition")
    
    elif current_state == "RETURNED":
        # Person came back - "welcome back" message (no GREETING_DELIVERED)
        greeting = _generate_greeting(event, state_dict)
        
        logger.info(f"Welcoming back identity {embedding_id} (track {track_id})")
        
        # Call TTS but do NOT publish GREETING_DELIVERED
        # RETURNED state doesn't transition on greeting
        _stub_tts_synthesize(greeting)
    
    else:
        # GREETED or AWAY - no greeting needed
        logger.debug(f"Identity {embedding_id} in state {current_state}, no greeting needed")


# =============================================================================
# TEXT QUESTION ROUTING (3-WAY ROUTER)
# =============================================================================

def _route_text_question(text: str, source: str) -> tuple[str, str, float]:
    """Route text question through 3-way decision paths: A → B → C.
    
    Args:
        text: User's question text (normalized).
        source: Input source ("voice" or "keyboard").
    
    Returns:
        Tuple of (answer: str, path: str, latency_ms: float)
        - answer: Response text to speak/display
        - path: Which path generated it ("deterministic", "cache", or "llm")
        - latency_ms: Time taken to generate response
    
    Path Selection:
        Path A (Deterministic): Check intents.py for exact intent match
        Path B (Cache): Check QA cache (exact + semantic + entity-gated)
        Path C (LLM): LangGraph reasoning with Ollama + MCP memory
    
    Takes first non-None result (A → B → C order).
    """
    start_time = time.time()
    
    # PATH A: Deterministic intents (hi, bye, help, thanks)
    intent_response = get_intent_response(text)
    if intent_response is not None:
        latency_ms = (time.time() - start_time) * 1000
        logger.info(f"Path A (deterministic): '{text[:30]}...' -> intent matched ({latency_ms:.1f}ms)")
        return intent_response, "deterministic", latency_ms
    
    # PATH B: QA Cache (stub for now - Task 1.11)
    cache_result = _stub_cache_check(text)
    if cache_result is not None:
        latency_ms = (time.time() - start_time) * 1000
        answer = cache_result.get("answer", "")
        logger.info(f"Path B (cache): '{text[:30]}...' -> cache hit ({latency_ms:.1f}ms)")
        return answer, "cache", latency_ms
    
    # PATH C: LLM Reasoning (stub for now - Task 1.14)
    llm_answer = _stub_llm_generate(text)
    if llm_answer is not None:
        latency_ms = (time.time() - start_time) * 1000
        logger.info(f"Path C (llm): '{text[:30]}...' -> LLM generated ({latency_ms:.1f}ms)")
        return llm_answer, "llm", latency_ms
    
    # All paths failed (shouldn't happen in practice - LLM should always return something)
    latency_ms = (time.time() - start_time) * 1000
    logger.error(f"All paths failed for: '{text[:50]}...'")
    return "I'm sorry, I couldn't process that question right now.", "llm", latency_ms


def _handle_text_input(event: TextInputEvent) -> None:
    """Handle TEXT_INPUT event - route through 3-way decision paths.
    
    Args:
        event: TEXT_INPUT event with text and source.
    
    Flow:
        1. Extract question text and source
        2. Route through Path A → B → C
        3. Publish RESPONSE event with answer and metadata
    """
    text = event["text"]
    source = event["source"]
    
    logger.info(f"Processing text input from {source}: '{text[:50]}...'")
    
    # Route through 3-way paths
    answer, path, latency_ms = _route_text_question(text, source)
    
    # Publish RESPONSE event
    response_event: ResponseEvent = {
        "event": "RESPONSE",
        "text": answer,
        "path": path,
        "latency_ms": latency_ms,
    }
    publish(response_event)
    
    logger.info(f"Published RESPONSE via path '{path}' ({latency_ms:.1f}ms)")


# =============================================================================
# INITIALIZATION
# =============================================================================

def start_decision_engine() -> None:
    """Start the Decision Engine by subscribing to relevant events.
    
    Subscribes to:
        - IDENTITY_RESOLVED: Manage greeting flow for NEW/RETURNED identities
        - TEXT_INPUT: Route text questions through Path A/B/C
    
    Does NOT subscribe to:
        - ACTION: SafetyGate (Task 1.5) handles this directly
        - GESTURE_DETECTED: gesture_actions.py (Task 1.4) handles this directly
    
    Call this once during application startup.
    """
    subscribe("IDENTITY_RESOLVED", _handle_identity_resolved)
    subscribe("TEXT_INPUT", _handle_text_input)
    
    logger.info("Decision Engine started - subscribed to IDENTITY_RESOLVED and TEXT_INPUT")


def stop_decision_engine() -> None:
    """Stop the Decision Engine (for testing/shutdown).
    
    Note: This is primarily for testing. In production, the event bus
    manages subscribers and they persist until application shutdown.
    """
    # Event bus doesn't have unsubscribe-all, so we rely on clear_subscribers in tests
    logger.info("Decision Engine stopped")
