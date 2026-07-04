"""Initialize memory database with seed facts for demo.

Creates memory.db with 20 college-contextual facts across 3 categories:
- People (5 facts) - Faculty and staff information
- Facilities (10 facts) - Locations, resources, services, equipment
- General (5 facts) - Policies, contact info, general college info

Note: No date-sensitive or schedule-based facts. All information is static
and non-temporal, suitable for indefinite caching.
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
    
    # People (5 facts) - Faculty and staff
    people_facts = [
        (1, 'person', 'hod_name', 'Dr. Rajesh Kumar', '{"title": "Professor", "department": "Computer Science"}', timestamp),
        (2, 'person', 'lab_instructor', 'Ms. Priya Sharma', '{"subjects": ["AI Lab", "ML Lab"]}', timestamp),
        (3, 'person', 'principal_name', 'Dr. Anita Desai', '{"since": 2020}', timestamp),
        (4, 'person', 'class_advisor', 'Prof. Venkat Raman', '{"department": "CSE"}', timestamp),
        (5, 'person', 'placement_officer', 'Mr. Suresh Naidu', '{"role": "Training and Placement"}', timestamp),
    ]
    
    # Facilities (10 facts) - Locations, resources, services, equipment
    facilities_facts = [
        (6, 'facility', 'library_location', 'Central Library, Block B, 3rd Floor', '{"floors": 3, "study_rooms": 12, "capacity": 200}', timestamp),
        (7, 'facility', 'library_rules', 'Silence mandatory, no food/drinks, laptops allowed', '{"wifi": "available", "printing": "floor 1"}', timestamp),
        (8, 'facility', 'canteen_location', 'Ground Floor, Block A', '{"seating": 150, "payment": "cash and card"}', timestamp),
        (9, 'facility', 'canteen_offerings', 'South Indian, North Indian, Chinese, Beverages', '{"veg": "yes", "non_veg": "limited"}', timestamp),
        (10, 'facility', 'lab_equipment', '5 humanoid robots available for projects', '{"reservation": "via lab portal", "location": "Lab 301"}', timestamp),
        (11, 'facility', 'sports_facilities', 'Indoor: Badminton, Table Tennis; Outdoor: Cricket, Football', '{"gym": "yes", "swimming_pool": "no"}', timestamp),
        (12, 'facility', 'placement_cell', 'Block C, 2nd Floor', '{"timings": "9 AM - 5 PM", "services": "training, counseling, internships"}', timestamp),
        (13, 'facility', 'department_location', 'Computer Science: Block C, 3rd Floor', '{"staff_room": "Room 301", "labs": "301-305"}', timestamp),
        (14, 'facility', 'auditorium_capacity', 'Main Auditorium seats 500 people', '{"AC": "yes", "projector": "yes", "sound_system": "Dolby"}', timestamp),
        (15, 'facility', 'parking_info', 'Two-wheeler: Block D; Four-wheeler: Behind Block A', '{"capacity": "200 bikes, 50 cars", "security": "24x7"}', timestamp),
    ]
    
    # General (5 facts) - Policies, contact info, general college info
    general_facts = [
        (16, 'general', 'helpdesk_number', '+91-80-12345678', '{"email": "helpdesk@college.edu", "location": "Admin Block"}', timestamp),
        (17, 'general', 'wifi_access', 'SSID: CollegeNet, Password available at helpdesk', '{"coverage": "all buildings", "speed": "100 Mbps"}', timestamp),
        (18, 'general', 'dress_code', 'Formal wear mandatory on weekdays, casual on Saturdays', '{"id_card": "mandatory"}', timestamp),
        (19, 'general', 'hostel_info', 'Separate hostels for boys and girls, 500 capacity each', '{"mess": "included", "wifi": "yes", "warden_contact": "+91-80-12345690"}', timestamp),
        (20, 'general', 'college_website', 'www.college.edu', '{"student_portal": "portal.college.edu", "email_format": "firstname.lastname@college.edu"}', timestamp),
    ]
    
    all_facts = people_facts + facilities_facts + general_facts
    
    cursor.executemany(
        "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)",
        all_facts
    )
    
    print(f"✓ Inserted {len(people_facts)} people facts")
    print(f"✓ Inserted {len(facilities_facts)} facilities facts")
    print(f"✓ Inserted {len(general_facts)} general facts")
    print(f"✓ Total: {len(all_facts)} facts")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Database initialized successfully: {config.MEMORY_DB_PATH}")
    print(f"   Data version: 1")
    print(f"\nYou can now run: python main.py")

if __name__ == "__main__":
    init_database()
