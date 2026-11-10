# API Contract — Document Chatbot

Source of truth for the FastAPI backend and the static frontend.
Backend base URL: `http://127.0.0.1:8000`. All API routes live under `/api`; the
frontend is served from `/app` by the same process.

- Content type: JSON for everything except upload (`multipart/form-data`).
- The browser never receives provider API keys; all model calls are server-side.
- Field names are snake_case everywhere.
- Document IDs are 64-character lowercase SHA-256 hex strings.

---

## 1. Error envelope

Every error written by application code uses:

```json
{
  "detail": {
    "code": "INVALID_FILE_TYPE",
    "message": "Unsupported file format. Upload PDF, DOCX, or TXT.",
    "details": null
  }
}
```

`details` is optional. FastAPI request-validation failures are normalized by a
global handler to:

```json
{
  "detail": {
    "code": "VALIDATION_ERROR",
    "message": "The request body or parameters are invalid.",
    "details": [{ "loc": ["body", "question"], "msg": "...", "type": "..." }]
  }
}
```

| HTTP | `code` | Meaning |
|---|---|---|
| 400 | `INVALID_REQUEST` | Generic bad input |
| 400 | `NO_DOCUMENTS` | Collection is empty; ingest something first |
| 400 | `INVALID_DOCUMENT_SELECTION` | One or more selected `doc_ids` are no longer indexed |
| 400 | `INVALID_DOCUMENT_ID` | Malformed `doc_id` |
| 404 | `DOCUMENT_NOT_FOUND` | Unknown `doc_id` |
| 413 | `FILE_TOO_LARGE` | Per-file limit exceeded |
| 415 | `INVALID_FILE_TYPE` | Extension or signature not allowed |
| 422 | `EMPTY_DOCUMENT` | Empty or text-less file |
| 422 | `MALFORMED_DOCUMENT` | File could not be parsed / signature mismatch |
| 422 | `VALIDATION_ERROR` | Pydantic request validation |
| 429 | `LLM_RATE_LIMIT` | Groq rate limit; includes `Retry-After` and `details.retry_after` |
| 500 | `DELETION_ERROR` | Vector or file deletion failed unexpectedly |
| 500 | `CHAT_ERROR` | Unexpected chat-service failure |
| 500 | `INTERNAL_ERROR` | Unexpected failure (never leaks stack traces/keys) |
| 502 | `LLM_PROVIDER_ERROR` | Groq returned an error |
| 503 | `STORAGE_ERROR` | Vector store write/read failure |
| 503 | `RETRIEVAL_ERROR` | Retrieval pipeline failure |
| 503 | `LLM_NOT_CONFIGURED` | Missing `GROQ_API_KEY` |
| 504 | `LLM_TIMEOUT` | Model call exceeded `LLM_TIMEOUT_SECONDS` |

Uploads are **per-request**: one file per request. The frontend uploads multiple
files sequentially and reports failures per file.

---

## 2. `GET /api/health`

Cheap readiness check; does not load the embedding model or call the LLM.

```json
{
  "status": "ok",
  "app_name": "Document Chatbot API",
  "app_version": "1.0.0",
  "llm_model": "openai/gpt-oss-20b",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "collection": "document_collection_v2",
  "document_count": 1
}
```

`status` is `"ok"` or `"degraded"` (vector store could not be read). The endpoint
still returns `200` when degraded; `document_count` may be `null`.

---

## 3. `GET /api/documents/`

```json
{
  "total_documents": 1,
  "documents": [
    {
      "doc_id": "6f1c...64 hex chars...",
      "filename": "lecture-01.pdf",
      "total_pages": 12,
      "total_chunks": 42
    }
  ]
}
```

- `total_pages` is `null` for TXT and DOCX.
- `total_chunks` is the number of vectors currently stored for the document.
- `doc_id` is the SHA-256 of the original file bytes (content-addressed).

---

## 4. `POST /api/documents/upload`

`multipart/form-data`, field name **`file`** (one file per request).

Limits: 10 MB per file (`MAX_FILE_SIZE_BYTES`).
Allowed extensions: `.pdf`, `.txt`, `.docx` (case-insensitive); the signature is
validated before ingestion and filenames are sanitized.

Response `200`:

```json
{
  "message": "Document uploaded and indexed successfully.",
  "filename": "lecture-01.pdf",
  "doc_id": "6f1c...64 hex chars...",
  "total_chunks": 42,
  "file_size_bytes": 1048576
}
```

Rules:

- Ingestion is synchronous: the response returns after chunks are embedded and
  stored.
- Re-uploading identical bytes is idempotent: new chunks are upserted first and
  stale chunk IDs are removed afterwards, so a failure cannot delete the previous
  working version.
- A failed brand-new upload cleans up its partial vectors and UUID directory.

---

## 5. `DELETE /api/documents/{doc_id}`

`doc_id` must match `^[a-f0-9]{64}$`.

Deletes vectors first, then any stored files whose content hash matches. If file
deletion fails after vectors are gone, the endpoint still returns `200` and lists
the problem in `warnings`.

```json
{
  "message": "Document deleted successfully.",
  "doc_id": "6f1c...",
  "filename": "lecture-01.pdf",
  "deleted_files": 1,
  "vectors_deleted": true,
  "warnings": []
}
```

- `404 DOCUMENT_NOT_FOUND` if the document is not indexed.
- The UI treats a 404 on delete as "already gone".

---

## 6. `POST /api/chat/`

JSON body:

```json
{
  "question": "What does chapter 3 say about caching?",
  "doc_ids": null,
  "k": 3
}
```

| Field | Rules |
|---|---|
| `question` | 1–4,000 characters, trimmed, required |
| `doc_ids` | `null`/omitted = search **all** documents. A non-empty array of 64-char IDs = search only those. `[]` is treated as "all" for backward compatibility |
| `k` | optional, 1–20; defaults to `DEFAULT_TOP_K` (3) |

Single-turn in v1: no conversation history is sent or stored.

Response `200`:

```json
{
  "question": "What does chapter 3 say about caching?",
  "answer": "Chapter 3 describes a write-through cache ... [1]",
  "total_chunks_retrieved": 2,
  "retrieved_chunks": [
    {
      "chunk_id": "6f1c..._18",
      "content": "A write-through cache writes to the cache and the backing store.",
      "metadata": {
        "doc_id": "6f1c...",
        "filename": "lecture-01.pdf",
        "chunk_index": 18,
        "page": 6,
        "page_number": 7,
        "page_label": null,
        "total_pages": 12
      }
    }
  ]
}
```

- `retrieved_chunks` may be empty. The LLM is then skipped and `answer` is the
  deterministic no-context message.
- `page` is zero-based (loader metadata); `page_number` is one-based for display.
- `429` responses include `Retry-After` and `detail.details.retry_after`.
- Raw provider error bodies are never forwarded.

---

## 7. Frontend mapping

| UI action | Request |
|---|---|
| Load page | `GET /api/health` + `GET /api/documents/` (parallel) |
| Drop / choose files | `POST /api/documents/upload` once per file, field `file` |
| Paste text → Save | Build a `.txt` `File` and upload it through the same endpoint |
| Trash icon | `DELETE /api/documents/{doc_id}` |
| "All documents" scope | `POST /api/chat/` with `doc_ids: null` |
| Specific selection | `POST /api/chat/` with `doc_ids: [...]` |
| Sources selector | `POST /api/chat/` with `k: 1..10` |

The UI uses the real API by default. Append `?mock=1` to use
`frontend/js/mock.js` without a backend; `?apiBase=http://127.0.0.1:8000` points a
cross-origin UI at the API.

---

## 8. Mock adapter behavior

- Seeds two documents: `lecture-notes.pdf` (12 chunks, 4 pages) and
  `getting-started.txt` (5 chunks).
- Upload accepts `.pdf`, `.txt`, `.docx`; a filename containing `fail` produces an
  upload error to demo per-file failures.
- A question containing `rate limit` returns `429 LLM_RATE_LIMIT` with
  `retry_after: 5`.
- Any other question returns a canned grounded answer and mock retrieved chunks.
- Latency is simulated (~600 ms) so loading states are visible.

---

## 9. Curl examples (PowerShell)

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/documents/

curl.exe -X POST http://127.0.0.1:8000/api/documents/upload `
  -F "file=@C:\path\lecture.pdf"

Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/chat/ `
  -ContentType 'application/json' `
  -Body '{"question":"What is the main topic?","doc_ids":null,"k":3}'

Invoke-RestMethod -Method Delete http://127.0.0.1:8000/api/documents/<64-hex-doc-id>
```

---

## 10. Serving the frontend

Same origin, no CORS required:

```python
app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")
```

The mount is declared **after** all `/api` routes and the root endpoint because
Starlette matches routes in declaration order. To run the UI from a separate dev
server, allow-list that origin in `CORS_ALLOW_ORIGINS`.
