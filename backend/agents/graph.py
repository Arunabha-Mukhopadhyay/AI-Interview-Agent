"""
agents/graph.py
Builds and compiles the LangGraph StateGraph for the Interview Agent.
"""
from langgraph.graph import StateGraph, START, END

from agents.state import InterviewState
from agents.nodes import retrieve_context_node, gap_analysis_node, generate_response_node


def build_interview_graph():
    """
    Constructs the LangGraph workflow for a single turn of conversation.
    
    Flow:
    START -> retrieve_context -> gap_analysis -> generate_response -> END
    """
    # 1. Initialize the StateGraph with our InterviewState schema
    workflow = StateGraph(InterviewState)
    
    # 2. Add the nodes (our python functions)
    workflow.add_node("retrieve_context", retrieve_context_node)
    workflow.add_node("gap_analysis", gap_analysis_node)
    workflow.add_node("generate_response", generate_response_node)
    
    # 3. Define the edges (the flow)
    # Start by fetching context relevant to the user's latest message
    workflow.add_edge(START, "retrieve_context")
    
    # After context is retrieved, analyze gaps (it skips internally if already done)
    workflow.add_edge("retrieve_context", "gap_analysis")
    
    # After gaps are analyzed, generate the LLM response
    workflow.add_edge("gap_analysis", "generate_response")
    
    # After generating the response, this turn is over. Wait for user audio again.
    workflow.add_edge("generate_response", END)
    
    # 4. Compile the graph into an executable application
    return workflow.compile()

# Instantiate the compiled graph so it can be imported and invoked by the WebSocket route
interview_agent = build_interview_graph()
