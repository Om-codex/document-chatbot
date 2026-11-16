# Document Chatbot

Ask grounded questions about your own PDF, TXT and DOCX files. The backend is a
FastAPI RAG service deployed on Render; the frontend is plain HTML/CSS/JS hosted
on Cloudflare Workers.

- Live frontend: https://document-chatbot.omm512462.workers.dev/
- Live backend: https://document-chatbot-urue.onrender.com/
- Architecture and endpoint reference: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)
- Engineering decisions: [`docs/DECISIONS.md`](docs/DECISIONS.md)

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Orchestration | LangChain 1.x (LCEL) |
| Vector store | Qdrant Cloud (768-dim, Cosine distance) |
| Chat model | Groq `openai/gpt-oss-20b` (temperature 0, 2 retries) |
| Embeddings | Google Gemini `gemini-embedding-2` API (768-dim, normalized) |
| Frontend | Plain HTML, CSS, JavaScript (no build step) |
| Tests | pytest + FastAPI `TestClient`, isolated temp storage |

Verified on Python 3.13.14, Windows.

## Project layout

```
document-chatbot/
├── app.py                     # FastAPI entrypoint, error handlers, static mount
├── requirements.txt           # pinned, direct dependencies
├── .env.example               # documented settings, copy to .env
├── pytest.ini                 # default test selection
├── config/settings.py         # typed settings (env-driven)
├── api/
│   ├── errors.py              # {detail: {code, message, details?}} helper
│   ├── routes/                # documents, chat, health routers
│   └── schemas/               # request/response Pydantic models
├── services/
│   ├── document_service.py    # upload, list, delete, cleanup/recovery
│   ├── chat_service.py        # validation, retrieval, LLM error mapping
│   └── exceptions.py          # service-level error types
├── ingestion/
│   ├── loaders.py             # PDF/TXT/DOCX loaders
│   ├── text_splitter.py       # chunking + metadata
│   ├── pipeline.py            # load -> split -> chunk metadata
│   └── exceptions.py
├── embeddings/
│   ├── embedding_model.py     # cached GeminiEmbedding factory
│   └── gemini_embedding.py    # Gemini Embedding API client (768-dim, batched)
├── vectorstore/
│   ├── qdrant_store.py        # Qdrant Cloud wrapper (replaces ChromaDB)
│   └── chroma_store.py        # ChromaDB implementation (kept for rollback)
├── retrieval/retriever.py          # top-k retrieval with optional doc filter
├── chains/
│   ├── prompt_template.py     # grounded prompt (context is untrusted data)
│   └── qa_chain.py            # LCEL chain
├── generation/
│   ├── llm.py                 # cached ChatGroq factory
│   └── exceptions.py          # provider error translation
├── utils/                     # logging, validation, file signatures, helpers
├── frontend/
│   ├── index.html             # landing page (site entry)
│   ├── chat.html              # chatbot UI
│   ├── tour.html              # tour chooser + accessible tour dialog
│   ├── about.html             # motivation, architecture, decisions, limits
│   ├── css/
│   │   ├── styles.css         # chatbot UI styles
│   │   └── site.css           # landing, tours and About styles
│   └── js/
│       ├── config.js          # real/mock switch + limits
│       ├── api.js             # HTTP client (fetch + XHR upload)
│       ├── mock.js            # optional demo adapter
│       ├── app.js             # chatbot UI controller
│       ├── theme.js           # shared theme controller for site pages
│       ├── site.js            # nav, scroll state and reveal behaviour
│       ├── tour-engine.js     # reusable accessible tour dialog
│       ├── tour-visuals.js    # CSS/HTML diagrams and app mockups
│       ├── tour-page.js       # tour chooser controller
│       ├── about.js           # interactive architecture diagram
│       └── tours/
│           ├── rag-tour.js    # 12-step engine tour content
│           └── app-tour.js    # 8-step app tour content
├── tests/
│   ├── conftest.py            # temp storage, fake embeddings, fake LLM
│   ├── test_documents_api.py
│   ├── test_chat_api.py
│   ├── test_vectorstore.py
│   ├── test_ingestion.py
│   ├── test_error_handling.py
│   ├── test_gemini_embedding.py
│   ├── test_qdrant_connection.py
│   ├── test_real_llm.py       # opt-in real Groq test
│   └── manual/                # original exploratory scripts (not collected)
```

## Setup (Windows PowerShell)

```powershell
cd document-chatbot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
# edit .env and set GROQ_API_KEY, QDRANT_URL, QDRANT_API_KEY, GEMINI_API_KEY
```

No PyTorch or sentence-transformers download is required. Embeddings are served by
the Google Gemini Embedding API.

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
```

- Site: <http://127.0.0.1:8000/app/>
- Chatbot: <http://127.0.0.1:8000/app/chat.html>
- Tours: <http://127.0.0.1:8000/app/tour.html> (`?tour=rag` or `?tour=app` opens one directly)
- About: <http://127.0.0.1:8000/app/about.html>
- API docs: <http://127.0.0.1:8000/docs>
- Root: <http://127.0.0.1:8000/> (JSON service banner)

The **Sources** box in the composer sets how many chunks are retrieved and passed
to the LLM (1–20, default 3). The value is clamped to that range and remembered in
the browser via `localStorage`.

The header toggle switches between light and dark themes. It follows the OS
preference on first visit, then remembers the user's choice in `localStorage`.
The chatbot's toggle is self-contained in `chat.html`; the landing, tour and About
pages use `js/theme.js`, which applies the saved theme before first paint. Both
share the same storage key. If a control appears unresponsive after an update,
hard-refresh the page (`Ctrl+Shift+R`) to drop cached CSS/JS, and make sure you are
using the `/app/` URL rather than opening a `frontend/*.html` file directly.

Run **one** Uvicorn worker in local development.

## Site pages and tours

- `frontend/index.html` introduces the project and links into the chatbot.
- `frontend/tour.html` offers two optional tours. The engine tour has 12 steps
  across ingestion, retrieval and generation, including the real system prompt
  from `chains/prompt_template.py`. The app tour has 8 steps based on the actual
  UI controls in `chat.html` and behaviour in `js/app.js`.
- Tour progress is stored per tour under `document-chatbot.tour.rag` and
  `document-chatbot.tour.app` (`in-progress`, `completed` or `skipped`). Tours
  never open without a button press or an explicit `?tour=` link, and can be
  replayed from the tour page, the site navigation or the About page.
- Tour content lives in `js/tours/`; the dialog, keyboard handling and focus
  management live in `js/tour-engine.js`. Diagrams and app mockups are HTML/CSS,
  not screenshots.

### Frontend-only preview (no backend)

```powershell
python -m http.server 5500 --directory frontend
```

Open <http://127.0.0.1:5500/chat.html?mock=1>. The landing, tour and About pages
are static and do not call the API, so they work without a server. Without
`?mock=1` the chatbot calls the real API at the same origin. When the UI is served
from another origin, pass `?apiBase=http://127.0.0.1:8000` and allow that origin in
`CORS_ALLOW_ORIGINS`.

Mock triggers: a filename containing `fail` fails that upload; a question
containing `rate limit` returns a 429; deleting every document leaves chat with a
`NO_DOCUMENTS` error.

## Configuration

Settings live in `config/settings.py` and are read from environment variables or
`.env` (case-insensitive). Copy `.env.example` to `.env` and set at minimum:

```dotenv
GROQ_API_KEY=...
QDRANT_URL=...
QDRANT_API_KEY=...
GEMINI_API_KEY=...
```

| Variable | Default | Notes |
|---|---|---|
| `GROQ_API_KEY` | — | <https://console.groq.com/keys> |
| `GEMINI_API_KEY` | — | <https://aistudio.google.com/app/apikey> |
| `QDRANT_URL` | — | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | — | Qdrant Cloud API key |
| `LLM_MODEL` | `openai/gpt-oss-20b` | Groq free tier; `gpt-oss-120b` also works |
| `LLM_TEMPERATURE` | `0` | Deterministic answers |
| `LLM_MAX_RETRIES` | `2` | Retries on transient provider errors |
| `LLM_TIMEOUT_SECONDS` | `60` | Per-request timeout |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-2` | Google Gemini Embedding API model |
| `EMBEDDING_DIMENSIONS` | `768` | Embedding vector dimensions |
| `EMBEDDING_BATCH_SIZE` | `100` | Texts per Gemini API call |
| `EMBEDDING_MAX_RETRIES` | `6` | Retries on transient embedding failures |
| `EMBEDDING_INITIAL_BACKOFF_SECONDS` | `3.0` | Initial backoff for embedding retries |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1000` / `200` | Changing them changes chunk IDs |
| `UPLOAD_DIRECTORY` | `data/uploads` | Temporary files during ingestion only |
| `MAX_FILE_SIZE_BYTES` | `10485760` (10 MB) | Also enforced client-side |
| `ALLOWED_EXTENSIONS` | `[".pdf", ".docx", ".txt"]` | JSON list |
| `DEFAULT_TOP_K` / `MAX_TOP_K` | `3` / `20` | Retrieval depth |
| `MAX_QUESTION_LENGTH` | `4000` | Chat question limit |
| `MAX_SELECTED_DOCUMENTS` | `50` | Subset filter limit |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `CORS_ALLOW_ORIGINS` | `["*"]` | Only needed for a cross-origin UI |

Do not commit `.env`; it is ignored by git.

## API

All endpoints are under `/api`. Errors use one envelope:

```json
{ "detail": { "code": "INVALID_FILE_TYPE", "message": "Unsupported file format. Upload PDF, DOCX, or TXT.", "details": null } }
```

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Cheap readiness check (no model call) |
| `GET` | `/api/documents/` | List indexed documents |
| `POST` | `/api/documents/upload` | Upload **one** file (`multipart/form-data`, field `file`) |
| `DELETE` | `/api/documents/{doc_id}` | Delete vectors belonging to the document |
| `POST` | `/api/chat/` | Retrieve chunks and generate an answer |

Chat request:

```json
{ "question": "What does chapter 3 say about caching?", "doc_ids": null, "k": 3 }
```

`doc_ids: null` (or omitted) searches all documents. `k` is 1–20. The response
contains `answer`, `total_chunks_retrieved`, and `retrieved_chunks` (chunk content
plus `metadata.doc_id`, `filename`, `chunk_index`, `page`, `page_number`,
`total_pages`). There is no conversation history in v1.

Upload is synchronous and accepts a single file per request; the UI uploads
multiple selected files sequentially. Re-uploading identical content replaces the
existing document's chunks safely (new chunks are upserted first, stale IDs are
deleted after).

## Reliability and error handling

- Uploads stream to a temporary file with a hard size limit; the file signature
  (magic bytes) is checked before ingestion.
- A failed upload removes partial vectors **only** for a brand-new document, so a
  failed replacement cannot destroy the previously working version.
- Duplicate detection: if a document with the same SHA-256 content hash already
  exists in Qdrant, ingestion and embedding are skipped entirely.
- Deletion removes vectors from Qdrant. Original files are temporary during
  ingestion only and are not stored persistently.
- The LLM is not called when retrieval returns no chunks; the API returns a
  deterministic "not found in the provided documents" answer.
- Provider failures are translated to stable codes (`LLM_RATE_LIMIT`,
  `LLM_TIMEOUT`, `LLM_PROVIDER_ERROR`, `LLM_NOT_CONFIGURED`). Raw provider
  payloads, secrets, filesystem paths and tracebacks are never returned to
  clients.
- All logs go through `utils/logging_config.py`. Log lines include request
  context (lengths, counts, short doc IDs) but no document contents or keys.
- The backend health check retries every 5 seconds for up to 3 minutes while
  Render spins up from cold start.

## Tests

The normal suite never touches real Qdrant and never calls Groq or Gemini. It
uses temporary directories, deterministic fake embeddings and a fake chat model.

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

`pytest.ini` selects `-m "not real_api"` by default, so the opt-in real-provider
test is skipped. To run it, use a real key:

```powershell
$env:RUN_REAL_LLM_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_real_llm.py -v -m real_api
Remove-Item Env:RUN_REAL_LLM_TESTS
```

Coverage highlights: document upload/list/delete happy paths and validation,
PDF/DOCX/TXT ingestion, safe chunk replacement, subset retrieval, chat validation,
LLM rate-limit/timeout/provider mapping, no-context answers, and sanitized error
responses.

The original milestone scripts were moved to `tests/manual/` and are excluded
from pytest collection. See [`tests/manual/README.md`](tests/manual/README.md).

## Limitations

- Single-turn chat only; no conversation memory.
- No authentication, rate limiting or multi-user isolation. Run locally or put it
  behind a trusted gateway.
- The Gemini Embedding free tier is limited to 100 embedding requests per minute.
  Large or rapid successive uploads may trigger rate-limit errors.
- Uploads are synchronous, so large PDFs keep the request open while embeddings
  run.
- Render free tier spins down after 15 minutes of inactivity; the first request
  after a spin-down incurs a cold start (~1 minute).
- Retrieval is similarity search only: no hybrid keyword search and no reranking.
- Scanned/image-only PDFs need OCR, which is not implemented.
- The frontend is intentionally framework-free and has no bundler.

## Next steps

1. Add conversation history with an explicit session store.
2. Add per-document re-index/repair tooling for interrupted replacements.
3. Add structured JSON logging and request IDs for production log aggregation.
4. Add coverage reporting (`pytest-cov`) and a CI workflow.
5. Add authentication and per-user document namespaces before exposing the app.
6. Add hybrid search combining vector similarity with keyword matching.
7. Add OCR support for scanned/image-only PDFs.
```
