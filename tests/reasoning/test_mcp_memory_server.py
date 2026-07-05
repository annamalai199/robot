"""Tests for MCP Memory Server.

All tests use mocked database to ensure fast execution without real DB dependency.
"""

import pytest
import sqlite3
from unittest.mock import Mock, patch, MagicMock
from robot_assistant.reasoning import mcp_memory_server


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection with sample data."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.row_factory = sqlite3.Row
    return mock_conn, mock_cursor


class TestQueryMemory:
    """Test the main query_memory tool function."""
    
    def test_query_memory_exact_key_match(self, mock_db_connection):
        """Test query matching exact key returns high confidence."""
        mock_conn, mock_cursor = mock_db_connection
        
        # Mock row result
        mock_row = {
            'category': 'person',
            'key': 'hod_name',
            'value': 'Dr. Rajesh Kumar',
            'metadata': '{}'
        }
        mock_cursor.fetchall.return_value = [mock_row]
        
        with patch('sqlite3.connect', return_value=mock_conn):
            result = mcp_memory_server.query_memory("Who is the HOD?")
        
        assert result['answer'] == 'Dr. Rajesh Kumar'
        assert result['confidence'] == 0.9  # High confidence for key match
        assert result['source'] == 'memory_db'
        assert result['category'] == 'person'
    
    def test_query_memory_value_match(self, mock_db_connection):
        """Test query matching value field returns lower confidence."""
        mock_conn, mock_cursor = mock_db_connection
        
        mock_row = {
            'category': 'facility',
            'key': 'library_location',
            'value': 'Central Library, Block B, 3rd Floor',
            'metadata': '{}'
        }
        mock_cursor.fetchall.return_value = [mock_row]
        
        with patch('sqlite3.connect', return_value=mock_conn):
            result = mcp_memory_server.query_memory("Where is Block B?")
        
        assert 'Block B' in result['answer']
        assert result['confidence'] == 0.7  # Lower confidence for value-only match
        assert result['category'] == 'facility'
    
    def test_query_memory_no_results(self, mock_db_connection):
        """Test query with no matches returns appropriate message."""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []
        
        with patch('sqlite3.connect', return_value=mock_conn):
            result = mcp_memory_server.query_memory("What is quantum physics?")
        
        assert "don't have information" in result['answer']
        assert result['confidence'] == 0.0
        assert result['category'] is None
    
    def test_query_memory_empty_query(self):
        """Test empty query returns error."""
        result = mcp_memory_server.query_memory("")
        
        assert result['answer'] == "No query provided"
        assert result['confidence'] == 0.0
    
    def test_query_memory_whitespace_only(self):
        """Test whitespace-only query returns error."""
        result = mcp_memory_server.query_memory("   \n\t  ")
        
        assert result['answer'] == "No query provided"
        assert result['confidence'] == 0.0
    
    def test_query_memory_case_insensitive(self, mock_db_connection):
        """Test query matching is case insensitive."""
        mock_conn, mock_cursor = mock_db_connection
        
        mock_row = {
            'category': 'person',
            'key': 'principal_name',
            'value': 'Dr. Anita Desai',
            'metadata': '{}'
        }
        mock_cursor.fetchall.return_value = [mock_row]
        
        with patch('sqlite3.connect', return_value=mock_conn):
            result = mcp_memory_server.query_memory("WHO IS THE PRINCIPAL?")
        
        assert result['answer'] == 'Dr. Anita Desai'
        assert result['confidence'] == 0.9
    
    def test_query_memory_database_error(self):
        """Test database error returns error message."""
        with patch('sqlite3.connect', side_effect=sqlite3.Error("Connection failed")):
            result = mcp_memory_server.query_memory("test query")
        
        assert "Database error" in result['answer']
        assert result['confidence'] == 0.0
    
    def test_query_memory_unexpected_exception(self):
        """Test unexpected exception is caught and returned."""
        with patch('sqlite3.connect', side_effect=Exception("Unexpected error")):
            result = mcp_memory_server.query_memory("test query")
        
        assert "Error querying memory" in result['answer']
        assert result['confidence'] == 0.0
    
    def test_query_memory_multiple_results_returns_best(self, mock_db_connection):
        """Test multiple results returns first (best) match."""
        mock_conn, mock_cursor = mock_db_connection
        
        mock_rows = [
            {
                'category': 'person',
                'key': 'hod_name',
                'value': 'Dr. Rajesh Kumar',
                'metadata': '{}'
            },
            {
                'category': 'facility',
                'key': 'department_location',
                'value': 'Computer Science: Block C, 3rd Floor',
                'metadata': '{}'
            }
        ]
        mock_cursor.fetchall.return_value = mock_rows
        
        with patch('sqlite3.connect', return_value=mock_conn):
            result = mcp_memory_server.query_memory("computer science")
        
        # Should return first result
        assert result['answer'] == 'Dr. Rajesh Kumar'
        assert result['category'] == 'person'
    
    def test_query_memory_sql_injection_safe(self, mock_db_connection):
        """Test query is safe from SQL injection."""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []
        
        malicious_query = "'; DROP TABLE memories; --"
        
        with patch('sqlite3.connect', return_value=mock_conn):
            result = mcp_memory_server.query_memory(malicious_query)
        
        # Should handle safely via parameterized query
        assert result['confidence'] == 0.0
        # Verify parameterized query was used (not string concatenation)
        call_args = mock_cursor.execute.call_args[0]
        assert '?' in call_args[0]  # Parameterized query uses ?
        assert 'DROP' not in call_args[0]  # SQL injection not in query string


class TestSearchByCategory:
    """Test category-based search function."""
    
    def test_search_by_category_returns_results(self, mock_db_connection):
        """Test searching by category returns all facts in category."""
        mock_conn, mock_cursor = mock_db_connection
        
        mock_rows = [
            {'key': 'hod_name', 'value': 'Dr. Rajesh Kumar', 'metadata': '{}'},
            {'key': 'principal_name', 'value': 'Dr. Anita Desai', 'metadata': '{}'}
        ]
        mock_cursor.fetchall.return_value = mock_rows
        
        with patch('sqlite3.connect', return_value=mock_conn):
            results = mcp_memory_server.search_by_category('person')
        
        assert len(results) == 2
        assert results[0]['key'] == 'hod_name'
        assert results[1]['key'] == 'principal_name'
    
    def test_search_by_category_empty_category(self, mock_db_connection):
        """Test searching non-existent category returns empty list."""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []
        
        with patch('sqlite3.connect', return_value=mock_conn):
            results = mcp_memory_server.search_by_category('nonexistent')
        
        assert results == []
    
    def test_search_by_category_database_error(self):
        """Test database error returns empty list."""
        with patch('sqlite3.connect', side_effect=sqlite3.Error("Error")):
            results = mcp_memory_server.search_by_category('person')
        
        assert results == []


class TestGetAllCategories:
    """Test get_all_categories helper function."""
    
    def test_get_all_categories_returns_list(self, mock_db_connection):
        """Test get all categories returns sorted list."""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = [
            ('facility',),
            ('general',),
            ('person',)
        ]
        
        with patch('sqlite3.connect', return_value=mock_conn):
            categories = mcp_memory_server.get_all_categories()
        
        assert categories == ['facility', 'general', 'person']
    
    def test_get_all_categories_database_error(self):
        """Test database error returns empty list."""
        with patch('sqlite3.connect', side_effect=sqlite3.Error("Error")):
            categories = mcp_memory_server.get_all_categories()
        
        assert categories == []


class TestGetMemoryStats:
    """Test get_memory_stats helper function."""
    
    def test_get_memory_stats_returns_counts(self, mock_db_connection):
        """Test memory stats returns total and category counts."""
        mock_conn, mock_cursor = mock_db_connection
        
        # Mock total count query
        mock_cursor.fetchone.return_value = (20,)
        
        # Mock category counts query
        mock_cursor.fetchall.return_value = [
            ('person', 5),
            ('facility', 10),
            ('general', 5)
        ]
        
        with patch('sqlite3.connect', return_value=mock_conn):
            stats = mcp_memory_server.get_memory_stats()
        
        assert stats['total_facts'] == 20
        assert stats['categories']['person'] == 5
        assert stats['categories']['facility'] == 10
        assert stats['categories']['general'] == 5
    
    def test_get_memory_stats_database_error(self):
        """Test database error returns zero counts."""
        with patch('sqlite3.connect', side_effect=sqlite3.Error("Error")):
            stats = mcp_memory_server.get_memory_stats()
        
        assert stats['total_facts'] == 0
        assert stats['categories'] == {}


class TestLatency:
    """Test latency requirements."""
    
    def test_query_memory_latency_under_100ms(self, mock_db_connection):
        """Test query_memory completes in under 100ms."""
        import time
        
        mock_conn, mock_cursor = mock_db_connection
        mock_row = {
            'category': 'person',
            'key': 'hod_name',
            'value': 'Dr. Rajesh Kumar',
            'metadata': '{}'
        }
        mock_cursor.fetchall.return_value = [mock_row]
        
        with patch('sqlite3.connect', return_value=mock_conn):
            start = time.perf_counter()
            mcp_memory_server.query_memory("Who is the HOD?")
            elapsed = time.perf_counter() - start
        
        # Should be under 100ms (mocked, so will be much faster)
        assert elapsed < 0.1, f"Query took {elapsed*1000:.2f}ms, expected <100ms"


class TestDocstring:
    """Test that function has proper LLM-readable docstring."""
    
    def test_query_memory_has_docstring(self):
        """Test query_memory has comprehensive docstring."""
        docstring = mcp_memory_server.query_memory.__doc__
        
        assert docstring is not None
        assert "Args:" in docstring
        assert "Returns:" in docstring
        assert "query" in docstring.lower()
        assert "memory" in docstring.lower()
    
    def test_query_memory_docstring_format(self):
        """Test docstring follows LLM-readable format."""
        docstring = mcp_memory_server.query_memory.__doc__
        
        # Should have summary line
        lines = [line.strip() for line in docstring.strip().split('\n') if line.strip()]
        assert len(lines[0]) > 0  # First line is summary
        
        # Should have Args section
        assert any('Args:' in line for line in lines)
        
        # Should have Returns section
        assert any('Returns:' in line for line in lines)


class TestRealDatabaseRegression:
    """Regression tests against actual seeded memory.db.
    
    These tests use the REAL database (not mocked) to catch issues that
    mocked tests miss, specifically the live integration bug where
    query_memory("Who is the HOD?") returned confidence 0.0 instead of
    finding the hod_name entry.
    """
    
    def test_natural_question_who_is_the_hod(self):
        """Regression: 'Who is the HOD?' must find hod_name entry.
        
        This is the EXACT failing case from live integration testing.
        Bug: keyword extraction happened only in scoring, not retrieval,
        so "who is the hod?" didn't substring-match "hod_name" and
        returned zero rows before scoring could run.
        
        Fix: Extract keywords BEFORE SQL query, search with individual
        keywords rather than whole phrase.
        """
        result = mcp_memory_server.query_memory("Who is the HOD?")
        
        # Must find the answer
        assert result['confidence'] > 0.0, "Should find hod_name entry with keyword 'hod'"
        assert "Rajesh Kumar" in result['answer'] or "rajesh" in result['answer'].lower()
        assert result['category'] == 'person'
    
    def test_natural_question_where_is_library(self):
        """Regression: 'Where is the library?' must find library_location."""
        result = mcp_memory_server.query_memory("Where is the library?")
        
        assert result['confidence'] > 0.0
        assert "Block B" in result['answer'] or "library" in result['answer'].lower()
        assert result['category'] == 'facility'
    
    def test_natural_question_with_stopwords(self):
        """Test that stopwords are correctly filtered in retrieval."""
        result = mcp_memory_server.query_memory("Can you tell me about the principal?")
        
        # Should extract 'principal' and find principal_name
        assert result['confidence'] > 0.0
        assert "Anita Desai" in result['answer'] or "anita" in result['answer'].lower()
    
    def test_single_keyword_still_works(self):
        """Test that simple single-keyword queries still work."""
        result = mcp_memory_server.query_memory("canteen")
        
        assert result['confidence'] > 0.0
        assert result['category'] == 'facility'
    
    def test_no_meaningful_keywords_returns_no_info(self):
        """Test query with only stopwords returns no info."""
        result = mcp_memory_server.query_memory("who is the")
        
        # All stopwords, should return no info
        assert result['confidence'] == 0.0
        assert "don't have information" in result['answer']
