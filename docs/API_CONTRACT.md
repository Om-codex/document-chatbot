# API Contract — Document Chatbot

Single source of truth for the FastAPI backend and the static frontend.
Backend base URL: `http://127.0.0.1:8000`. All API routes live under `/api` so the
frontend can be mounted at `/` without route conflicts.

- Content type: JSON for everything except file upload (`multipart/form-data`).
- The frontend never receives provider API keys; all model calls happen server-side.
- Timestamps are ISO-8601 UTC strings.
- Field names are snake_case everywhere (matches Python and JSON).

---

## 1. Error envelope

Every non-2xx response written by our own code uses:

```json
{
  "detail": {
    "code": "INVALID_FILE_TYPE",
    "message": "Unsupported file type: .exe",
    "details": { "filename": "notes.exe", "allowed": [".pdf", ".txt", ".md", ".docx"] }
  }
}
```

`details` is optional. The only exception is FastAPI's automatic request-validation
error, which returns `{"detail": [ ... ]}`. The frontend's `api.js` normalizes both
shapes, but the backend should override the validation handler (M5) so clients see
one shape.

| HTTP | `code` | Meaning |
|---|---|---|
| 400 | `NO_FILES` | Upload request contained no files |
| 400 | `NO_DOCUMENTS_SELECTED` | Chat asked for a subset but sent an empty list |
| 400 | `NO_DOCUMENTS` | Collection is empty; ingest something first |
| 400 | `INVALID_REQUEST` | Generic bad input |
| 401 | `LLM_AUTH_ERROR` | Missing/invalid `GROQ_API_KEY` (server-side only) |
| 404 | `DOCUMENT_NOT_FOUND` | Unknown `doc_id` |
| 413 | `FILE_TOO_LARGE` | Per-file limit exceeded |
| 415 | `INVALID_FILE_TYPE` | Extension not allowed |
| 422 | `EMPTY_DOCUMENT` | Empty text or unreadable file |
| 429 | `LLM_RATE_LIMIT` | Groq rate limit; includes `Retry-After` header and `details.retry_after` |
| 500 | `EMBEDDING_ERROR` | Embedding/vector-store failure |
| 500 | `INTERNAL_ERROR` | Unexpected failure (never leak stack traces/keys) |
| 502 | `LLM_PROVIDER_ERROR` | Groq returned an error |
| 504 | `LLM_TIMEOUT` | Model call exceeded `LLM_TIMEOUT_SECONDS` |

Uploads are **per-file tolerant**: one bad file must not fail the whole request.
Per-file problems are reported inside a 200/422 response (see §4).

---

## 2. `GET /api/health`

Cheap readiness check; no model invocation.

```json
{
  "status": "ok",
  "llm_model": "openai/gpt-oss-120b",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "collection": "document_chatbot",
  "document_count": 3
}
```

`status` is `"ok"` or `"degraded"`. Return `503` only if the app is not ready to
serve at all (e.g. vector store could not be opened). Never include secrets.

---

## 3. `GET /api/documents`

```json
{
  "documents": [
    {
      "doc_id": "9f2c1a7b3d40",
      "filename": "lecture-01.pdf",
      "source_type": "pdf",
      "chunk_count": 42,
      "page_count": 12,
      "size_bytes": 1048576,
      "created_at": "2026-11-03T09:15:00Z"
    }
  ]
}
```

`source_type` is one of `pdf`, `txt`, `markdown`, `docx`, `text`.
`page_count` is `null` for txt/markdown/docx/text. `doc_id` is a stable
content-derived identifier (see `docs/DECISIONS.md`, ADR-4).

---

## 4. `POST /api/documents/upload`

`multipart/form-data`, field name **`files`** (repeat the field for multiple files).
Limits: 20 MB per file, 10 files per request, 50 MB total.

Allowed extensions: `.pdf`, `.txt`, `.md`, `.docx` (case-insensitive).
The backend must validate extension **and magic bytes**, and sanitize filenames
(path traversal, control characters) before writing to disk.

Response `200` (partial success is normal):

```json
{
  "documents": [
    {
      "doc_id": "9f2c1a7b3d40",
      "filename": "lecture-01.pdf",
      "source_type": "pdf",
      "chunk_count": 42,
      "page_count": 12,
      "size_bytes": 1048576,
      "created_at": "2026-11-03T09:15:00Z"
    }
  ],
  "errors": [
    {
      "filename": "notes.exe",
      "code": "INVALID_FILE_TYPE",
      "message": "Unsupported file type: .exe"
    }
  ]
}
```

Rules:

- Duplicate content (same `doc_id`) → `errors[]` entry with code
  `DUPLICATE_DOCUMENT`; nothing is re-embedded.
- `documents` may be empty when every file failed, but the status stays `200`
  so the UI can display the per-file reasons. A completely malformed request
  (no `files` field) returns `400 NO_FILES`.
- Ingestion is synchronous in v1: the response returns only after chunks are
  stored. Expect a few seconds for large PDFs (local embeddings on CPU).

---

## 5. `POST /api/documents/text`

For the "Paste text" dialog. JSON body:

```json
{ "title": "Meeting notes", "content": "..." }
```

- `title`: 1–120 characters, used as `filename` and in citations.
- `content`: 1–100,000 characters.
- Runs the same chunk → embed → store pipeline with `source_type: "text"` and
  `page_count: null`.

Response `201`:

```json
{ "document": { "doc_id": "...", "filename": "Meeting notes", "source_type": "text", "chunk_count": 3, "page_count": null, "size_bytes": 812, "created_at": "..." } }
```

---

## 6. `DELETE /api/documents/{doc_id}`

Deletes the stored original file, all chunks/vectors for that `doc_id`, and any
document registry row.

- `200` → `{ "deleted": true, "doc_id": "9f2c1a7b3d40" }`
- `404` → `DOCUMENT_NOT_FOUND`

Deletion must be idempotent from the client's point of view: if the UI double-clicks,
the second call may return 404 and the UI treats it as "already gone".

---

## 7. `POST /api/chat`

JSON body:

```json
{
  "question": "What does chapter 3 say about caching?",
  "document_ids": null,
  "top_k": 4
}
```

| Field | Rules |
|---|---|
| `question` | 1–2,000 characters, required |
| `document_ids` | `null`/absent = search **all** documents. A non-empty array = search only those docs. `[]` → `400 NO_DOCUMENTS_SELECTED`. Unknown ids → `400 INVALID_REQUEST` (or `404`) |
| `top_k` | optional, 1–10; defaults to `TOP_K` from settings |

Single-turn in v1: no conversation history is sent or stored.

Response `200`:

```json
{
  "answer": "Chapter 3 describes a write-through cache ... [1]",
  "sources": [
    {
      "doc_id": "9f2c1a7b3d40",
      "filename": "lecture-01.pdf",
      "page": 7,
      "chunk_index": 18,
      "score": 0.82,
      "snippet": "A write-through cache writes to ..."
    }
  ],
  "model": "openai/gpt-oss-120b"
}
```

- `score` = **cosine similarity** in `[-1, 1]`, higher is more similar.
  Do not expose raw Chroma distances in the API; convert once at the boundary.
- `page` is a number for PDFs, `null` for text-like sources.
- `snippet` is at most ~300 characters of the retrieved chunk (do not return the
  full chunk; the UI only needs enough to recognize the source).
- `sources` may be empty if the retriever found nothing; `answer` should then be
  an explicit "not found in the provided documents" message.
- `429` responses include `Retry-After` (seconds) and
  `detail.details.retry_after`.
- The backend must not forward the raw Groq error body (it can contain internal
  request metadata).

---

## 8. Frontend mapping

| UI action | Request |
|---|---|
| Load page | `GET /api/health` + `GET /api/documents` (parallel) |
| Drop / choose files | `POST /api/documents/upload` (FormData, `files`) |
| Paste text → Save | `POST /api/documents/text` |
| Trash icon | `DELETE /api/documents/{doc_id}` |
| "All documents" scope | `POST /api/chat` with `document_ids: null` |
| Specific selection | `POST /api/chat` with `document_ids: [...]` |

The frontend ships with a mock adapter (`frontend/js/mock.js`) that implements the
same method signatures, so the UI works before the backend exists. Switch it with
`frontend/js/config.js` (`useMock: false`) or the URL flag `?mock=0`.

---

## 9. Mock adapter behavior (M1 only)

- Seeds two documents: `lecture-notes.pdf` (pdf, 12 chunks, 4 pages) and
  `getting-started.md` (markdown, 5 chunks).
- Uploads accept the four allowed extensions; a filename containing `fail`
  produces a `INVALID_FILE_TYPE`-style per-file error to demo partial failures.
- Questions containing `rate limit` return a `429 LLM_RATE_LIMIT` to demo the
  retry path. Any other question returns a canned grounded answer with two
  citations from the current selection.
- Latency is simulated (~600 ms) so loading states are visible.

---

## 10. Curl examples (PowerShell)

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health

curl.exe -X POST http://127.0.0.1:8000/api/documents/upload `
  -F "files=@C:\path\lecture.pdf" `
  -F "files=@C:\path\notes.md"

Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/chat `
  -ContentType 'application/json' `
  -Body '{"question":"What is the main topic?","document_ids":null}'

Invoke-RestMethod -Method Delete http://127.0.0.1:8000/api/documents/9f2c1a7b3d40
```

---

## 11. Serving the frontend (M6)

Recommended: same origin, no CORS.

```python
# app.py — after all /api routes are declared
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```

Mounting at `/` must be the **last** statement, because Starlette matches routes
in order. Avoid adding `CORSMiddleware` if the UI is served this way. If you
instead run the UI from `http://127.0.0.1:5500`, allow exactly that origin.
