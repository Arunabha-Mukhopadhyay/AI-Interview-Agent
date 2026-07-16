# Voice Agent Interview Platform - Deep System Instructions

This file serves as the definitive reference manual for any AI coding assistant (Claude, Antigravity, GitHub Copilot) working on this repository. Read these constraints carefully before writing or modifying code.

## 🏗️ Immutable Tech Stack Constraints

1.  **Dependency Management**: `uv`
    *   **Rule**: NEVER use `pip install`. Always use `uv add <package>` for new dependencies.
    *   **Rule**: NEVER run scripts with just `python <script.py>`. Always prefix with `uv run` to ensure the correct virtual environment is used (e.g., `uv run uvicorn main:app --reload`).
2.  **Relational Database**: PostgreSQL + SQLAlchemy
    *   **Rule**: NEVER execute raw SQL strings. You must always use the SQLAlchemy ORM models defined in `db/models.py`.
    *   **Rule**: Sessions must be acquired via the FastAPI dependency `Depends(get_db)` exported from `db/session.py`.
    *   **Rule**: You must handle graceful fallbacks if the database is unreachable.
3.  **Vector Database**: ChromaDB
    *   **Rule**: Metadata schemas are strictly enforced. Every chunk inserted into ChromaDB MUST have this exact dictionary shape:
        ```python
        {
            "session_id": str,     # Crucial for multi-tenant isolation
            "type": str,           # Must be one of: "resume", "jd", "github", "linkedin"
            "source": str,         # Filename or URL
            "chunk_index": int     # Sequential integer
        }
        ```
    *   **Rule**: Distance metric is strictly Cosine Similarity (`"hnsw:space": "cosine"`). Do not change to L2.
4.  **State Management**: LangGraph
    *   **Rule**: Do not mutate LangChain memory manually. All state transitions must occur via the `InterviewState` TypedDict defined in `agents/state.py`.
    *   **Rule**: To add a message to history, simply return `{"messages": [new_message]}` from a node; the `add_messages` reducer handles the appending.

## 📂 Codebase Geography & Rules

### Environment Variables (`core/config.py`)
*   **Rule**: NEVER use `os.environ.get()` anywhere in the codebase. All environment variables must be declared in the `Settings` class in `core/config.py` and accessed via the `get_settings()` function.
*   **Fallback Behavior**: APIs (ElevenLabs, AssemblyAI, Groq) must not crash the server if keys are missing. They should catch the missing key condition and return a mocked string or `b""` (empty bytes) to allow local UI development without paying for API calls.

### Logging (`core/logging.py`)
*   **Rule**: NEVER use `print()`. Always instantiate a structured logger at the top of your file:
    ```python
    from core.logging import get_logger
    logger = get_logger(__name__)
    ```

### Parsing Pipeline (`parsing/`)
*   **Rule**: Web scraping must route through `proxy_session.py`. LinkedIn scraping is highly volatile; ensure `try/except` blocks gracefully degrade to returning empty dictionaries rather than throwing 500 errors.
*   **Rule**: GitHub API calls should use the `GITHUB_TOKEN` via `PyGithub`. Do not scrape GitHub via HTML unless the API call fails completely.
*   **Rule**: URL validation is mandatory before making network calls. Use the regex validators in `validators.py` and raise 422 HTTP exceptions if malformed.

### WebSocket Flow (`api/routes/interview.py`)
1.  Verify the `session_id` against the PostgreSQL database. Drop connection if invalid.
2.  Initialize the LangGraph state.
3.  *Immediate Action*: Generate and send a hardcoded TTS greeting to the client. This masks the latency of establishing the LLM connection and gives the user instant feedback.
4.  Enter the continuous `while True` loop:
    *   Await binary audio from client.
    *   STT execution (must be asynchronous or threadpool-wrapped if using a blocking SDK like AssemblyAI's file API).
    *   LangGraph Node Execution (Context Retrieval -> Gap Analysis (if needed) -> LLM Generation).
    *   TTS execution.
    *   Send binary audio back to client.

## 🗄️ Database Schema Reference (PostgreSQL)

If you need to query or update data, be aware of the existing relationships:
*   `User` (id, email) -> `InterviewSession` (1:N)
*   `InterviewSession` (id, status flags) -> `ParsedDocument` (1:N)
*   `InterviewSession` -> `GitHubMetadata` (1:1) -> *Contains JSON columns for top_repos and languages*
*   `InterviewSession` -> `LinkedInMetadata` (1:1) -> *Contains JSON columns for experience and education*
*   `InterviewSession` -> `JDStructured` (1:1) -> *Contains JSON columns for required_skills*
*   `InterviewSession` -> `VectorIndexRef` (1:N) -> *Ledger of ChromaDB IDs*

## 🐛 Standard Debugging Procedures for AI
If a user reports an error, check these first:
1.  **ModuleNotFoundError**: Check if they ran `python <script>` instead of `uv run python <script>`. Advise them to use `uv run`.
2.  **Database Not Found**: Remind the user to run `createdb voice_agent` in their terminal before starting the server.
3.  **Missing Audio / Silent Responses**: Check if the TTS API key is empty in the `.env` file resulting in the fallback `b""` return.
4.  **GitHub 403 Forbidden**: Rate limit exceeded because they didn't provide a `GITHUB_TOKEN`.
