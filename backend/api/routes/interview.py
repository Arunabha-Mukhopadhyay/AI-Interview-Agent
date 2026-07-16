"""
api/routes/interview.py
WebSocket endpoint for the real-time voice interview.

Flow:
1. Client connects with a specific session_id.
2. Backend loads the session and sends an initial greeting (Approach 1: hardcoded for speed).
3. Loop:
   - Receive audio chunk from client.
   - Convert audio to text (STT).
   - Pass text to LangGraph orchestrator (agents/graph.py).
   - Get agent's text response.
   - Convert text to audio (TTS).
   - Send audio chunk back to client.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage

from core.logging import get_logger
from db.session import get_db
from db.models import InterviewSession
from agents.graph import interview_agent
from voice.stt import transcribe_audio
from voice.tts import generate_audio

logger = get_logger(__name__)

router = APIRouter(prefix="/interview", tags=["Interview"])

@router.websocket("/ws/{session_id}")
async def websocket_interview_endpoint(websocket: WebSocket, session_id: str, db: Session = Depends(get_db)):
    """
    Real-time bidirectional audio stream for the interview.
    """
    await websocket.accept()
    logger.info("WebSocket connected for session: %s", session_id)
    
    # 1. Verify session exists
    session_row = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session_row:
        logger.warning("Session %s not found. Closing connection.", session_id)
        await websocket.close(code=1008, reason="Session not found")
        return

    # 2. Initialize conversation state for LangGraph
    # We maintain this state in memory for the duration of the WebSocket connection.
    # If the connection drops, we'd ideally load this from Postgres/Redis to resume.
    graph_state = {
        "session_id": session_id,
        "messages": [],
        "context_docs": "",
        "gap_analysis": "",
        "current_stage": "intro"
    }
    
    try:
        # 3. Initial Greeting (Approach 1: Hardcoded for zero latency)
        intro_text = (
            "Hi there! I'm your AI interviewer. "
            "I've reviewed your background. "
            "To get us started, could you briefly introduce yourself?"
        )
        logger.info("Sending initial greeting for session: %s", session_id)
        
        # Add the intro to our state so the LLM knows we said it
        # Note: We don't invoke the graph here, we just append to the state manually.
        from langchain_core.messages import AIMessage
        graph_state["messages"].append(AIMessage(content=intro_text))
        
        # Generate and send the audio for the greeting
        intro_audio = await generate_audio(intro_text)
        await websocket.send_bytes(intro_audio)
        
        # 4. Main Conversation Loop
        while True:
            # A. Receive audio from the user
            # In a real implementation, you might receive a stream of small chunks 
            # and use a VAD (Voice Activity Detector) to know when they stop speaking.
            # For simplicity, we assume one complete utterance per websocket message.
            user_audio_chunk = await websocket.receive_bytes()
            logger.debug("Received audio chunk from user (%d bytes)", len(user_audio_chunk))
            
            # B. Speech-to-Text (User Audio -> Text)
            user_text = await transcribe_audio(user_audio_chunk)
            logger.info("User said: %s", user_text)
            
            # C. LangGraph Agent (User Text -> Agent Text)
            # We append the user's message to the state and invoke the graph
            graph_state["messages"].append(HumanMessage(content=user_text))
            
            logger.debug("Invoking LangGraph agent...")
            result = interview_agent.invoke(graph_state)
            
            # Update our local state with the result from the graph
            graph_state = result
            
            # The agent's response is the last message in the state
            agent_text = graph_state["messages"][-1].content
            logger.info("Agent said: %s", agent_text)
            
            # D. Text-to-Speech (Agent Text -> Audio)
            agent_audio = await generate_audio(agent_text)
            
            # E. Send audio back to the user
            await websocket.send_bytes(agent_audio)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session: %s", session_id)
        # Here you would typically persist the final graph_state["messages"] to Postgres
        # so you have a transcript of the interview.
    except Exception as e:
        logger.error("Error in WebSocket for session %s: %s", session_id, e)
        await websocket.close(code=1011, reason="Internal server error")
