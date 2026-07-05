"""Tests for motion gate frame difference detection.

Tests use synthetic frames (generated numpy arrays) to ensure deterministic,
reproducible results without requiring actual camera hardware.
"""

import pytest
import numpy as np
import time
from robot_assistant.vision import motion_gate
from robot_assistant.config import config


@pytest.fixture
def static_frame():
    """Create a static synthetic frame (640x480, solid color)."""
    # Create a solid gray frame
    frame = np.full((480, 640, 3), 128, dtype=np.uint8)
    return frame


@pytest.fixture
def shifted_frame():
    """Create a shifted version of static frame (simulate camera movement)."""
    # Create a frame with significant pixel value changes to exceed threshold
    frame = np.full((480, 640, 3), 128, dtype=np.uint8)
    # Add a large bright region (simulates significant motion/object appearance)
    # Need enough pixels changed to push mean diff > 5.0
    # Changing 1/3 of frame by ~40 pixels gives mean diff ~13
    frame[100:380, 150:490, :] = 168  # +40 pixel difference over large area
    return frame


@pytest.fixture
def noisy_frame():
    """Create a frame with small random noise."""
    # Base frame
    frame = np.full((480, 640, 3), 128, dtype=np.uint8)
    # Add small random noise (±2 pixel values)
    noise = np.random.randint(-2, 3, frame.shape, dtype=np.int16)
    frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return frame


class TestHasMotion:
    """Test motion detection function."""
    
    def test_has_motion_identical_frames(self, static_frame):
        """Test that identical frames show no motion."""
        result = motion_gate.has_motion(static_frame, static_frame)
        
        assert result is False, "Identical frames should show no motion"
    
    def test_has_motion_shifted_frames(self, static_frame, shifted_frame):
        """Test that frames with significant change show motion."""
        result = motion_gate.has_motion(shifted_frame, static_frame)
        
        assert result is True, "Shifted frames should show motion"
    
    def test_has_motion_small_noise(self, static_frame, noisy_frame):
        """Test that small noise below threshold doesn't trigger motion."""
        # Small noise (±2 pixels) should have mean diff < 5.0
        result = motion_gate.has_motion(noisy_frame, static_frame)
        
        # With default threshold (5.0), small noise shouldn't trigger
        # (mean diff of ±2 pixels is ~1.3)
        assert result is False, "Small noise should not trigger motion"
    
    def test_has_motion_custom_threshold(self, static_frame, noisy_frame):
        """Test custom threshold parameter."""
        # With very low threshold, even small noise triggers motion
        result = motion_gate.has_motion(noisy_frame, static_frame, threshold=0.5)
        
        assert result is True, "Small noise should trigger with low threshold"
    
    def test_has_motion_uses_config_threshold(self, static_frame, shifted_frame):
        """Test that default threshold comes from config."""
        # Check that config value is used
        assert config.MOTION_GATE_THRESHOLD == 5.0
        
        # Test with None threshold (should use config value)
        result = motion_gate.has_motion(shifted_frame, static_frame, threshold=None)
        
        assert result is True


class TestGetMotionScore:
    """Test motion score calculation function."""
    
    def test_get_motion_score_identical_frames(self, static_frame):
        """Test that identical frames have zero motion score."""
        score = motion_gate.get_motion_score(static_frame, static_frame)
        
        assert score == 0.0, "Identical frames should have zero motion score"
    
    def test_get_motion_score_shifted_frames(self, static_frame, shifted_frame):
        """Test that shifted frames have non-zero motion score."""
        score = motion_gate.get_motion_score(shifted_frame, static_frame)
        
        assert score > 0.0, "Shifted frames should have positive motion score"
        assert score > config.MOTION_GATE_THRESHOLD, "Significant motion should exceed threshold"
    
    def test_get_motion_score_range(self, static_frame, shifted_frame):
        """Test that motion score is in valid range [0, 255]."""
        score = motion_gate.get_motion_score(shifted_frame, static_frame)
        
        assert 0.0 <= score <= 255.0, f"Motion score {score} out of valid range"
    
    def test_get_motion_score_returns_float(self, static_frame):
        """Test that motion score returns a float."""
        score = motion_gate.get_motion_score(static_frame, static_frame)
        
        assert isinstance(score, float), f"Expected float, got {type(score)}"


class TestLatency:
    """Test latency requirements."""
    
    def test_has_motion_latency_under_5ms(self, static_frame, shifted_frame):
        """Test that has_motion completes in < 5ms.
        
        Task 3.2 acceptance criteria: latency < 5ms
        """
        # Warmup (first call may be slower due to numpy/cv2 initialization)
        motion_gate.has_motion(shifted_frame, static_frame)
        
        # Measure actual latency
        iterations = 100
        start = time.perf_counter()
        
        for _ in range(iterations):
            motion_gate.has_motion(shifted_frame, static_frame)
        
        elapsed = time.perf_counter() - start
        avg_latency = (elapsed / iterations) * 1000  # Convert to milliseconds
        
        assert avg_latency < 5.0, f"Average latency {avg_latency:.2f}ms exceeds 5ms requirement"
        
        print(f"\n  Average latency: {avg_latency:.2f}ms (target: < 5ms)")


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_has_motion_different_resolutions(self):
        """Test behavior with different frame resolutions."""
        frame1 = np.full((480, 640, 3), 128, dtype=np.uint8)
        frame2 = np.full((720, 1280, 3), 128, dtype=np.uint8)
        
        # Should raise an error (OpenCV requires same dimensions)
        with pytest.raises(Exception):
            motion_gate.has_motion(frame2, frame1)
    
    def test_has_motion_grayscale_input(self):
        """Test that function works with BGR input (not grayscale)."""
        # Create BGR frames with significant motion
        bgr1 = np.full((480, 640, 3), 128, dtype=np.uint8)
        bgr2 = np.full((480, 640, 3), 128, dtype=np.uint8)
        # Add significant motion (change large area by enough to exceed threshold)
        bgr2[150:330, 220:420, :] = 180  # +52 pixels over ~1/4 of frame
        
        # Should work without error
        result = motion_gate.has_motion(bgr2, bgr1)
        
        assert isinstance(result, bool)
        assert result is True
    
    def test_has_motion_all_black_frames(self):
        """Test with all-black frames (edge case: no pixel values)."""
        black1 = np.zeros((480, 640, 3), dtype=np.uint8)
        black2 = np.zeros((480, 640, 3), dtype=np.uint8)
        
        result = motion_gate.has_motion(black2, black1)
        
        assert result is False, "All-black identical frames should show no motion"
    
    def test_has_motion_all_white_frames(self):
        """Test with all-white frames (edge case: max pixel values)."""
        white1 = np.full((480, 640, 3), 255, dtype=np.uint8)
        white2 = np.full((480, 640, 3), 255, dtype=np.uint8)
        
        result = motion_gate.has_motion(white2, white1)
        
        assert result is False, "All-white identical frames should show no motion"
    
    def test_has_motion_extreme_change(self):
        """Test with extreme pixel change (black to white)."""
        black = np.zeros((480, 640, 3), dtype=np.uint8)
        white = np.full((480, 640, 3), 255, dtype=np.uint8)
        
        result = motion_gate.has_motion(white, black)
        
        assert result is True, "Extreme change (black to white) should show motion"
        
        # Check motion score is very high
        score = motion_gate.get_motion_score(white, black)
        assert score == 255.0, "Maximum possible motion score is 255"


class TestRealWorldScenarios:
    """Test scenarios similar to real-world usage."""
    
    def test_person_entering_frame(self):
        """Simulate person entering an empty frame."""
        # Empty room (uniform background)
        empty_room = np.full((480, 640, 3), 120, dtype=np.uint8)
        
        # Person appears (darker pixels in person-shaped region)
        with_person = empty_room.copy()
        # Simulate person (larger region to exceed threshold)
        # Person needs to cover ~1/3 of frame with 20+ pixel difference to get mean diff > 5
        with_person[100:420, 200:440, :] = 80  # Person's body (larger area, -40 pixels)
        with_person[60:100, 260:380, :] = 85  # Person's head
        
        result = motion_gate.has_motion(with_person, empty_room)
        
        assert result is True, "Person entering frame should trigger motion"
    
    def test_camera_shake_small(self):
        """Simulate small camera shake (shouldn't trigger with default threshold)."""
        frame1 = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        
        # Slight shift (1 pixel in each direction, simulates tiny vibration)
        frame2 = np.roll(frame1, shift=1, axis=0)  # Shift vertically by 1 pixel
        
        # Small shifts typically have mean diff around 2-3 pixels
        result = motion_gate.has_motion(frame2, frame1)
        
        # May or may not trigger depending on image content
        # Just verify it runs without error
        assert isinstance(result, bool)
    
    def test_lighting_change(self):
        """Simulate gradual lighting change (e.g., cloud passing)."""
        frame1 = np.full((480, 640, 3), 100, dtype=np.uint8)
        # Slight brightness increase (simulates lighting change)
        frame2 = np.full((480, 640, 3), 103, dtype=np.uint8)
        
        result = motion_gate.has_motion(frame2, frame1)
        
        # Mean diff of 3 pixels should NOT trigger (threshold is 5.0)
        assert result is False, "Small lighting change should not trigger motion"
    
    def test_rapid_motion(self):
        """Simulate rapid motion (large object moving across frame)."""
        # Object on left side
        frame1 = np.full((480, 640, 3), 120, dtype=np.uint8)
        frame1[150:350, 50:150, :] = 200  # Bright object on left
        
        # Object moved to right side
        frame2 = np.full((480, 640, 3), 120, dtype=np.uint8)
        frame2[150:350, 490:590, :] = 200  # Bright object on right
        
        result = motion_gate.has_motion(frame2, frame1)
        
        assert result is True, "Rapid motion should trigger detection"
