"""
parsing/validators.py
URL validation helpers shared by GitHub and LinkedIn parsers.
"""
import re
from urllib.parse import urlparse

# ─────────────────────────────────────────────────────────────────────────────
# GitHub
# ─────────────────────────────────────────────────────────────────────────────

_GITHUB_RE = re.compile(
    r"^https?://(www\.)?github\.com/(?P<username>[A-Za-z0-9](?:[A-Za-z0-9\-]{0,37}[A-Za-z0-9])?)(/[^/?#]*)?$"
)


def validate_github_url(url: str) -> str:
    """
    Validate and normalise a GitHub profile/repo URL.

    Returns the cleaned URL on success.
    Raises ValueError with a descriptive message on failure.
    """
    if not url or not isinstance(url, str):
        raise ValueError("GitHub URL must be a non-empty string.")

    url = url.strip().rstrip("/")

    # Ensure scheme is present
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    host = parsed.netloc.lower().lstrip("www.")

    if host != "github.com":
        raise ValueError(f"URL does not point to github.com: {url!r}")

    m = _GITHUB_RE.match(url)
    if not m:
        raise ValueError(
            f"Malformed GitHub URL: {url!r}. Expected format: https://github.com/<username>"
        )

    return url


def extract_github_username(url: str) -> str:
    """Extract the username portion from a validated GitHub URL."""
    url = validate_github_url(url)
    parsed = urlparse(url)
    # path = /username  or  /username/repo
    parts = parsed.path.strip("/").split("/")
    return parts[0]


# ─────────────────────────────────────────────────────────────────────────────
# LinkedIn
# ─────────────────────────────────────────────────────────────────────────────

_LINKEDIN_RE = re.compile(
    r"^https?://(www\.|[a-z]{2}\.)?linkedin\.com/in/(?P<slug>[A-Za-z0-9\-_%]+)/?$"
)


def validate_linkedin_url(url: str) -> str:
    """
    Validate and normalise a LinkedIn public profile URL.

    Returns the cleaned URL on success.
    Raises ValueError with a descriptive message on failure.
    """
    if not url or not isinstance(url, str):
        raise ValueError("LinkedIn URL must be a non-empty string.")

    url = url.strip().rstrip("/")

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    host = parsed.netloc.lower().lstrip("www.")

    if "linkedin.com" not in host:
        raise ValueError(f"URL does not point to linkedin.com: {url!r}")

    m = _LINKEDIN_RE.match(url)
    if not m:
        raise ValueError(
            f"Malformed LinkedIn URL: {url!r}. Expected format: https://www.linkedin.com/in/<username>"
        )

    return url


def extract_linkedin_slug(url: str) -> str:
    """Extract the profile slug from a validated LinkedIn URL."""
    url = validate_linkedin_url(url)
    parsed = urlparse(url)
    # path = /in/slug
    parts = parsed.path.strip("/").split("/")
    # parts[0] == 'in', parts[1] == slug
    return parts[1] if len(parts) > 1 else parts[0]
