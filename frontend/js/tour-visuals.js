/**
 * HTML renderers for the tour visuals.
 *
 * Everything here is static, authored markup — no data from the API, no user
 * input. `escapeHtml` is still used for the few values that come from tour
 * content so the module stays safe if content is edited later.
 */

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function chip(text, accent) {
  return `<span class="tv-chip${accent ? " tv-chip--accent" : ""}">${escapeHtml(text)}</span>`;
}

function node(title, sub, accent) {
  return `<div class="tv-node${accent ? " tv-node--accent" : ""}">
    <strong>${title}</strong>
    ${sub ? `<span>${sub}</span>` : ""}
  </div>`;
}

function arrow() {
  return '<div class="tv-arrow" aria-hidden="true"></div>';
}

function title(text) {
  return `<p class="tv-title">${escapeHtml(text)}</p>`;
}

/* ------------------------------------------------------------- Tour A pieces */

const ragVisuals = {
  upload() {
    return `${title("Request path")}
      <div class="tv-stack">
        ${node("Browser", "multipart/form-data · one file")}
        ${arrow()}
        ${node("POST /api/documents/upload", "FastAPI <code>UploadFile</code>", true)}
        ${arrow()}
        ${node("Document service", "validate · stream · save")}
      </div>
      <div class="tv-chip-row">
        ${chip(".pdf .txt .docx", true)}
        ${chip("≤ 10 MB")}
        ${chip("signature check")}
      </div>
      <p class="tv-note">The file is streamed to a per-upload directory. If validation or ingestion fails, the partial upload is cleaned up.</p>`;
  },

  loaders() {
    return `${title("Format-specific loaders")}
      <div class="tv-split">
        <div class="tv-file"><strong>PDF</strong><span>PyPDFLoader</span></div>
        <div class="tv-file"><strong>DOCX</strong><span>Docx2txtLoader</span></div>
        <div class="tv-file"><strong>TXT</strong><span>TextLoader</span></div>
      </div>
      ${arrow()}
      ${node("Document objects", "page text + loader metadata", true)}
      <p class="tv-note">Page metadata from the loader is carried forward, so a source can point to a page rather than only a file.</p>`;
  },

  chunking() {
    return `${title("Splitting one document")}
      <div class="tv-doc">
        <div class="tv-doc__bar" aria-hidden="true"></div>
        <div class="tv-chunks">
          <div class="tv-chunk"><span>chunk 0 · up to 1,000 chars</span></div>
          <div class="tv-chunk tv-chunk--2"><span>chunk 1 · 200 char overlap</span></div>
          <div class="tv-chunk tv-chunk--3"><span>chunk 2 · 200 char overlap</span></div>
        </div>
      </div>
      <div class="tv-chip-row">
        ${chip("size 1000", true)}
        ${chip("overlap 200")}
        ${chip("paragraph → line → space")}
      </div>
      <p class="tv-note">Overlap keeps a sentence that straddles a boundary retrievable from both sides.</p>`;
  },

  metadata() {
    return `${title("Chunk metadata")}
      <pre class="tv-code">doc_id:  "9f2c…a41e"   // SHA-256 of file bytes
filename: "annual-report.pdf"
chunk_index: 5
page: 12
page_label: "12"</pre>
      <div class="tv-chip-row">
        ${chip("same file → same doc_id", true)}
        ${chip("upsert by chunk id")}
      </div>
      <p class="tv-note">New chunks are upserted first; only chunk IDs that no longer exist are pruned. A failed update does not delete the working version first.</p>`;
  },

  embeddings() {
    return `${title("Local embedding")}
      ${node("Chunk text", "up to 1,000 characters")}
      ${arrow()}
      ${node("sentence-transformers/all-MiniLM-L6-v2", "CPU · normalised", true)}
      ${arrow()}
      <div class="tv-vector" aria-label="Illustration of a 384-dimension vector">
        <span>0.12</span><span>-0.04</span><span>0.31</span><span>0.08</span>
        <span>-0.22</span><span>0.17</span><span>0.05</span><span>-0.11</span>
      </div>
      <div class="tv-chip-row">${chip("384 dimensions", true)}${chip("no embedding API key")}</div>
      <p class="tv-note">The model is loaded once per process and reused for both chunks and questions.</p>`;
  },

  chroma() {
    return `${title("Persistent vector collection")}
      <div class="tv-store">
        <div class="tv-store__box"><strong>Vectors</strong><span>384-dim embeddings</span></div>
        <div class="tv-store__box"><strong>Documents</strong><span>chunk text</span></div>
        <div class="tv-store__box"><strong>Metadata</strong><span>doc_id · filename · chunk_index</span></div>
        <div class="tv-store__box"><strong>On disk</strong><span>data/chroma_db</span></div>
      </div>
      <div class="tv-chip-row">${chip("document_collection_v2", true)}${chip("persistent")}</div>
      <p class="tv-note">Deleting a document removes every vector whose metadata matches its doc_id.</p>`;
  },

  "query-embedding"() {
    return `${title("Query side")}
      ${node("Question", "“What changed in revenue this year?”")}
      ${arrow()}
      ${node("Same MiniLM embedding model", "same normalisation", true)}
      ${arrow()}
      <div class="tv-vector" aria-label="Illustration of the query vector">
        <span>0.09</span><span>0.21</span><span>-0.13</span><span>0.27</span>
        <span>0.04</span><span>-0.18</span><span>0.15</span><span>0.02</span>
      </div>
      <p class="tv-note">Both sides must use the same model and preprocessing, or similarity scores are meaningless.</p>`;
  },

  retrieval() {
    return `${title("Top-k similarity search")}
      <div class="tv-ranks">
        <div class="tv-rank">
          <span class="tv-rank__num">1</span>
          <div><strong>annual-report.pdf</strong><span>chunk 5 · page 12 · highest similarity</span></div>
        </div>
        <div class="tv-rank">
          <span class="tv-rank__num">2</span>
          <div><strong>annual-report.pdf</strong><span>chunk 6 · page 14</span></div>
        </div>
        <div class="tv-rank">
          <span class="tv-rank__num">3</span>
          <div><strong>strategy-notes.docx</strong><span>chunk 2 · page 3</span></div>
        </div>
      </div>
      <div class="tv-chip-row">
        ${chip("k = 3 default", true)}
        ${chip("k range 1–20")}
        ${chip("optional doc_id filter")}
      </div>
      <p class="tv-note">Scoping adds a metadata filter: <code>{"doc_id": {"$in": [...]}}</code>.</p>`;
  },

  prompt(step) {
    return `${title("chains/prompt_template.py")}
      <p class="tv-title" style="margin-bottom:6px">system</p>
      <pre class="tv-code">${escapeHtml(step.systemPrompt)}</pre>
      <p class="tv-title" style="margin:12px 0 6px">human</p>
      <pre class="tv-code">${escapeHtml(step.humanPrompt)}</pre>
      <p class="tv-note">Context is the retrieved chunks joined with a blank line. The wording above is the real template, not a paraphrase.</p>`;
  },

  generation() {
    return `${title("Generation path")}
      ${node("ChatPromptTemplate", "system + human messages")}
      ${arrow()}
      ${node("ChatGroq · openai/gpt-oss-20b", "temperature 0.0", true)}
      ${arrow()}
      ${node("Answer text", "parsed by StrOutputParser")}
      <div class="tv-chip-row">
        ${chip("max_tokens 1024")}
        ${chip("timeout 60 s")}
        ${chip("max_retries 2")}
      </div>
      <p class="tv-note">When retrieval is empty the chain skips the model and returns a fixed “no relevant information” answer.</p>`;
  },

  sources() {
    return `${title("Cited response")}
      <div class="tv-source">
        <strong>annual-report.pdf</strong>
        <span>chunk 5 · page 12</span>
        <p>“Revenue grew across all three regions, led by the services division…”</p>
      </div>
      <div class="tv-source">
        <strong>annual-report.pdf</strong>
        <span>chunk 6 · page 14</span>
        <p>“Operating costs were held flat while headcount increased in support…”</p>
      </div>
      <pre class="tv-code" style="margin-top:12px">{
  "question": "…",
  "answer": "…",
  "total_chunks_retrieved": 3,
  "retrieved_chunks": [ … ]
}</pre>`;
  },

  architecture() {
    return `${title("Two paths, one service")}
      <div class="tv-arch">
        <div class="tv-lane">
          <p class="tv-lane__label">Ingestion</p>
          <div class="tv-lane__flow">
            <span class="tv-lane__node">Upload</span><span class="tv-lane__arrow">→</span>
            <span class="tv-lane__node">Loader</span><span class="tv-lane__arrow">→</span>
            <span class="tv-lane__node">Splitter</span><span class="tv-lane__arrow">→</span>
            <span class="tv-lane__node">Embeddings</span><span class="tv-lane__arrow">→</span>
            <span class="tv-lane__node">ChromaDB</span>
          </div>
        </div>
        <div class="tv-lane">
          <p class="tv-lane__label">Question answering</p>
          <div class="tv-lane__flow">
            <span class="tv-lane__node">Question</span><span class="tv-lane__arrow">→</span>
            <span class="tv-lane__node">Embed</span><span class="tv-lane__arrow">→</span>
            <span class="tv-lane__node">Retrieve</span><span class="tv-lane__arrow">→</span>
            <span class="tv-lane__node">Prompt</span><span class="tv-lane__arrow">→</span>
            <span class="tv-lane__node">Groq</span><span class="tv-lane__arrow">→</span>
            <span class="tv-lane__node">Answer + sources</span>
          </div>
        </div>
        <div class="tv-lane">
          <p class="tv-lane__label">Shared</p>
          <div class="tv-lane__flow">
            <span class="tv-lane__node">config/settings.py</span>
            <span class="tv-lane__node">FastAPI routes</span>
            <span class="tv-lane__node">Structured errors</span>
            <span class="tv-lane__node">Static frontend</span>
          </div>
        </div>
      </div>`;
  },
};

/* ------------------------------------------------------------- Tour B pieces */

const appVisuals = {
  "app-shell"() {
    return `<div class="app-mock" role="img" aria-label="Illustration of the chatbot header with a connected status pill.">
      <div class="app-mock__bar"><span></span><span></span><span></span><strong>Document Chatbot</strong></div>
      <div class="app-mock__body">
        <div class="app-mock__panel">
          <div class="app-mock__panel-head">
            <span class="app-mock__label">Header</span>
            <span class="app-mock__pill">Connected</span>
          </div>
          <div class="app-mock__row" style="border-bottom:0;padding-bottom:0">
            <span class="app-mock__badge" style="background:var(--accent);color:#fff">DC</span>
            <div class="app-mock__file"><strong>Document Chatbot</strong><span>Grounded answers from your own files</span></div>
            <span class="app-mock__pill">Dark</span>
          </div>
        </div>
        <div class="app-mock__layout" style="margin-top:8px">
          <div class="app-mock__col">
            <div class="app-mock__panel">
              <span class="app-mock__label">Add documents</span>
              <div class="app-mock__drop"><strong>Drop files here</strong>or browse</div>
            </div>
            <div class="app-mock__panel">
              <div class="app-mock__panel-head"><span class="app-mock__label">Library</span><span class="app-mock__pill">3</span></div>
              <div class="app-mock__row"><span class="app-mock__check app-mock__check--on"></span><div class="app-mock__file"><strong>annual-report.pdf</strong><span>4 pages · 14 chunks</span></div></div>
            </div>
          </div>
          <div class="app-mock__col">
            <div class="app-mock__panel">
              <div class="app-mock__panel-head"><span class="app-mock__label">Ask your documents</span><span class="app-mock__pill">Searching all 3</span></div>
              <div class="app-mock__empty" style="margin-top:8px">
                <strong>Ask your first question</strong>
                <span>Answers are grounded in the documents currently selected.</span>
              </div>
            </div>
            <div class="app-mock__composer">
              <p class="app-mock__placeholder">Ask a question about your documents…</p>
              <div class="app-mock__composer-bar"><span>Answers cite sources</span><span class="app-mock__send">Send</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <p class="tv-note">Hover the status pill to see the configured LLM, embedding model, collection and document count.</p>`;
  },

  "app-upload"() {
    return `<div class="app-mock" role="img" aria-label="Illustration of the upload panel with a file being indexed.">
      <div class="app-mock__bar"><span></span><span></span><span></span><strong>Add documents</strong></div>
      <div class="app-mock__body">
        <div class="app-mock__panel">
          <div class="app-mock__panel-head"><span class="app-mock__label">Add documents</span><span class="app-mock__pill">PDF · TXT · DOCX</span></div>
          <div class="app-mock__drop app-mock__drop--active"><strong>Drop files here</strong>or browse</div>
          <div class="app-mock__buttons">
            <span class="app-mock__btn app-mock__btn--primary">Choose files</span>
            <span class="app-mock__btn">Paste text</span>
          </div>
          <div class="app-mock__progress"><span></span></div>
          <div class="app-mock__row" style="border-bottom:0">
            <span class="app-mock__badge">OK</span>
            <div class="app-mock__file"><strong>annual-report.pdf</strong><span>Indexed · 14 chunks</span></div>
          </div>
        </div>
        <p class="tv-note">Up to 10 MB per file and 10 files at a time. Each file reports its own result.</p>
      </div>
    </div>`;
  },

  "app-library"() {
    return `<div class="app-mock" role="img" aria-label="Illustration of the document library with selection checkboxes and delete controls.">
      <div class="app-mock__bar"><span></span><span></span><span></span><strong>Library</strong></div>
      <div class="app-mock__body">
        <div class="app-mock__panel">
          <div class="app-mock__panel-head"><span class="app-mock__label">Library</span><span class="app-mock__pill">3 documents</span></div>
          <div class="app-mock__toolbar"><span class="app-mock__check app-mock__check--on"></span><span>Select all</span><span class="app-mock__refresh">⟳</span></div>
          <div class="app-mock__row app-mock__row--active">
            <span class="app-mock__check app-mock__check--on"></span>
            <div class="app-mock__file"><strong>annual-report.pdf</strong><span>4 pages · 14 chunks</span></div>
            <span class="app-mock__badge">PDF</span>
            <span class="app-mock__trash">×</span>
          </div>
          <div class="app-mock__row">
            <span class="app-mock__check app-mock__check--on"></span>
            <div class="app-mock__file"><strong>strategy-notes.docx</strong><span>2 pages · 6 chunks</span></div>
            <span class="app-mock__badge">DOCX</span>
            <span class="app-mock__trash">×</span>
          </div>
          <div class="app-mock__row">
            <span class="app-mock__check"></span>
            <div class="app-mock__file"><strong>glossary.txt</strong><span>1 page · 3 chunks</span></div>
            <span class="app-mock__badge">TXT</span>
            <span class="app-mock__trash">×</span>
          </div>
        </div>
        <p class="tv-note">Deleting asks for confirmation, then removes the document's vectors and its uploaded file.</p>
      </div>
    </div>`;
  },

  "app-scope"() {
    return `<div class="app-mock" role="img" aria-label="Illustration of the scope summary and the Sources field.">
      <div class="app-mock__bar"><span></span><span></span><span></span><strong>Scope and depth</strong></div>
      <div class="app-mock__body">
        <div class="app-mock__panel">
          <div class="app-mock__panel-head"><span class="app-mock__label">Chat header</span><span class="app-mock__pill">2 selected</span></div>
          <div class="app-mock__row" style="border-bottom:0;padding-bottom:0">
            <div class="app-mock__file"><strong>Ask your documents</strong><span>Searching 2 of 3 documents</span></div>
          </div>
        </div>
        <div class="app-mock__composer" style="margin-top:8px">
          <p class="app-mock__placeholder">Ask a question about your documents…</p>
          <div class="app-mock__composer-bar">
            <span>Sources</span>
            <span class="app-mock__pill">3</span>
            <span>0 / 4000</span>
            <span class="app-mock__send">Send</span>
          </div>
        </div>
        <div class="app-mock__callout">Sources accepts 1–20. The value is remembered in this browser.</div>
      </div>
    </div>`;
  },

  "app-composer"() {
    return `<div class="app-mock" role="img" aria-label="Illustration of the question composer with an example prompt.">
      <div class="app-mock__bar"><span></span><span></span><span></span><strong>Ask a question</strong></div>
      <div class="app-mock__body">
        <div class="app-mock__panel">
          <span class="app-mock__label">Example prompts</span>
          <div class="tv-chip-row">
            ${chip("Summarize the key points")}
            ${chip("What are the main definitions?")}
            ${chip("Explain the conclusion in simple terms")}
          </div>
        </div>
        <div class="app-mock__composer app-mock__composer--focus" style="margin-top:8px">
          <p>What changed in revenue this year?</p>
          <div class="app-mock__composer-bar">
            <span>Answers cite sources · Enter to send</span>
            <span>34 / 4000</span>
            <span class="app-mock__send">Send</span>
          </div>
        </div>
        <p class="tv-note">Enter sends. Shift+Enter adds a line. Send stays disabled while the question is empty or the app is busy.</p>
      </div>
    </div>`;
  },

  "app-answer"() {
    return `<div class="app-mock" role="img" aria-label="Illustration of an answer with an expandable sources section.">
      <div class="app-mock__bar"><span></span><span></span><span></span><strong>Conversation</strong></div>
      <div class="app-mock__body">
        <div class="app-mock__message app-mock__message--user">
          <div class="app-mock__bubble">What changed in revenue this year?</div>
          <span class="app-mock__avatar">You</span>
        </div>
        <div class="app-mock__message" style="margin-top:8px">
          <span class="app-mock__avatar">AI</span>
          <div class="app-mock__bubble">
            Revenue grew across all three regions, with the services division leading growth while operating costs stayed flat.
            <div class="app-mock__sources">2 sources</div>
            <div class="app-mock__source">
              <strong>annual-report.pdf</strong>
              <span>chunk 5 · page 12</span>
              <p>Revenue grew across all three regions, led by the services division…</p>
            </div>
            <div class="app-mock__source">
              <strong>annual-report.pdf</strong>
              <span>chunk 6 · page 14</span>
              <p>Operating costs were held flat while headcount increased in support…</p>
            </div>
          </div>
        </div>
        <p class="tv-note">If retrieval finds nothing, the app says so without calling the LLM.</p>
      </div>
    </div>`;
  },

  "app-errors"() {
    return `<div class="app-mock" role="img" aria-label="Illustration of an error banner, per-file upload feedback and a success toast.">
      <div class="app-mock__bar"><span></span><span></span><span></span><strong>Error handling</strong></div>
      <div class="app-mock__body">
        <div class="app-mock__callout" style="margin-top:0">Rate limit reached. Try again in 30 seconds. <strong style="float:right">×</strong></div>
        <div class="app-mock__panel" style="margin-top:8px">
          <span class="app-mock__label">Upload feedback</span>
          <div class="app-mock__row">
            <span class="app-mock__badge">!</span>
            <div class="app-mock__file"><strong>unsupported.docx</strong><span>Unsupported file format. Upload PDF, DOCX, or TXT.</span></div>
          </div>
          <div class="app-mock__row" style="border-bottom:0">
            <span class="app-mock__badge">OK</span>
            <div class="app-mock__file"><strong>notes.txt</strong><span>Indexed · 3 chunks</span></div>
          </div>
        </div>
        <div class="app-mock__callout" style="border-color:var(--success-border);background:var(--success-soft);color:var(--success)">“glossary.txt” deleted</div>
        <p class="tv-note">The banner can be dismissed. Nothing interrupts the session with a browser alert.</p>
      </div>
    </div>`;
  },

  "app-tips"() {
    return `${title("A reliable way to use it")}
      <div class="tv-stack">
        ${node("Ask a specific question", "Whole sentences retrieve better than single keywords.")}
        ${node("Scope to the right document", "Fewer, relevant sources beat the whole library.")}
        ${node("Read the cited passage", "The answer is only as good as the context it used.")}
        ${node("Keep top-k modest", "More context is not always better context.")}
      </div>
      <div class="tv-chip-row">
        ${chip("verify important details", true)}
        ${chip("re-upload replaces")}
        ${chip("?mock=1 preview")}
      </div>`;
  },
};

/* ------------------------------------------------------------------ export */

const allVisuals = Object.assign({}, ragVisuals, appVisuals);

export function renderTourVisual(step) {
  const render = allVisuals[step.visual];
  if (!render) {
    return `<p class="tv-note">No visual for this step.</p>`;
  }
  return render(step);
}
