"""LangGraph reasoning workflow for Path C (LLM branch).

Simple linear graph: Retrieve → Tool Call → Generate → Cache Write-Back
with timeout protection and fallback messaging.
"""

from typing import Dict, List, Optional, TypedDict, Annotated
import operator
from robot_assistant.config import config
from robot_assistant.reasoning import llm_client, mcp_memory_server
from robot_assistant.qa_cache import cache_manager


class GraphState(TypedDict):
    """State object passed through the graph nodes.
    
    Attributes:
        question: Original user question
        context: Retrieved context for LLM
        mcp_result: Result from MCP tool call
        answer: Final generated answer
        cache_written: Whether answer was written to cache
        error: Error message if any step failed
    """
    question: str
    context: Annotated[List[str], operator.add]  # Accumulated context
    mcp_result: Optional[Dict]
    answer: Optional[str]
    cache_written: bool
    error: Optional[str]


def retrieve_node(state: GraphState) -> GraphState:
    """Retrieve relevant context for the question.
    
    Currently a stub that will be replaced with vector search in Phase 5.
    For now, returns empty context list.
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with context field populated
    """
    # Stub: Will be vector search in Phase 5
    # For now, just pass through with empty context
    state['context'] = []
    return state


def mcp_tool_call_node(state: GraphState) -> GraphState:
    """Call MCP memory server tool to retrieve facts.
    
    Queries the memory database for facts related to the question.
    This is the primary knowledge source for the LLM.
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with mcp_result populated
    """
    question = state['question']
    
    try:
        # Call MCP memory server
        result = mcp_memory_server.query_memory(question)
        state['mcp_result'] = result
        
        # Add MCP answer to context if confidence is reasonable
        if result.get('confidence', 0.0) > 0.5 and result.get('answer'):
            state['context'].append(f"Memory: {result['answer']}")
        
    except Exception as e:
        state['error'] = f"MCP tool error: {str(e)}"
        state['mcp_result'] = None
    
    return state


def generate_node(state: GraphState) -> GraphState:
    """Generate answer using LLM with retrieved context.
    
    Constructs prompt from question and context, calls LLM via Ollama.
    Falls back to generic message if LLM fails or times out.
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with answer populated
    """
    question = state['question']
    context = state.get('context', [])
    mcp_result = state.get('mcp_result')
    
    # Check if we already have an error
    if state.get('error'):
        state['answer'] = config.LANGGRAPH_FALLBACK_MESSAGE
        return state
    
    # Build context string
    context_str = '\n'.join(context) if context else 'No additional context available.'
    
    # Build prompt
    prompt = f"""You are a helpful college assistant. Answer the following question concisely and accurately.

Question: {question}

Context:
{context_str}

Answer (be brief and direct):"""
    
    try:
        # Call LLM with timeout
        answer = llm_client.generate(
            prompt=prompt,
            context=None,  # Context already in prompt
            timeout=config.LLM_TIMEOUT_SECONDS
        )
        
        state['answer'] = answer.strip() if answer else config.LANGGRAPH_FALLBACK_MESSAGE
        
    except TimeoutError:
        state['error'] = "LLM timeout"
        state['answer'] = config.LANGGRAPH_FALLBACK_MESSAGE
    except Exception as e:
        state['error'] = f"LLM error: {str(e)}"
        state['answer'] = config.LANGGRAPH_FALLBACK_MESSAGE
    
    return state


def cache_write_back_node(state: GraphState) -> GraphState:
    """Write generated answer back to cache for future hits.
    
    Writes to both exact and semantic caches with current data version.
    Only writes if answer was successfully generated (not a fallback).
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with cache_written flag set
    """
    question = state['question']
    answer = state.get('answer')
    error = state.get('error')
    
    # Only write to cache if we have a real answer (not fallback due to error)
    if answer and not error and answer != config.LANGGRAPH_FALLBACK_MESSAGE:
        try:
            cache_manager.write_cache(question, answer)
            state['cache_written'] = True
        except Exception as e:
            # Don't fail the whole request if cache write fails
            # Just log and continue
            state['cache_written'] = False
    else:
        state['cache_written'] = False
    
    return state


def create_graph():
    """Create the LangGraph reasoning workflow.
    
    Linear flow: retrieve → mcp_tool_call → generate → cache_write_back
    
    Returns:
        Compiled StateGraph ready for execution
    """
    from langgraph.graph import StateGraph, END
    
    # Create graph
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("mcp_tool_call", mcp_tool_call_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("cache_write_back", cache_write_back_node)
    
    # Set entry point
    workflow.set_entry_point("retrieve")
    
    # Add edges (linear flow)
    workflow.add_edge("retrieve", "mcp_tool_call")
    workflow.add_edge("mcp_tool_call", "generate")
    workflow.add_edge("generate", "cache_write_back")
    workflow.add_edge("cache_write_back", END)
    
    # Compile and return
    return workflow.compile()


def run_reasoning_graph(question: str) -> Dict[str, any]:
    """Run the reasoning graph for a question.
    
    Convenience function that creates state, runs graph, and returns result.
    
    Args:
        question: User's question
    
    Returns:
        dict with keys:
            - answer (str): Generated answer
            - cache_written (bool): Whether answer was cached
            - error (str | None): Error message if any
            - mcp_confidence (float): Confidence from MCP tool
    """
    # Create initial state
    initial_state: GraphState = {
        'question': question,
        'context': [],
        'mcp_result': None,
        'answer': None,
        'cache_written': False,
        'error': None
    }
    
    # Create and run graph
    graph = create_graph()
    
    try:
        # Run with timeout
        final_state = graph.invoke(initial_state)
        
        return {
            'answer': final_state.get('answer', config.LANGGRAPH_FALLBACK_MESSAGE),
            'cache_written': final_state.get('cache_written', False),
            'error': final_state.get('error'),
            'mcp_confidence': final_state.get('mcp_result', {}).get('confidence', 0.0) if final_state.get('mcp_result') else 0.0
        }
        
    except Exception as e:
        return {
            'answer': config.LANGGRAPH_FALLBACK_MESSAGE,
            'cache_written': False,
            'error': f"Graph execution error: {str(e)}",
            'mcp_confidence': 0.0
        }
