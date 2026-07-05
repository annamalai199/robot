"""Tests for YOLO pose detector.

Tests use mocked YOLO model outputs to ensure fast execution without requiring
actual model downloads or inference. Real inference timing is covered by
bench_latency.py (Phase 3.8).
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from robot_assistant.vision import detector
from robot_assistant.config import config


@pytest.fixture
def mock_yolo_model():
    """Create a mock YOLO model with realistic output structure."""
    mock_model = MagicMock()
    return mock_model


@pytest.fixture
def synthetic_frame():
    """Create a synthetic frame for testing."""
    # 640x480 BGR frame
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def mock_yolo_result_single_person():
    """Create mock YOLO result with one person detection.
    
    Output format is grounded in actual YOLO11n-pose output structure:
    - boxes.data: (N, 6) tensor [x1, y1, x2, y2, conf, cls]
    - keypoints.data: (N, 17, 3) tensor [x, y, conf] for each keypoint
    """
    mock_result = Mock()
    
    # Mock boxes (1 person detection)
    # Bounding box: [100, 150, 300, 450] (reasonable person box in 640x480 frame)
    # Confidence: 0.85
    # Class: 0 (person in COCO)
    mock_boxes = Mock()
    boxes_data = np.array([[100.0, 150.0, 300.0, 450.0, 0.85, 0.0]])  # (1, 6)
    mock_boxes.data.cpu.return_value.numpy.return_value = boxes_data
    mock_result.boxes = mock_boxes
    
    # Mock keypoints (17 COCO keypoints)
    # Representative values based on typical person pose
    # Format: [x, y, confidence] for each of 17 keypoints
    mock_keypoints = Mock()
    keypoints_data = np.array([
        [
            [200.0, 170.0, 0.95],  # 0: nose
            [190.0, 165.0, 0.90],  # 1: left_eye
            [210.0, 165.0, 0.90],  # 2: right_eye
            [185.0, 170.0, 0.85],  # 3: left_ear
            [215.0, 170.0, 0.85],  # 4: right_ear
            [175.0, 200.0, 0.92],  # 5: left_shoulder
            [225.0, 200.0, 0.92],  # 6: right_shoulder
            [160.0, 250.0, 0.88],  # 7: left_elbow
            [240.0, 250.0, 0.88],  # 8: right_elbow
            [150.0, 300.0, 0.85],  # 9: left_wrist
            [250.0, 300.0, 0.85],  # 10: right_wrist
            [180.0, 320.0, 0.90],  # 11: left_hip
            [220.0, 320.0, 0.90],  # 12: right_hip
            [185.0, 380.0, 0.87],  # 13: left_knee
            [215.0, 380.0, 0.87],  # 14: right_knee
            [190.0, 440.0, 0.83],  # 15: left_ankle
            [210.0, 440.0, 0.83],  # 16: right_ankle
        ]
    ])  # (1, 17, 3)
    mock_keypoints.data.cpu.return_value.numpy.return_value = keypoints_data
    mock_result.keypoints = mock_keypoints
    
    return mock_result


@pytest.fixture
def mock_yolo_result_multiple_people():
    """Create mock YOLO result with multiple person detections."""
    mock_result = Mock()
    
    # Mock boxes (2 person detections)
    mock_boxes = Mock()
    boxes_data = np.array([
        [100.0, 150.0, 300.0, 450.0, 0.85, 0.0],  # Person 1
        [350.0, 100.0, 550.0, 420.0, 0.78, 0.0],  # Person 2
    ])  # (2, 6)
    mock_boxes.data.cpu.return_value.numpy.return_value = boxes_data
    mock_result.boxes = mock_boxes
    
    # Mock keypoints (2 people × 17 keypoints)
    mock_keypoints = Mock()
    # Simplified: just different x-offsets for each person
    keypoints_person1 = np.array([[200.0 + i*10, 170.0 + i*20, 0.9] for i in range(17)])
    keypoints_person2 = np.array([[450.0 + i*10, 150.0 + i*20, 0.85] for i in range(17)])
    keypoints_data = np.stack([keypoints_person1, keypoints_person2])  # (2, 17, 3)
    mock_keypoints.data.cpu.return_value.numpy.return_value = keypoints_data
    mock_result.keypoints = mock_keypoints
    
    return mock_result


@pytest.fixture
def mock_yolo_result_mixed_classes():
    """Create mock YOLO result with person and non-person detections.
    
    Used to test person-only filtering (class 0).
    """
    mock_result = Mock()
    
    # Mock boxes (1 person + 1 non-person)
    mock_boxes = Mock()
    boxes_data = np.array([
        [100.0, 150.0, 300.0, 450.0, 0.85, 0.0],  # Person (class 0)
        [400.0, 200.0, 500.0, 300.0, 0.92, 16.0],  # Cat (class 16 in COCO)
    ])  # (2, 6)
    mock_boxes.data.cpu.return_value.numpy.return_value = boxes_data
    mock_result.boxes = mock_boxes
    
    # Mock keypoints (2 detections, but only person should be returned)
    mock_keypoints = Mock()
    keypoints_person = np.array([[200.0 + i*10, 170.0 + i*20, 0.9] for i in range(17)])
    keypoints_cat = np.zeros((17, 3))  # Cat keypoints (shouldn't be used)
    keypoints_data = np.stack([keypoints_person, keypoints_cat])  # (2, 17, 3)
    mock_keypoints.data.cpu.return_value.numpy.return_value = keypoints_data
    mock_result.keypoints = mock_keypoints
    
    return mock_result


@pytest.fixture
def mock_yolo_result_empty():
    """Create mock YOLO result with no detections."""
    mock_result = Mock()
    mock_result.boxes = None
    mock_result.keypoints = None
    return mock_result


class TestDetectPoses:
    """Test pose detection function."""
    
    def test_detect_poses_single_person(self, mock_yolo_model, mock_yolo_result_single_person, synthetic_frame):
        """Test detection of single person."""
        # Mock model to return single person result
        mock_yolo_model.return_value = [mock_yolo_result_single_person]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame)
        
        # Should return 1 detection
        assert len(detections) == 1
        
        # Check detection structure
        det = detections[0]
        assert 'bbox' in det
        assert 'keypoints' in det
        assert 'confidence' in det
        
        # Check bbox format [x1, y1, x2, y2]
        bbox = det['bbox']
        assert len(bbox) == 4
        assert bbox == [100.0, 150.0, 300.0, 450.0]
        
        # Check keypoints shape (17, 3)
        keypoints = det['keypoints']
        assert keypoints.shape == (17, 3)
        
        # Check confidence
        assert det['confidence'] == 0.85
    
    def test_detect_poses_multiple_people(self, mock_yolo_model, mock_yolo_result_multiple_people, synthetic_frame):
        """Test detection of multiple people."""
        mock_yolo_model.return_value = [mock_yolo_result_multiple_people]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame)
        
        # Should return 2 detections
        assert len(detections) == 2
        
        # Check both detections have correct structure
        for det in detections:
            assert 'bbox' in det
            assert 'keypoints' in det
            assert 'confidence' in det
            assert det['keypoints'].shape == (17, 3)
    
    def test_detect_poses_filters_non_person_class(self, mock_yolo_model, mock_yolo_result_mixed_classes, synthetic_frame):
        """Test that only person class (0) is returned, filtering other classes.
        
        Critical acceptance criteria: Filter results to cls == 0 (person only)
        """
        mock_yolo_model.return_value = [mock_yolo_result_mixed_classes]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame)
        
        # Should return only 1 detection (person), not 2 (person + cat)
        assert len(detections) == 1
        
        # Verify it's the person detection
        det = detections[0]
        assert det['bbox'] == [100.0, 150.0, 300.0, 450.0]
        assert det['confidence'] == 0.85
    
    def test_detect_poses_empty_frame(self, mock_yolo_model, mock_yolo_result_empty, synthetic_frame):
        """Test handling of frame with no detections."""
        mock_yolo_model.return_value = [mock_yolo_result_empty]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame)
        
        # Should return empty list
        assert detections == []
    
    def test_detect_poses_custom_confidence_threshold(self, mock_yolo_model, mock_yolo_result_single_person, synthetic_frame):
        """Test custom confidence threshold parameter."""
        mock_yolo_model.return_value = [mock_yolo_result_single_person]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame, conf_threshold=0.7)
        
        # Verify model was called with custom threshold
        mock_yolo_model.assert_called_once()
        call_kwargs = mock_yolo_model.call_args[1]
        assert call_kwargs['conf'] == 0.7


class TestKeypointFormat:
    """Test COCO keypoint format compliance."""
    
    def test_keypoints_are_17_point_coco_format(self, mock_yolo_model, mock_yolo_result_single_person, synthetic_frame):
        """Test that keypoints follow COCO 17-point format.
        
        Acceptance criteria: Keypoints in 17-point COCO format
        """
        mock_yolo_model.return_value = [mock_yolo_result_single_person]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame)
        
        keypoints = detections[0]['keypoints']
        
        # Must be exactly 17 keypoints
        assert keypoints.shape[0] == 17
        
        # Each keypoint must have 3 values: [x, y, confidence]
        assert keypoints.shape[1] == 3
    
    def test_keypoint_names_match_coco_order(self):
        """Test that keypoint names are in correct COCO order."""
        names = detector.get_keypoint_names()
        
        # Must be exactly 17 names
        assert len(names) == 17
        
        # Check specific keypoint positions (COCO standard)
        assert names[0] == "nose"
        assert names[5] == "left_shoulder"
        assert names[6] == "right_shoulder"
        assert names[11] == "left_hip"
        assert names[12] == "right_hip"
        assert names[15] == "left_ankle"
        assert names[16] == "right_ankle"
    
    def test_keypoint_coordinates_in_valid_range(self, mock_yolo_model, mock_yolo_result_single_person, synthetic_frame):
        """Test that keypoint coordinates are within frame bounds.
        
        Note: This test uses synthetic data, but validates format correctness.
        """
        mock_yolo_model.return_value = [mock_yolo_result_single_person]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame)
        
        keypoints = detections[0]['keypoints']
        height, width = synthetic_frame.shape[:2]
        
        # x coordinates should be within [0, width]
        x_coords = keypoints[:, 0]
        assert np.all(x_coords >= 0)
        assert np.all(x_coords <= width)
        
        # y coordinates should be within [0, height]
        y_coords = keypoints[:, 1]
        assert np.all(y_coords >= 0)
        assert np.all(y_coords <= height)
        
        # confidence should be in [0, 1]
        confs = keypoints[:, 2]
        assert np.all(confs >= 0)
        assert np.all(confs <= 1)


class TestModelManagement:
    """Test model loading and management."""
    
    def test_get_model_loads_once(self, mock_yolo_model):
        """Test that model is loaded only once (singleton pattern)."""
        with patch('robot_assistant.vision.detector.YOLO', return_value=mock_yolo_model) as mock_constructor:
            # Reset global model
            detector._model = None
            
            # Call multiple times
            model1 = detector._get_model()
            model2 = detector._get_model()
            
            # Constructor should be called only once
            assert mock_constructor.call_count == 1
            assert model1 is model2
    
    def test_check_model_available_success(self, mock_yolo_model):
        """Test check_model_available returns True when model loads."""
        with patch('robot_assistant.vision.detector.YOLO', return_value=mock_yolo_model):
            detector._model = None
            result = detector.check_model_available()
        
        assert result is True
    
    def test_check_model_available_failure(self):
        """Test check_model_available returns False on error."""
        with patch('robot_assistant.vision.detector.YOLO', side_effect=Exception("Model not found")):
            detector._model = None
            result = detector.check_model_available()
        
        assert result is False


class TestBboxFormat:
    """Test bounding box format."""
    
    def test_bbox_is_xyxy_format(self, mock_yolo_model, mock_yolo_result_single_person, synthetic_frame):
        """Test that bounding boxes are in xyxy format [x1, y1, x2, y2]."""
        mock_yolo_model.return_value = [mock_yolo_result_single_person]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame)
        
        bbox = detections[0]['bbox']
        x1, y1, x2, y2 = bbox
        
        # x2 should be greater than x1
        assert x2 > x1, "Bounding box should be in xyxy format"
        
        # y2 should be greater than y1
        assert y2 > y1, "Bounding box should be in xyxy format"
    
    def test_bbox_within_frame_bounds(self, mock_yolo_model, mock_yolo_result_single_person, synthetic_frame):
        """Test that bounding boxes are within frame dimensions."""
        mock_yolo_model.return_value = [mock_yolo_result_single_person]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame)
        
        bbox = detections[0]['bbox']
        height, width = synthetic_frame.shape[:2]
        
        x1, y1, x2, y2 = bbox
        
        # All coordinates should be within frame bounds
        assert 0 <= x1 <= width
        assert 0 <= x2 <= width
        assert 0 <= y1 <= height
        assert 0 <= y2 <= height


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_detect_poses_returns_list(self, mock_yolo_model, mock_yolo_result_empty, synthetic_frame):
        """Test that detect_poses always returns a list."""
        mock_yolo_model.return_value = [mock_yolo_result_empty]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame)
        
        assert isinstance(detections, list)
    
    def test_detect_poses_with_very_low_confidence(self, mock_yolo_model, mock_yolo_result_single_person, synthetic_frame):
        """Test detection with very low confidence threshold."""
        mock_yolo_model.return_value = [mock_yolo_result_single_person]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame, conf_threshold=0.1)
        
        # Should still work (model handles filtering)
        assert isinstance(detections, list)
    
    def test_detect_poses_with_very_high_confidence(self, mock_yolo_model, mock_yolo_result_empty, synthetic_frame):
        """Test detection with very high confidence threshold."""
        mock_yolo_model.return_value = [mock_yolo_result_empty]
        
        with patch('robot_assistant.vision.detector._get_model', return_value=mock_yolo_model):
            detections = detector.detect_poses(synthetic_frame, conf_threshold=0.99)
        
        # Should return empty (no detections meet threshold)
        assert detections == []
