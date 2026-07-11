"""
parsing/Github_parser.py
GitHub profile + repository metadata extractor.

Strategy:
  - Uses PyGithub (authenticated via GITHUB_TOKEN) for the primary API calls
    (avoids rate-limits far more reliably than IP rotation against the API).
  - Falls back to the proxy session for fetching the profile README HTML when
    needed.
  - URL is validated before any network call is made.

Output shape (dict):
    {
        "username": str,
        "profile_url": str,
        "bio": str | None,
        "public_repos_count": int,
        "followers": int,
        "following": int,
        "top_languages": {"Python": 12, ...},   # aggregated across top repos
        "pinned_repos": [{name, description, stars, forks, url, language}],
        "top_repos": [...],                      # top-10 by stars
        "readme_text": str | None,               # profile README if present
        "raw_text": str,                         # flat text for embedding
    }
"""
from __future__ import annotations

from typing import Any

from core.config import get_settings
from core.logging import get_logger
from parsing.validators import validate_github_url, extract_github_username
from parsing.proxy_session import get_proxy_session

logger = get_logger(__name__)

_TOP_N_REPOS = 10


def _build_raw_text(data: dict) -> str:
    """Flatten metadata dict into a single text blob for embedding."""
    lines = [
        f"GitHub Profile: {data['profile_url']}",
        f"Username: {data['username']}",
    ]
    if data.get("bio"):
        lines.append(f"Bio: {data['bio']}")
    if data.get("top_languages"):
        lang_str = ", ".join(f"{k} ({v} repos)" for k, v in data["top_languages"].items())
        lines.append(f"Top Languages: {lang_str}")
    for repo in data.get("top_repos", []):
        lines.append(
            f"Repo: {repo['name']} | Stars: {repo['stars']} | "
            f"Language: {repo.get('language', 'N/A')} | {repo.get('description', '')}"
        )
    if data.get("readme_text"):
        lines.append("\n--- Profile README ---")
        lines.append(data["readme_text"][:3000])  # cap at 3k chars
    return "\n".join(lines)


def _fetch_readme_via_api(user) -> str | None:
    """Try to get profile README from <username>/<username> repo."""
    try:
        repo = user.get_repo(user.login)
        contents = repo.get_contents("README.md")
        return contents.decoded_content.decode("utf-8", errors="ignore")
    except Exception:
        return None


def parse_github(github_url: str) -> dict[str, Any]:
    """
    Parse a GitHub profile URL and return structured metadata + raw_text.

    Raises ValueError for malformed URLs.
    Raises RuntimeError if the GitHub API call fails.
    """
    # ── 1. Validate URL ───────────────────────────────────────────────────────
    clean_url = validate_github_url(github_url)
    username = extract_github_username(clean_url)
    logger.info("Parsing GitHub profile: %s", username)

    settings = get_settings()

    # ── 2. Fetch via PyGithub (uses token if available) ───────────────────────
    try:
        from github import Github, GithubException  # type: ignore

        token = settings.GITHUB_TOKEN or None
        gh = Github(token) if token else Github()  # unauthenticated = 60 req/hr
        logger.info("GitHub API: %s mode", "authenticated" if token else "unauthenticated")

        user = gh.get_user(username)

        # ── Repos ──────────────────────────────────────────────────────────────
        repos = sorted(
            [r for r in user.get_repos() if not r.fork],
            key=lambda r: r.stargazers_count,
            reverse=True,
        )[:_TOP_N_REPOS]

        top_repos = [
            {
                "name": r.name,
                "description": r.description or "",
                "stars": r.stargazers_count,
                "forks": r.forks_count,
                "language": r.language,
                "url": r.html_url,
            }
            for r in repos
        ]

        # ── Language aggregation ───────────────────────────────────────────────
        lang_counter: dict[str, int] = {}
        for r in repos:
            if r.language:
                lang_counter[r.language] = lang_counter.get(r.language, 0) + 1

        # ── Profile README ─────────────────────────────────────────────────────
        readme = _fetch_readme_via_api(user)

        data: dict[str, Any] = {
            "username": username,
            "profile_url": clean_url,
            "bio": user.bio,
            "public_repos_count": user.public_repos,
            "followers": user.followers,
            "following": user.following,
            "top_languages": dict(
                sorted(lang_counter.items(), key=lambda x: x[1], reverse=True)
            ),
            "pinned_repos": top_repos[:6],   # first 6 as "pinned"
            "top_repos": top_repos,
            "readme_text": readme,
        }
        data["raw_text"] = _build_raw_text(data)
        return data

    except Exception as exc:
        logger.error("GitHub API fetch failed for %s: %s", username, exc)
        # ── Fallback: minimal scrape via proxy session ────────────────────────
        return _scrape_fallback(username, clean_url)


def _scrape_fallback(username: str, profile_url: str) -> dict[str, Any]:
    """
    Last-resort: hit the public GitHub profile page via the proxy session
    and extract minimal info from HTML (bio, public repos count).
    """
    logger.warning("Using HTML scrape fallback for GitHub user: %s", username)
    bio = None
    try:
        from bs4 import BeautifulSoup  # type: ignore

        with get_proxy_session("https://github.com") as session:
            resp = session.get(profile_url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            bio_tag = soup.find("div", class_="p-note")
            if bio_tag:
                bio = bio_tag.get_text(strip=True)
    except Exception as e:
        logger.error("HTML scrape fallback also failed: %s", e)

    data: dict[str, Any] = {
        "username": username,
        "profile_url": profile_url,
        "bio": bio,
        "public_repos_count": 0,
        "followers": 0,
        "following": 0,
        "top_languages": {},
        "pinned_repos": [],
        "top_repos": [],
        "readme_text": None,
    }
    data["raw_text"] = _build_raw_text(data)
    return data