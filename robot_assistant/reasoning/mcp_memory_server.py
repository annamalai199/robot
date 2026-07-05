"""MCP Memory Server for querying stored facts and memories.

Single tool implementation that searches the memory database for answers to questions.
Used by LangGraph reasoning branch to retrieve factual information.
"""

import sqlite3
from typing import Dict, List, Optional
from robot_assistant.config import config


def query_memory(query: str) -> Dict[str, any]:
    """Retrieve stored memories, facts, or personal information about users.
    
    Searches the memory database for facts matching the natural language query.
    Uses simple keyword matching to find relevant facts across all categories
    (people, facilities, general information).
    
    Args:
        query: Natural language question about stored memories.
    
    Returns:
        dict with keys:
            - answer (str): The retrieved answer or error message
            - confidence (float): Confidence score (0.0-1.0)
            - source (str): Data source identifier
            - category (str | None): Category of the fact (person/facility/general)
    """
    if not query or not query.strip():
        return {
            "answer": "No query provided",
            "confidence": 0.0,
            "source": "memory_db",
            "category": None
        }
    
    try:
        # Connect to database
        conn = sqlite3.connect(config.MEMORY_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Extract keywords from query (same logic used for confidence scoring)
        # Strip stopwords and punctuation before searching
        import string
        stop_words = {'the', 'who', 'what', 'where', 'when', 'how', 'are', 'can', 'you', 'tell', 'about', 'for', 'and', 'is', 'a', 'an'}
        search_words = [w.lower().strip(string.punctuation) 
                       for w in query.split() 
                       if len(w.strip(string.punctuation)) >= 3 and w.lower().strip(string.punctuation) not in stop_words]
        
        if not search_words:
            # No meaningful keywords extracted
            return {
                "answer": "I don't have information about that in my memory.",
                "confidence": 0.0,
                "source": "memory_db",
                "category": None
            }
        
        # Build SQL query with OR conditions for each keyword
        # Search in both key and value fields
        conditions = []
        params = []
        for word in search_words:
            conditions.append("(LOWER(key) LIKE ? OR LOWER(value) LIKE ?)")
            params.extend([f'%{word}%', f'%{word}%'])
        
        where_clause = " OR ".join(conditions)
        
        # Order by key matches first (more specific than value matches)
        order_conditions = []
        order_params = []
        for word in search_words:
            order_conditions.append("WHEN LOWER(key) LIKE ? THEN 1")
            order_params.append(f'%{word}%')
        
        order_clause = "\n                    ".join(order_conditions) if order_conditions else "WHEN 1=1 THEN 1"
        
        query_sql = f"""
            SELECT category, key, value, metadata
            FROM memories
            WHERE {where_clause}
            ORDER BY 
                CASE 
                    {order_clause}
                    ELSE 2
                END,
                category
            LIMIT 5
        """
        
        cursor.execute(query_sql, params + order_params)
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return {
                "answer": "I don't have information about that in my memory.",
                "confidence": 0.0,
                "source": "memory_db",
                "category": None
            }
        
        # Take the best match (first result due to ORDER BY)
        best_match = results[0]
        
        # High confidence if key matches (exact topic), lower if only value matches
        # Check if any keyword appears in the key (already extracted above)
        key_lower = best_match['key'].lower()
        key_match = any(word in key_lower for word in search_words)
        
        confidence = 0.9 if key_match else 0.7
        
        return {
            "answer": best_match['value'],
            "confidence": confidence,
            "source": "memory_db",
            "category": best_match['category']
        }
        
    except sqlite3.Error as e:
        return {
            "answer": f"Database error: {str(e)}",
            "confidence": 0.0,
            "source": "memory_db",
            "category": None
        }
    except Exception as e:
        return {
            "answer": f"Error querying memory: {str(e)}",
            "confidence": 0.0,
            "source": "memory_db",
            "category": None
        }


def search_by_category(category: str) -> List[Dict[str, str]]:
    """Retrieve all facts in a specific category.
    
    Args:
        category: Category name (person, facility, general)
    
    Returns:
        List of dicts with keys: key, value, metadata
    """
    try:
        conn = sqlite3.connect(config.MEMORY_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT key, value, metadata
            FROM memories
            WHERE category = ?
            ORDER BY key
        """, (category,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]
        
    except sqlite3.Error:
        return []


def get_all_categories() -> List[str]:
    """Get list of all available categories in memory database.
    
    Returns:
        List of category names.
    """
    try:
        conn = sqlite3.connect(config.MEMORY_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT category FROM memories ORDER BY category")
        results = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in results]
        
    except sqlite3.Error:
        return []


def get_memory_stats() -> Dict[str, int]:
    """Get statistics about the memory database.
    
    Returns:
        dict with keys:
            - total_facts (int): Total number of facts
            - categories (dict): Count per category
    """
    try:
        conn = sqlite3.connect(config.MEMORY_DB_PATH)
        cursor = conn.cursor()
        
        # Total count
        cursor.execute("SELECT COUNT(*) FROM memories")
        total = cursor.fetchone()[0]
        
        # Count per category
        cursor.execute("""
            SELECT category, COUNT(*) 
            FROM memories 
            GROUP BY category
        """)
        categories = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            "total_facts": total,
            "categories": categories
        }
        
    except sqlite3.Error:
        return {
            "total_facts": 0,
            "categories": {}
        }
