"""
vectorStore/embeddings.py
Embedding model factory — returns a LangChain Embeddings object.
All vector store operations import get_embeddings() from here.
"""
from functools import lru_cache

from langchain_core.embeddings import Embeddings
from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


@lru_cache()
def get_embeddings() -> Embeddings:
    """Return a cached embedding model based on configured provider."""
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower()
    model = settings.EMBEDDING_MODEL

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        logger.info("Using OpenAI Embeddings: %s", model)
        return OpenAIEmbeddings(model=model, api_key=settings.OPENAI_API_KEY)

    elif provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        logger.info("Using Google GenAI Embeddings: %s", model)
        return GoogleGenerativeAIEmbeddings(
            model=model or "models/embedding-001",
            google_api_key=settings.GOOGLE_API_KEY,
        )

    elif provider == "groq":
        # Groq doesn't provide embeddings. Run FastEmbed locally (no PyTorch dependencies!)
        logger.info("Using local FastEmbed embeddings for Groq: %s", model)
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        return FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")

    else:
        raise ValueError(f"Unknown LLM_PROVIDER for embeddings: {provider!r}")
