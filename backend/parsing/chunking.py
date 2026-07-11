"""
Wraps RecursiveCharacterTextSplitter with the metadata convention used
everywhere downstream (vectorstore/indexer.py, agents/nodes/retriever_node.py):

    { "session_id": str, "type": "resume"|"jd"|"github", "source": str, "chunk_index": int }

Keeping this one place means the metadata schema only needs to change once.
"""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=DEFAULT_CHUNK_SIZE,
    chunk_overlap=DEFAULT_CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def chunk_text(
    text: str,
    *,
    session_id: str,
    doc_type: str,
    source: str,
) -> list[Document]:
    """Split text and attach the standard metadata to every chunk.

    doc_type: one of "resume" | "jd" | "github"
    source: filename, repo URL, or "pasted" — used for traceability/dashboard display
    """
    if not text or not text.strip():
        return []

    raw_chunks = _splitter.split_text(text)

    return [
        Document(
            page_content=chunk,
            metadata={
                "session_id": session_id,
                "type": doc_type,
                "source": source,
                "chunk_index": i,
            },
        )
        for i, chunk in enumerate(raw_chunks)
    ]
