"""Face identification using InsightFace and FAISS matching.

Runs face recognition on new track_ids only (one-time cost per identity).
Uses InsightFace buffalo_s for 512-dim embeddings and FAISS IndexFlatL2
for known-face matching with distance threshold 1.08.
"""

import logging
import numpy as np
import json
from typing import Dict, Set, Optional
from pathlib import Path
import insightface
from insightface.app import FaceAnalysis
import faiss

from robot_assistant.config import config
from robot_assistant.events.bus import publish
from robot_assistant.events.schemas import IdentityResolvedEvent

logger = logging.getLogger(__name__)

# Global face analysis model (loaded once on first use)
_face_app: Optional[FaceAnalysis] = None

# FAISS index for known faces (512-dim embeddings from InsightFace)
_face_index: Optional[faiss.IndexFlatL2] = None

# Mapping from FAISS index position to identity metadata
_id_mapping: Dict[int, Dict] = {}  # {faiss_idx: {embedding_id, name}}

# Counter for generating new embedding IDs
_next_embedding_id: int = 1

# Track IDs already processed this session (string track_ids from tracker)
# Decision: Entries persist after TRACK_LOST and are only cleared via reset().
# Reason: ByteTrack never reuses track_ids - once lost, same person gets a NEW
# track_id on return. Persisting prevents wasted re-processing if TRACK_LOST
# has bugs or race conditions.
_processed_track_ids: Set[str] = set()


def _get_face_app() -> FaceAnalysis:
    """Get or initialize the InsightFace face analysis model (lazy loading).
    
    Returns:
        Initialized FaceAnalysis instance with buffalo_s model
    """
    global _face_app
    
    if _face_app is None:
        logger.info("Loading InsightFace buffalo_s model")
        _face_app = FaceAnalysis(name='buffalo_s')
        # ctx_id=-1 forces CPU, ctx_id>=0 would use GPU
        _face_app.prepare(ctx_id=-1, det_size=(640, 640))
        logger.info("InsightFace buffalo_s loaded successfully")
    
    return _face_app


def _get_face_index() -> faiss.IndexFlatL2:
    """Get or initialize the FAISS face index (lazy loading).
    
    Creates new empty 512-dim index or loads existing from disk.
    
    Returns:
        FAISS IndexFlatL2 instance for face embeddings
    """
    global _face_index, _id_mapping
    
    if _face_index is None:
        index_path = config.FAISS_FACE_INDEX_PATH
        mapping_path = config.FACE_ID_MAPPING_PATH
        
        # Create directories if needed
        index_path.parent.mkdir(parents=True, exist_ok=True)
        
        if index_path.exists():
            # Load existing index
            logger.info(f"Loading face index from {index_path}")
            _face_index = faiss.read_index(str(index_path))
            
            # Load mapping
            if mapping_path.exists():
                with open(mapping_path, 'r') as f:
                    # Keys in JSON are strings, convert back to ints
                    _id_mapping = {int(k): v for k, v in json.load(f).items()}
            
            logger.info(f"Loaded {_face_index.ntotal} known faces from index")
        else:
            # Create new empty index (512-dim from InsightFace buffalo_s)
            logger.info("Creating new empty face index (512-dim)")
            _face_index = faiss.IndexFlatL2(512)
            _id_mapping = {}
    
    return _face_index


def _save_face_index():
    """Save FAISS index and mapping to disk."""
    if _face_index is None:
        return
    
    index_path = config.FAISS_FACE_INDEX_PATH
    mapping_path = config.FACE_ID_MAPPING_PATH
    
    # Save index
    faiss.write_index(_face_index, str(index_path))
    
    # Save mapping (convert int keys to strings for JSON)
    with open(mapping_path, 'w') as f:
        json.dump({str(k): v for k, v in _id_mapping.items()}, f, indent=2)
    
    logger.debug(f"Saved face index ({_face_index.ntotal} faces) to {index_path}")


def _select_face_for_bbox(faces, bbox):
    """Select the face that best corresponds to a YOLO person bbox.
    
    Args:
        faces: List of face objects from InsightFace
        bbox: [x1, y1, x2, y2] YOLO person bounding box
    
    Returns:
        Selected face object, or None if no face overlaps with bbox
    """
    if len(faces) == 0:
        return None
    
    # Sort faces by bbox x-coordinate for deterministic ordering
    faces = sorted(faces, key=lambda f: f.bbox[0])
    
    x1, y1, x2, y2 = [int(coord) for coord in bbox]
    yolo_center_x = (x1 + x2) / 2
    yolo_center_y = (y1 + y2) / 2
    
    best_face = None
    best_overlap = 0.0
    
    for face in faces:
        # InsightFace provides face.bbox as [x1, y1, x2, y2]
        face_bbox = face.bbox.astype(int)
        fx1, fy1, fx2, fy2 = face_bbox
        
        # Check if face bbox center is within YOLO person bbox
        face_center_x = (fx1 + fx2) / 2
        face_center_y = (fy1 + fy2) / 2
        
        if fx1 <= yolo_center_x <= fx2 and fy1 <= yolo_center_y <= fy2:
            # YOLO center is inside face bbox - perfect match
            best_face = face
            break
        elif x1 <= face_center_x <= x2 and y1 <= face_center_y <= y2:
            # Face center is inside YOLO bbox - good match
            # Calculate overlap area as a simple heuristic
            overlap_x1 = max(x1, fx1)
            overlap_y1 = max(y1, fy1)
            overlap_x2 = min(x2, fx2)
            overlap_y2 = min(y2, fy2)
            
            if overlap_x2 > overlap_x1 and overlap_y2 > overlap_y1:
                overlap_area = (overlap_x2 - overlap_x1) * (overlap_y2 - overlap_y1)
                face_area = (fx2 - fx1) * (fy2 - fy1)
                overlap_ratio = overlap_area / face_area if face_area > 0 else 0
                
                if overlap_ratio > best_overlap:
                    best_overlap = overlap_ratio
                    best_face = face
    
    return best_face


def identify_face(frame: np.ndarray, bbox: list, track_id: str) -> Optional[Dict]:
    """Identify a person's face from a detection bounding box.
    
    Runs face recognition only on new track_ids (one-time cost per identity).
    Uses InsightFace for 512-dim embeddings and FAISS for known-face matching.
    
    Args:
        frame: BGR frame (shape: [height, width, 3], dtype: uint8)
        bbox: [x1, y1, x2, y2] bounding box from pose detector
        track_id: Vision tracker ID (string, e.g. "T1", "42")
    
    Returns:
        Identity dict if face found, None if no face or already processed:
        - embedding_id: str, persistent ID (e.g. "E0001" for known, "U0001" for new)
        - status: "known" | "new" | "registered_unknown"
        - name: str | None, person's name if known
        - confidence: float | None, match confidence 0-1 (None for new faces)
        
        Returns None if:
        - track_id already processed this session (skip duplicate work)
        - No face detected in bbox (pose detection doesn't guarantee face visibility)
    
    Side Effects:
        - Publishes IdentityResolvedEvent to event bus
        - Adds new faces to FAISS index (auto-saved to disk)
        - Updates _processed_track_ids set (persists until reset())
    
    Example:
        >>> frame = cv2.imread('person.jpg')
        >>> bbox = [100, 50, 300, 400]
        >>> result = identify_face(frame, bbox, track_id="T1")
        >>> if result:
        ...     print(f"{result['status']}: {result['embedding_id']}")
    
    Performance:
        <200ms per call (one-time cost per identity)
        Subsequent calls with same track_id return None immediately
    """
    global _processed_track_ids, _next_embedding_id
    
    # Skip if already processed this track_id
    if track_id in _processed_track_ids:
        logger.debug(f"Track {track_id} already processed, skipping face identification")
        return None
    
    # Mark as processed (persists even after TRACK_LOST - see module docstring)
    _processed_track_ids.add(track_id)
    
    # Use InsightFace's face detector on FULL FRAME instead of pre-cropping to YOLO bbox
    # YOLO bbox is used only to select which detected face corresponds to this track
    face_app = _get_face_app()
    faces = face_app.get(frame)  # Detect faces in full frame
    
    # DEBUG: Log all detected faces
    logger.info(f"[{track_id}] InsightFace detected {len(faces)} face(s) in frame")
    for idx, f in enumerate(faces):
        logger.info(f"[{track_id}]   Face {idx}: bbox={f.bbox}, det_score={f.det_score if hasattr(f, 'det_score') else 'N/A'}")
    
    if len(faces) == 0:
        logger.debug(f"No face detected in frame for track {track_id}")
        return None
    
    # Select the face that corresponds to this YOLO person bbox
    face = _select_face_for_bbox(faces, bbox)
    
    if face is None:
        logger.debug(f"No face bbox overlaps with YOLO bbox for track {track_id}")
        return None
    
    # DEBUG: Log which face was selected
    selected_idx = None
    sorted_faces = sorted(faces, key=lambda f: f.bbox[0])
    for idx, f in enumerate(sorted_faces):
        if f is face:
            selected_idx = idx
            break
    
    # Calculate overlap score for logging
    x1, y1, x2, y2 = [int(coord) for coord in bbox]
    face_bbox = face.bbox.astype(int)
    fx1, fy1, fx2, fy2 = face_bbox
    
    yolo_center_x = (x1 + x2) / 2
    yolo_center_y = (y1 + y2) / 2
    face_center_x = (fx1 + fx2) / 2
    face_center_y = (fy1 + fy2) / 2
    
    if fx1 <= yolo_center_x <= fx2 and fy1 <= yolo_center_y <= fy2:
        best_overlap = 1.0
    elif x1 <= face_center_x <= x2 and y1 <= face_center_y <= y2:
        overlap_x1 = max(x1, fx1)
        overlap_y1 = max(y1, fy1)
        overlap_x2 = min(x2, fx2)
        overlap_y2 = min(y2, fy2)
        
        if overlap_x2 > overlap_x1 and overlap_y2 > overlap_y1:
            overlap_area = (overlap_x2 - overlap_x1) * (overlap_y2 - overlap_y1)
            face_area = (fx2 - fx1) * (fy2 - fy1)
            best_overlap = overlap_area / face_area if face_area > 0 else 0
        else:
            best_overlap = 0.0
    else:
        best_overlap = 0.0
    
    logger.info(f"[{track_id}] SELECTED Face {selected_idx}: bbox={face.bbox}, overlap_score={best_overlap:.4f}")
    
    embedding = face.embedding  # 512-dim numpy array
    
    # Normalize embedding (L2 normalization for cosine similarity via L2 distance)
    embedding = embedding / np.linalg.norm(embedding)
    embedding = embedding.reshape(1, -1).astype('float32')
    
    # Search FAISS index for known faces
    face_index = _get_face_index()
    
    if face_index.ntotal == 0:
        # No known faces yet - this is a new face
        status = "new"
        embedding_id = f"U{_next_embedding_id:04d}"
        _next_embedding_id += 1
        name = None
        confidence = None
        
        # Add to index
        face_index.add(embedding)
        _id_mapping[face_index.ntotal - 1] = {
            'embedding_id': embedding_id,
            'name': name
        }
        _save_face_index()
        
        logger.info(f"New face registered: {embedding_id} for track {track_id}")
    else:
        # Search for nearest neighbor
        distances, indices = face_index.search(embedding, k=1)
        distance = distances[0][0]
        nearest_idx = indices[0][0]
        
        # Check against threshold (L2 distance, lower = more similar)
        if distance < config.FACE_MATCH_THRESHOLD:
            # Known face match
            match_info = _id_mapping[nearest_idx]
            embedding_id = match_info['embedding_id']
            name = match_info['name']
            status = "known" if name else "registered_unknown"
            # Convert L2 distance to confidence (0-1, higher = more confident)
            # distance=0 -> confidence=1, distance=1.08 -> confidence=0
            confidence = max(0.0, 1.0 - (distance / config.FACE_MATCH_THRESHOLD))
            
            logger.info(f"Known face matched: {embedding_id} (confidence {confidence:.2f}, L2 distance {distance:.4f}) for track {track_id}")
        else:
            # New face (no match within threshold)
            status = "new"
            embedding_id = f"U{_next_embedding_id:04d}"
            _next_embedding_id += 1
            name = None
            confidence = None
            
            # Add to index
            face_index.add(embedding)
            _id_mapping[face_index.ntotal - 1] = {
                'embedding_id': embedding_id,
                'name': name
            }
            _save_face_index()
            
            logger.info(f"New face registered: {embedding_id} (no match, distance {distance:.2f}) for track {track_id}")
    
    # Publish IDENTITY_RESOLVED event
    event: IdentityResolvedEvent = {
        'event': 'IDENTITY_RESOLVED',
        'track_id': track_id,
        'embedding_id': embedding_id,
        'status': status,
        'name': name,
        'confidence': confidence
    }
    publish(event)
    
    # Return result dict
    return {
        'embedding_id': embedding_id,
        'status': status,
        'name': name,
        'confidence': confidence
    }


def reset():
    """Reset face identification state (for testing or reinitialization).
    
    Clears processed track IDs but does NOT clear the FAISS index or known faces.
    Use clear_index() to remove all known faces.
    """
    global _processed_track_ids
    _processed_track_ids = set()
    logger.debug("Face ID state reset (processed track_ids cleared)")


def clear_index():
    """Clear all known faces from FAISS index (destructive operation).
    
    WARNING: This removes all face embeddings and mappings. Use only for
    testing or when explicitly requested by user.
    
    Deletes index files from disk and resets in-memory state.
    """
    global _face_index, _id_mapping, _next_embedding_id
    
    # Reset in-memory state
    _face_index = faiss.IndexFlatL2(512)
    _id_mapping = {}
    _next_embedding_id = 1
    
    # Delete files from disk to prevent reload of stale data
    index_path = config.FAISS_FACE_INDEX_PATH
    mapping_path = config.FACE_ID_MAPPING_PATH
    
    if index_path.exists():
        index_path.unlink()
        logger.info(f"Deleted face index file: {index_path}")
    
    if mapping_path.exists():
        mapping_path.unlink()
        logger.info(f"Deleted face mapping file: {mapping_path}")
    
    # Save new empty index to disk
    _save_face_index()
    
    logger.warning("Face index cleared - all known faces removed")

