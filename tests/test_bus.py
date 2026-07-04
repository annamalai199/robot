"""Tests for event bus pub/sub functionality."""

import pytest
from robot_assistant.events import bus


@pytest.fixture(autouse=True)
def reset_bus():
    """Clear all subscribers before and after each test."""
    bus.clear_subscribers()
    yield
    bus.clear_subscribers()


def test_subscribe_and_publish():
    """Test basic subscribe and publish flow."""
    received_events = []
    
    def callback(event):
        received_events.append(event)
    
    bus.subscribe("TEST_EVENT", callback)
    
    event = {"event": "TEST_EVENT", "data": "hello"}
    bus.publish(event)
    
    assert len(received_events) == 1
    assert received_events[0] == event


def test_multiple_subscribers_same_event():
    """Test multiple subscribers receive the same event."""
    received_1 = []
    received_2 = []
    
    def callback1(event):
        received_1.append(event)
    
    def callback2(event):
        received_2.append(event)
    
    bus.subscribe("TEST_EVENT", callback1)
    bus.subscribe("TEST_EVENT", callback2)
    
    event = {"event": "TEST_EVENT", "data": "broadcast"}
    bus.publish(event)
    
    assert len(received_1) == 1
    assert len(received_2) == 1
    assert received_1[0] == event
    assert received_2[0] == event


def test_different_event_types_dont_interfere():
    """Test that different event types don't trigger each other's callbacks."""
    received_a = []
    received_b = []
    
    def callback_a(event):
        received_a.append(event)
    
    def callback_b(event):
        received_b.append(event)
    
    bus.subscribe("EVENT_A", callback_a)
    bus.subscribe("EVENT_B", callback_b)
    
    bus.publish({"event": "EVENT_A", "data": "for A"})
    bus.publish({"event": "EVENT_B", "data": "for B"})
    
    assert len(received_a) == 1
    assert received_a[0]["data"] == "for A"
    
    assert len(received_b) == 1
    assert received_b[0]["data"] == "for B"


def test_unsubscribe():
    """Test unsubscribing a callback."""
    received = []
    
    def callback(event):
        received.append(event)
    
    bus.subscribe("TEST_EVENT", callback)
    bus.publish({"event": "TEST_EVENT", "data": "first"})
    
    assert len(received) == 1
    
    # Unsubscribe and verify no more events received
    result = bus.unsubscribe("TEST_EVENT", callback)
    assert result is True
    
    bus.publish({"event": "TEST_EVENT", "data": "second"})
    assert len(received) == 1  # Still just the first event


def test_unsubscribe_nonexistent_callback():
    """Test unsubscribing a callback that wasn't subscribed."""
    def callback(event):
        pass
    
    result = bus.unsubscribe("TEST_EVENT", callback)
    assert result is False


def test_publish_without_subscribers():
    """Test publishing when no subscribers exist (should not error)."""
    # Should not raise any exception
    bus.publish({"event": "LONELY_EVENT", "data": "nobody listening"})


def test_invalid_event_missing_event_field():
    """Test publishing an invalid event (missing 'event' field)."""
    received = []
    
    def callback(event):
        received.append(event)
    
    bus.subscribe("TEST_EVENT", callback)
    
    # Invalid event - missing 'event' field - should now raise ValueError
    with pytest.raises(ValueError, match="missing required 'event' field"):
        bus.publish({"data": "invalid"})
    
    # Callback should not be invoked
    assert len(received) == 0


def test_callback_exception_doesnt_stop_other_callbacks():
    """Test that exception in one callback doesn't prevent others from running."""
    received_good = []
    
    def bad_callback(event):
        raise ValueError("Intentional error")
    
    def good_callback(event):
        received_good.append(event)
    
    bus.subscribe("TEST_EVENT", bad_callback)
    bus.subscribe("TEST_EVENT", good_callback)
    
    # Should not raise, good_callback should still execute
    bus.publish({"event": "TEST_EVENT", "data": "test"})
    
    assert len(received_good) == 1


def test_get_subscriber_count():
    """Test getting subscriber counts."""
    def callback1(event):
        pass
    
    def callback2(event):
        pass
    
    assert bus.get_subscriber_count("TEST_EVENT") == 0
    assert bus.get_subscriber_count() == 0
    
    bus.subscribe("TEST_EVENT", callback1)
    assert bus.get_subscriber_count("TEST_EVENT") == 1
    assert bus.get_subscriber_count() == 1
    
    bus.subscribe("TEST_EVENT", callback2)
    assert bus.get_subscriber_count("TEST_EVENT") == 2
    assert bus.get_subscriber_count() == 2
    
    bus.subscribe("OTHER_EVENT", callback1)
    assert bus.get_subscriber_count("TEST_EVENT") == 2
    assert bus.get_subscriber_count("OTHER_EVENT") == 1
    assert bus.get_subscriber_count() == 3


def test_get_event_types():
    """Test getting list of subscribed event types."""
    def callback(event):
        pass
    
    assert bus.get_event_types() == []
    
    bus.subscribe("EVENT_A", callback)
    bus.subscribe("EVENT_B", callback)
    
    event_types = bus.get_event_types()
    assert len(event_types) == 2
    assert "EVENT_A" in event_types
    assert "EVENT_B" in event_types


def test_clear_subscribers_specific_type():
    """Test clearing subscribers for a specific event type."""
    def callback(event):
        pass
    
    bus.subscribe("EVENT_A", callback)
    bus.subscribe("EVENT_B", callback)
    
    assert bus.get_subscriber_count("EVENT_A") == 1
    assert bus.get_subscriber_count("EVENT_B") == 1
    
    bus.clear_subscribers("EVENT_A")
    
    assert bus.get_subscriber_count("EVENT_A") == 0
    assert bus.get_subscriber_count("EVENT_B") == 1


def test_clear_all_subscribers():
    """Test clearing all subscribers."""
    def callback(event):
        pass
    
    bus.subscribe("EVENT_A", callback)
    bus.subscribe("EVENT_B", callback)
    
    assert bus.get_subscriber_count() == 2
    
    bus.clear_subscribers()
    
    assert bus.get_subscriber_count() == 0
    assert bus.get_event_types() == []


def test_subscribe_non_callable_raises():
    """Test that subscribing a non-callable raises TypeError."""
    with pytest.raises(TypeError):
        bus.subscribe("TEST_EVENT", "not a function")


def test_thread_safety_stress():
    """Stress test for thread safety (multiple threads publishing/subscribing)."""
    import threading
    import time
    
    received = []
    lock = threading.Lock()
    
    def callback(event):
        with lock:
            received.append(event)
    
    bus.subscribe("STRESS_EVENT", callback)
    
    def publisher(n):
        for i in range(10):
            bus.publish({"event": "STRESS_EVENT", "data": f"thread-{n}-msg-{i}"})
            time.sleep(0.001)
    
    threads = [threading.Thread(target=publisher, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Should have received 5 threads * 10 messages = 50 events
    assert len(received) == 50
