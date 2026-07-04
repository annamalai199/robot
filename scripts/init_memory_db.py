"""Initialize memory database with seed facts for demo.

Creates memory.db with 20 college-contextual facts across 3 categories:
- People (5 facts)
- Schedule (10 facts)
- General (5 facts)
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from robot_assistant.config import config

def init_database():
    """Create memory database and populate with seed data."""
    
    # Ensure data directory exists
    config.ensure_directories()
    
    # Remove existing database if present
    if config.MEMORY_DB_PATH.exists():
        print(f"Removing existing database: {config.MEMORY_DB_PATH}")
        config.MEMORY_DB_PATH.unlink()
    
    # Create database and tables
    print(f"Creating database: {config.MEMORY_DB_PATH}")
    conn = sqlite3.connect(config.MEMORY_DB_PATH)
    cursor = conn.cursor()
    
    # Create identities table for face recognition
    cursor.execute("""
        CREATE TABLE identities (
            embedding_id TEXT PRIMARY KEY,
            name TEXT,
            created_at REAL,
            last_seen REAL
        )
    """)
    
    # Create memories table for QA facts
    cursor.execute("""
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY,
            category TEXT,
            key TEXT UNIQUE,
            value TEXT,
            metadata TEXT,
            created_at REAL
        )
    """)
    
    cursor.execute("CREATE INDEX idx_category ON memories(category)")
    cursor.execute("CREATE INDEX idx_key ON memories(key)")
    
    # Create metadata table for data versioning
    cursor.execute("""
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    cursor.execute("INSERT INTO metadata VALUES ('data_version', '1')")
    
    print("Created tables: identities, memories, metadata")
    
    # Seed memory facts
    print("\nInserting seed facts...")
    
    import time
    timestamp = time.time()
    
    # People (5 facts)
    people_facts = [
        (1, 'person', 'hod_name', 'Dr. Rajesh Kumar', '{"title": "Professor", "department": "Computer Science"}', timestamp),
        (2, 'person', 'lab_instructor', 'Ms. Priya Sharma', '{"subjects": ["AI Lab", "ML Lab"]}', timestamp),
        (3, 'person', 'principal_name', 'Dr. Anita Desai', '{"since": 2020}', timestamp),
        (4, 'person', 'class_advisor', 'Prof. Venkat Raman', '{"department": "CSE"}', timestamp),
        (5, 'person', 'placement_officer', 'Mr. Suresh Naidu', '{"role": "Training and Placement"}', timestamp),
    ]
    
    # Schedule (10 facts)
    schedule_facts = [
        (6, 'schedule', 'lab_hours_monday', '2:00 PM - 5:00 PM', '{"subject": "AI Lab", "room": "Lab 301"}', timestamp),
        (7, 'schedule', 'lab_hours_wednesday', '10:00 AM - 1:00 PM', '{"subject": "ML Lab", "room": "Lab 302"}', timestamp),
        (8, 'schedule', 'office_hours_hod', 'Monday & Thursday 3-5 PM', '{"room": "HOD Office, Block A"}', timestamp),
        (9, 'schedule', 'library_hours', '8:00 AM - 8:00 PM', '{"weekend": "9 AM - 5 PM"}', timestamp),
        (10, 'schedule', 'exam_schedule', 'Final exams: Dec 15-30, 2026', '{"mid_term": "Oct 10-20"}', timestamp),
        (11, 'schedule', 'semester_start', 'July 1, 2026', '{"end": "November 30, 2026"}', timestamp),
        (12, 'schedule', 'class_timings', '9:00 AM - 4:00 PM', '{"lunch": "1-2 PM"}', timestamp),
        (13, 'schedule', 'project_deadline', 'November 15, 2026', '{"submission": "online portal"}', timestamp),
        (14, 'schedule', 'holiday_next', 'Independence Day - Aug 15', '{"type": "national holiday"}', timestamp),
        (15, 'schedule', 'career_fair', 'September 20-22, 2026', '{"venue": "Main Auditorium"}', timestamp),
    ]
    
    # General (5 facts)
    general_facts = [
        (16, 'general', 'library_location', 'Central Library, Block B', '{"floors": 3, "study_rooms": 12}', timestamp),
        (17, 'general', 'canteen_menu_today', 'Veg thali, Biryani, Dosa', '{"timings": "12-2:30 PM"}', timestamp),
        (18, 'general', 'department_location', 'Block C, 3rd Floor', '{"dept": "Computer Science"}', timestamp),
        (19, 'general', 'helpdesk_number', '+91-80-12345678', '{"email": "helpdesk@college.edu"}', timestamp),
        (20, 'general', 'lab_equipment', 'Robots: 5 humanoid units', '{"reservation": "via lab portal"}', timestamp),
    ]
    
    all_facts = people_facts + schedule_facts + general_facts
    
    cursor.executemany(
        "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)",
        all_facts
    )
    
    print(f"✓ Inserted {len(people_facts)} people facts")
    print(f"✓ Inserted {len(schedule_facts)} schedule facts")
    print(f"✓ Inserted {len(general_facts)} general facts")
    print(f"✓ Total: {len(all_facts)} facts")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Database initialized successfully: {config.MEMORY_DB_PATH}")
    print(f"   Data version: 1")
    print(f"\nYou can now run: python main.py")

if __name__ == "__main__":
    init_database()
