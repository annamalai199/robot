"""Verify database contents after initialization."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from robot_assistant.config import config

def verify_database():
    """Check database tables and contents."""
    
    if not config.MEMORY_DB_PATH.exists():
        print(f"❌ Database not found: {config.MEMORY_DB_PATH}")
        print("   Run: python scripts/init_memory_db.py")
        return
    
    conn = sqlite3.connect(config.MEMORY_DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 70)
    print("Database Verification")
    print("=" * 70)
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n✓ Tables: {', '.join(tables)}")
    
    # Check memories by category
    print("\n📊 Memory Facts by Category:")
    cursor.execute("SELECT category, COUNT(*) FROM memories GROUP BY category")
    for category, count in cursor.fetchall():
        print(f"   {category:10s}: {count} facts")
    
    # Total count
    cursor.execute("SELECT COUNT(*) FROM memories")
    total = cursor.fetchone()[0]
    print(f"   {'TOTAL':10s}: {total} facts")
    
    # Check data version
    cursor.execute("SELECT value FROM metadata WHERE key='data_version'")
    version = cursor.fetchone()[0]
    print(f"\n✓ Data version: {version}")
    
    # Sample facts
    print("\n📝 Sample Facts:")
    cursor.execute("SELECT category, key, value FROM memories LIMIT 5")
    for category, key, value in cursor.fetchall():
        print(f"   [{category}] {key}: {value[:50]}...")
    
    conn.close()
    print("\n" + "=" * 70)
    print("✅ Database verification complete")
    print("=" * 70)

if __name__ == "__main__":
    verify_database()
