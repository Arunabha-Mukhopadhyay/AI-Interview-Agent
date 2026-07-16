"""
voice/stt.py
Speech-to-Text integration.
Converts incoming audio bytes from the user into text.
"""
import io
from core.logging import get_logger
from core.config import get_settings

logger = get_logger(__name__)

async def transcribe_audio(audio_chunk: bytes) -> str:
    """
    Takes an audio chunk from the WebSocket and converts it to text.
    Using AssemblyAI for high-accuracy speech-to-text.
    """
    settings = get_settings()
    
    if not settings.ASSEMBLYAI_API_KEY:
        logger.warning("ASSEMBLYAI_API_KEY not set. Returning placeholder text.")
        return "This is a placeholder transcript. Please configure your AssemblyAI API key."
        
    logger.info("Transcribing audio chunk of size %d bytes", len(audio_chunk))
    
    try:
        import assemblyai as aai
        
        # Configure API key
        aai.settings.api_key = settings.ASSEMBLYAI_API_KEY
        
        # We need to treat the raw bytes as a file-like object so AssemblyAI can upload it
        # Note: AssemblyAI's async transcriber works best with valid audio files. 
        # In a production WebSocket setting with continuous streaming, you would use their RealtimeTranscriber.
        # For this chunk-by-chunk approach, we assume the frontend sends a complete audio blob (e.g. webm/wav).
        audio_stream = io.BytesIO(audio_chunk)
        
        # We use aai.Transcriber().transcribe()
        transcriber = aai.Transcriber()
        
        # Run transcription (this is blocking under the hood, but we are running in an async endpoint)
        # Ideally, we should run this in a threadpool to prevent blocking the event loop:
        import asyncio
        loop = asyncio.get_event_loop()
        
        # Run the synchronous transcribe function in a background thread
        transcript = await loop.run_in_executor(None, transcriber.transcribe, audio_stream)
        
        if transcript.error:
            logger.error("AssemblyAI transcription error: %s", transcript.error)
            return ""
            
        logger.debug("Successfully transcribed: '%s'", transcript.text)
        return transcript.text or ""
        
    except Exception as e:
        logger.error("AssemblyAI transcription failed: %s", e)
        return ""
