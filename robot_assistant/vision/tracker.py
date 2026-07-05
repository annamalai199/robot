"""Multi-person tracking with ByteTrack algorithm.

Maintains stable track IDs across frames using ByteTrack's association algorithm.
Handles occlusion (temporary track loss) up to a configurable number of frames.
"""

import logging
import numpy as np
from typing import List, Dict, Optional
from collections import defaultdict
from robot_assistant.config import config
from robot_assistant.events import bus

logger = logging.getLogger(__name__)


class Tracker:
    """ByteTrack-based multi-person tracker with stable IDs.
    
    Tracks multiple people across frames, maintaining stable track_ids even
    through brief occlusions. Uses IoU (Intersection over Union) matching
    for association and age-based track management.
    """
    
    def __init__(self, max_age: int = None):
        """Initialize tracker.
        
        Args:
            max_age: Maximum frames to keep track alive without detection (occlusion tolerance).
                    If None, uses config.TRACK_MAX_AGE (default: 30 frames)
        """
        self.max_age = max_age if max_age is not None else config.TRACK_MAX_AGE
        
        # Track state
        self.tracks: Dict[int, Dict] = {}  # track_id -> {bbox, keypoints, age, embedding_id}
        self.next_track_id = 1
        
        # Track age tracking (frames since last detection)
        self.track_ages: Dict[int, int] = defaultdict(int)
        
        logger.info(f"Tracker initialized with max_age={self.max_age}")
    
    def update(self, detections: List[Dict]) -> List[Dict]:
        """Update tracker with new detections.
        
        Associates detections with existing tracks using IoU matching,
        creates new tracks for unmatched detections, and removes stale tracks.
        
        Args:
            detections: List of detection dicts from detector.detect_poses(),
                       each containing {bbox, keypoints, confidence}
        
        Returns:
            List of tracked objects, each containing:
            - track_id: int, stable tracking ID
            - bbox: [x1, y1, x2, y2] bounding box
            - keypoints: (17, 3) array of keypoints
            - embedding_id: str or None (set by face_id module later)
        
        Side Effects:
            Publishes TRACK_LOST events for tracks that exceed max_age
        
        Example:
            >>> tracker = Tracker()
            >>> detections = detector.detect_poses(frame)
            >>> tracks = tracker.update(detections)
            >>> for track in tracks:
            ...     print(f"Person {track['track_id']} at {track['bbox']}")
        """
        # Convert detections to numpy for easier processing
        det_boxes = np.array([d['bbox'] for d in detections]) if detections else np.array([])
        
        # Match detections to existing tracks
        matched_tracks, unmatched_detections = self._match_detections_to_tracks(det_boxes, detections)
        
        # Update matched tracks
        for track_id, detection in matched_tracks:
            self.tracks[track_id].update({
                'bbox': detection['bbox'],
                'keypoints': detection['keypoints'],
            })
            self.track_ages[track_id] = 0  # Reset age (track is active)
        
        # Create new tracks for unmatched detections
        for detection in unmatched_detections:
            track_id = self.next_track_id
            self.next_track_id += 1
            
            self.tracks[track_id] = {
                'bbox': detection['bbox'],
                'keypoints': detection['keypoints'],
                'embedding_id': None,  # Will be set by face_id module
            }
            self.track_ages[track_id] = 0
            
            logger.debug(f"Created new track {track_id}")
        
        # Age unmatched tracks
        matched_track_ids = set(track_id for track_id, _ in matched_tracks)
        for track_id in list(self.tracks.keys()):
            if track_id not in matched_track_ids:
                self.track_ages[track_id] += 1
        
        # Remove tracks that exceeded max_age (publish TRACK_LOST)
        tracks_to_remove = []
        for track_id, age in list(self.track_ages.items()):
            if age > self.max_age:
                tracks_to_remove.append(track_id)
        
        for track_id in tracks_to_remove:
            self._remove_track(track_id)
        
        # Return active tracks
        return [
            {
                'track_id': track_id,
                'bbox': track_data['bbox'],
                'keypoints': track_data['keypoints'],
                'embedding_id': track_data.get('embedding_id'),
            }
            for track_id, track_data in self.tracks.items()
        ]
    
    def _match_detections_to_tracks(self, det_boxes: np.ndarray, detections: List[Dict]) -> tuple:
        """Match detections to existing tracks using IoU.
        
        Args:
            det_boxes: (N, 4) array of detection bounding boxes [x1, y1, x2, y2]
            detections: List of detection dicts
        
        Returns:
            Tuple of (matched_pairs, unmatched_detections)
            - matched_pairs: List of (track_id, detection) tuples
            - unmatched_detections: List of detection dicts
        """
        if len(self.tracks) == 0 or len(detections) == 0:
            return [], detections
        
        # Get track boxes
        track_ids = list(self.tracks.keys())
        track_boxes = np.array([self.tracks[tid]['bbox'] for tid in track_ids])
        
        # Compute IoU matrix
        iou_matrix = self._compute_iou_matrix(track_boxes, det_boxes)
        
        # Simple greedy matching (better than nothing, ByteTrack uses Hungarian algorithm via LAP)
        # For proper ByteTrack, we'd use the lap package here
        matched_pairs = []
        unmatched_det_indices = list(range(len(detections)))
        matched_track_indices = set()
        
        # Greedy assignment: for each detection, find best matching track
        for det_idx in range(len(detections)):
            best_track_idx = -1
            best_iou = 0.3  # Minimum IoU threshold
            
            for track_idx in range(len(track_ids)):
                if track_idx in matched_track_indices:
                    continue
                
                if iou_matrix[track_idx, det_idx] > best_iou:
                    best_iou = iou_matrix[track_idx, det_idx]
                    best_track_idx = track_idx
            
            if best_track_idx >= 0:
                matched_pairs.append((track_ids[best_track_idx], detections[det_idx]))
                matched_track_indices.add(best_track_idx)
                unmatched_det_indices.remove(det_idx)
        
        unmatched_detections = [detections[i] for i in unmatched_det_indices]
        
        return matched_pairs, unmatched_detections
    
    def _compute_iou_matrix(self, boxes1: np.ndarray, boxes2: np.ndarray) -> np.ndarray:
        """Compute IoU (Intersection over Union) between two sets of boxes.
        
        Args:
            boxes1: (M, 4) array of boxes [x1, y1, x2, y2]
            boxes2: (N, 4) array of boxes [x1, y1, x2, y2]
        
        Returns:
            (M, N) array of IoU values
        """
        # Ensure 2D arrays
        if boxes1.ndim == 1:
            boxes1 = boxes1.reshape(1, -1)
        if boxes2.ndim == 1:
            boxes2 = boxes2.reshape(1, -1)
        
        M = boxes1.shape[0]
        N = boxes2.shape[0]
        
        # Expand dimensions for broadcasting
        boxes1_exp = boxes1[:, None, :]  # (M, 1, 4)
        boxes2_exp = boxes2[None, :, :]  # (1, N, 4)
        
        # Compute intersection coordinates
        inter_x1 = np.maximum(boxes1_exp[..., 0], boxes2_exp[..., 0])
        inter_y1 = np.maximum(boxes1_exp[..., 1], boxes2_exp[..., 1])
        inter_x2 = np.minimum(boxes1_exp[..., 2], boxes2_exp[..., 2])
        inter_y2 = np.minimum(boxes1_exp[..., 3], boxes2_exp[..., 3])
        
        # Compute intersection area
        inter_w = np.maximum(0, inter_x2 - inter_x1)
        inter_h = np.maximum(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        
        # Compute box areas
        boxes1_area = (boxes1_exp[..., 2] - boxes1_exp[..., 0]) * (boxes1_exp[..., 3] - boxes1_exp[..., 1])
        boxes2_area = (boxes2_exp[..., 2] - boxes2_exp[..., 0]) * (boxes2_exp[..., 3] - boxes2_exp[..., 1])
        
        # Compute union area
        union_area = boxes1_area + boxes2_area - inter_area
        
        # Compute IoU
        iou = inter_area / (union_area + 1e-6)  # Add epsilon to avoid division by zero
        
        # Reshape to (M, N) - remove the extra dimensions but keep 2D shape
        iou = iou.reshape(M, N)
        
        return iou
    
    def _remove_track(self, track_id: int):
        """Remove a track and publish TRACK_LOST event.
        
        Args:
            track_id: Track ID to remove
        """
        if track_id not in self.tracks:
            return
        
        track_data = self.tracks[track_id]
        embedding_id = track_data.get('embedding_id', 'unknown')
        
        # Publish TRACK_LOST event
        from robot_assistant.events.schemas import TrackLostEvent
        event: TrackLostEvent = {
            'event': 'TRACK_LOST',
            'track_id': str(track_id),
            'embedding_id': embedding_id if embedding_id else 'unknown',
        }
        bus.publish(event)
        
        logger.info(f"Track {track_id} lost (age exceeded {self.max_age}), published TRACK_LOST event")
        
        # Remove from tracking
        del self.tracks[track_id]
        del self.track_ages[track_id]
    
    def set_embedding_id(self, track_id: int, embedding_id: str):
        """Set the embedding_id for a track (called by face_id module).
        
        Args:
            track_id: Track ID
            embedding_id: Face embedding ID
        """
        if track_id in self.tracks:
            self.tracks[track_id]['embedding_id'] = embedding_id
            logger.debug(f"Set embedding_id={embedding_id} for track {track_id}")
    
    def get_track_count(self) -> int:
        """Get the number of active tracks.
        
        Returns:
            Number of active tracks
        """
        return len(self.tracks)
    
    def reset(self):
        """Reset tracker state (clear all tracks)."""
        self.tracks.clear()
        self.track_ages.clear()
        self.next_track_id = 1
        logger.info("Tracker reset")
