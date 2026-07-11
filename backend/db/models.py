"""
db/models.py
SQLAlchemy ORM models for the Voice Agent Interview Platform.

Tables:
  - users          : one row per candidate
  - sessions       : one interview session per upload batch
  - parsed_documents : parsed content blobs keyed by session + doc_type
  - github_metadata  : extracted GitHub profile + repo statistics
  - linkedin_metadata: extracted LinkedIn profile fields
  - jd_structured    : structured job description payload per session
  - vector_index_refs: lightweight ledger pointing to ChromaDB entries
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.session import Base


def _uuid():
    return str(uuid.uuid4())



class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid, index=True)
    email = Column(String(320), unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=True)
    phone = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # relationships
    sessions = relationship("InterviewSession", back_populates="user", cascade="all, delete-orphan")




class InterviewSession(Base):
    """One session = one upload batch (resume + GitHub + LinkedIn + JD)."""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=_uuid, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    # Raw URLs provided at upload time (after validation)
    github_url = Column(String(512), nullable=True)
    linkedin_url = Column(String(512), nullable=True)
    resume_filename = Column(String(512), nullable=True)

    # Status flags
    resume_parsed = Column(Boolean, default=False)
    github_parsed = Column(Boolean, default=False)
    linkedin_parsed = Column(Boolean, default=False)
    jd_parsed = Column(Boolean, default=False)
    indexed_in_vector_store = Column(Boolean, default=False)

    # Interview state
    interview_status = Column(String(50), default="pending")  # pending | active | completed
    workflow_json = Column(JSON, nullable=True)  # LLM-generated interview workflow

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # relationships
    user = relationship("User", back_populates="sessions")
    parsed_documents = relationship("ParsedDocument", back_populates="session", cascade="all, delete-orphan")
    github_metadata = relationship("GitHubMetadata", back_populates="session", uselist=False, cascade="all, delete-orphan")
    linkedin_metadata = relationship("LinkedInMetadata", back_populates="session", uselist=False, cascade="all, delete-orphan")
    jd_structured = relationship("JDStructured", back_populates="session", uselist=False, cascade="all, delete-orphan")
    vector_index_refs = relationship("VectorIndexRef", back_populates="session", cascade="all, delete-orphan")




class ParsedDocument(Base):
    """
    Stores the raw extracted text for a single document type within a session.
    doc_type: "resume" | "jd" | "github_readme" | "linkedin"
    """
    __tablename__ = "parsed_documents"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type = Column(String(50), nullable=False)   # "resume" | "jd" | "github" | "linkedin"
    source = Column(String(512), nullable=True)     # filename or URL
    raw_text = Column(Text, nullable=False)
    quick_fields = Column(JSON, nullable=True)       # email, phone, links etc.
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="parsed_documents")




class GitHubMetadata(Base):
    """Structured metadata extracted from a GitHub profile + repos."""
    __tablename__ = "github_metadata"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    github_username = Column(String(255), nullable=True)
    profile_url = Column(String(512), nullable=True)
    bio = Column(Text, nullable=True)
    public_repos_count = Column(Integer, default=0)
    followers = Column(Integer, default=0)
    following = Column(Integer, default=0)
    top_languages = Column(JSON, nullable=True)          # {"Python": 12, "TypeScript": 5, ...}
    pinned_repos = Column(JSON, nullable=True)           # [{name, description, stars, url}]
    top_repos = Column(JSON, nullable=True)              # top-N by stars
    readme_text = Column(Text, nullable=True)            # profile README if present
    raw_payload = Column(JSON, nullable=True)            # full raw API response for future use
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="github_metadata")




class LinkedInMetadata(Base):
    """Structured metadata scraped from a LinkedIn public profile."""
    __tablename__ = "linkedin_metadata"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    linkedin_username = Column(String(255), nullable=True)
    profile_url = Column(String(512), nullable=True)
    headline = Column(Text, nullable=True)
    about = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    experience = Column(JSON, nullable=True)   # [{title, company, duration, description}]
    education = Column(JSON, nullable=True)    # [{degree, institution, year}]
    skills = Column(JSON, nullable=True)       # [str]
    certifications = Column(JSON, nullable=True)
    raw_html_snapshot = Column(Text, nullable=True)  # optional: store page HTML for debugging
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="linkedin_metadata")




class JDStructured(Base):
    """LLM-structured job description fields per session."""
    __tablename__ = "jd_structured"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=True)
    seniority = Column(String(100), nullable=True)
    required_skills = Column(JSON, nullable=True)       # [str]
    nice_to_have_skills = Column(JSON, nullable=True)   # [str]
    responsibilities = Column(JSON, nullable=True)      # [str]
    years_experience = Column(String(50), nullable=True)
    raw_jd_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="jd_structured")




class VectorIndexRef(Base):
    """
    Lightweight ledger: each row tracks one ChromaDB document chunk.
    Useful for dashboard display ('X chunks indexed') and cleanup.
    """
    __tablename__ = "vector_index_refs"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    chroma_doc_id = Column(String(128), nullable=False, index=True)  # ID in ChromaDB
    doc_type = Column(String(50), nullable=False)    # "resume" | "jd" | "github" | "linkedin"
    source = Column(String(512), nullable=True)
    chunk_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="vector_index_refs")
