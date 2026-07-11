"""
core/config.py
Central config loaded from environment / .env file.
All modules should import settings from here — never read os.environ directly.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Voice Agent Interview Platform"
    DEBUG: bool = False

    # ── LLM ──────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    LLM_PROVIDER: str = "openai"          # "openai" | "groq" | "google"
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ── Vector store (ChromaDB) ───────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION_NAME: str = "interview_docs"

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    POSTGRES_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/voice_agent"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 3600        # 1 hour default cache TTL

    # ── GitHub ────────────────────────────────────────────────────────────────
    GITHUB_TOKEN: str = ""               # Personal access token (optional, avoids rate-limit)

    # ── Proxy rotation (AWS API Gateway) ─────────────────────────────────────
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    USE_PROXY_ROTATION: bool = False     # set True to enable requests-ip-rotator


@lru_cache()
def get_settings() -> Settings:
    return Settings()
