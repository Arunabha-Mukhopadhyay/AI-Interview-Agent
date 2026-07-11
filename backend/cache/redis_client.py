"""
cache/redis_client.py
Redis caching utilities.

Usage:
    from cache.redis_client import cache_set, cache_get, cache_delete, make_key

    # Store parsed metadata for 1 hour
    cache_set(make_key("github", session_id), data_dict)

    # Retrieve later
    data = cache_get(make_key("github", session_id))
"""
from __future__ import annotations

import json
from typing import Any

import redis

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Singleton client
# ─────────────────────────────────────────────────────────────────────────────

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return a singleton Redis client. Lazy-initialised on first call."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        logger.info("Connecting to Redis: %s", settings.REDIS_URL)
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis_client


# ─────────────────────────────────────────────────────────────────────────────
# Key builder
# ─────────────────────────────────────────────────────────────────────────────

def make_key(prefix: str, session_id: str) -> str:
    """
    Build a namespaced cache key.

    Examples:
        make_key("github",   "abc123")  →  "vai:github:abc123"
        make_key("linkedin", "abc123")  →  "vai:linkedin:abc123"
        make_key("resume",   "abc123")  →  "vai:resume:abc123"
        make_key("jd",       "abc123")  →  "vai:jd:abc123"
    """
    return f"vai:{prefix}:{session_id}"


# ─────────────────────────────────────────────────────────────────────────────
# Cache operations
# ─────────────────────────────────────────────────────────────────────────────

def cache_set(key: str, value: Any, ttl: int | None = None) -> bool:
    """
    Serialise `value` to JSON and store in Redis with optional TTL.

    Args:
        key  : cache key (use make_key() to build it)
        value: any JSON-serialisable object
        ttl  : seconds until expiry (defaults to settings.CACHE_TTL_SECONDS)

    Returns True on success, False on Redis error (non-fatal).
    """
    settings = get_settings()
    expiry = ttl if ttl is not None else settings.CACHE_TTL_SECONDS
    try:
        r = get_redis()
        r.setex(key, expiry, json.dumps(value, default=str))
        logger.debug("cache_set: %s (ttl=%ds)", key, expiry)
        return True
    except Exception as exc:
        logger.warning("cache_set failed for %s: %s", key, exc)
        return False


def cache_get(key: str) -> Any | None:
    """
    Retrieve and deserialise a cached value.

    Returns None if the key does not exist or Redis is unavailable.
    """
    try:
        r = get_redis()
        raw = r.get(key)
        if raw is None:
            logger.debug("cache_miss: %s", key)
            return None
        logger.debug("cache_hit: %s", key)
        return json.loads(raw)
    except Exception as exc:
        logger.warning("cache_get failed for %s: %s", key, exc)
        return None


def cache_delete(key: str) -> bool:
    """Invalidate a cached entry. Returns True if deleted, False otherwise."""
    try:
        r = get_redis()
        deleted = r.delete(key)
        logger.debug("cache_delete: %s (deleted=%d)", key, deleted)
        return bool(deleted)
    except Exception as exc:
        logger.warning("cache_delete failed for %s: %s", key, exc)
        return False


def cache_exists(key: str) -> bool:
    """Check if a key exists in Redis without fetching the value."""
    try:
        return bool(get_redis().exists(key))
    except Exception:
        return False
