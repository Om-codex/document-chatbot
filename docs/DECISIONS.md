# Engineering Decisions (ADR log)

Purpose: record *why* the project is built this way, not just what it does. Update
this file whenever a decision changes; do not silently drift from the contract.

Environment verified on 2026-11-03: Windows, Python 3.13.14, venv in
`document-chatbot/.venv`.

Updated 2026-11-17: ADRs 1, 3, 4, 6 and 7 were revised when embeddings moved from
local Hugging Face to the Gemini Embedding API and the vector store moved from
Chroma to Qdrant Cloud.

Updated 2026-11-22: added JWT Bearer auth (ADR-12), owner-scoped vectors
(ADR-13) and Neon/SQLite user storage (ADR-14); revised the CORS and deployment
notes to match the cross-origin frontend.

---

## ADR-1 — Groq for chat, Gemini Embedding API for embeddings

**Decision:** `ChatGroq` (`openai/gpt-oss-20b` by default, temperature 0, 2
retries) for generation; Google's `gemini-embedding-2` API (768-dim,
L2-normalized) for embeddings.

**Why:** free chat inference with no card, and embeddings served by a small API
client with no local model weights. This keeps the deployment within free-tier
memory limits without shipping ~1 GB of `torch` dependencies.

**Alternatives rejected:** OpenAI for both (paid, one more key); local
`sentence-transformers/all-MiniLM-L6-v2` (the original choice, but heavy and slow
on CPU); Ollama (several GB of local models, slower on CPU).

**Consequences:**
- Groq's free tier is 30 req/min, 1,000 req/day, **8K tokens/min**, 200K tokens/day.
  Keep `DEFAULT_TOP_K=3`, chunk size ~1,000 chars, concise answers, and back off on `429`.
- Llama models left Groq's free tier in Aug 2026; do not default to
  `llama-3.3-70b-versatile`. Use `openai/gpt-oss-20b` or `openai/gpt-oss-120b`.
- The Gemini Embedding free tier is limited to 100 requests/minute. Batching
  (`EMBEDDING_BATCH_SIZE`) and retries with backoff are implemented in
  `embeddings/gemini_embedding.py`; rapid large uploads can still hit a quota.
- Uploads remain synchronous in v1: embedding happens during the request, so the
  UI shows an ingestion state.

---

## ADR-2 — LCEL instead of `langchain-classic` chains

**Decision:** build the QA pipeline with LangChain Expression Language from
`langchain-core`:

```python
{"context": retriever | format_docs, "input": RunnablePassthrough()}
  | prompt | llm | StrOutputParser()
```

**Why:** in LangChain 1.x, `langchain.chains` (including
`create_stuff_documents_chain` / `create_retrieval_chain`) moved to
`langchain-classic`, which is legacy and scheduled to end support in Dec 2026.
The supported path is LCEL. It also makes retrieval → prompt assembly → generation
explicit, which is the point of this learning project.

**Alternatives rejected:** `langchain_classic.chains` (works today, wrong direction,
hides the data flow); `create_agent` (agentic loop is unnecessary for single-turn
grounded QA and adds nondeterminism).

**Consequences:** we must return sources ourselves. Use
`RunnableParallel`/`RunnablePassthrough.assign` so retrieved `Document`s are still
available next to the parsed answer. `langchain-community` still pulls
`langchain-classic` for loaders — install it, but never import chains from it.

---

## ADR-3 — Qdrant cosine distance and normalized embeddings

**Decision:** embed with `NORMALIZE_EMBEDDINGS=true` and create the Qdrant
collection with `Distance.COSINE` and 768 dimensions. Retrieval uses LangChain's
`similarity` search; the API returns the retrieved chunks themselves and does
**not** expose a distance or score.

**Why:** normalizing vectors keeps retrieval stable and matches the Cosine metric,
and the UI only needs the passage plus its metadata to cite it. Exposing an
undocumented raw distance previously caused confusion in the contract.

**Consequences:**
- Vector size and distance are fixed when the collection is created. Changing
  `GEMINI_EMBEDDING_MODEL` or `EMBEDDING_DIMENSIONS` requires a new
  `QDRANT_COLLECTION_NAME` and re-ingestion.
- If a similarity score is added later, interpret it once in
  `retrieval/retriever.py` and document the metric; do not let the UI compare
  mixed metrics.
- Qdrant point IDs must be UUIDs, so the owner-prefixed seed
  `{user_id}_{doc_id}_{chunk_index}` is mapped with `uuid5`. The logical
  `{doc_id}_{chunk_index}` string remains in payload and API responses.

---

## ADR-4 — Content-hash document IDs and deterministic chunk IDs

**Decision:** `doc_id = sha256(file bytes).hexdigest()` (all 64 characters); the
logical chunk ID is `f"{doc_id}_{chunk_index}"`. The Qdrant point ID is a `uuid5`
of `f"{user_id}_{doc_id}_{chunk_index}"` so two accounts uploading the same file
never share a point.

**Why:** re-uploading the same file is idempotent for one account (we detect the
duplicate and skip), and re-ingesting after a bug is safe (upsert instead of
duplicate vectors). Deterministic IDs also make deletion and test assertions
trivial.

**Consequences:**
- Identical content under two different filenames collapses into one document per
  account. That is intentional content-addressed deduplication; re-uploading
  replaces the existing chunks instead of adding duplicates.
- Chunk IDs are stable only while `CHUNK_SIZE`/`CHUNK_OVERLAP` are unchanged. Changing
  them changes chunk boundaries; re-ingest the document.
- Metadata must carry `user_id` and `doc_id` so owner-scoped subset filtering
  (`FieldCondition(key="metadata.user_id", ...)` plus
  `FieldCondition(key="metadata.doc_id", match=MatchAny(...))`) and document
  deletion work.

---

## ADR-5 — Metadata flows through every pipeline stage

**Decision:** every chunk carries `user_id`, `doc_id`, `filename`, `chunk_index`,
and the loader metadata (`page`, `page_label`, `total_pages`, etc. when available).

**Why:** without metadata, citations, owner scoping and selective retrieval cannot
be implemented. LangChain loaders preserve page numbers only if we do not discard
them while splitting, and the authenticated owner must travel with the vector.

**Consequences:** the splitter must copy document metadata to every child chunk and
append `chunk_index`; the retriever must keep metadata when returning `Document`s;
the API maps metadata to `retrieved_chunks[].metadata`. Tests should assert page
numbers survive.

---

## ADR-6 — Qdrant Cloud collection, single worker

**Decision:** use a hosted Qdrant Cloud collection (`QDRANT_URL` plus
`QDRANT_API_KEY`); run uvicorn with one worker (`--workers 1`) in `render.yaml`.

**Why:** a managed vector store removes local SQLite locking/corruption concerns
and works on hosts with ephemeral filesystems. One process is plenty for this
small authenticated app and keeps the process-local caches (ADR-7) simple.

**Consequences:** `--reload` is fine locally (it restarts the process). Extra
workers would each create their own Qdrant and embedding clients — safe for reads,
but needlessly duplicating connections. The collection is created on first access;
changing its name requires re-ingestion.

---

## ADR-7 — Lazy, process-local caches for expensive services

**Decision:** cache the Gemini embedding client, Qdrant store wrapper, and LLM with
`lru_cache` factories instead of building them per request. The `lifespan` handler
logs startup configuration and warns when `GROQ_API_KEY` is missing; it does not
initialize clients.

**Why:** creating API clients and opening connections per request would be slow and
leak resources, while doing it at import time makes health checks and tests
unnecessarily heavy.

**Consequences:** the first upload/chat pays client-initialization cost;
`/api/health` stays cheap because it reads Qdrant without embeddings. Tests clear
the caches between cases and patch the Qdrant client with an in-memory instance plus
fake embeddings and LLM.

---

## ADR-8 — Static frontend with an explicit CORS allow-list

**Decision:** FastAPI serves `frontend/` with `StaticFiles(..., html=True)` mounted
at `/app` as the last route. The root `/` returns a small JSON service banner.
Locally the UI is same-origin; in production the static site lives on Cloudflare
Workers and `CORS_ALLOW_ORIGINS` allow-lists that exact origin.

**Why:** keeping the UI under `/app` in development leaves `/` and `/api`
unambiguous, while hosting the static site on Workers removes backend serving
work. An explicit origin is safer than a wildcard now that Bearer tokens and
user data cross the boundary.

**Consequences:** mount order matters — Starlette matches in declaration order.
CORS must wrap the unhandled-error middleware so a structured `500` still carries
`Access-Control-Allow-Origin`; otherwise the browser reports a misleading network
failure. `?mock=1` still supports backend-free UI work.

---

## ADR-9 — One error envelope, provider errors translated

**Decision:** application errors return
`{"detail": {"code", "message", "details"}}`; Groq/embedding exceptions are mapped
to our codes at the API boundary.

**Why:** the UI needs stable machine-readable codes to decide whether to retry
(429/502/504) or show a fixable message (415/422). Leaking raw provider payloads can
expose request metadata and confuses the client.

**Consequences:** no bare `raise HTTPException(500, str(exc))`. Log the full exception
server-side, return a sanitized message. `Retry-After` is preserved for 429.

---

## ADR-10 — Mock-first frontend against a frozen contract

**Decision:** ship `frontend/js/mock.js` implementing the same method surface as the
real client, but default the UI to the real API. The mock is opt-in with `?mock=1`.

**Why:** the mock remains useful for UI work without a backend, while the default
experience exercises the actual RAG pipeline and catches contract drift early.

**Consequences:** any contract change must update `docs/API_CONTRACT.md`, the mock, and
the real client together. Mock-only seeds and error triggers must be documented, not
hidden.

---

## ADR-11 — Uploaded text is untrusted data, never instructions

**Decision:** the prompt template wraps retrieved chunks as context and explicitly
tells the model to ignore instructions found inside them; the model may only answer
from context and must say it does not know otherwise.

**Why:** PDFs and pasted text can contain prompt-injection attempts. Retrieval must
not grant them authority.

**Consequences:** user questions are sent separately from context; citations are
derived from metadata (not model output); UI renders all model text with
`textContent` to avoid XSS. JWT auth and owner-scoped retrieval limit who can read
a document (ADRs 12-13), but prompt injection is not a solved problem and the
browser-held token is an XSS trade-off.

---

## ADR-12 — JWT Bearer authentication

**Decision:** `POST /api/auth/register`, `POST /api/auth/login` and `GET /api/health`
are public. Every document and chat route requires an HS256 JWT in
`Authorization: Bearer <token>`. Passwords are hashed with Argon2 through
`pwdlib`; the backend assigns `role: "editor"` and never trusts a role from the
client.

**Why:** the API and frontend are deployed on different hosts, so a stateless
signed token keeps protected routes simple while still letting the backend own
identity checks. Short-lived tokens limit exposure, and a single storage module
keeps session handling consistent in the UI.

**Alternatives rejected:** no authentication (the original local tool);
server-side cookie sessions (cleaner for XSS, but requires a session store and a
backend logout flow — recorded as future work).

**Consequences:** `401` clears the browser session and redirects to
`/app/login.html`; `403` shows access denied without logging out. The interim
session lives in `localStorage`, which is readable by JavaScript, so tokens are
never logged or placed in URLs. Frontend guards are convenience only; the backend
validates every protected operation.

---

## ADR-13 — Owner-scoped vector storage

**Decision:** the authenticated `user_id` is written to every chunk as
`metadata.user_id`. Qdrant payload indexes cover `metadata.user_id` (integer) and
`metadata.doc_id` (keyword). Upload, list, count, delete and similarity search all
include the owner filter.

**Why:** `doc_id` is a content hash that a user can learn from a shared filename
or response. Without an owner filter, knowing that ID would be enough to read or
delete another account's chunks. Filtering at the storage boundary keeps the
invariant even if a route or UI check is missed.

**Consequences:** Qdrant point identifiers are UUIDs derived from the owner plus
doc/chunk IDs (ADR-4), and chat responses include `user_id` with chunk metadata.
Chunks ingested before this decision must be re-indexed to gain the new payload
field and index.

---

## ADR-14 — Neon user database with SQLite fallback

**Decision:** SQLAlchemy selects its engine from `DATABASE_URL`. Production uses
Neon PostgreSQL with `postgresql+psycopg://...` (psycopg v3); an unset URL falls
back to `data/users.db` on local disk. `init_database()` runs at startup to create
tables.

**Why:** Render's filesystem is ephemeral, so SQLite cannot hold accounts in
production. psycopg v3 was chosen over `psycopg2-binary` because the latter could
not be installed on the verified Python 3.13 Windows environment. The fallback
keeps offline development possible without a remote database.

**Consequences:** `DATABASE_URL` and `JWT_SECRET_KEY` must be set in the Render
dashboard (`render.yaml` declares them with `sync: false`). A database outage is
logged but does not stop startup; DB-backed auth requests fail until it recovers.
Production must use Neon — the SQLite fallback is not durable.
