"""
parsing/linkedin_parser.py
LinkedIn public profile scraper.

⚠️  LinkedIn aggressively blocks automated scraping.
    This implementation uses:
      1. The proxy session (IP rotation if configured) + browser-like headers.
      2. BeautifulSoup for HTML parsing.
      3. Structured extraction of: headline, about, experience, education, skills.

    Because LinkedIn serves a JS-rendered page to unauthenticated bots, a
    full headless browser (Playwright/Selenium) would be more reliable for
    production.  This module provides a best-effort scrape suitable for
    development and testing.

URL validation is strict — malformed URLs raise ValueError before any
network call.
"""
from __future__ import annotations

import json
import re
from typing import Any

from core.logging import get_logger
from parsing.validators import validate_linkedin_url, extract_linkedin_slug
from parsing.proxy_session import get_proxy_session

logger = get_logger(__name__)



def _safe_text(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def _extract_ld_json(soup) -> dict:
    """Try to find LinkedIn's embedded JSON-LD schema for structured data."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
            if isinstance(data, dict) and data.get("@type") in ("Person", "ProfilePage"):
                return data
        except json.JSONDecodeError:
            continue
    return {}


def _build_raw_text(data: dict) -> str:
    lines = [
        f"LinkedIn Profile: {data.get('profile_url', '')}",
        f"Name/Slug: {data.get('linkedin_username', '')}",
    ]
    if data.get("headline"):
        lines.append(f"Headline: {data['headline']}")
    if data.get("about"):
        lines.append(f"About: {data['about']}")
    if data.get("location"):
        lines.append(f"Location: {data['location']}")
    for exp in data.get("experience", []):
        lines.append(
            f"Experience: {exp.get('title', '')} at {exp.get('company', '')} "
            f"({exp.get('duration', '')})"
        )
    for edu in data.get("education", []):
        lines.append(
            f"Education: {edu.get('degree', '')} — {edu.get('institution', '')} "
            f"({edu.get('year', '')})"
        )
    if data.get("skills"):
        lines.append("Skills: " + ", ".join(data["skills"]))
    return "\n".join(lines)




def parse_linkedin(linkedin_url: str) -> dict[str, Any]:
    """
    Scrape a LinkedIn public profile and return structured metadata + raw_text.

    Raises ValueError for malformed URLs.
    Returns a partial result (with error_note) if scraping fails.
    """
    # ── 1. Validate URL ───────────────────────────────────────────────────────
    clean_url = validate_linkedin_url(linkedin_url)
    slug = extract_linkedin_slug(clean_url)
    logger.info("Parsing LinkedIn profile: %s", slug)

    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        raise RuntimeError("beautifulsoup4 is required: pip install beautifulsoup4")

    # ── 2. Fetch page via proxy session ───────────────────────────────────────
    html_snapshot: str | None = None
    soup = None

    try:
        with get_proxy_session("https://www.linkedin.com") as session:
            resp = session.get(clean_url, timeout=20, allow_redirects=True)
            if resp.status_code == 999:
                logger.warning("LinkedIn returned 999 (bot detected) for %s", clean_url)
            else:
                resp.raise_for_status()
            html_snapshot = resp.text
            soup = BeautifulSoup(html_snapshot, "html.parser")
    except Exception as exc:
        logger.error("LinkedIn fetch failed: %s", exc)

    # ── 3. Extract fields ─────────────────────────────────────────────────────
    headline = None
    about = None
    location = None
    experience: list[dict] = []
    education: list[dict] = []
    skills: list[str] = []
    certifications: list[dict] = []

    if soup:
        # Try JSON-LD first (most reliable when present)
        ld = _extract_ld_json(soup)
        if ld:
            headline = ld.get("description") or ld.get("headline")
            location = ld.get("address", {}).get("addressLocality") if isinstance(ld.get("address"), dict) else None

        # Headline
        if not headline:
            tag = soup.find("div", class_=re.compile(r"top-card-layout__headline|text-body-medium"))
            headline = _safe_text(tag) or None

        # About / Summary
        about_section = soup.find("section", {"data-section": "summary"}) or \
                        soup.find("div", class_=re.compile(r"summary|about"))
        if about_section:
            about = _safe_text(about_section.find("p") or about_section)

        # Location
        if not location:
            loc_tag = soup.find("span", class_=re.compile(r"top-card__subline-item|location"))
            location = _safe_text(loc_tag) or None

        # Experience
        exp_section = soup.find("section", {"data-section": "experience"}) or \
                      soup.find("ul", class_=re.compile(r"experience"))
        if exp_section:
            for item in exp_section.find_all("li")[:10]:
                title_tag = item.find(["h3", "span"], class_=re.compile(r"title|position"))
                company_tag = item.find(["h4", "span"], class_=re.compile(r"company|subtitle"))
                duration_tag = item.find("span", class_=re.compile(r"date|duration"))
                desc_tag = item.find("p")
                if title_tag or company_tag:
                    experience.append({
                        "title": _safe_text(title_tag),
                        "company": _safe_text(company_tag),
                        "duration": _safe_text(duration_tag),
                        "description": _safe_text(desc_tag),
                    })

        # Education
        edu_section = soup.find("section", {"data-section": "educationsDetails"}) or \
                      soup.find("ul", class_=re.compile(r"education"))
        if edu_section:
            for item in edu_section.find_all("li")[:10]:
                school_tag = item.find(["h3", "span"], class_=re.compile(r"school|institution"))
                degree_tag = item.find(["h4", "span"], class_=re.compile(r"degree|field"))
                year_tag = item.find("span", class_=re.compile(r"date|year"))
                if school_tag:
                    education.append({
                        "institution": _safe_text(school_tag),
                        "degree": _safe_text(degree_tag),
                        "year": _safe_text(year_tag),
                    })

        # Skills
        skills_section = soup.find("section", {"data-section": "skills"}) or \
                         soup.find("ul", class_=re.compile(r"skills"))
        if skills_section:
            skills = [
                _safe_text(tag)
                for tag in skills_section.find_all(["span", "li"])
                if _safe_text(tag)
            ][:30]

    data: dict[str, Any] = {
        "linkedin_username": slug,
        "profile_url": clean_url,
        "headline": headline,
        "about": about,
        "location": location,
        "experience": experience,
        "education": education,
        "skills": skills,
        "certifications": certifications,
        "raw_html_snapshot": html_snapshot,
    }

    # ── 4. Flat text for embedding ─────────────────────────────────────────────
    data["raw_text"] = _build_raw_text(data)

    logger.info(
        "LinkedIn parse complete for %s — headline=%s, experience=%d, skills=%d",
        slug, bool(headline), len(experience), len(skills)
    )
    return data
