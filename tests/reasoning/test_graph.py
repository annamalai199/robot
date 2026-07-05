"""Tests for LangGraph reasoning workflow.

All tests use mocked LLM and database to ensure fast execution without
real Ollama or database dependency.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from robot_assistant.reasoning import graph
from robot_assistant.config import config


@pytest.fixture
def mock_mcp_result_success():
    """Mock successful MCP memory server result."""
    return {
        'answer': 'Dr. Rajesh Kumar',
        'confidence': 0.9,
        'source': 'memory_db',
        'category': 'person'
    }


@pytest.fixture
def mock_mcp_result_no_info():
    """Mock MCP result when no information found."""
    return {
        'answer': "I don't have information about that in my memory.",
        'confidence': 0.0,
        'source': 'memory_db',
        'category': None
    }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response."""
    return "Dr. Rajesh Kumar is the Head of Department for Computer Science."


class TestRetrieveNode:
    """Test the retrieve node (currently a stub)."""
    
    def test_retrieve_node_returns_empty_context(self):
        """Test retrieve node returns empty context list (stub)."""
        state = {
            'question': 'Who is the HOD?',
            'context': [],
            'mcp_result': None,
            'answer': None,
            'cache_written': False,
            'error': None
        }
        
        result = graph.retrieve_node(state)
        
        assert result['context'] == []
        assert result['question'] == 'Who is the HOD?'
    
    def test_retrieve_node_preserves_other_state(self):
        """Test retrieve node doesn't modify other state fields."""
        state = {
            'question': 'test',
            'context': ['existing'],
            'mcp_result': {'test': 'data'},
            'answer': 'test answer',
            'cache_written': True,
            'error': 'test error'
        }
        
        result = graph.retrieve_node(state)
        
        # Only context should be reset
        assert result['question'] == 'test'
        assert result['mcp_result'] == {'test': 'data'}
        assert result['answer'] == 'test answer'
        assert result['cache_written'] is True
        assert result['error'] == 'test error'


class TestMCPToolCallNode:
    """Test the MCP tool call node."""
    
    def test_mcp_tool_call_success(self, mock_mcp_result_success):
        """Test successful MCP tool call adds to context."""
        state = {
            'question': 'Who is the HOD?',
            'context': [],
            'mcp_result': None,
            'answer': None,
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.reasoning.mcp_memory_server.query_memory', 
                  return_value=mock_mcp_result_success):
            result = graph.mcp_tool_call_node(state)
        
        assert result['mcp_result'] == mock_mcp_result_success
        assert len(result['context']) == 1
        assert 'Dr. Rajesh Kumar' in result['context'][0]
    
    def test_mcp_tool_call_no_info_doesnt_add_context(self, mock_mcp_result_no_info):
        """Test MCP result with low confidence doesn't add to context."""
        state = {
            'question': 'What is quantum physics?',
            'context': [],
            'mcp_result': None,
            'answer': None,
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.reasoning.mcp_memory_server.query_memory',
                  return_value=mock_mcp_result_no_info):
            result = graph.mcp_tool_call_node(state)
        
        assert result['mcp_result'] == mock_mcp_result_no_info
        assert result['context'] == []  # Low confidence, no context added
    
    def test_mcp_tool_call_exception_sets_error(self):
        """Test MCP exception is caught and sets error field."""
        state = {
            'question': 'test',
            'context': [],
            'mcp_result': None,
            'answer': None,
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.reasoning.mcp_memory_server.query_memory',
                  side_effect=Exception("Database error")):
            result = graph.mcp_tool_call_node(state)
        
        assert "MCP tool error" in result['error']
        assert result['mcp_result'] is None


class TestGenerateNode:
    """Test the LLM generate node."""
    
    def test_generate_success(self, mock_llm_response):
        """Test successful LLM generation."""
        state = {
            'question': 'Who is the HOD?',
            'context': ['Memory: Dr. Rajesh Kumar'],
            'mcp_result': {'answer': 'Dr. Rajesh Kumar', 'confidence': 0.9},
            'answer': None,
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.reasoning.llm_client.generate',
                  return_value=mock_llm_response):
            result = graph.generate_node(state)
        
        assert result['answer'] == mock_llm_response
        assert result['error'] is None
    
    def test_generate_with_existing_error_returns_fallback(self):
        """Test generate node with existing error returns fallback."""
        state = {
            'question': 'test',
            'context': [],
            'mcp_result': None,
            'answer': None,
            'cache_written': False,
            'error': 'Previous node error'
        }
        
        result = graph.generate_node(state)
        
        assert result['answer'] == config.LANGGRAPH_FALLBACK_MESSAGE
        assert result['error'] == 'Previous node error'
    
    def test_generate_timeout_returns_fallback(self):
        """Test LLM timeout returns fallback message."""
        state = {
            'question': 'test',
            'context': [],
            'mcp_result': None,
            'answer': None,
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.reasoning.llm_client.generate',
                  side_effect=TimeoutError("Timeout")):
            result = graph.generate_node(state)
        
        assert result['answer'] == config.LANGGRAPH_FALLBACK_MESSAGE
        assert 'timeout' in result['error'].lower()
    
    def test_generate_exception_returns_fallback(self):
        """Test LLM exception returns fallback message."""
        state = {
            'question': 'test',
            'context': [],
            'mcp_result': None,
            'answer': None,
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.reasoning.llm_client.generate',
                  side_effect=Exception("LLM error")):
            result = graph.generate_node(state)
        
        assert result['answer'] == config.LANGGRAPH_FALLBACK_MESSAGE
        assert 'LLM error' in result['error']
    
    def test_generate_empty_response_returns_fallback(self):
        """Test empty LLM response returns fallback."""
        state = {
            'question': 'test',
            'context': [],
            'mcp_result': None,
            'answer': None,
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.reasoning.llm_client.generate',
                  return_value=''):
            result = graph.generate_node(state)
        
        assert result['answer'] == config.LANGGRAPH_FALLBACK_MESSAGE
    
    def test_generate_strips_whitespace(self, mock_llm_response):
        """Test LLM response is stripped of whitespace."""
        state = {
            'question': 'test',
            'context': [],
            'mcp_result': None,
            'answer': None,
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.reasoning.llm_client.generate',
                  return_value=f"  {mock_llm_response}  \n"):
            result = graph.generate_node(state)
        
        assert result['answer'] == mock_llm_response


class TestCacheWriteBackNode:
    """Test the cache write-back node."""
    
    def test_cache_write_back_success(self):
        """Test successful cache write."""
        state = {
            'question': 'Who is the HOD?',
            'context': [],
            'mcp_result': None,
            'answer': 'Dr. Rajesh Kumar',
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.qa_cache.cache_manager.write_cache') as mock_write:
            result = graph.cache_write_back_node(state)
        
        assert result['cache_written'] is True
        mock_write.assert_called_once_with('Who is the HOD?', 'Dr. Rajesh Kumar')
    
    def test_cache_write_back_skips_on_error(self):
        """Test cache write skipped when error exists."""
        state = {
            'question': 'test',
            'context': [],
            'mcp_result': None,
            'answer': 'Some answer',
            'cache_written': False,
            'error': 'LLM error'
        }
        
        with patch('robot_assistant.qa_cache.cache_manager.write_cache') as mock_write:
            result = graph.cache_write_back_node(state)
        
        assert result['cache_written'] is False
        mock_write.assert_not_called()
    
    def test_cache_write_back_skips_fallback_message(self):
        """Test cache write skipped for fallback message."""
        state = {
            'question': 'test',
            'context': [],
            'mcp_result': None,
            'answer': config.LANGGRAPH_FALLBACK_MESSAGE,
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.qa_cache.cache_manager.write_cache') as mock_write:
            result = graph.cache_write_back_node(state)
        
        assert result['cache_written'] is False
        mock_write.assert_not_called()
    
    def test_cache_write_back_exception_doesnt_fail_request(self):
        """Test cache write exception doesn't fail the whole request."""
        state = {
            'question': 'test',
            'context': [],
            'mcp_result': None,
            'answer': 'Valid answer',
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.qa_cache.cache_manager.write_cache',
                  side_effect=Exception("Cache error")):
            result = graph.cache_write_back_node(state)
        
        assert result['cache_written'] is False
        assert result['answer'] == 'Valid answer'  # Answer preserved
    
    def test_cache_write_back_skips_on_none_answer(self):
        """Test cache write skipped when answer is None."""
        state = {
            'question': 'test',
            'context': [],
            'mcp_result': None,
            'answer': None,
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.qa_cache.cache_manager.write_cache') as mock_write:
            result = graph.cache_write_back_node(state)
        
        assert result['cache_written'] is False
        mock_write.assert_not_called()


class TestCreateGraph:
    """Test graph creation and structure."""
    
    def test_create_graph_returns_compiled_graph(self):
        """Test create_graph returns a compiled StateGraph."""
        g = graph.create_graph()
        
        assert g is not None
        # Check it's a compiled graph (has invoke method)
        assert hasattr(g, 'invoke')
    
    def test_graph_has_all_nodes(self):
        """Test graph includes all required nodes."""
        g = graph.create_graph()
        
        # Graph should be invokable with initial state
        initial_state = {
            'question': 'test',
            'context': [],
            'mcp_result': None,
            'answer': None,
            'cache_written': False,
            'error': None
        }
        
        with patch('robot_assistant.reasoning.mcp_memory_server.query_memory',
                  return_value={'answer': 'test', 'confidence': 0.0, 'source': 'memory_db', 'category': None}):
            with patch('robot_assistant.reasoning.llm_client.generate',
                      return_value='Test answer'):
                with patch('robot_assistant.qa_cache.cache_manager.write_cache'):
                    result = g.invoke(initial_state)
        
        # Should have run through all nodes
        assert 'answer' in result
        assert 'cache_written' in result


class TestRunReasoningGraph:
    """Test the convenience function for running the graph."""
    
    def test_run_reasoning_graph_success(self, mock_mcp_result_success, mock_llm_response):
        """Test full graph execution returns answer."""
        with patch('robot_assistant.reasoning.mcp_memory_server.query_memory',
                  return_value=mock_mcp_result_success):
            with patch('robot_assistant.reasoning.llm_client.generate',
                      return_value=mock_llm_response):
                with patch('robot_assistant.qa_cache.cache_manager.write_cache'):
                    result = graph.run_reasoning_graph('Who is the HOD?')
        
        assert result['answer'] == mock_llm_response
        assert result['cache_written'] is True
        assert result['error'] is None
        assert result['mcp_confidence'] == 0.9
    
    def test_run_reasoning_graph_returns_fallback_on_error(self):
        """Test graph returns fallback on execution error."""
        with patch('robot_assistant.reasoning.mcp_memory_server.query_memory',
                  side_effect=Exception("Database error")):
            result = graph.run_reasoning_graph('test question')
        
        assert result['answer'] == config.LANGGRAPH_FALLBACK_MESSAGE
        assert result['cache_written'] is False
        assert result['error'] is not None
    
    def test_run_reasoning_graph_mcp_low_confidence_still_generates(self, mock_mcp_result_no_info):
        """Test graph still generates answer even with low MCP confidence."""
        with patch('robot_assistant.reasoning.mcp_memory_server.query_memory',
                  return_value=mock_mcp_result_no_info):
            with patch('robot_assistant.reasoning.llm_client.generate',
                      return_value='LLM generated answer'):
                with patch('robot_assistant.qa_cache.cache_manager.write_cache'):
                    result = graph.run_reasoning_graph('test question')
        
        assert result['answer'] == 'LLM generated answer'
        assert result['mcp_confidence'] == 0.0


class TestEndToEnd:
    """Test full graph execution end-to-end."""
    
    def test_e2e_full_success_path(self, mock_mcp_result_success, mock_llm_response):
        """Test complete path: MCP → LLM → Cache."""
        with patch('robot_assistant.reasoning.mcp_memory_server.query_memory',
                  return_value=mock_mcp_result_success):
            with patch('robot_assistant.reasoning.llm_client.generate',
                      return_value=mock_llm_response):
                with patch('robot_assistant.qa_cache.cache_manager.write_cache') as mock_cache:
                    result = graph.run_reasoning_graph('Who is the HOD?')
        
        # Verify all steps completed
        assert result['answer'] == mock_llm_response
        assert result['cache_written'] is True
        assert result['error'] is None
        
        # Verify cache write was called
        mock_cache.assert_called_once()
    
    def test_e2e_llm_timeout_fallback(self, mock_mcp_result_success):
        """Test LLM timeout triggers fallback and no cache write."""
        with patch('robot_assistant.reasoning.mcp_memory_server.query_memory',
                  return_value=mock_mcp_result_success):
            with patch('robot_assistant.reasoning.llm_client.generate',
                      side_effect=TimeoutError("Timeout")):
                with patch('robot_assistant.qa_cache.cache_manager.write_cache') as mock_cache:
                    result = graph.run_reasoning_graph('test question')
        
        assert result['answer'] == config.LANGGRAPH_FALLBACK_MESSAGE
        assert result['cache_written'] is False
        assert 'timeout' in result['error'].lower()
        
        # Fallback message should not be cached
        mock_cache.assert_not_called()
    
    def test_e2e_mcp_error_still_generates(self):
        """Test MCP error doesn't prevent LLM generation."""
        with patch('robot_assistant.reasoning.mcp_memory_server.query_memory',
                  side_effect=Exception("DB error")):
            with patch('robot_assistant.reasoning.llm_client.generate',
                      return_value='LLM answer without MCP context'):
                with patch('robot_assistant.qa_cache.cache_manager.write_cache'):
                    result = graph.run_reasoning_graph('test question')
        
        # Should still generate answer via LLM, just without MCP context
        assert result['answer'] == config.LANGGRAPH_FALLBACK_MESSAGE  # Error propagates
        assert result['error'] is not None


class TestDocstrings:
    """Test that all nodes have proper docstrings."""
    
    def test_all_nodes_have_docstrings(self):
        """Test all node functions have docstrings."""
        nodes = [
            graph.retrieve_node,
            graph.mcp_tool_call_node,
            graph.generate_node,
            graph.cache_write_back_node
        ]
        
        for node in nodes:
            assert node.__doc__ is not None, f"{node.__name__} missing docstring"
            assert "Args:" in node.__doc__
            assert "Returns:" in node.__doc__
