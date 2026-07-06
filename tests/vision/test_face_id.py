"""Tests for face identification using InsightFace and FAISS.

Tests use mocked InsightFace output (synthetic 512-dim embeddings) to avoid
requiring real face photos or model inference in automated tests.
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch, MagicMock
from robot_assistant.vision import face_id
from robot_assistant.events import bus


@pytest.fixture(autouse=True)
def reset_face_id():
    """Reset face_id state before each test."""
    face_id.reset()
    face_id.clear_index()
    bus._subscribers.clear()
    yield
    face_id.reset()
    face_id.clear_index()
    bus._subscribers.clear()


def create_mock_face(embedding: np.ndarray):
    """Create a mock InsightFace face result.
    
    Args:
        embedding: 512-dim embedding vector
    
    Returns:
        Mock face object with embedding and bbox attributes
    """
    mock_face = Mock()
    mock_face.embedding = embedding
    # Add bbox attribute (InsightFace face.bbox is [x1, y1, x2, y2])
    # Place face bbox within typical YOLO bbox region to ensure overlap
    mock_face.bbox = np.array([110, 110, 190, 290], dtype=np.float32)
    return mock_face


def create_synthetic_embedding(seed: int) -> np.ndarray:
    """Create a synthetic 512-dim embedding for testing.
    
    Args:
        seed: Random seed for reproducibility
    
    Returns:
        512-dim float32 array
    """
    np.random.seed(seed)
    embedding = np.random.randn(512).astype('float32')
    # Normalize to unit length (InsightFace embeddings are normalized)
    embedding = embedding / np.linalg.norm(embedding)
    return embedding


class TestTrackIdCaching:
    """Test that track_ids are processed only once."""
    
    def test_track_id_uses_string_type(self):
        """Track ID must be string to match tracker/event schemas."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        embedding = create_synthetic_embedding(1)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_app.get.return_value = [create_mock_face(embedding)]
            mock_get_app.return_value = mock_app
            
            # Use realistic string track_id like "T1", not integer
            result = face_id.identify_face(frame, bbox, track_id="T1")
            
            assert result is not None
            # Verify track_id stored as string
            assert "T1" in face_id._processed_track_ids
            assert 1 not in face_id._processed_track_ids  # NOT stored as int
    
    def test_same_track_id_skipped_on_second_call(self):
        """Second call with same track_id returns None (already processed)."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        embedding = create_synthetic_embedding(1)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_app.get.return_value = [create_mock_face(embedding)]
            mock_get_app.return_value = mock_app
            
            # First call processes
            result1 = face_id.identify_face(frame, bbox, track_id="42")
            assert result1 is not None
            
            # Second call skipped
            result2 = face_id.identify_face(frame, bbox, track_id="42")
            assert result2 is None
            
            # Model only called once
            assert mock_app.get.call_count == 1
    
    def test_track_id_persists_after_track_lost(self):
        """Track ID remains in processed set after TRACK_LOST (never reused).
        
        Decision: Entries persist because ByteTrack never reuses track_ids.
        If same person returns, they get a NEW track_id.
        """
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        embedding = create_synthetic_embedding(1)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_app.get.return_value = [create_mock_face(embedding)]
            mock_get_app.return_value = mock_app
            
            # Process track
            result = face_id.identify_face(frame, bbox, track_id="T1")
            assert result is not None
            assert "T1" in face_id._processed_track_ids
            
            # Simulate TRACK_LOST (in real system, tracker would fire this)
            # Face ID doesn't listen to TRACK_LOST - just checking persistence
            
            # Track ID still in set (intentional - ByteTrack won't reuse it)
            assert "T1" in face_id._processed_track_ids
            
            # Subsequent call still skipped
            result2 = face_id.identify_face(frame, bbox, track_id="T1")
            assert result2 is None


class TestNewFaceRegistration:
    """Test registration of new (unknown) faces."""
    
    def test_first_face_registered_as_new(self):
        """First face in empty index registered as new."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        embedding = create_synthetic_embedding(1)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_app.get.return_value = [create_mock_face(embedding)]
            mock_get_app.return_value = mock_app
            
            result = face_id.identify_face(frame, bbox, track_id="T1")
            
            assert result is not None
            assert result['status'] == 'new'
            assert result['embedding_id'].startswith('U')  # Unknown face
            assert result['name'] is None
            assert result['confidence'] is None
    
    def test_different_face_registered_as_separate_new(self):
        """Two different faces get separate embedding_ids."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        embedding1 = create_synthetic_embedding(1)
        embedding2 = create_synthetic_embedding(2)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_get_app.return_value = mock_app
            
            # First face
            mock_app.get.return_value = [create_mock_face(embedding1)]
            result1 = face_id.identify_face(frame, bbox, track_id="T1")
            
            # Second face (different embedding)
            mock_app.get.return_value = [create_mock_face(embedding2)]
            result2 = face_id.identify_face(frame, bbox, track_id="T2")
            
            assert result1['embedding_id'] != result2['embedding_id']
            assert result1['status'] == 'new'
            assert result2['status'] == 'new'


class TestKnownFaceMatching:
    """Test matching against known faces in FAISS index."""
    
    def test_same_face_matched_on_second_appearance(self):
        """Same person reappearing (new track_id) matched to existing embedding."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        # Same embedding for both appearances (same person)
        embedding = create_synthetic_embedding(1)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_get_app.return_value = mock_app
            
            # First appearance: registered as new
            mock_app.get.return_value = [create_mock_face(embedding.copy())]
            result1 = face_id.identify_face(frame, bbox, track_id="T1")
            
            assert result1['status'] == 'new'
            first_embedding_id = result1['embedding_id']
            
            # Second appearance: should match (new track_id, same face)
            mock_app.get.return_value = [create_mock_face(embedding.copy())]
            result2 = face_id.identify_face(frame, bbox, track_id="T2")
            
            assert result2 is not None
            assert result2['status'] in ['known', 'registered_unknown']
            assert result2['embedding_id'] == first_embedding_id  # Same ID!
            assert result2['confidence'] is not None
            # With threshold=1.08:
            # - Perfect mock match (distance≈0) gives confidence≈1.0
            # - Real same-person (distance 0.82-0.97) gives confidence 0.10-0.24
            # This is a mock test with copied embedding, so distance should be very small
            # Assert realistic range: must be positive (matched) and reasonable
            assert 0.05 < result2['confidence'] <= 1.0, \
                f"Confidence {result2['confidence']} outside realistic range [0.05, 1.0]"
    
    def test_no_match_beyond_threshold(self):
        """Faces with distance > threshold registered as separate new faces."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        # Very different embeddings (large L2 distance)
        embedding1 = create_synthetic_embedding(1)
        embedding2 = create_synthetic_embedding(999)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_get_app.return_value = mock_app
            
            # First face
            mock_app.get.return_value = [create_mock_face(embedding1)]
            result1 = face_id.identify_face(frame, bbox, track_id="T1")
            
            # Different face (should not match)
            mock_app.get.return_value = [create_mock_face(embedding2)]
            result2 = face_id.identify_face(frame, bbox, track_id="T2")
            
            assert result1['embedding_id'] != result2['embedding_id']
            assert result1['status'] == 'new'
            assert result2['status'] == 'new'  # No match, new face


class TestEventPublishing:
    """Test IDENTITY_RESOLVED event publishing."""
    
    def test_identity_resolved_event_published(self):
        """IDENTITY_RESOLVED event published when face identified."""
        events = []
        bus.subscribe('IDENTITY_RESOLVED', lambda e: events.append(e))
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        embedding = create_synthetic_embedding(1)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_app.get.return_value = [create_mock_face(embedding)]
            mock_get_app.return_value = mock_app
            
            face_id.identify_face(frame, bbox, track_id="T1")
            
            assert len(events) == 1
            assert events[0]['event'] == 'IDENTITY_RESOLVED'
            assert events[0]['track_id'] == 'T1'
            assert events[0]['embedding_id'].startswith('U')
            assert events[0]['status'] == 'new'
    
    def test_no_event_when_already_processed(self):
        """No event published if track_id already processed."""
        events = []
        bus.subscribe('IDENTITY_RESOLVED', lambda e: events.append(e))
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        embedding = create_synthetic_embedding(1)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_app.get.return_value = [create_mock_face(embedding)]
            mock_get_app.return_value = mock_app
            
            # First call
            face_id.identify_face(frame, bbox, track_id="T1")
            assert len(events) == 1
            
            # Second call (skipped)
            face_id.identify_face(frame, bbox, track_id="T1")
            assert len(events) == 1  # Still just 1 event
    
    def test_event_schema_matches(self):
        """Published event matches IdentityResolvedEvent schema."""
        from robot_assistant.events.schemas import validate_event
        
        events = []
        bus.subscribe('IDENTITY_RESOLVED', lambda e: events.append(e))
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        embedding = create_synthetic_embedding(1)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_app.get.return_value = [create_mock_face(embedding)]
            mock_get_app.return_value = mock_app
            
            face_id.identify_face(frame, bbox, track_id="T1")
            
            # Validate against schema
            assert len(events) == 1
            is_valid, error = validate_event(events[0])
            assert is_valid, f"Event validation failed: {error}"
            
            # Verify exact field structure from schemas.py
            assert events[0]['event'] == 'IDENTITY_RESOLVED'
            assert isinstance(events[0]['track_id'], str)
            assert isinstance(events[0]['embedding_id'], str)
            assert events[0]['status'] in ['known', 'new', 'registered_unknown']
            # name and confidence can be None for new faces


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_no_face_detected_in_bbox(self):
        """Returns None if InsightFace finds no face in crop."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_app.get.return_value = []  # No faces detected
            mock_get_app.return_value = mock_app
            
            result = face_id.identify_face(frame, bbox, track_id="T1")
            
            # Should return None but still mark as processed
            assert result is None
            assert "T1" in face_id._processed_track_ids
    
    def test_empty_bbox_returns_none(self):
        """Returns None if bbox produces empty crop."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 100, 100]  # Zero-size bbox
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_app.get.return_value = []  # No faces detected
            mock_get_app.return_value = mock_app
            
            result = face_id.identify_face(frame, bbox, track_id="T1")
            
            assert result is None
            # Track ID still marked as processed (to avoid retry loops)
            assert "T1" in face_id._processed_track_ids


class TestLatency:
    """Test latency of face identification."""
    
    def test_latency_under_200ms_with_mocked_model(self):
        """Face identification completes in <200ms (mocked, realistic timing)."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        embedding = create_synthetic_embedding(1)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            
            # Simulate realistic InsightFace latency (~50-100ms)
            def slow_get(*args, **kwargs):
                time.sleep(0.05)  # 50ms simulated model inference
                return [create_mock_face(embedding)]
            
            mock_app.get = slow_get
            mock_get_app.return_value = mock_app
            
            # Measure time for embedding + FAISS search
            start = time.perf_counter()
            result = face_id.identify_face(frame, bbox, track_id="T1")
            end = time.perf_counter()
            
            latency_ms = (end - start) * 1000
            
            assert result is not None
            # Should complete in <200ms even with simulated model delay
            assert latency_ms < 200, f"Latency {latency_ms:.1f}ms exceeds 200ms target"


class TestReset:
    """Test reset functionality."""
    
    def test_reset_clears_processed_track_ids(self):
        """Reset clears processed track_ids but not FAISS index."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]
        
        embedding = create_synthetic_embedding(1)
        
        with patch('robot_assistant.vision.face_id._get_face_app') as mock_get_app:
            mock_app = Mock()
            mock_app.get.return_value = [create_mock_face(embedding)]
            mock_get_app.return_value = mock_app
            
            # Process a track
            face_id.identify_face(frame, bbox, track_id="T1")
            assert "T1" in face_id._processed_track_ids
            
            # Reset
            face_id.reset()
            
            # Track IDs cleared
            assert "T1" not in face_id._processed_track_ids
            
            # But FAISS index still has the face
            index = face_id._get_face_index()
            assert index.ntotal == 1  # Face still in index
