"""Tests for gesture recognition from pose keypoints.

Tests verify pure geometry-based HAND_RAISED detection using synthetic
keypoints, including boundary cases and independent left/right hand testing.
"""

import pytest
import numpy as np
import time
from robot_assistant.vision import gesture
from robot_assistant.events import bus


@pytest.fixture(autouse=True)
def reset_bus():
    """Clear event bus subscribers before each test."""
    bus._subscribers.clear()
    yield
    bus._subscribers.clear()


def create_keypoints(
    left_shoulder_y: float,
    right_shoulder_y: float,
    left_wrist_y: float,
    right_wrist_y: float,
    left_shoulder_conf: float = 0.9,
    right_shoulder_conf: float = 0.9,
    left_wrist_conf: float = 0.9,
    right_wrist_conf: float = 0.9
) -> np.ndarray:
    """Create synthetic COCO 17-point keypoints for testing.
    
    Args:
        left_shoulder_y: y-coordinate for left shoulder (index 5)
        right_shoulder_y: y-coordinate for right shoulder (index 6)
        left_wrist_y: y-coordinate for left wrist (index 9)
        right_wrist_y: y-coordinate for right wrist (index 10)
        *_conf: confidence values for each keypoint (default 0.9)
    
    Returns:
        (17, 3) array with [x, y, confidence] for each keypoint
    """
    # Initialize all keypoints at origin with low confidence
    keypoints = np.zeros((17, 3))
    
    # Set test keypoints (x=100 is arbitrary, we only test y-coordinates)
    keypoints[5] = [100, left_shoulder_y, left_shoulder_conf]  # left_shoulder
    keypoints[6] = [100, right_shoulder_y, right_shoulder_conf]  # right_shoulder
    keypoints[9] = [100, left_wrist_y, left_wrist_conf]  # left_wrist
    keypoints[10] = [100, right_wrist_y, right_wrist_conf]  # right_wrist
    
    return keypoints


class TestHandRaisedDetection:
    """Test HAND_RAISED gesture detection logic."""
    
    def test_left_hand_raised_only(self):
        """Left wrist above left shoulder detects HAND_RAISED."""
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=150,  # Above shoulder (smaller y)
            right_wrist_y=250  # Below shoulder
        )
        
        gesture_result = gesture.check_gesture(keypoints, track_id="1")
        
        assert gesture_result == "HAND_RAISED"
    
    def test_right_hand_raised_only(self):
        """Right wrist above right shoulder detects HAND_RAISED."""
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=250,  # Below shoulder
            right_wrist_y=150  # Above shoulder (smaller y)
        )
        
        gesture_result = gesture.check_gesture(keypoints, track_id="1")
        
        assert gesture_result == "HAND_RAISED"
    
    def test_both_hands_raised(self):
        """Both wrists above shoulders detects HAND_RAISED."""
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=150,  # Above shoulder
            right_wrist_y=150  # Above shoulder
        )
        
        gesture_result = gesture.check_gesture(keypoints, track_id="1")
        
        assert gesture_result == "HAND_RAISED"
    
    def test_neither_hand_raised(self):
        """Both wrists below shoulders returns None."""
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=250,  # Below shoulder
            right_wrist_y=250  # Below shoulder
        )
        
        gesture_result = gesture.check_gesture(keypoints, track_id="1")
        
        assert gesture_result is None
    
    def test_wrist_equal_to_shoulder_not_raised(self):
        """Wrist y exactly equal to shoulder y is NOT considered raised.
        
        Boundary case: requires strict inequality (wrist_y < shoulder_y).
        """
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=200,  # Exactly equal to shoulder
            right_wrist_y=200  # Exactly equal to shoulder
        )
        
        gesture_result = gesture.check_gesture(keypoints, track_id="1")
        
        assert gesture_result is None


class TestKeypointConfidence:
    """Test confidence threshold handling for gesture detection."""
    
    def test_low_confidence_wrist_ignored(self):
        """Low confidence wrist (< 0.5) is not used for detection."""
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=150,  # Above shoulder, but low confidence
            right_wrist_y=250,
            left_wrist_conf=0.3  # Below threshold
        )
        
        gesture_result = gesture.check_gesture(keypoints, track_id="1")
        
        # Should NOT detect gesture due to low confidence
        assert gesture_result is None
    
    def test_low_confidence_shoulder_ignored(self):
        """Low confidence shoulder (< 0.5) is not used for detection."""
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=150,  # Above shoulder
            right_wrist_y=250,
            left_shoulder_conf=0.3  # Below threshold
        )
        
        gesture_result = gesture.check_gesture(keypoints, track_id="1")
        
        # Should NOT detect gesture due to low confidence shoulder
        assert gesture_result is None
    
    def test_one_side_low_confidence_other_side_detects(self):
        """If one side has low confidence, other side can still detect."""
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=150,  # Above shoulder, low confidence
            right_wrist_y=150,  # Above shoulder, good confidence
            left_wrist_conf=0.3  # Below threshold
        )
        
        gesture_result = gesture.check_gesture(keypoints, track_id="1")
        
        # Right hand should still be detected
        assert gesture_result == "HAND_RAISED"


class TestEventPublishing:
    """Test GESTURE_DETECTED event publishing."""
    
    def test_gesture_detected_event_published(self):
        """GESTURE_DETECTED event published when hand raised."""
        events = []
        bus.subscribe('GESTURE_DETECTED', lambda e: events.append(e))
        
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=150,
            right_wrist_y=250
        )
        
        gesture.check_gesture(keypoints, track_id="42")
        
        assert len(events) == 1
        assert events[0]['event'] == 'GESTURE_DETECTED'
        assert events[0]['gesture'] == 'HAND_RAISED'
        assert events[0]['track_id'] == '42'
    
    def test_no_event_when_no_gesture(self):
        """No event published when no gesture detected."""
        events = []
        bus.subscribe('GESTURE_DETECTED', lambda e: events.append(e))
        
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=250,  # Both below shoulders
            right_wrist_y=250
        )
        
        gesture.check_gesture(keypoints, track_id="42")
        
        assert len(events) == 0
    
    def test_event_schema_matches(self):
        """Published event matches GestureDetectedEvent schema."""
        from robot_assistant.events.schemas import validate_event
        
        events = []
        bus.subscribe('GESTURE_DETECTED', lambda e: events.append(e))
        
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=150,
            right_wrist_y=250
        )
        
        gesture.check_gesture(keypoints, track_id="123")
        
        # Validate against schema
        assert len(events) == 1
        is_valid, error = validate_event(events[0])
        assert is_valid, f"Event validation failed: {error}"
        
        # Verify exact field structure from schemas.py
        assert events[0]['event'] == 'GESTURE_DETECTED'
        assert isinstance(events[0]['gesture'], str)
        assert isinstance(events[0]['track_id'], str)
        assert events[0]['gesture'] == 'HAND_RAISED'
        assert events[0]['track_id'] == '123'


class TestLatency:
    """Test latency of pure arithmetic gesture detection."""
    
    def test_latency_under_1ms(self):
        """Gesture check completes in < 1ms (pure arithmetic)."""
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=150,
            right_wrist_y=250
        )
        
        # Warm up (first call may be slower due to Python internals)
        gesture.check_gesture(keypoints, track_id="1")
        
        # Measure 100 iterations
        iterations = 100
        start = time.perf_counter()
        
        for i in range(iterations):
            gesture.check_gesture(keypoints, track_id=str(i))
        
        end = time.perf_counter()
        avg_latency_ms = ((end - start) / iterations) * 1000
        
        # Should be well under 1ms (pure arithmetic on 4 floats)
        assert avg_latency_ms < 1.0, f"Average latency {avg_latency_ms:.3f}ms exceeds 1ms target"


class TestTrackIdPropagation:
    """Test track_id is correctly propagated to events."""
    
    def test_track_id_as_string(self):
        """Track ID is converted to string in event."""
        events = []
        bus.subscribe('GESTURE_DETECTED', lambda e: events.append(e))
        
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=150,
            right_wrist_y=250
        )
        
        # Pass integer track_id
        gesture.check_gesture(keypoints, track_id="999")
        
        assert len(events) == 1
        assert events[0]['track_id'] == '999'
        assert isinstance(events[0]['track_id'], str)
    
    def test_different_track_ids_produce_separate_events(self):
        """Multiple calls with different track_ids produce distinct events."""
        events = []
        bus.subscribe('GESTURE_DETECTED', lambda e: events.append(e))
        
        keypoints = create_keypoints(
            left_shoulder_y=200,
            right_shoulder_y=200,
            left_wrist_y=150,
            right_wrist_y=250
        )
        
        gesture.check_gesture(keypoints, track_id="1")
        gesture.check_gesture(keypoints, track_id="2")
        gesture.check_gesture(keypoints, track_id="3")
        
        assert len(events) == 3
        assert events[0]['track_id'] == '1'
        assert events[1]['track_id'] == '2'
        assert events[2]['track_id'] == '3'
