# Document Chatbot

Ask grounded questions about your own PDF, TXT, Markdown and DOCX files.

**Status:** M0 (foundation) and M1 (frontend, mock mode) are complete.
The backend/RAG modules are intentionally empty placeholders for the next
milestones — they will be implemented step by step.

- Architecture and API contract: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)
- Engineering decisions: [`docs/DECISIONS.md`](docs/DECISIONS.md)

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Orchestration | LangChain 1.x (LCEL) |
| Vector store | ChromaDB (persistent, cosine distance) |
| Chat model | Groq (`openai/gpt-oss-120b` by default) |
| Embeddings | Local Hugging Face `all-MiniLM-L6-v2` (384-dim, CPU) |
| Frontend | Plain HTML, CSS, JavaScript (no build step) |

Verified on Python 3.13.14, Windows.

## Project layout

```
document-chatbot/
├── app.py                     # FastAPI entrypoint (M5 — yours)
├── requirements.txt           # pinned, direct dependencies
├── .env.example               # documented settings, copy to .env
├── config/settings.py         # typed settings (M2 — yours)
├── ingestion/
│   ├── document_loader.py     # PDF/TXT/MD/DOCX loaders (M2 — yours)
│   └── text_splitter.py       # chunking + metadata (M2 — yours)
├── embeddings/embedding_model.py   # HuggingFaceEmbeddings factory (M3)
├── vectorstore/chroma_store.py     # persistent Chroma wrapper (M3)
├── retrieval/retriever.py          # top-k retrieval (M3)
├── chains/
│   ├── prompt_template.py     # grounded prompt (M4)
│   └── qa_chain.py            # LCEL chain (M4)
├── utils/helpers.py           # validation, IDs, formatting (M2+)
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/
│       ├── config.js          # mock/real switch + limits
│       ├── api.js             # HTTP client (fetch + XHR upload)
│       ├── mock.js            # M1 mock adapter
│       └── app.js             # UI controller
├── docs/                      # API contract + decision log
├── tests/                     # pytest suite (M6)
├── chroma_db/                 # persisted vectors (gitignored)
└── data/uploaded_documents/   # original uploads (gitignored)
```

## Setup (Windows PowerShell)

```powershell
cd document-chatbot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

First install downloads PyTorch + sentence-transformers (roughly 1 GB) and the
first embedding call downloads the model (~90 MB).

If PowerShell blocks activation, either run `Set-ExecutionPolicy -Scope Process Bypass`
or call `.\.venv\Scripts\python.exe` directly.

## Preview the UI (mock mode, no backend needed)

```powershell
python -m http.server 5500 --directory frontend
```

Open <http://127.0.0.1:5500/>.

The mock adapter seeds two documents, simulates latency, and supports every UI
state. Useful triggers:

- upload a file named `broken-fail.pdf` → per-file upload error
- ask a question containing `rate limit` → 429 error with a retry hint
- delete all documents → empty state / `NO_DOCUMENTS`

Mock behavior is documented in [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md#9-mock-adapter-behavior-m1-only).

### Switching to the real API later

1. Set `useMock: false` in `frontend/js/config.js`, **or** open the page with
   `?mock=0`.
2. If you serve the frontend from a different origin than the API, pass
   `?apiBase=http://127.0.0.1:8000` and allow that origin in FastAPI. The
   recommended M6 setup is same-origin (`StaticFiles` mount), which needs no CORS.

## Configuration

Copy `.env.example` to `.env` and set at minimum:

```dotenv
GROQ_API_KEY=...
```

| Variable | Default | Notes |
|---|---|---|
| `GROQ_API_KEY` | — | <https://console.groq.com/keys> |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Llama models are not on Groq's free tier |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Changing it changes vector dimensions |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1000` / `150` | Changing them requires re-ingestion |
| `TOP_K` | `4` | Keep small on Groq's 8K tokens/min free limit |
| `COLLECTION_NAME` | `document_chatbot` | Use a new name when changing embedding models |
| `MAX_FILE_MB` | `20` | Also enforced in the UI |

Do not commit `.env`; it is ignored by git.

## Current frontend capabilities (M1)

- Drag-and-drop / file picker for PDF, TXT, MD, DOCX (client-side type + size checks)
- Paste-text dialog (title + content, character counter)
- Document library with per-document checkboxes, “Select all”, delete, refresh
- Search scope sent to the API as `document_ids: null` (all) or an array (subset)
- Chat transcript with typing state, retry on failure, abortable requests
- Source citations rendered as collapsible cards (page, chunk, match score, snippet)
- Error banner, upload progress, per-file feedback, toast confirmations
- Responsive layout, keyboard support, reduced-motion support, `aria-live` announcements
- All API/model text rendered with `textContent` (no HTML injection)

## Verification performed in M0

- Clean virtualenv install of `requirements.txt`
- Import checks for FastAPI, Chroma, LangChain integrations, Groq, and Hugging Face embeddings
- Chroma smoke test (persistent collection, cosine space, add + query with score)
- Embedding smoke test (model download + 384-dimensional vectors)

See the M0 report for exact command output and any warnings.

## Next milestones

| Milestone | Owner | Scope |
|---|---|---|
| M2 | you | settings, exceptions, loaders, splitter |
| M3 | you | embeddings, Chroma store, retriever |
| M4 | you | prompt template, LCEL chain, Groq |
| M5 | you | FastAPI routes, validation, error mapping |
| M6 | joint | integration, tests, hardening, final README |

No milestone starts before the previous one passes its acceptance check.
