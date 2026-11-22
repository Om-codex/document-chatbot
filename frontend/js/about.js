/**
 * About page interactivity.
 *
 * The architecture diagram is a set of real buttons; selecting one updates a
 * single detail panel. All copy is authored here, so no API or user data is
 * injected into the page.
 */

const DETAILS = {
  client: {
    kicker: "Client",
    title: "Browser UI",
    body: "The sign-in page creates the session; the chatbot page hides itself until /api/auth/me confirms the JWT, then renders the document library, upload progress, conversation and source citations. It uses textContent for anything that came from a file or the API.",
    file: "frontend/chat.html · frontend/js/app.js",
    owns: "Interface state, upload flow, library selection, chat rendering",
    talks: "API client → FastAPI",
  },
  apiclient: {
    kicker: "Client",
    title: "API client",
    body: "A small fetch wrapper with request timeouts and one error type. It attaches Authorization: Bearer &lt;token&gt; to protected calls and normalises the backend's error envelope so the UI never deals with raw fetch semantics.",
    file: "frontend/js/api.js · frontend/js/config.js",
    owns: "HTTP calls, Bearer header, timeouts, error normalisation, mock switch",
    talks: "FastAPI routes",
  },
  auth: {
    kicker: "Identity",
    title: "JWT authentication",
    body: "Registration and login are validated by the backend. A successful login returns a short-lived JWT; the browser keeps it in one session module and the API validates it on every protected request.",
    file: "api/routes/auth.py · auth/token.py · auth/dependencies.py · frontend/js/session.js",
    owns: "Sign-in, token issue/validation, 401 session clearing",
    talks: "User database and every protected route",
  },
  database: {
    kicker: "Identity",
    title: "Neon user database",
    body: "User records — id, email, Argon2 password hash, role, active flag and created_at — live in SQLAlchemy. Deployment uses Neon PostgreSQL via psycopg v3 (postgresql+psycopg://); SQLite remains a local fallback.",
    file: "database/connection.py · database/init_db.py · database/models.py",
    owns: "User persistence and startup table creation",
    talks: "Auth services and routes",
  },
  routes: {
    kicker: "Transport",
    title: "FastAPI routes",
    body: "Four route groups: auth, chat, documents and health. Routes stay thin — they validate input, resolve the current user, call a service, and map typed exceptions to the shared error envelope.",
    file: "api/routes/auth.py · chat.py · documents.py · health.py",
    owns: "HTTP endpoints, status codes, error mapping",
    talks: "Auth dependencies, services and Pydantic schemas",
  },
  schemas: {
    kicker: "Transport",
    title: "Pydantic schemas",
    body: "Request and response models enforce question length, top-k bounds, document-ID format and the shape of every response. FastAPI uses them for validation and documentation.",
    file: "api/schemas/chat.py · documents.py · health.py",
    owns: "Input validation and response contracts",
    talks: "Routes and services",
  },
  services: {
    kicker: "Application",
    title: "Services",
    body: "The document service streams and validates uploads, lists the library and deletes documents. The chat service validates document selection, builds the retriever, runs the chain and translates failures.",
    file: "services/document_service.py · services/chat_service.py",
    owns: "Use-case orchestration, cleanup, retrieval setup",
    talks: "Ingestion, vector store, chain and generation",
  },
  loaders: {
    kicker: "Ingestion",
    title: "Document loaders",
    body: "PyPDFLoader, Docx2txtLoader and TextLoader turn a file into LangChain Document objects. Loader metadata such as page numbers is preserved for later citations.",
    file: "ingestion/loaders.py · ingestion/pipeline.py",
    owns: "Format detection and text extraction",
    talks: "Splitter",
  },
  splitter: {
    kicker: "Ingestion",
    title: "Recursive splitter",
    body: "Splits page text into chunks of at most 1,000 characters with 200 characters of overlap, preferring paragraph and line boundaries before hard cuts.",
    file: "ingestion/text_splitter.py",
    owns: "Chunk boundaries and overlap",
    talks: "Pipeline metadata step, then embeddings",
  },
  embeddings: {
    kicker: "Ingestion and query",
    title: "Gemini Embedding API",
    body: "Calls Google Gemini Embedding API (<code>gemini-embedding-2</code>) to produce 768-dimensional vectors. Each chunk text is embedded on ingestion; each question is embedded at query time.",
    file: "embeddings/gemini_embedding.py",
    owns: "768-dim vectors for text chunks and queries",
    talks: "Qdrant Cloud and the retriever",
  },
  qdrant: {
    kicker: "Storage",
    title: "Qdrant Cloud",
    body: "Stores vectors, chunk text and metadata in document_collection_v2_gemini. Payload indexes on metadata.user_id and metadata.doc_id support per-user filtering; replacement upserts new chunk IDs first, then prunes stale ones.",
    file: "vectorstore/qdrant_store.py",
    owns: "Upsert, list, count, delete and per-user similarity search",
    talks: "Retriever and document service",
  },
  retriever: {
    kicker: "Retrieval",
    title: "Retriever",
    body: "Creates a similarity retriever with a configurable k. It always filters on metadata.user_id and can additionally filter on the document IDs the user selected, so another account's chunks are never returned.",
    file: "retrieval/retriever.py",
    owns: "Top-k selection, owner scoping and document scoping",
    talks: "Prompt chain",
  },
  prompt: {
    kicker: "Generation",
    title: "Prompt and LCEL chain",
    body: "The system prompt restricts the answer to the retrieved context and the human message carries the question. The chain formats documents, calls the model, parses text, and returns a fixed message when retrieval is empty.",
    file: "chains/prompt_template.py · chains/qa_chain.py",
    owns: "Grounding rules, context formatting, no-context branch",
    talks: "Groq LLM",
  },
  llm: {
    kicker: "Generation",
    title: "Groq LLM",
    body: "A cached ChatGroq client using openai/gpt-oss-20b at temperature 0, with a 1,024-token output limit and SDK-level retries. Provider errors are translated into typed exceptions.",
    file: "generation/llm.py · generation/exceptions.py",
    owns: "Model configuration and provider error translation",
    talks: "Chain, then the chat service",
  },
  response: {
    kicker: "Response",
    title: "Cited response",
    body: "The response carries the question, answer, retrieved chunk count and each chunk with its content and metadata, including the owning user_id. The UI renders these as an expandable sources section.",
    file: "api/schemas/chat.py · frontend/js/app.js",
    owns: "Answer payload and source presentation",
    talks: "Browser",
  },
  uploads: {
    kicker: "Storage",
    title: "Temporary uploads",
    body: "Each upload is streamed into its own temporary directory and removed after ingestion. The durable record is the chunk text and metadata in Qdrant, not the original file.",
    file: "data/uploads/ · services/document_service.py",
    owns: "Bounded temporary storage and cleanup",
    talks: "Ingestion pipeline",
  },
  settings: {
    kicker: "Configuration",
    title: "Settings",
    body: "One settings object reads environment variables and .env: model names, chunk sizes, upload limits, top-k bounds, paths, log level, DATABASE_URL and the JWT secret. DATABASE_URL selects Neon PostgreSQL or the SQLite fallback.",
    file: "config/settings.py · .env.example",
    owns: "All configurable values and defaults",
    talks: "Every backend module",
  },
};

const detail = document.getElementById("arch-detail");
const nodes = Array.prototype.slice.call(
  document.querySelectorAll("[data-node]")
);

function renderDetail(key) {
  const item = DETAILS[key];
  if (!detail || !item) return;

  detail.innerHTML =
    `<p class="arch-detail__kicker">${item.kicker}</p>` +
    `<h3>${item.title}</h3>` +
    `<p>${item.body}</p>` +
    `<dl>` +
    `<dt>File</dt><dd><code>${item.file}</code></dd>` +
    `<dt>Owns</dt><dd>${item.owns}</dd>` +
    `<dt>Talks to</dt><dd>${item.talks}</dd>` +
    `</dl>`;
}

function selectNode(node) {
  nodes.forEach(function (candidate) {
    candidate.setAttribute(
      "aria-pressed",
      candidate === node ? "true" : "false"
    );
  });
  renderDetail(node.dataset.node);
}

nodes.forEach(function (node) {
  node.addEventListener("click", function () {
    selectNode(node);
  });
});

/* ----------------------------------------------------- open the first decision */

const firstDecision = document.querySelector(".decision");
if (firstDecision) firstDecision.open = true;

/* --------------------------------------------- optional deep-link to a section */

if (window.location.hash) {
  const target = document.getElementById(window.location.hash.slice(1));
  if (target) {
    window.setTimeout(function () {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 60);
  }
}
