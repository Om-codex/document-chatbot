# Document Chatbot

Ask grounded questions about your own PDF, TXT and DOCX files. The backend is a
FastAPI RAG service deployed on Render; the frontend is plain HTML/CSS/JS hosted
on Cloudflare Workers.

- Live frontend: https://document-chatbot.omm512462.workers.dev/
- Architecture and endpoint reference: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)
- Engineering decisions: [`docs/DECISIONS.md`](docs/DECISIONS.md)

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Orchestration | LangChain 1.x (LCEL) |
| Authentication | JWT Bearer tokens (`PyJWT`) with Argon2 password hashing (`pwdlib`) |
| User database | Neon PostgreSQL via SQLAlchemy + `psycopg` v3 (`postgresql+psycopg://`); SQLite fallback for local development |
| Vector store | Qdrant Cloud (768-dim, Cosine distance, per-user metadata filters) |
| Chat model | Groq `openai/gpt-oss-20b` (temperature 0, 2 retries) |
| Embeddings | Google Gemini `gemini-embedding-2` API (768-dim, normalized) |
| Frontend | Plain HTML, CSS, JavaScript (no build step) |
| Tests | pytest + FastAPI `TestClient`, isolated temp storage |

Verified on Python 3.13.14, Windows.

## Project layout

```
document-chatbot/
├── app.py                     # FastAPI entrypoint, middleware, startup DB init, static mount
├── requirements.txt           # pinned, direct dependencies
├── .env.example               # documented settings, copy to .env
├── pytest.ini                 # default test selection
├── config/settings.py         # typed settings (env-driven)
├── api/
│   ├── errors.py              # {detail: {code, message, details?}} helper
│   ├── routes/                # auth, documents, chat, health routers
│   └── schemas/               # request/response Pydantic models
├── auth/
│   ├── token.py               # JWT encode/decode and expiry handling
│   ├── dependencies.py        # Bearer extraction and current-user lookup
│   └── security.py            # password hashing/verification
├── database/
│   ├── connection.py          # SQLAlchemy engine/session (psycopg or SQLite)
│   ├── init_db.py             # creates tables at application startup
│   └── models.py              # User model (id, email, hash, role, active, created_at)
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
├── retrieval/retriever.py          # top-k retrieval with owner + optional doc filters
├── chains/
│   ├── prompt_template.py     # grounded prompt (context is untrusted data)
│   └── qa_chain.py            # LCEL chain
├── generation/
│   ├── llm.py                 # cached ChatGroq factory
│   └── exceptions.py          # provider error translation
├── utils/                     # logging, validation, file signatures, helpers
├── frontend/
│   ├── index.html             # landing page (site entry)
│   ├── login.html             # sign in / create account
│   ├── chat.html              # authenticated chatbot UI
│   ├── tour.html              # tour chooser + accessible tour dialog
│   ├── about.html             # motivation, architecture, decisions, limits
│   ├── css/
│   │   ├── styles.css         # chatbot UI styles
│   │   └── site.css           # landing, tours and About styles
│   └── js/
│       ├── config.js          # API base, mock switch and limits
│       ├── api.js             # HTTP client (fetch + XHR upload, Bearer header)
│       ├── mock.js            # optional demo adapter
│       ├── auth.js            # register/login/session operations
│       ├── auth-page.js       # login/signup form controller
│       ├── session.js         # single localStorage session store
│       ├── app.js             # authenticated dashboard controller
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
# edit .env and set GROQ_API_KEY, QDRANT_URL, QDRANT_API_KEY, GEMINI_API_KEY,
# JWT_SECRET_KEY and (for Neon) DATABASE_URL
```

For the deployed user database, `DATABASE_URL` uses the psycopg v3 dialect:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
JWT_SECRET_KEY=<random string of at least 32 bytes>
```

If `DATABASE_URL` is omitted, the backend falls back to a local SQLite file at
`data/users.db`. That is useful for offline development but is not durable on
Render; the live service uses Neon. The vector library is Qdrant Cloud in both
cases. No PyTorch or sentence-transformers download is required. Embeddings are
served by the Google Gemini Embedding API.

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
```

- Site: <http://127.0.0.1:8000/app/>
- Sign in / create account: <http://127.0.0.1:8000/app/login.html>
- Chatbot (sign-in required): <http://127.0.0.1:8000/app/chat.html>
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
- `frontend/login.html` provides sign-in and registration; the dashboard redirects
  there until `GET /api/auth/me` confirms a valid JWT.
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

Open <http://127.0.0.1:5500/login.html?mock=1>, sign in with any valid email and
8–128 character password, then open
<http://127.0.0.1:5500/chat.html?mock=1>. The landing, tour and About pages are
static and do not call the API, so they work without a server. Without `?mock=1`
the chatbot calls the real API at the same origin and requires a real account.
When the UI is served from another origin, pass
`?apiBase=http://127.0.0.1:8000` and allow that origin in `CORS_ALLOW_ORIGINS`.

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
JWT_SECRET_KEY=...
DATABASE_URL=postgresql+psycopg://...
```

`DATABASE_URL` is optional for offline development (SQLite fallback), but must be
set for the Neon-backed deployment. Use the `postgresql+psycopg://` scheme; the
old `postgresql+psycopg2://` scheme is no longer supported.

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
| `DATABASE_URL` | `sqlite:///data/users.db` | Use `postgresql+psycopg://...` for Neon; SQLite is a local fallback |
| `JWT_SECRET_KEY` | — | Required, at least 32 bytes; HS256 signing secret |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Lifetime of the access token inside the JWT |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `CORS_ALLOW_ORIGINS` | `["*"]` | Only needed for a cross-origin UI |

Do not commit `.env`; it is ignored by git.

## API

All endpoints are under `/api`. Errors use one envelope:

```json
{ "detail": { "code": "INVALID_FILE_TYPE", "message": "Unsupported file format. Upload PDF, DOCX, or TXT.", "details": null } }
```

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/health` | public | Cheap readiness check (no model call) |
| `POST` | `/api/auth/register` | public | Create an account with email + password |
| `POST` | `/api/auth/login` | public | Verify credentials and return a JWT |
| `GET` | `/api/auth/me` | Bearer | Validate the token and return the public user |
| `GET` | `/api/documents/` | Bearer | List the signed-in user's indexed documents |
| `POST` | `/api/documents/upload` | Bearer | Upload **one** file (`multipart/form-data`, field `file`) |
| `DELETE` | `/api/documents/{doc_id}` | Bearer | Delete the user's vectors for that document |
| `POST` | `/api/chat/` | Bearer | Retrieve the user's chunks and generate an answer |

Chat request:

```json
{ "question": "What does chapter 3 say about caching?", "doc_ids": null, "k": 3 }
```

`doc_ids: null` (or omitted) searches all documents. `k` is 1–20. The response
contains `answer`, `total_chunks_retrieved`, and `retrieved_chunks` (chunk content
plus `metadata.user_id`, `doc_id`, `filename`, `chunk_index`, `page`, `page_number`,
and `total_pages`). There is no conversation history in v1.

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
- Every document and chat operation is scoped by the authenticated `user_id`.
  Qdrant payload indexes on `metadata.user_id` and `metadata.doc_id` make those
  filters efficient, and retrieval always includes the owner filter.
- `init_database()` runs at startup so the `users` table is created on a fresh
  instance. If the database is unreachable the failure is logged and the app
  still starts, but DB-backed auth requests will fail until it is reachable.
- Unhandled errors are converted by middleware that sits inside CORS, so browser
  clients receive the structured error envelope rather than an opaque network
  error.
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

## Authentication (frontend integration)

The API is JWT Bearer based; the backend owns registration, login, hashing and
authorization. The frontend adds `frontend/login.html` (sign in / create
account) and guards the dashboard at `frontend/chat.html`.

1. `POST /api/auth/register` sends only `email` and `password`. Password rule is
   **8–128 characters**, with no complexity policy. The backend assigns the
   role (`editor`); the form never sends or accepts one.
2. `POST /api/auth/login` returns `access_token`, `token_type: bearer` and the
   public user. `frontend/js/auth.js` persists them through the single storage
   module `frontend/js/session.js`.
3. `GET /api/auth/me` validates the session on dashboard load, reload and after
   login. `frontend/js/api.js` attaches `Authorization: Bearer <token>` to every
   protected document and chat request. Uploads use XHR and deliberately do not
   set `Content-Type`, so the browser supplies the multipart boundary.
4. `401 Unauthorized` clears the session and redirects to the sign-in page.
   `403 Forbidden` shows an access-denied message without logging the user out.
5. Logout is frontend-only: it clears the session. No backend logout endpoint
   exists or is needed.

**Token-storage trade-off.** The backend returns the JWT in the response body,
so the interim frontend keeps it in `localStorage` under
`document-chatbot.session`, centralized in `session.js`. `localStorage` is
readable by JavaScript and is therefore vulnerable to token theft through XSS;
this is **not** a fully secure cookie replacement. Passwords are never stored,
tokens are never logged, and tokens are never placed in URLs. Moving to
HttpOnly + Secure + SameSite cookies would require a backend change and is out
of scope for this integration.

The marketing pages, tours, `GET /api/health`, registration and login stay
public; only the document and chat features require authentication.

### User storage and per-user isolation

User records live in the `users` table and contain:

- `id` — the user ID. The JWT carries it as the `sub` claim.
- `email` — normalized to lowercase and unique.
- `hashed_password` — an Argon2 hash. Plain passwords are never stored.
- `role` — assigned by the backend (`editor`); the UI never sends one.
- `is_active` — inactive accounts cannot authenticate.
- `created_at` — account creation time.

Token expiry is **not** a database column. It is the `exp` claim inside the
signed JWT (`iat` and `sub` are also in the token). The browser keeps the JWT
and public user fields in `document-chatbot.session`.

The deployed user store is **Neon PostgreSQL**, reached with SQLAlchemy and the
psycopg v3 driver through `postgresql+psycopg://...`. SQLite at
`data/users.db` remains the automatic fallback when `DATABASE_URL` is unset, so
local development can run without external database access. The two modes are
configured only by `DATABASE_URL`; no code change is needed to switch.

Document isolation has two layers:

1. The API derives `user_id` from the validated JWT and passes it to every
   document/chat service call.
2. Each Qdrant chunk stores `metadata.user_id`; upload, list, delete and
   retrieval filters include that field, so one account cannot read or delete
   another account's chunks even when a `doc_id` is known.

## Tests

The normal suite never touches real Qdrant and never calls Groq or Gemini. It
uses an in-memory Qdrant client, deterministic fake embeddings and a fake chat
model.

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

The auth flow is also smoke-tested locally against the SQLite fallback:
registration, login, `/api/auth/me`, and rejection of protected requests without
a token.

The original milestone scripts and the live Qdrant/Gemini smoke checks live in
`tests/manual/` and are excluded from pytest collection. See
[`tests/manual/README.md`](tests/manual/README.md).

## Limitations

- Single-turn chat only; no conversation memory.
- No rate limiting yet. Authentication and per-user document isolation are
  implemented, but the JWT is held in browser storage (see above) and frontend
  route protection is not a security boundary: the backend validates every
  protected operation.
- The SQLite fallback writes to the local container filesystem and is not
  durable on Render. Production must set `DATABASE_URL` to Neon PostgreSQL;
  local SQLite is for development only.
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
5. Move sessions from browser storage to backend-managed HttpOnly cookies.
6. Add hybrid search combining vector similarity with keyword matching.
7. Add OCR support for scanned/image-only PDFs.
