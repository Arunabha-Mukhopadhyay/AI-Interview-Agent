"""
agents/nodes.py
The individual execution steps (nodes) for the LangGraph orchestrator.
"""
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from core.llm import get_llm
from core.logging import get_logger
from vectorStore.indexer import query_session
from agents.state import InterviewState
from agents.prompts import GAP_ANALYSIS_PROMPT, INTERVIEW_SYSTEM_PROMPT

logger = get_logger(__name__)


def retrieve_context_node(state: InterviewState) -> Dict[str, Any]:
    """
    Retrieves context from ChromaDB based on the latest user message.
    If it's the very first turn, fetches a broad summary of the documents.
    """
    session_id = state["session_id"]
    messages = state["messages"]
    
    # If no messages exist yet, or just starting, we do a broad query
    if not messages:
        query_text = "job description requirements and candidate resume skills"
    else:
        # Get the latest message from the user
        last_message = messages[-1].content if messages else "job description"
        query_text = str(last_message)

    # Query ChromaDB for this session
    logger.info("Retrieving context for session %s using query: %s", session_id, query_text[:50])
    results = query_session(session_id=session_id, query_text=query_text, n_results=10)
    
    # Format the retrieved chunks into a single string
    docs_text = "\n\n".join([f"Source ({res['metadata'].get('type')}): {res['text']}" for res in results])
    if not docs_text:
        docs_text = "No context documents found for this session."
        
    return {"context_docs": docs_text}


def gap_analysis_node(state: InterviewState) -> Dict[str, Any]:
    """
    Performs gap analysis once at the start of the interview (or when needed).
    Compares JD to candidate profile.
    """
    # If we already have a gap analysis, we don't need to re-run it every turn
    if state.get("gap_analysis"):
        return {}
        
    logger.info("Running gap analysis for session %s", state["session_id"])
    llm = get_llm(temperature=0.1) # low temp for analytical task
    
    prompt = GAP_ANALYSIS_PROMPT.format(context_docs=state["context_docs"])
    response = llm.invoke([SystemMessage(content=prompt)])
    
    return {"gap_analysis": str(response.content)}


def generate_response_node(state: InterviewState) -> Dict[str, Any]:
    """
    The main conversation node. Takes context, gap analysis, and history,
    and generates the agent's next spoken response.
    """
    logger.info("Generating interview response for session %s", state["session_id"])
    llm = get_llm(temperature=0.7) # slightly higher temp for conversational tone
    
    stage = state.get("current_stage", "intro")
    
    sys_prompt_text = INTERVIEW_SYSTEM_PROMPT.format(
        current_stage=stage,
        context_docs=state.get("context_docs", ""),
        gap_analysis=state.get("gap_analysis", "No gaps identified.")
    )
    
    # Build the full message list for the LLM
    # System Prompt -> History -> LLM Call
    llm_messages = [SystemMessage(content=sys_prompt_text)]
    llm_messages.extend(state["messages"])
    
    response = llm.invoke(llm_messages)
    
    # Update the stage if needed (very simple heuristic for now)
    next_stage = stage
    if stage == "intro" and len(state["messages"]) >= 2:
        next_stage = "clarifying"
        
    return {
        "messages": [response], # add_messages reducer will append this
        "current_stage": next_stage
    }
