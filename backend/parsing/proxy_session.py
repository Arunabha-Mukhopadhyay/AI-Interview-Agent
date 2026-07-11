"""
parsing/proxy_session.py
Shared proxy-session factory.

Two modes:
  1. USE_PROXY_ROTATION=True  → spins up an AWS API Gateway endpoint via
     requests-ip-rotator (rotates source IP to avoid rate-limits).
  2. USE_PROXY_ROTATION=False → plain requests.Session with browser-like
     headers (sufficient for GitHub API; LinkedIn blocks headless access
     regardless of IP).

NOTE: requests_ip_rotator requires valid AWS credentials and the endpoint
      must be created/destroyed per host.  Always call .shutdown() when done.
"""
from __future__ import annotations

import contextlib
from typing import Generator

import requests

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@contextlib.contextmanager
def get_proxy_session(target_url: str) -> Generator[requests.Session, None, None]:
    """
    Context manager that yields a requests.Session configured for the target URL.

    Usage:
        with get_proxy_session("https://github.com") as session:
            resp = session.get(url)
    """
    settings = get_settings()

    if settings.USE_PROXY_ROTATION:
        try:
            from requests_ip_rotator import ApiGateway  # type: ignore

            logger.info("Starting IP-rotation gateway for %s", target_url)
            gateway = ApiGateway(
                target_url,
                access_key_id=settings.AWS_ACCESS_KEY_ID,
                access_key_secret=settings.AWS_SECRET_ACCESS_KEY,
                regions=[settings.AWS_REGION],
            )
            gateway.start()
            session = requests.Session()
            session.mount(target_url, gateway)
            session.headers.update(_HEADERS)
            try:
                yield session
            finally:
                logger.info("Shutting down IP-rotation gateway")
                gateway.shutdown()
            return
        except ImportError:
            logger.warning(
                "requests_ip_rotator not installed; falling back to plain session."
            )

    # Fallback — plain session
    session = requests.Session()
    session.headers.update(_HEADERS)
    yield session
