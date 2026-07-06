"""Regression test for clear_index() bug.

This test was missing every time the clear_index() bug resurfaced.
It simulates the scenario that exposed the bug: clear the index,
then reload from disk (simulating fresh process start).

Expected: Index size = 0 after reload
Actual (before fix): Index loads stale entries from disk

This is a REGRESSION TEST - keep it and run it whenever clear_index()
behavior is modified.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from robot_assistant.vision import face_id
from robot_assistant.config import config


def main():
    print("=" * 80)
    print("CLEAR_INDEX() REGRESSION TEST")
    print("=" * 80)
    print()
    print("This test verifies that clear_index() actually deletes files from disk,")
    print("not just resets in-memory state.")
    print()
    
    # Step 1: Add a dummy face to index
    print("Step 1: Adding dummy face to index...")
    face_id.clear_index()  # Start clean
    
    # Simulate adding a face by directly manipulating the index
    import numpy as np
    index = face_id._get_face_index()
    dummy_embedding = np.random.rand(1, 512).astype('float32')
    dummy_embedding = dummy_embedding / np.linalg.norm(dummy_embedding)
    
    index.add(dummy_embedding)
    face_id._id_mapping[0] = {'embedding_id': 'TEST001', 'name': 'Test Person'}
    face_id._save_face_index()
    
    print(f"  Index size: {index.ntotal}")
    print(f"  Mapping: {face_id._id_mapping}")
    
    if index.ntotal != 1:
        print("ERROR: Failed to add dummy face")
        return 1
    
    print("  ✓ Dummy face added")
    print()
    
    # Step 2: Verify files exist on disk
    print("Step 2: Verifying files exist on disk...")
    index_path = config.FAISS_FACE_INDEX_PATH
    mapping_path = config.FACE_ID_MAPPING_PATH
    
    print(f"  Index file: {index_path}")
    print(f"  Exists: {index_path.exists()}")
    print(f"  Mapping file: {mapping_path}")
    print(f"  Exists: {mapping_path.exists()}")
    
    if not index_path.exists() or not mapping_path.exists():
        print("ERROR: Files not saved to disk")
        return 1
    
    print("  ✓ Files exist on disk")
    print()
    
    # Step 3: Call clear_index()
    print("Step 3: Calling clear_index()...")
    face_id.clear_index()
    
    # Check in-memory state
    index_after_clear = face_id._get_face_index()
    print(f"  In-memory index size: {index_after_clear.ntotal}")
    print(f"  In-memory mapping: {face_id._id_mapping}")
    print(f"  In-memory next_id: {face_id._next_embedding_id}")
    
    if index_after_clear.ntotal != 0:
        print("  ✗ FAIL: In-memory index not cleared")
        return 1
    
    if len(face_id._id_mapping) != 0:
        print("  ✗ FAIL: In-memory mapping not cleared")
        return 1
    
    if face_id._next_embedding_id != 1:
        print("  ✗ FAIL: ID counter not reset")
        return 1
    
    print("  ✓ In-memory state cleared")
    print()
    
    # Step 4: CRITICAL TEST - Simulate fresh process by forcing reload from disk
    print("Step 4: Simulating fresh process start (reload from disk)...")
    print("  This is the test that catches the bug!")
    print()
    
    # Reset the global variables to force reload
    face_id._face_index = None
    face_id._id_mapping = {}
    face_id._next_embedding_id = 1
    
    # Now get the index again - this will load from disk
    index_reloaded = face_id._get_face_index()
    
    print(f"  Reloaded index size: {index_reloaded.ntotal}")
    print(f"  Reloaded mapping: {face_id._id_mapping}")
    print()
    
    # THE CRITICAL CHECK
    if index_reloaded.ntotal != 0:
        print("✗ REGRESSION TEST FAILED!")
        print()
        print("clear_index() did not properly delete files from disk.")
        print("The index was reloaded with stale data.")
        print()
        print("This is the bug that caused:")
        print("- First image showing status='registered_unknown' instead of 'new'")
        print("- Multiple people assigned the same ID (U0001)")
        print("- Distance mismatches between identify_face() and pairwise comparison")
        print()
        return 1
    
    if len(face_id._id_mapping) != 0:
        print("✗ REGRESSION TEST FAILED!")
        print("Mapping file was not deleted - reloaded with stale data")
        return 1
    
    # SUCCESS
    print("=" * 80)
    print("✓ REGRESSION TEST PASSED")
    print("=" * 80)
    print()
    print("clear_index() correctly:")
    print("  1. Resets in-memory state")
    print("  2. Deletes index file from disk")
    print("  3. Deletes mapping file from disk")
    print("  4. Saves new empty index")
    print("  5. Prevents reload of stale data on next process start")
    print()
    print("The bug is FIXED.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
