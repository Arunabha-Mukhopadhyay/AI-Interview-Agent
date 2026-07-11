"""
parsing/resume_parser.py
Resume parsing.

Two layers of output, deliberately kept separate:
  1. `raw_text`    — full extracted text, chunked + embedded into the vector
                     store for semantic retrieval.
  2. `quick_fields`— cheap regex-based extraction (email, phone, links) used
                     for dashboard display / dedup.  NOT a substitute for
                     LLM-based structuring — deeper skill/experience extraction
                     belongs in the gap_analysis agent node which has full JD
                     context to reason against.

Supported file types: PDF (.pdf), Word (.docx)
"""
import re
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import Docx2txtLoader

from core.logging import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Regex patterns
# ─────────────────────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d{1,3}[.\-\s]?)?(\(?\d{3,4}\)?[.\-\s]?\d{3,4}[.\-\s]?\d{3,4})")
LINK_RE = re.compile(r"https?://[^\s)>\"']+")

# ─────────────────────────────────────────────────────────────────────────────
# Allowed extensions
# ─────────────────────────────────────────────────────────────────────────────

_LOADERS = {
    ".pdf": PyPDFLoader,
    ".docx": Docx2txtLoader,
}


def _load_file(file_path: Path) -> str:
    """Load a single resume file and return concatenated raw text."""
    suffix = file_path.suffix.lower()
    loader_cls = _LOADERS.get(suffix)
    if loader_cls is None:
        raise ValueError(
            f"Unsupported file type: {suffix!r}. Allowed: {list(_LOADERS.keys())}"
        )
    logger.info("Loading resume: %s", file_path.name)
    docs = loader_cls(str(file_path)).load()
    return "\n".join(doc.page_content for doc in docs)


def extract_quick_fields(raw_text: str) -> dict[str, Any]:
    """Regex-based extraction for fast dashboard display. Not LLM-dependent."""
    emails = EMAIL_RE.findall(raw_text)
    phones = [m[0] + m[1] for m in PHONE_RE.findall(raw_text)]
    links = LINK_RE.findall(raw_text)
    github_links = [l for l in links if "github.com" in l.lower()]
    linkedin_links = [l for l in links if "linkedin.com" in l.lower()]

    return {
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None,
        "github_links_found_in_resume": github_links,
        "linkedin_links_found_in_resume": linkedin_links,
        "all_links": links,
    }


def parse_resume(file_path: str | Path) -> dict[str, Any]:
    """
    Parse a resume file and return:
        {
            "raw_text": str,
            "quick_fields": dict,
            "source": str,   # filename
        }

    Raises:
        FileNotFoundError if the file does not exist.
        ValueError for unsupported file types.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Resume file not found: {path}")

    raw_text = _load_file(path)
    quick_fields = extract_quick_fields(raw_text)

    logger.info(
        "Resume parsed — %d chars | email=%s | github_links=%d",
        len(raw_text),
        quick_fields.get("email"),
        len(quick_fields.get("github_links_found_in_resume", [])),
    )

    return {
        "raw_text": raw_text,
        "quick_fields": quick_fields,
        "source": path.name,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Batch loader (kept for backward compatibility / dev tooling)
# ─────────────────────────────────────────────────────────────────────────────

def load_all_documents(data_dir: str) -> list:
    """
    Load all supported files from a directory into LangChain Document objects.
    Primarily useful for bulk ingestion during development.
    """
    from langchain_core.documents import Document  # noqa: F401

    data_path = Path(data_dir).resolve()
    logger.debug("Scanning data dir: %s", data_path)
    documents = []

    for suffix, loader_cls in _LOADERS.items():
        for f in data_path.glob(f"**/*{suffix}"):
            try:
                loaded = loader_cls(str(f)).load()
                documents.extend(loaded)
                logger.debug("Loaded %d docs from %s", len(loaded), f.name)
            except Exception as e:
                logger.error("Failed to load %s: %s", f, e)

    logger.info("Total documents loaded: %d", len(documents))
    return documents


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = parse_resume(sys.argv[1])
        print("=== Quick Fields ===")
        for k, v in result["quick_fields"].items():
            print(f"  {k}: {v}")
        print(f"\n=== Raw Text (first 500 chars) ===\n{result['raw_text'][:500]}")