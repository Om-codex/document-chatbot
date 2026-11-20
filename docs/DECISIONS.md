# Engineering Decisions (ADR log)

Purpose: record *why* the project is built this way, not just what it does. Update
this file whenever a decision changes; do not silently drift from the contract.

Environment verified on 2026-11-03: Windows, Python 3.13.14, venv in
`document-chatbot/.venv`.

Updated 2026-11-17: ADRs 1, 3, 4, 6 and 7 were revised when embeddings moved from
local Hugging Face to the Gemini Embedding API and the vector store moved from
Chroma to Qdrant Cloud.

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
- Qdrant point IDs must be UUIDs, so chunk IDs are mapped with `uuid5` while the
  original `{doc_id}_{chunk_index}` strings remain in payload and API responses.

---

## ADR-4 — Content-hash document IDs and deterministic chunk IDs

**Decision:** `doc_id = sha256(file bytes).hexdigest()` (all 64 characters); chunk
IDs are `f"{doc_id}_{chunk_index}"`.

**Why:** re-uploading the same file is idempotent (we detect the duplicate and skip),
and re-ingesting after a bug is safe (upsert instead of duplicate vectors).
Deterministic IDs also make deletion and test assertions trivial.

**Consequences:**
- Identical content under two different filenames collapses into one document. That
  is intentional content-addressed deduplication; re-uploading replaces the existing
  chunks instead of adding duplicates.
- Chunk IDs are stable only while `CHUNK_SIZE`/`CHUNK_OVERLAP` are unchanged. Changing
  them changes chunk boundaries; re-ingest the document.
- Metadata must carry `doc_id` so subset filtering
  (`FieldCondition(key="metadata.doc_id", match=MatchAny(...))`) and document
  deletion work.

---

## ADR-5 — Metadata flows through every pipeline stage

**Decision:** every chunk carries `doc_id`, `filename`, `chunk_index`, and the
loader metadata (`page`, `page_label`, `total_pages`, etc. when available).

**Why:** without metadata, citations are impossible and selective retrieval cannot
be implemented. LangChain loaders preserve page numbers only if we do not discard
them while splitting.

**Consequences:** the splitter must copy document metadata to every child chunk and
append `chunk_index`; the retriever must keep metadata when returning `Document`s;
the API maps metadata to `retrieved_chunks[].metadata`. Tests should assert page
numbers survive.

---

## ADR-6 — Qdrant Cloud collection, single worker

**Decision:** use a hosted Qdrant Cloud collection (`QDRANT_URL` plus
`QDRANT_API_KEY`); run uvicorn with one worker (`--workers 1`) in `render.yaml`.

**Why:** a managed vector store removes local SQLite locking/corruption concerns
and works on hosts with ephemeral filesystems. One process is plenty for a
single-user learning app and keeps the process-local caches (ADR-7) simple.

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

## ADR-8 — Same-origin static frontend, no CORS by default

**Decision:** FastAPI serves `frontend/` with `StaticFiles(..., html=True)` mounted
at `/app` as the last route. The root `/` returns a small JSON service banner.

**Why:** no CORS configuration, no duplicate servers, and relative asset paths just
work. Keeping the UI under `/app` leaves `/` and `/api` unambiguous.

**Consequences:** mount order matters — Starlette matches in declaration order. For
frontend development without a backend, `python -m http.server` on another port is
used with `?mock=1`; otherwise the UI calls the same origin or an explicit
`?apiBase` origin allow-listed in `CORS_ALLOW_ORIGINS`.

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
`textContent` to avoid XSS. This is not a complete security boundary — no auth,
local-only deployment — but it is the right baseline.
