# AI Voice Interview Agent Platform

An advanced, real-time, interactive voice AI platform that conducts deeply personalized technical interviews. By analyzing a candidate's Resume, GitHub profile, LinkedIn profile, and the target Job Description (JD), the AI formulates a customized interview plan and interacts with the candidate via a low-latency WebSockets voice stream.

---

## 🏗️ High-Level Architecture

The system is built on a modern, asynchronous Python stack optimized for real-time AI workloads.

### Tech Stack
*   **Core Framework**: FastAPI, Python 3.11+
*   **Package Manager**: `uv` (Lightning-fast Python dependency manager)
*   **AI Orchestration**: LangChain & LangGraph (State-machine based agent logic)
*   **Relational Database**: PostgreSQL + SQLAlchemy (For structured state & metadata)
*   **Vector Database**: ChromaDB (For semantic retrieval of chunks)
*   **Caching Layer**: Redis (For rate-limiting mitigation & fast retrieval)
*   **Speech-to-Text (STT)**: AssemblyAI (or Deepgram for ultra-low latency)
*   **Text-to-Speech (TTS)**: ElevenLabs (Turbo models for conversational AI)

### Architecture Flow

```mermaid
graph TD
    A[Frontend] -->|POST /ingest| B(Ingestion Pipeline)
    A -->|WS /interview/ws/{id}| C(WebSocket Voice Stream)
    
    subgraph Ingestion
    B --> B1[Parse Resume PDF]
    B --> B2[Scrape GitHub API]
    B --> B3[Scrape LinkedIn]
    B --> B4[Structure JD via LLM]
    B1 & B2 & B3 & B4 --> D[Chunk & Embed]
    D --> E[(ChromaDB Vector Store)]
    B1 & B2 & B3 & B4 --> F[(PostgreSQL Metadata)]
    end
    
    subgraph Interview Agent
    C -->|Audio Bytes| G[AssemblyAI STT]
    G -->|User Text| H{LangGraph Orchestrator}
    E -.->|Context Retrieval| H
    F -.->|State & Gap Analysis| H
    H -->|Agent Text Response| I[ElevenLabs TTS]
    I -->|Audio Bytes| C
    end
```

---

## 🚀 Detailed Setup Guide

### 1. System Requirements
*   Python 3.11 or higher
*   [uv](https://github.com/astral-sh/uv) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
*   PostgreSQL running locally on port 5432
*   Redis running locally on port 6379

### 2. Clone & Install
```bash
# Navigate to the backend
cd backend

# Use uv to resolve and install all dependencies into a fast virtual environment
uv add -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the `backend/` directory:
```bash
cp .env.example .env
```

You must configure the following core variables:
*   `LLM_PROVIDER`: Choose `openai`, `groq`, or `google`.
*   `LLM_MODEL`: e.g., `gpt-4o-mini`, `llama3-8b-8192`, `gemini-1.5-flash`.
*   `OPENAI_API_KEY` (or Groq/Google keys depending on your choice).
*   `GITHUB_TOKEN`: Highly recommended. Without this, GitHub's API limits you to 60 requests/hour.
*   `ELEVENLABS_API_KEY`: Required for Text-to-Speech.
*   `ASSEMBLYAI_API_KEY`: Required for Speech-to-Text.
*   `POSTGRES_URL`: E.g., `postgresql+psycopg2://username@localhost:5432/voice_agent`.

### 4. Database Initialization
Before running the server, you must construct the relational tables in Postgres:
```bash
# Ensure your Postgres server is running and the 'voice_agent' DB exists
createdb voice_agent 2>/dev/null || true

# Run the SQLAlchemy initialization script
uv run python -m db.init_db
```

### 5. Run the Server
```bash
uv run uvicorn main:app --reload --port 8000
```
The server will start at `http://localhost:8000`. You can view the interactive API docs at `http://localhost:8000/docs`.

---

## 📂 Deep Dive into the Codebase

### `api/routes/`
*   **`ingest.py`**: The entry point for candidate data. It accepts `multipart/form-data` containing a PDF resume, GitHub URL, LinkedIn URL, and pasted JD text. It orchestrates the parsing modules, chunks the text, embeds it into ChromaDB, and saves the structured summaries (like top languages and past experience) into PostgreSQL. It leverages Redis to cache GitHub/LinkedIn responses to prevent rate-limit bans if a user re-submits.
*   **`interview.py`**: The real-time WebSocket endpoint (`ws://.../interview/ws/{session_id}`). It establishes a persistent connection, sends an immediate hardcoded TTS greeting to bypass LLM latency, and enters a continuous loop of: Receive Audio -> STT -> LangGraph Agent -> TTS -> Send Audio.

### `agents/` (The Brain)
*   **`state.py`**: Defines `InterviewState`, a LangGraph TypedDict representing the "memory" of the interview. It holds the `session_id`, the full conversation history (`messages`), the retrieved `context_docs`, the LLM's `gap_analysis`, and the `current_stage`.
*   **`nodes.py`**: The distinct operational steps the agent can take.
    *   `retrieve_context_node`: Queries ChromaDB based on the user's latest spoken sentence to pull relevant resume/JD chunks into context.
    *   `gap_analysis_node`: Evaluates the candidate's profile against the JD to find missing skills.
    *   `generate_response_node`: The main LLM call that looks at the context, the gap analysis, and the chat history to formulate the next spoken response.
*   **`graph.py`**: Wires the nodes together into a state machine (`START -> retrieve -> gap_analysis -> response -> END`).
*   **`prompts.py`**: Contains the highly specific system prompts that instruct the LLM to act as a technical interviewer and keep responses concise for voice output.

### `db/` (The Relational Truth)
*   **`models.py`**: SQLAlchemy schemas.
    *   `users`: Basic identity.
    *   `sessions`: Tracks the status of parsing and the interview stage.
    *   `parsed_documents`: Stores the raw text and quick regex fields (emails, phones).
    *   `github_metadata` / `linkedin_metadata`: Stores beautifully structured JSON (top repos, followers, job history).
    *   `jd_structured`: LLM-extracted job requirements.
    *   `vector_index_refs`: A ledger mapping every ChromaDB chunk back to a PostgreSQL session.

### `parsing/` (Data Extraction)
*   **`Github_parser.py`**: Connects via `PyGithub`. Aggregates languages, sorts top repositories, and pulls the profile `README.md`. Includes a fallback HTML scraper.
*   **`linkedin_parser.py`**: Uses a proxy session and BeautifulSoup to extract JSON-LD schema data and HTML nodes for work experience and education. Handles LinkedIn's aggressive 999 anti-bot responses gracefully.
*   **`resume_parser.py`**: Extracts text from PDFs and DOCX files.
*   **`JD_parser.py`**: Feeds raw JD text to the LLM to output a strictly typed JSON object containing required skills, nice-to-haves, and seniority levels.
*   **`proxy_session.py`**: Contains an AWS API Gateway IP rotation integration (`requests-ip-rotator`) for heavy scraping.

### `vectorStore/` (Semantic Memory)
*   **`indexer.py`**: The ingestion pipeline (`chunk_text` -> `_embed_documents` -> ChromaDB insertion). Ensures every chunk is tagged with `{"session_id": "...", "type": "...", "source": "...", "chunk_index": 0}`.
*   **`chroma_client.py`**: Singleton persistent ChromaDB client using Cosine Similarity.
*   **`embeddings.py`**: Factory returning OpenAI or Google GenAI embeddings based on `.env`.

### `voice/` (Ears and Mouth)
*   **`stt.py`**: Wraps the AssemblyAI SDK to convert inbound binary audio chunks into text.
*   **`tts.py`**: Wraps the ElevenLabs SDK (`eleven_turbo_v2_5` model) to convert outbound agent text into streaming binary audio bytes.

---

## 🛠️ Typical Errors & Debugging

1. **`ModuleNotFoundError: No module named 'sqlalchemy'`**
   *   *Cause*: You are not running the command inside the `uv` virtual environment.
   *   *Fix*: Always prefix commands with `uv run` (e.g., `uv run python -m db.init_db`) or activate the `.venv` first.

2. **`psycopg2.OperationalError: FATAL: database "voice_agent" does not exist`**
   *   *Cause*: The PostgreSQL server is running, but the specific database hasn't been created.
   *   *Fix*: Run `createdb voice_agent` in your terminal.

3. **Rate Limit / 403 Errors on GitHub Parsing**
   *   *Cause*: You are making unauthenticated requests to the GitHub API (limit 60/hr).
   *   *Fix*: Generate a Personal Access Token in GitHub and add it to `GITHUB_TOKEN` in `.env`.

4. **Empty Audio or Silent Responses**
   *   *Cause*: Missing or invalid `ELEVENLABS_API_KEY`. The backend is designed to fail gracefully and return empty bytes if the key is missing to prevent server crashes.
   *   *Fix*: Verify your ElevenLabs key in the `.env` file.
