"""
core/llm.py
LLM factory — returns a LangChain chat model based on configured provider.
Import get_llm() wherever you need the model.
"""
from functools import lru_cache
from langchain_core.language_models import BaseChatModel
from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


def get_llm(temperature: float = 0.3) -> BaseChatModel:
    """Return a chat model from the configured provider."""
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        logger.info("Using OpenAI LLM: %s", settings.LLM_MODEL)
        return ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=temperature,
            api_key=settings.OPENAI_API_KEY,
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        logger.info("Using Groq LLM: %s", settings.LLM_MODEL)
        return ChatGroq(
            model=settings.LLM_MODEL,
            temperature=temperature,
            api_key=settings.GROQ_API_KEY,
        )
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        logger.info("Using Google GenAI LLM: %s", settings.LLM_MODEL)
        return ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            temperature=temperature,
            google_api_key=settings.GOOGLE_API_KEY,
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Use 'openai', 'groq', or 'google'.")
