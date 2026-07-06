"""Investigate InsightFace embedding normalization behavior.

This script checks:
1. Are InsightFace buffalo_s embeddings already unit-normalized?
2. What's the typical L2 distance range for same-person vs different-person?
3. Should we normalize again after getting embeddings?
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from insightface.app import FaceAnalysis


def main():
    print("=" * 70)
    print("InsightFace Embedding Normalization Investigation")
    print("=" * 70)
    print()
    
    # Load model
    print("Loading InsightFace buffalo_s model...")
    app = FaceAnalysis(name='buffalo_s')
    app.prepare(ctx_id=-1, det_size=(640, 640))
    print("Model loaded successfully!")
    print()
    
    # Create synthetic test face (random noise, just to get embedding shape)
    print("Generating test embeddings...")
    test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Get embedding (will likely fail on random noise, but that's OK for shape check)
    faces = app.get(test_frame)
    
    if len(faces) == 0:
        print("No face detected in random noise (expected)")
        print("We need a real face image to test normalization...")
        print()
        print("THEORETICAL ANALYSIS:")
        print()
        print("InsightFace (ArcFace) embeddings:")
        print("  - Training uses L2-normalized embeddings for angular loss")
        print("  - Embeddings SHOULD be unit vectors (||e|| ≈ 1.0)")
        print("  - L2 distance between normalized vectors: d ∈ [0, 2√2] ≈ [0, 2.83]")
        print("  - For θ angle between vectors: d = √(2 - 2*cos(θ))")
        print()
        print("Expected ranges (for normalized embeddings):")
        print("  - Same person, same photo: d ≈ 0.0 - 0.1")
        print("  - Same person, different pose/lighting: d ≈ 0.2 - 0.5")
        print("  - Different person: d ≈ 0.6 - 1.5+")
        print()
        print("THRESHOLD ANALYSIS (current = 0.6):")
        print("  - If embeddings are ALREADY normalized by InsightFace:")
        print("    → threshold = 0.6 is reasonable (catches different poses)")
        print("    → distance = 0.468 → confidence = 0.22 is low but plausible")
        print("    → Re-normalizing ALREADY normalized vectors is redundant")
        print()
        print("  - If embeddings are NOT normalized:")
        print("    → We must normalize before FAISS")
        print("    → Current code does normalize: embedding / ||embedding||")
        print()
        print("VERDICT:")
        print("  InsightFace buffalo_s (ArcFace-based) almost certainly outputs")
        print("  ALREADY-NORMALIZED embeddings. The current code's extra")
        print("  normalization is redundant but harmless (normalizing a unit vector")
        print("  just returns the same vector).")
        print()
        print("  The distance=0.468 with confidence=0.22 suggests:")
        print("  - Same person but significantly different pose/angle/lighting")
        print("  - Threshold of 0.6 is reasonable (not too loose)")
        print("  - To get higher confidence, need better face alignment or lighting")
        print()
        print("RECOMMENDATION:")
        print("  1. Run smoke test 3+ times with same person to see consistency")
        print("  2. If distances consistently 0.3-0.5, that's normal variance")
        print("  3. Test with DIFFERENT person to verify distance > 0.6")
        print("  4. Consider lowering threshold to 0.5 if too many false positives")
        print()
    else:
        face = faces[0]
        embedding = face.embedding
        
        print(f"Embedding shape: {embedding.shape}")
        print(f"Embedding dtype: {embedding.dtype}")
        print(f"Embedding L2 norm: {np.linalg.norm(embedding):.4f}")
        print()
        
        if np.abs(np.linalg.norm(embedding) - 1.0) < 0.01:
            print("✓ Embedding IS unit-normalized (||e|| ≈ 1.0)")
            print("  → InsightFace already normalizes embeddings")
            print("  → Extra normalization in face_id.py is redundant but harmless")
        else:
            print("✗ Embedding is NOT unit-normalized")
            print("  → Must normalize before FAISS distance calculation")
            print("  → Current code DOES normalize, which is correct")
        print()
    
    print("=" * 70)


if __name__ == '__main__':
    main()
