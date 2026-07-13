"""
agents/state.py
Defines the state structure for the LangGraph orchestrator.
This is the "memory" that gets passed between all nodes in the graph.
"""
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class InterviewState(TypedDict):
    """
    State definition for the Interview Agent.
    
    Attributes:
        session_id: The UUID of the current interview session.
        messages: The conversation history (User and AI messages).
                  The `add_messages` reducer handles appending new messages properly.
        context_docs: Formatted text of retrieved context (resume, github, jd).
        gap_analysis: LLM's internal analysis of what is missing from the candidate's profile.
        current_stage: Where we are in the interview ("intro", "technical", "clarifying", "closing").
    """
    
    session_id: str
    
    # Conversation history
    # Annotated[Sequence[BaseMessage], add_messages] tells LangGraph 
    # to automatically append new messages to the existing list rather than overwriting it.
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Retrieved data from ChromaDB/Postgres
    context_docs: str
    
    # Internal agent reasoning
    gap_analysis: str
    
    # Workflow tracking
    current_stage: str
