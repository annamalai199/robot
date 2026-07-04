"""Tests for Session State Store."""

import pytest
import time
from robot_assistant.session_state.store import (
    update_identity_state,
    get_state,
    get_all_states,
    clear_state,
    clear_all_states,
    get_state_summary,
    cleanup_old_sessions,
)


@pytest.fixture(autouse=True)
def reset_store():
    """Clear session store before and after each test."""
    clear_all_states()
    yield
    clear_all_states()


def test_new_identity_starts_in_new_state():
    """Test that a new identity starts in NEW state."""
    state = update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    
    assert state == "NEW"
    
    state_dict = get_state("E0001")
    assert state_dict is not None
    assert state_dict["state"] == "NEW"
    assert state_dict["track_id"] == "T1"
    assert "last_seen" in state_dict
    assert "created_at" in state_dict


def test_transition_new_to_greeted():
    """Test NEW → GREETED transition when greeting delivered."""
    # First detection
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    assert get_state("E0001")["state"] == "NEW"
    
    # Greeting delivered
    state = update_identity_state("E0001", "GREETING_DELIVERED")
    assert state == "GREETED"
    assert get_state("E0001")["state"] == "GREETED"


def test_transition_greeted_to_away():
    """Test GREETED → AWAY transition when track lost."""
    # Get to GREETED state
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state("E0001", "GREETING_DELIVERED")
    assert get_state("E0001")["state"] == "GREETED"
    
    # Person leaves frame
    state = update_identity_state("E0001", "TRACK_LOST")
    assert state == "AWAY"
    assert get_state("E0001")["state"] == "AWAY"


def test_transition_away_to_returned():
    """Test AWAY → RETURNED transition when person re-detected."""
    # Get to AWAY state
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state("E0001", "GREETING_DELIVERED")
    update_identity_state("E0001", "TRACK_LOST")
    assert get_state("E0001")["state"] == "AWAY"
    
    # Person returns (different track_id)
    state = update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T2")
    assert state == "RETURNED"
    assert get_state("E0001")["state"] == "RETURNED"
    
    # Track ID should be updated
    assert get_state("E0001")["track_id"] == "T2"


def test_transition_returned_to_away():
    """Test RETURNED → AWAY transition when person leaves again."""
    # Get to RETURNED state
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state("E0001", "GREETING_DELIVERED")
    update_identity_state("E0001", "TRACK_LOST")
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T2")
    assert get_state("E0001")["state"] == "RETURNED"
    
    # Person leaves again
    state = update_identity_state("E0001", "TRACK_LOST")
    assert state == "AWAY"
    assert get_state("E0001")["state"] == "AWAY"


def test_full_state_machine_cycle():
    """Test complete state machine: NEW → GREETED → AWAY → RETURNED → AWAY."""
    embedding_id = "E0001"
    
    # 1. NEW (first detection)
    state = update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    assert state == "NEW"
    
    # 2. GREETED (greeting delivered)
    state = update_identity_state(embedding_id, "GREETING_DELIVERED")
    assert state == "GREETED"
    
    # 3. AWAY (person leaves)
    state = update_identity_state(embedding_id, "TRACK_LOST")
    assert state == "AWAY"
    
    # 4. RETURNED (person comes back)
    state = update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T2")
    assert state == "RETURNED"
    
    # 5. AWAY (person leaves again)
    state = update_identity_state(embedding_id, "TRACK_LOST")
    assert state == "AWAY"


def test_two_track_ids_same_embedding_share_state():
    """Test that two different track_ids with same embedding_id share session state.
    
    Critical test: State is keyed by embedding_id (persistent face identity),
    NOT by track_id (transient vision tracking).
    """
    embedding_id = "E0042"
    
    # First detection with track T1
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    assert get_state(embedding_id)["state"] == "GREETED"
    assert get_state(embedding_id)["track_id"] == "T1"
    
    # Person leaves
    update_identity_state(embedding_id, "TRACK_LOST")
    assert get_state(embedding_id)["state"] == "AWAY"
    
    # Person returns but with NEW track_id T2 (vision system assigned new ID)
    # Should transition to RETURNED, not NEW - same embedding_id
    state = update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T2")
    assert state == "RETURNED", "Same embedding_id should go to RETURNED, not NEW"
    assert get_state(embedding_id)["track_id"] == "T2"
    
    # Verify NOT in NEW state (would happen if keyed by track_id)
    assert get_state(embedding_id)["state"] != "NEW"


def test_different_embedding_ids_have_independent_states():
    """Test that different people have independent state machines."""
    # Person 1
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state("E0001", "GREETING_DELIVERED")
    
    # Person 2
    update_identity_state("E0002", "IDENTITY_RESOLVED", track_id="T2")
    
    # Person 1 should be GREETED
    assert get_state("E0001")["state"] == "GREETED"
    
    # Person 2 should be NEW
    assert get_state("E0002")["state"] == "NEW"
    
    # Person 1 leaves
    update_identity_state("E0001", "TRACK_LOST")
    assert get_state("E0001")["state"] == "AWAY"
    
    # Person 2 should be unaffected
    assert get_state("E0002")["state"] == "NEW"


def test_get_state_returns_none_for_unknown_identity():
    """Test that get_state returns None for never-seen identity."""
    result = get_state("E9999")
    assert result is None


def test_new_state_stays_new_until_greeting():
    """Test that NEW state persists until GREETING_DELIVERED event."""
    embedding_id = "E0001"
    
    # First detection
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    assert get_state(embedding_id)["state"] == "NEW"
    
    # Another IDENTITY_RESOLVED (person still in frame, no greeting yet)
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    assert get_state(embedding_id)["state"] == "NEW"  # Should stay NEW
    
    # Only GREETING_DELIVERED changes state
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    assert get_state(embedding_id)["state"] == "GREETED"


def test_greeted_state_stable_with_continued_presence():
    """Test that GREETED state is stable when person remains in frame."""
    embedding_id = "E0001"
    
    # Get to GREETED
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    assert get_state(embedding_id)["state"] == "GREETED"
    
    # Multiple IDENTITY_RESOLVED events (person still present)
    for _ in range(5):
        update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
        assert get_state(embedding_id)["state"] == "GREETED"  # Should stay GREETED


def test_returned_state_no_re_greeting():
    """Test that RETURNED state doesn't transition back to NEW (no re-greeting)."""
    embedding_id = "E0001"
    
    # Get to RETURNED
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    update_identity_state(embedding_id, "TRACK_LOST")
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T2")
    assert get_state(embedding_id)["state"] == "RETURNED"
    
    # GREETING_DELIVERED should NOT change state (no re-greeting)
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    assert get_state(embedding_id)["state"] == "RETURNED"  # Should stay RETURNED


def test_person_leaves_before_greeting():
    """Test NEW → AWAY transition if person leaves before greeting delivered."""
    embedding_id = "E0001"
    
    # Detected but leaves before greeting
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    assert get_state(embedding_id)["state"] == "NEW"
    
    # Person leaves before robot finishes greeting
    state = update_identity_state(embedding_id, "TRACK_LOST")
    assert state == "AWAY"


def test_last_seen_timestamp_updates():
    """Test that last_seen timestamp updates on each event."""
    embedding_id = "E0001"
    
    # First event
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    first_seen = get_state(embedding_id)["last_seen"]
    
    time.sleep(0.01)  # Small delay
    
    # Second event
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    second_seen = get_state(embedding_id)["last_seen"]
    
    assert second_seen > first_seen


def test_get_all_states():
    """Test retrieving all session states."""
    # Create multiple sessions
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state("E0002", "IDENTITY_RESOLVED", track_id="T2")
    update_identity_state("E0003", "IDENTITY_RESOLVED", track_id="T3")
    
    all_states = get_all_states()
    
    assert len(all_states) == 3
    assert "E0001" in all_states
    assert "E0002" in all_states
    assert "E0003" in all_states


def test_clear_state():
    """Test clearing a specific identity's state."""
    # Create two sessions
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state("E0002", "IDENTITY_RESOLVED", track_id="T2")
    
    # Clear one
    clear_state("E0001")
    
    # E0001 should be gone
    assert get_state("E0001") is None
    
    # E0002 should still exist
    assert get_state("E0002") is not None


def test_clear_all_states():
    """Test clearing all session states."""
    # Create multiple sessions
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state("E0002", "IDENTITY_RESOLVED", track_id="T2")
    update_identity_state("E0003", "IDENTITY_RESOLVED", track_id="T3")
    
    # Clear all
    clear_all_states()
    
    # All should be gone
    assert get_state("E0001") is None
    assert get_state("E0002") is None
    assert get_state("E0003") is None
    assert len(get_all_states()) == 0


def test_get_state_summary():
    """Test state summary statistics."""
    # Create sessions in different states
    # NEW
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    
    # GREETED
    update_identity_state("E0002", "IDENTITY_RESOLVED", track_id="T2")
    update_identity_state("E0002", "GREETING_DELIVERED")
    
    # AWAY
    update_identity_state("E0003", "IDENTITY_RESOLVED", track_id="T3")
    update_identity_state("E0003", "GREETING_DELIVERED")
    update_identity_state("E0003", "TRACK_LOST")
    
    # RETURNED
    update_identity_state("E0004", "IDENTITY_RESOLVED", track_id="T4")
    update_identity_state("E0004", "GREETING_DELIVERED")
    update_identity_state("E0004", "TRACK_LOST")
    update_identity_state("E0004", "IDENTITY_RESOLVED", track_id="T5")
    
    summary = get_state_summary()
    
    assert summary["NEW"] == 1
    assert summary["GREETED"] == 1
    assert summary["AWAY"] == 1
    assert summary["RETURNED"] == 1


def test_cleanup_old_sessions():
    """Test cleanup of old sessions."""
    # Create session
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    
    # Should not be cleaned up (just created)
    removed = cleanup_old_sessions(max_age_seconds=10)
    assert removed == 0
    assert get_state("E0001") is not None
    
    # Manually set last_seen to old timestamp
    state_dict = get_state("E0001")
    state_dict["last_seen"] = time.time() - 3700  # Over 1 hour ago
    
    # Now should be cleaned up
    removed = cleanup_old_sessions(max_age_seconds=3600)
    assert removed == 1
    assert get_state("E0001") is None


def test_cleanup_preserves_recent_sessions():
    """Test that cleanup only removes old sessions, keeps recent ones."""
    # Create old session
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    state_dict = get_state("E0001")
    state_dict["last_seen"] = time.time() - 7200  # 2 hours ago
    
    # Create recent session
    update_identity_state("E0002", "IDENTITY_RESOLVED", track_id="T2")
    
    # Cleanup (max age 1 hour)
    removed = cleanup_old_sessions(max_age_seconds=3600)
    
    assert removed == 1
    assert get_state("E0001") is None  # Old one removed
    assert get_state("E0002") is not None  # Recent one preserved


def test_track_id_updates_on_re_detection():
    """Test that track_id updates when person re-detected with new track_id."""
    embedding_id = "E0001"
    
    # First detection
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    assert get_state(embedding_id)["track_id"] == "T1"
    
    # Re-detection with new track_id (person left and returned)
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    update_identity_state(embedding_id, "TRACK_LOST")
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T2")
    
    # Track ID should be updated to T2
    assert get_state(embedding_id)["track_id"] == "T2"


def test_multiple_cycles_same_identity():
    """Test that identity can go through multiple AWAY/RETURNED cycles."""
    embedding_id = "E0001"
    
    # First cycle
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    update_identity_state(embedding_id, "TRACK_LOST")  # → AWAY
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T2")  # → RETURNED
    assert get_state(embedding_id)["state"] == "RETURNED"
    
    # Second cycle
    update_identity_state(embedding_id, "TRACK_LOST")  # → AWAY
    assert get_state(embedding_id)["state"] == "AWAY"
    
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T3")  # → RETURNED
    assert get_state(embedding_id)["state"] == "RETURNED"
    
    # Third cycle
    update_identity_state(embedding_id, "TRACK_LOST")  # → AWAY
    assert get_state(embedding_id)["state"] == "AWAY"
    
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T4")  # → RETURNED
    assert get_state(embedding_id)["state"] == "RETURNED"


def test_state_persistence_across_events():
    """Test that state persists correctly across various event sequences."""
    embedding_id = "E0001"
    
    # Complex event sequence
    events = [
        ("IDENTITY_RESOLVED", "T1", "NEW"),
        ("IDENTITY_RESOLVED", "T1", "NEW"),  # Still NEW
        ("GREETING_DELIVERED", None, "GREETED"),
        ("IDENTITY_RESOLVED", "T1", "GREETED"),  # Still GREETED
        ("IDENTITY_RESOLVED", "T1", "GREETED"),  # Still GREETED
        ("TRACK_LOST", None, "AWAY"),
        ("IDENTITY_RESOLVED", "T2", "RETURNED"),
        ("IDENTITY_RESOLVED", "T2", "RETURNED"),  # Still RETURNED
        ("GREETING_DELIVERED", None, "RETURNED"),  # No re-greeting
        ("TRACK_LOST", None, "AWAY"),
    ]
    
    for event_type, track_id, expected_state in events:
        state = update_identity_state(embedding_id, event_type, track_id=track_id)
        assert state == expected_state, f"Event {event_type} should result in {expected_state}, got {state}"


def test_state_dict_structure():
    """Test that state dict has all required fields."""
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    state_dict = get_state("E0001")
    
    # Required fields
    assert "state" in state_dict
    assert "last_seen" in state_dict
    assert "track_id" in state_dict
    assert "created_at" in state_dict
    
    # Field types
    assert isinstance(state_dict["state"], str)
    assert isinstance(state_dict["last_seen"], float)
    assert isinstance(state_dict["track_id"], str)
    assert isinstance(state_dict["created_at"], float)
    
    # Valid state value
    assert state_dict["state"] in ["NEW", "GREETED", "AWAY", "RETURNED"]


def test_concurrent_identities_state_machine():
    """Test multiple identities going through state machine simultaneously."""
    # Person 1: NEW → GREETED
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state("E0001", "GREETING_DELIVERED")
    
    # Person 2: NEW
    update_identity_state("E0002", "IDENTITY_RESOLVED", track_id="T2")
    
    # Person 1: GREETED → AWAY
    update_identity_state("E0001", "TRACK_LOST")
    
    # Person 3: NEW → GREETED
    update_identity_state("E0003", "IDENTITY_RESOLVED", track_id="T3")
    update_identity_state("E0003", "GREETING_DELIVERED")
    
    # Person 1: AWAY → RETURNED
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T4")
    
    # Person 2: NEW → GREETED
    update_identity_state("E0002", "GREETING_DELIVERED")
    
    # Verify final states
    assert get_state("E0001")["state"] == "RETURNED"
    assert get_state("E0002")["state"] == "GREETED"
    assert get_state("E0003")["state"] == "GREETED"


def test_greeting_initiated_event():
    """Test that GREETING_INITIATED event records timestamp but doesn't change state."""
    embedding_id = "E0001"
    
    # First detection
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    assert get_state(embedding_id)["state"] == "NEW"
    assert get_state(embedding_id)["greeting_initiated_at"] is None
    
    # Greeting sent to TTS
    update_identity_state(embedding_id, "GREETING_INITIATED")
    
    # Should still be NEW but with timestamp
    assert get_state(embedding_id)["state"] == "NEW"
    assert get_state(embedding_id)["greeting_initiated_at"] is not None
    assert isinstance(get_state(embedding_id)["greeting_initiated_at"], float)


def test_greeting_timeout_auto_transitions_to_greeted():
    """Test that NEW state auto-transitions to GREETED after timeout via check_timeouts()."""
    from robot_assistant.session_state import store
    import time
    
    embedding_id = "E0001"
    
    # Detection + greeting initiated
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_INITIATED")
    assert get_state(embedding_id)["state"] == "NEW"
    
    # Manually set greeting_initiated_at to simulate timeout (5+ seconds ago)
    state_dict = get_state(embedding_id)
    state_dict["greeting_initiated_at"] = time.time() - (store.GREETING_TIMEOUT_SECONDS + 1)
    
    # Explicit check_timeouts() should trigger timeout and auto-transition
    from robot_assistant.session_state.store import check_timeouts
    timed_out = check_timeouts()
    
    # Should have auto-transitioned to GREETED due to timeout
    assert timed_out == 1
    assert get_state(embedding_id)["state"] == "GREETED"
    assert get_state(embedding_id)["greeting_initiated_at"] is None  # Cleared


def test_greeting_timeout_prevents_re_greet_loop():
    """Test that timeout prevents infinite re-greet loops if TTS fails.
    
    This is the critical safety feature: if TTS crashes/fails, we don't want
    to keep re-greeting the same person.
    """
    from robot_assistant.session_state import store
    from robot_assistant.session_state.store import check_timeouts
    import time
    
    embedding_id = "E0001"
    
    # Detection + greeting initiated
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_INITIATED")
    
    # Simulate timeout
    state_dict = get_state(embedding_id)
    state_dict["greeting_initiated_at"] = time.time() - (store.GREETING_TIMEOUT_SECONDS + 1)
    
    # Call check_timeouts() - should transition to GREETED
    timed_out = check_timeouts()
    assert timed_out == 1
    assert get_state(embedding_id)["state"] == "GREETED"
    
    # Multiple subsequent check_timeouts() calls should not trigger again
    for i in range(5):
        timed_out = check_timeouts()
        assert timed_out == 0, f"Iteration {i}: should not timeout again"
        assert get_state(embedding_id)["state"] == "GREETED", f"Iteration {i}: should stay GREETED"


def test_greeting_delivered_before_timeout_clears_timestamp():
    """Test that GREETING_DELIVERED clears the timeout timestamp."""
    embedding_id = "E0001"
    
    # Detection + greeting initiated
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_INITIATED")
    assert get_state(embedding_id)["greeting_initiated_at"] is not None
    
    # Greeting delivered successfully (before timeout)
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    
    # Should be GREETED and timestamp cleared
    assert get_state(embedding_id)["state"] == "GREETED"
    assert get_state(embedding_id)["greeting_initiated_at"] is None


def test_track_lost_before_greeting_clears_timeout():
    """Test that TRACK_LOST before greeting completes clears timeout."""
    embedding_id = "E0001"
    
    # Detection + greeting initiated
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_INITIATED")
    assert get_state(embedding_id)["greeting_initiated_at"] is not None
    
    # Person leaves before greeting completes
    update_identity_state(embedding_id, "TRACK_LOST")
    
    # Should be AWAY and timestamp cleared
    assert get_state(embedding_id)["state"] == "AWAY"
    assert get_state(embedding_id)["greeting_initiated_at"] is None


def test_greeting_timeout_only_applies_to_new_state():
    """Test that timeout only applies when in NEW state, not other states."""
    from robot_assistant.session_state import store
    import time
    
    embedding_id = "E0001"
    
    # Get to GREETED state
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    assert get_state(embedding_id)["state"] == "GREETED"
    
    # Manually set a stale timestamp (shouldn't affect GREETED state)
    state_dict = get_state(embedding_id)
    state_dict["greeting_initiated_at"] = time.time() - (store.GREETING_TIMEOUT_SECONDS + 1)
    
    # Should stay GREETED, not be affected by timeout
    state = update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    assert state == "GREETED"


def test_get_greeting_timeout():
    """Test that greeting timeout value is accessible."""
    from robot_assistant.session_state.store import get_greeting_timeout
    
    timeout = get_greeting_timeout()
    assert timeout > 0
    assert timeout == 5.0  # Default value


def test_greeting_timeout_with_no_initiated_event():
    """Test that NEW state without GREETING_INITIATED doesn't trigger timeout."""
    from robot_assistant.session_state import store
    import time
    
    embedding_id = "E0001"
    
    # Detection but NO greeting initiated
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    assert get_state(embedding_id)["state"] == "NEW"
    assert get_state(embedding_id)["greeting_initiated_at"] is None
    
    # Wait and re-detect
    time.sleep(0.01)
    state = update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    
    # Should still be NEW (no timeout without GREETING_INITIATED)
    assert state == "NEW"


def test_session_state_event_published_on_transitions():
    """Test that SESSION_STATE events are published when state changes."""
    from robot_assistant.events import bus
    
    session_events = []
    bus.subscribe("SESSION_STATE", lambda e: session_events.append(e))
    
    embedding_id = "E0001"
    
    # NEW → GREETED transition
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    
    # Should have published SESSION_STATE event
    assert len(session_events) == 1
    assert session_events[0]["event"] == "SESSION_STATE"
    assert session_events[0]["embedding_id"] == embedding_id
    assert session_events[0]["state"] == "GREETED"
    
    # GREETED → AWAY transition
    update_identity_state(embedding_id, "TRACK_LOST")
    
    assert len(session_events) == 2
    assert session_events[1]["state"] == "AWAY"
    
    # AWAY → RETURNED transition
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T2")
    
    assert len(session_events) == 3
    assert session_events[2]["state"] == "RETURNED"


def test_session_state_event_published_on_timeout():
    """Test that SESSION_STATE event is published when timeout auto-transitions."""
    from robot_assistant.events import bus
    from robot_assistant.session_state import store
    from robot_assistant.session_state.store import check_timeouts
    import time
    
    session_events = []
    bus.subscribe("SESSION_STATE", lambda e: session_events.append(e))
    
    embedding_id = "E0001"
    
    # Detection + greeting initiated
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_INITIATED")
    
    # Simulate timeout
    state_dict = get_state(embedding_id)
    state_dict["greeting_initiated_at"] = time.time() - (store.GREETING_TIMEOUT_SECONDS + 1)
    
    # Trigger timeout check
    check_timeouts()
    
    # Should have published SESSION_STATE event for auto-transition
    assert len(session_events) == 1
    assert session_events[0]["event"] == "SESSION_STATE"
    assert session_events[0]["embedding_id"] == embedding_id
    assert session_events[0]["state"] == "GREETED"


def test_session_state_event_not_published_when_state_unchanged():
    """Test that SESSION_STATE event is NOT published when state doesn't change."""
    from robot_assistant.events import bus
    
    session_events = []
    bus.subscribe("SESSION_STATE", lambda e: session_events.append(e))
    
    embedding_id = "E0001"
    
    # Get to GREETED state
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_DELIVERED")
    assert len(session_events) == 1  # NEW → GREETED
    
    # Multiple IDENTITY_RESOLVED (person still present, state unchanged)
    for _ in range(5):
        update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    
    # Should still only have 1 event (no events for unchanged state)
    assert len(session_events) == 1


def test_check_timeouts_without_any_events():
    """Test that check_timeouts() triggers timeout without any IDENTITY_RESOLVED events.
    
    Critical test: Confirms timeout fires via explicit periodic check, NOT via
    lazy checking on incidental state updates. This addresses the logical gap
    where IDENTITY_RESOLVED fires only once per track appearance.
    """
    from robot_assistant.session_state import store
    from robot_assistant.session_state.store import check_timeouts
    import time
    
    embedding_id = "E0001"
    
    # Detection + greeting initiated
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_INITIATED")
    assert get_state(embedding_id)["state"] == "NEW"
    
    # Simulate timeout (person standing still, no more IDENTITY_RESOLVED events)
    state_dict = get_state(embedding_id)
    state_dict["greeting_initiated_at"] = time.time() - (store.GREETING_TIMEOUT_SECONDS + 1)
    
    # NO IDENTITY_RESOLVED events - just call check_timeouts() directly
    timed_out = check_timeouts()
    
    # Timeout should still fire
    assert timed_out == 1
    assert get_state(embedding_id)["state"] == "GREETED"


def test_check_timeouts_multiple_identities():
    """Test that check_timeouts() handles multiple identities correctly."""
    from robot_assistant.session_state import store
    from robot_assistant.session_state.store import check_timeouts
    import time
    
    # Three identities with different states
    # E0001: NEW with timeout expired
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state("E0001", "GREETING_INITIATED")
    state1 = get_state("E0001")
    state1["greeting_initiated_at"] = time.time() - (store.GREETING_TIMEOUT_SECONDS + 1)
    
    # E0002: NEW with timeout NOT expired
    update_identity_state("E0002", "IDENTITY_RESOLVED", track_id="T2")
    update_identity_state("E0002", "GREETING_INITIATED")
    state2 = get_state("E0002")
    state2["greeting_initiated_at"] = time.time() - 2.0  # Only 2 seconds (< 5s timeout)
    
    # E0003: GREETED (no timeout applicable)
    update_identity_state("E0003", "IDENTITY_RESOLVED", track_id="T3")
    update_identity_state("E0003", "GREETING_DELIVERED")
    
    # Check timeouts
    timed_out = check_timeouts()
    
    # Only E0001 should have timed out
    assert timed_out == 1
    assert get_state("E0001")["state"] == "GREETED"
    assert get_state("E0002")["state"] == "NEW"  # Still waiting
    assert get_state("E0003")["state"] == "GREETED"  # Already greeted


def test_check_timeouts_returns_zero_when_no_timeouts():
    """Test that check_timeouts() returns 0 when no identities have timed out."""
    from robot_assistant.session_state.store import check_timeouts
    
    # No identities at all
    timed_out = check_timeouts()
    assert timed_out == 0
    
    # Identity with no greeting initiated
    update_identity_state("E0001", "IDENTITY_RESOLVED", track_id="T1")
    timed_out = check_timeouts()
    assert timed_out == 0
    
    # Identity already greeted
    update_identity_state("E0001", "GREETING_DELIVERED")
    timed_out = check_timeouts()
    assert timed_out == 0


def test_check_timeouts_updates_last_seen():
    """Test that check_timeouts() updates last_seen timestamp on timeout."""
    from robot_assistant.session_state import store
    from robot_assistant.session_state.store import check_timeouts
    import time
    
    embedding_id = "E0001"
    
    # Setup with timeout
    update_identity_state(embedding_id, "IDENTITY_RESOLVED", track_id="T1")
    update_identity_state(embedding_id, "GREETING_INITIATED")
    
    original_last_seen = get_state(embedding_id)["last_seen"]
    
    # Simulate timeout
    state_dict = get_state(embedding_id)
    state_dict["greeting_initiated_at"] = time.time() - (store.GREETING_TIMEOUT_SECONDS + 1)
    
    time.sleep(0.01)  # Small delay to ensure last_seen changes
    
    # Trigger timeout
    check_timeouts()
    
    # last_seen should be updated
    new_last_seen = get_state(embedding_id)["last_seen"]
    assert new_last_seen > original_last_seen
