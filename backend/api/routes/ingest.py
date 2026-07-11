"""
api/routes/ingest.py
POST /ingest  — Upload resume + GitHub/LinkedIn/JD, parse & index everything.

Flow:
  1. Validate GitHub and LinkedIn URLs (raise 422 if malformed).
  2. Check Redis cache — skip re-parsing if already done for this session.
  3. Parse resume (PDF/DOCX), GitHub profile, LinkedIn profile, JD text.
  4. Chunk + embed + store each document type in ChromaDB.
  5. Persist structured metadata to PostgreSQL.
  6. Cache parsed metadata in Redis for the session TTL.
  7. Return a summary response for the dashboard.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from cache.redis_client import cache_get, cache_set, make_key
from core.logging import get_logger
from db.models import (
    GitHubMetadata,
    InterviewSession,
    JDStructured,
    LinkedInMetadata,
    ParsedDocument,
    User,
    VectorIndexRef,
)
from db.session import get_db
from parsing.Github_parser import parse_github
from parsing.JD_parser import parse_jd
from parsing.linkedin_parser import parse_linkedin
from parsing.resume_parser import parse_resume
from parsing.validators import validate_github_url, validate_linkedin_url
from vectorStore.indexer import index_document, get_session_chunk_count

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingest"])


# ─────────────────────────────────────────────────────────────────────────────
# Response schema
# ─────────────────────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    session_id: str
    resume_parsed: bool
    github_parsed: bool
    linkedin_parsed: bool
    jd_parsed: bool
    total_chunks_indexed: int
    quick_fields: dict
    github_summary: dict
    linkedin_summary: dict
    jd_structured: dict
    cached: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _save_temp_file(upload: UploadFile) -> str:
    """Write an UploadFile to a temp file and return its path."""
    suffix = os.path.splitext(upload.filename or "resume.pdf")[1] or ".pdf"
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return path


def _store_parsed_doc(db: Session, session_id: str, doc_type: str, source: str,
                       raw_text: str, quick_fields: dict | None, chunk_ids: list[str]):
    """Persist a parsed document + vector index refs to PostgreSQL."""
    doc = ParsedDocument(
        session_id=session_id,
        doc_type=doc_type,
        source=source,
        raw_text=raw_text,
        quick_fields=quick_fields or {},
        chunk_count=len(chunk_ids),
    )
    db.add(doc)

    for i, chroma_id in enumerate(chunk_ids):
        ref = VectorIndexRef(
            session_id=session_id,
            chroma_doc_id=chroma_id,
            doc_type=doc_type,
            source=source,
            chunk_index=i,
        )
        db.add(ref)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", response_model=IngestResponse, status_code=status.HTTP_200_OK)
async def ingest(
    resume: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
    github_url: str = Form(..., description="GitHub profile URL"),
    linkedin_url: str = Form(..., description="LinkedIn public profile URL"),
    jd_text: str = Form(..., description="Job description text (paste it in)"),
    user_email: Optional[str] = Form(None, description="Optional candidate email"),
    db: Session = Depends(get_db),
):
    """
    Ingest all candidate documents for a new interview session.

    - Validates GitHub and LinkedIn URLs before any network calls.
    - Parses resume (PDF/DOCX), scrapes GitHub + LinkedIn, structures JD via LLM.
    - Chunks, embeds, and stores everything in ChromaDB with metadata.
    - Persists structured rows in PostgreSQL.
    - Caches parsed metadata in Redis to avoid re-parsing.
    """

    # ── 1. Validate URLs ───────────────────────────────────────────────────────
    try:
        clean_github_url = validate_github_url(github_url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid GitHub URL: {e}")

    try:
        clean_linkedin_url = validate_linkedin_url(linkedin_url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid LinkedIn URL: {e}")

    # ── 2. Create session ──────────────────────────────────────────────────────
    session_id = str(uuid.uuid4())
    logger.info("New ingest session: %s", session_id)

    # Upsert user record if email provided
    user_id: str | None = None
    if user_email:
        existing = db.query(User).filter(User.email == user_email).first()
        if existing:
            user_id = existing.id
        else:
            new_user = User(email=user_email)
            db.add(new_user)
            db.flush()
            user_id = new_user.id

    session_row = InterviewSession(
        id=session_id,
        user_id=user_id,
        github_url=clean_github_url,
        linkedin_url=clean_linkedin_url,
        resume_filename=resume.filename,
    )
    db.add(session_row)
    db.flush()

    # ── 3. Parse Resume ────────────────────────────────────────────────────────
    resume_parsed_flag = False
    quick_fields: dict = {}
    resume_chunk_ids: list[str] = []

    tmp_path = None
    try:
        tmp_path = _save_temp_file(resume)
        resume_data = parse_resume(tmp_path)
        quick_fields = resume_data["quick_fields"]

        # Check cache
        resume_cache_key = make_key("resume", session_id)
        if not cache_get(resume_cache_key):
            resume_chunk_ids = index_document(
                resume_data["raw_text"],
                session_id=session_id,
                doc_type="resume",
                source=resume_data["source"],
            )
            _store_parsed_doc(
                db, session_id, "resume", resume_data["source"],
                resume_data["raw_text"], quick_fields, resume_chunk_ids,
            )
            cache_set(resume_cache_key, {"quick_fields": quick_fields, "chunk_count": len(resume_chunk_ids)})
        
        session_row.resume_parsed = True
        resume_parsed_flag = True
        logger.info("Resume indexed: %d chunks", len(resume_chunk_ids))
    except Exception as e:
        logger.error("Resume parsing failed: %s", e)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    # ── 4. Parse GitHub ────────────────────────────────────────────────────────
    github_parsed_flag = False
    github_summary: dict = {}
    github_cache_key = make_key("github", session_id)

    cached_github = cache_get(github_cache_key)
    if cached_github:
        logger.info("GitHub metadata served from cache for session %s", session_id)
        github_summary = cached_github
        github_parsed_flag = True
    else:
        try:
            github_data = parse_github(clean_github_url)
            github_summary = {k: v for k, v in github_data.items() if k != "raw_text"}

            github_chunk_ids = index_document(
                github_data["raw_text"],
                session_id=session_id,
                doc_type="github",
                source=clean_github_url,
            )
            _store_parsed_doc(
                db, session_id, "github", clean_github_url,
                github_data["raw_text"], None, github_chunk_ids,
            )

            # Persist GitHub metadata row
            gh_row = GitHubMetadata(
                session_id=session_id,
                github_username=github_data.get("username"),
                profile_url=clean_github_url,
                bio=github_data.get("bio"),
                public_repos_count=github_data.get("public_repos_count", 0),
                followers=github_data.get("followers", 0),
                following=github_data.get("following", 0),
                top_languages=github_data.get("top_languages"),
                pinned_repos=github_data.get("pinned_repos"),
                top_repos=github_data.get("top_repos"),
                readme_text=github_data.get("readme_text"),
            )
            db.add(gh_row)

            cache_set(github_cache_key, github_summary)
            session_row.github_parsed = True
            github_parsed_flag = True
            logger.info("GitHub indexed: %d chunks", len(github_chunk_ids))
        except Exception as e:
            logger.error("GitHub parsing failed: %s", e)

    # ── 5. Parse LinkedIn ──────────────────────────────────────────────────────
    linkedin_parsed_flag = False
    linkedin_summary: dict = {}
    linkedin_cache_key = make_key("linkedin", session_id)

    cached_linkedin = cache_get(linkedin_cache_key)
    if cached_linkedin:
        logger.info("LinkedIn metadata served from cache for session %s", session_id)
        linkedin_summary = cached_linkedin
        linkedin_parsed_flag = True
    else:
        try:
            linkedin_data = parse_linkedin(clean_linkedin_url)
            linkedin_summary = {k: v for k, v in linkedin_data.items()
                                if k not in ("raw_text", "raw_html_snapshot")}

            linkedin_chunk_ids = index_document(
                linkedin_data["raw_text"],
                session_id=session_id,
                doc_type="linkedin",
                source=clean_linkedin_url,
            )
            _store_parsed_doc(
                db, session_id, "linkedin", clean_linkedin_url,
                linkedin_data["raw_text"], None, linkedin_chunk_ids,
            )

            li_row = LinkedInMetadata(
                session_id=session_id,
                linkedin_username=linkedin_data.get("linkedin_username"),
                profile_url=clean_linkedin_url,
                headline=linkedin_data.get("headline"),
                about=linkedin_data.get("about"),
                location=linkedin_data.get("location"),
                experience=linkedin_data.get("experience"),
                education=linkedin_data.get("education"),
                skills=linkedin_data.get("skills"),
                certifications=linkedin_data.get("certifications"),
            )
            db.add(li_row)

            cache_set(linkedin_cache_key, linkedin_summary)
            session_row.linkedin_parsed = True
            linkedin_parsed_flag = True
            logger.info("LinkedIn indexed: %d chunks", len(linkedin_chunk_ids))
        except Exception as e:
            logger.error("LinkedIn parsing failed: %s", e)

    # ── 6. Parse JD ────────────────────────────────────────────────────────────
    jd_parsed_flag = False
    jd_structured: dict = {}

    try:
        jd_data = parse_jd(jd_text)
        jd_structured = jd_data["structured"]

        jd_chunk_ids = index_document(
            jd_data["raw_text"],
            session_id=session_id,
            doc_type="jd",
            source="pasted",
        )
        _store_parsed_doc(
            db, session_id, "jd", "pasted",
            jd_data["raw_text"], None, jd_chunk_ids,
        )

        jd_row = JDStructured(
            session_id=session_id,
            title=jd_structured.get("title"),
            seniority=jd_structured.get("seniority"),
            required_skills=jd_structured.get("required_skills"),
            nice_to_have_skills=jd_structured.get("nice_to_have_skills"),
            responsibilities=jd_structured.get("responsibilities"),
            years_experience=jd_structured.get("years_experience"),
            raw_jd_text=jd_data["raw_text"],
        )
        db.add(jd_row)

        session_row.jd_parsed = True
        jd_parsed_flag = True
        logger.info("JD indexed: %d chunks", len(jd_chunk_ids))
    except Exception as e:
        logger.error("JD parsing failed: %s", e)

    # ── 7. Finalise ────────────────────────────────────────────────────────────
    total_chunks = get_session_chunk_count(session_id)
    session_row.indexed_in_vector_store = total_chunks > 0

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("DB commit failed: %s", e)
        raise HTTPException(status_code=500, detail="Database write failed.")

    logger.info(
        "Ingest complete — session=%s chunks=%d resume=%s github=%s linkedin=%s jd=%s",
        session_id, total_chunks, resume_parsed_flag, github_parsed_flag,
        linkedin_parsed_flag, jd_parsed_flag,
    )

    return IngestResponse(
        session_id=session_id,
        resume_parsed=resume_parsed_flag,
        github_parsed=github_parsed_flag,
        linkedin_parsed=linkedin_parsed_flag,
        jd_parsed=jd_parsed_flag,
        total_chunks_indexed=total_chunks,
        quick_fields=quick_fields,
        github_summary=github_summary,
        linkedin_summary=linkedin_summary,
        jd_structured=jd_structured,
        cached=bool(cached_github or cached_linkedin),
    )
