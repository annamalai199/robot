"""Tests for ByteTrack multi-person tracker.

Tests use synthetic detection sequences to verify tracking behavior without
requiring the real detector. Tests verify stable IDs, occlusion handling,
and TRACK_LOST event publishing.
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch
from robot_assistant.vision.tracker import Tracker
from robot_assistant.config import config
from robot_assistant.events import bus


@pytest.fixture
def mock_detection_single_person():
    """Create a single person detection."""
    return {
        'bbox': [100.0, 150.0, 300.0, 450.0],
        'keypoints': np.random.rand(17, 3),  # Synthetic keypoints
        'confidence': 0.85
    }


@pytest.fixture
def mock_detection_two_people():
    """Create two person detections."""
    return [
        {
            'bbox': [100.0, 150.0, 300.0, 450.0],
            'keypoints': np.random.rand(17, 3),
            'confidence': 0.85
        },
        {
            'bbox': [350.0, 100.0, 550.0, 420.0],
            'keypoints': np.random.rand(17, 3),
            'confidence': 0.78
        }
    ]


def create_detection_at(x, y, width=200, height=300):
    """Helper to create a detection at specific position."""
    return {
        'bbox': [float(x), float(y), float(x + width), float(y + height)],
        'keypoints': np.random.rand(17, 3),
        'confidence': 0.8
    }


class TestTrackerBasics:
    """Test basic tracker functionality."""
    
    def test_tracker_initialization(self):
        """Test tracker initializes correctly."""
        tracker = Tracker()
        
        assert tracker.get_track_count() == 0
        assert tracker.max_age == config.TRACK_MAX_AGE
    
    def test_tracker_custom_max_age(self):
        """Test tracker with custom max_age."""
        tracker = Tracker(max_age=15)
        
        assert tracker.max_age == 15
    
    def test_tracker_creates_new_track(self, mock_detection_single_person):
        """Test that first detection creates a new track."""
        tracker = Tracker()
        
        tracks = tracker.update([mock_detection_single_person])
        
        assert len(tracks) == 1
        assert tracks[0]['track_id'] == 1
        assert tracks[0]['bbox'] == mock_detection_single_person['bbox']
        assert np.array_equal(tracks[0]['keypoints'], mock_detection_single_person['keypoints'])
    
    def test_tracker_creates_multiple_tracks(self, mock_detection_two_people):
        """Test that multiple detections create multiple tracks."""
        tracker = Tracker()
        
        tracks = tracker.update(mock_detection_two_people)
        
        assert len(tracks) == 2
        assert tracks[0]['track_id'] == 1
        assert tracks[1]['track_id'] == 2
    
    def test_tracker_empty_detections(self):
        """Test tracker handles empty detection list."""
        tracker = Tracker()
        
        tracks = tracker.update([])
        
        assert len(tracks) == 0


class TestStableTrackIds:
    """Test stable track ID maintenance across frames."""
    
    def test_stable_track_id_across_frames(self):
        """Test that same person keeps same track_id across consecutive frames.
        
        Critical acceptance criteria: Maintains stable track_id across occlusion
        """
        tracker = Tracker()
        
        # Frame 1: Person appears
        det1 = create_detection_at(100, 150)
        tracks1 = tracker.update([det1])
        track_id_1 = tracks1[0]['track_id']
        
        # Frame 2: Same person, slightly moved (high IoU overlap)
        det2 = create_detection_at(105, 155)  # Moved 5 pixels
        tracks2 = tracker.update([det2])
        track_id_2 = tracks2[0]['track_id']
        
        # Frame 3: Same person, moved again
        det3 = create_detection_at(110, 160)
        tracks3 = tracker.update([det3])
        track_id_3 = tracks3[0]['track_id']
        
        # Track ID should remain stable
        assert track_id_1 == track_id_2 == track_id_3
    
    def test_different_people_get_different_track_ids(self):
        """Test that different people get different track IDs."""
        tracker = Tracker()
        
        # Two people in same frame, far apart (low IoU)
        det1 = create_detection_at(100, 150)
        det2 = create_detection_at(400, 150)
        
        tracks = tracker.update([det1, det2])
        
        # Should have different track IDs
        assert len(tracks) == 2
        assert tracks[0]['track_id'] != tracks[1]['track_id']


class TestOcclusionHandling:
    """Test occlusion tolerance (track persistence without detections)."""
    
    def test_track_survives_brief_occlusion(self):
        """Test that track survives brief occlusion (< max_age frames).
        
        Acceptance criteria: Maintains stable track_id across occlusion (up to 30 frames)
        """
        tracker = Tracker()
        
        # Frame 1: Person detected
        det = create_detection_at(100, 150)
        tracks = tracker.update([det])
        original_track_id = tracks[0]['track_id']
        
        # Frames 2-10: Person occluded (no detection)
        for _ in range(9):
            tracks = tracker.update([])
            # Track should still exist but not be returned (no detection)
            # Internal track count includes occluded tracks
        
        # Frame 11: Person re-appears at same location
        det_reappear = create_detection_at(100, 150)
        tracks = tracker.update([det_reappear])
        
        # Should re-associate with original track
        assert len(tracks) == 1
        assert tracks[0]['track_id'] == original_track_id
    
    def test_track_lost_after_max_age(self):
        """Test that track is removed after exceeding max_age.
        
        Uses actual config value for max_age threshold.
        """
        tracker = Tracker()
        
        # Frame 1: Person detected
        det = create_detection_at(100, 150)
        tracks = tracker.update([det])
        original_track_id = tracks[0]['track_id']
        
        # Frames 2 to (max_age + 2): Person occluded
        for i in range(config.TRACK_MAX_AGE + 1):
            tracks = tracker.update([])
        
        # Track should be removed now
        assert tracker.get_track_count() == 0
        
        # If person re-appears, should get NEW track ID
        det_reappear = create_detection_at(100, 150)
        tracks = tracker.update([det_reappear])
        
        assert len(tracks) == 1
        assert tracks[0]['track_id'] != original_track_id  # New ID


class TestTrackLostEvent:
    """Test TRACK_LOST event publishing."""
    
    def test_track_lost_event_published(self):
        """Test that TRACK_LOST event is published when track exceeds max_age.
        
        Acceptance criteria: Emits TRACK_LOST event when track disappears for >30 frames
        """
        tracker = Tracker()
        
        # Subscribe to events
        events_received = []
        bus.subscribe("TRACK_LOST", lambda e: events_received.append(e))
        
        # Frame 1: Person detected
        det = create_detection_at(100, 150)
        tracks = tracker.update([det])
        track_id = tracks[0]['track_id']
        
        # Set embedding_id (simulates face_id module)
        tracker.set_embedding_id(track_id, "E001")
        
        # Occlude for max_age + 1 frames
        for _ in range(config.TRACK_MAX_AGE + 1):
            tracker.update([])
        
        # TRACK_LOST event should have been published
        assert len(events_received) == 1
        
        event = events_received[0]
        assert event['event'] == 'TRACK_LOST'
        assert event['track_id'] == str(track_id)
        assert event['embedding_id'] == 'E001'
    
    def test_track_lost_event_schema(self):
        """Test that TRACK_LOST event matches expected schema.
        
        Schema from events/schemas.py: {event, track_id, embedding_id}
        """
        from robot_assistant.events.schemas import TrackLostEvent
        
        tracker = Tracker()
        
        # Subscribe to events
        events_received = []
        bus.subscribe("TRACK_LOST", lambda e: events_received.append(e))
        
        # Create and lose a track
        det = create_detection_at(100, 150)
        tracks = tracker.update([det])
        track_id = tracks[0]['track_id']
        tracker.set_embedding_id(track_id, "E002")
        
        # Exceed max_age
        for _ in range(config.TRACK_MAX_AGE + 1):
            tracker.update([])
        
        # Verify event schema
        event = events_received[0]
        
        # Check required fields from TrackLostEvent TypedDict
        assert 'event' in event
        assert 'track_id' in event
        assert 'embedding_id' in event
        
        assert event['event'] == 'TRACK_LOST'
        assert isinstance(event['track_id'], str)
        assert isinstance(event['embedding_id'], str)
    
    def test_track_lost_without_embedding_id(self):
        """Test TRACK_LOST event when embedding_id was never set."""
        tracker = Tracker()
        
        events_received = []
        bus.subscribe("TRACK_LOST", lambda e: events_received.append(e))
        
        # Create track without setting embedding_id
        det = create_detection_at(100, 150)
        tracker.update([det])
        
        # Exceed max_age
        for _ in range(config.TRACK_MAX_AGE + 1):
            tracker.update([])
        
        # Event should still be published with "unknown" embedding_id
        assert len(events_received) == 1
        event = events_received[0]
        assert event['embedding_id'] == 'unknown'


class TestLatency:
    """Test latency requirements."""
    
    def test_update_latency_under_5ms(self):
        """Test that tracker.update() completes in < 5ms.
        
        Acceptance criteria: Test asserts latency < 5ms per update
        """
        tracker = Tracker()
        
        # Pre-populate tracker with some tracks
        detections = [create_detection_at(100 + i*250, 150) for i in range(3)]
        tracker.update(detections)
        
        # Warmup
        tracker.update(detections)
        
        # Measure latency
        iterations = 100
        start = time.perf_counter()
        
        for _ in range(iterations):
            # Slightly move detections to simulate realistic updates
            detections = [create_detection_at(100 + i*250 + np.random.randint(-5, 5), 150) for i in range(3)]
            tracker.update(detections)
        
        elapsed = time.perf_counter() - start
        avg_latency = (elapsed / iterations) * 1000  # Convert to milliseconds
        
        assert avg_latency < 5.0, f"Average latency {avg_latency:.2f}ms exceeds 5ms requirement"
        
        print(f"\n  Average latency: {avg_latency:.2f}ms (target: < 5ms)")


class TestReidentification:
    """Test re-identification after brief occlusion."""
    
    def test_reidentification_after_brief_occlusion(self):
        """Test that person is re-identified with same track_id after brief occlusion.
        
        Acceptance criteria: Test asserts stable IDs and re-identification after brief occlusion
        """
        tracker = Tracker()
        
        # Frame 1: Person appears
        det = create_detection_at(100, 150)
        tracks = tracker.update([det])
        original_track_id = tracks[0]['track_id']
        
        # Frames 2-5: Person occluded
        for _ in range(4):
            tracker.update([])
        
        # Frame 6: Person re-appears at similar location
        det_reappear = create_detection_at(105, 155)  # Slightly moved
        tracks = tracker.update([det_reappear])
        
        # Should re-identify with same track_id
        assert len(tracks) == 1
        assert tracks[0]['track_id'] == original_track_id


class TestMultiPersonScenarios:
    """Test multi-person tracking scenarios."""
    
    def test_multiple_people_independent_tracking(self):
        """Test that multiple people are tracked independently."""
        tracker = Tracker()
        
        # Frame 1: Two people appear
        det1 = create_detection_at(100, 150)
        det2 = create_detection_at(400, 150)
        tracks = tracker.update([det1, det2])
        
        track_ids = {tracks[0]['track_id'], tracks[1]['track_id']}
        assert len(track_ids) == 2
        
        # Frame 2: Both people move slightly
        det1_moved = create_detection_at(110, 160)
        det2_moved = create_detection_at(410, 160)
        tracks = tracker.update([det1_moved, det2_moved])
        
        # Both should keep their IDs
        new_track_ids = {tracks[0]['track_id'], tracks[1]['track_id']}
        assert track_ids == new_track_ids
    
    def test_person_leaves_while_other_stays(self):
        """Test that one person leaving doesn't affect other's track."""
        tracker = Tracker()
        
        # Frame 1: Two people
        det1 = create_detection_at(100, 150)
        det2 = create_detection_at(400, 150)
        tracks = tracker.update([det1, det2])
        
        track_id_1 = tracks[0]['track_id']
        track_id_2 = tracks[1]['track_id']
        
        # Frames 2+: Only person 1 stays (person 2 leaves)
        for _ in range(config.TRACK_MAX_AGE + 1):
            det1_moved = create_detection_at(100, 150)
            tracks = tracker.update([det1_moved])
        
        # Person 1 should still be tracked with same ID
        assert len(tracks) == 1
        assert tracks[0]['track_id'] == track_id_1


class TestTrackerUtilities:
    """Test utility functions."""
    
    def test_set_embedding_id(self):
        """Test setting embedding_id for a track."""
        tracker = Tracker()
        
        det = create_detection_at(100, 150)
        tracks = tracker.update([det])
        track_id = tracks[0]['track_id']
        
        # Initially no embedding_id
        assert tracks[0]['embedding_id'] is None
        
        # Set embedding_id
        tracker.set_embedding_id(track_id, "E123")
        
        # Update again to get updated track
        tracks = tracker.update([det])
        assert tracks[0]['embedding_id'] == "E123"
    
    def test_get_track_count(self):
        """Test getting active track count."""
        tracker = Tracker()
        
        assert tracker.get_track_count() == 0
        
        # Add tracks
        detections = [create_detection_at(100 + i*250, 150) for i in range(3)]
        tracker.update(detections)
        
        assert tracker.get_track_count() == 3
    
    def test_reset(self):
        """Test resetting tracker state."""
        tracker = Tracker()
        
        # Add some tracks
        detections = [create_detection_at(100 + i*250, 150) for i in range(2)]
        tracker.update(detections)
        
        assert tracker.get_track_count() == 2
        
        # Reset
        tracker.reset()
        
        assert tracker.get_track_count() == 0
        assert tracker.next_track_id == 1


class TestEdgeCases:
    """Test edge cases."""
    
    def test_detection_disappears_and_reappears_new_location(self):
        """Test person disappearing and reappearing at different location."""
        tracker = Tracker()
        
        # Person at location A
        det_a = create_detection_at(100, 150)
        tracks = tracker.update([det_a])
        original_track_id = tracks[0]['track_id']
        
        # Person disappears beyond max_age
        for _ in range(config.TRACK_MAX_AGE + 1):
            tracker.update([])
        
        # Person reappears at very different location (should get new ID)
        det_b = create_detection_at(500, 300)
        tracks = tracker.update([det_b])
        
        assert tracks[0]['track_id'] != original_track_id
    
    def test_many_detections_in_single_frame(self):
        """Test handling many detections in a single frame."""
        tracker = Tracker()
        
        # 10 people in frame
        detections = [create_detection_at(50 + i*60, 150, width=50, height=250) for i in range(10)]
        tracks = tracker.update(detections)
        
        assert len(tracks) == 10
        # All should have unique IDs
        track_ids = {t['track_id'] for t in tracks}
        assert len(track_ids) == 10
