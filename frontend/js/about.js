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
    body: "The chatbot page renders the document library, upload progress, conversation and source citations. It uses textContent for anything that came from a file or the API.",
    file: "frontend/chat.html · frontend/js/app.js",
    owns: "Interface state, upload flow, library selection, chat rendering",
    talks: "API client → FastAPI",
  },
  apiclient: {
    kicker: "Client",
    title: "API client",
    body: "A small fetch wrapper with request timeouts and one error type. It normalises the backend's error envelope so the UI never deals with raw fetch semantics.",
    file: "frontend/js/api.js · frontend/js/config.js",
    owns: "HTTP calls, timeouts, error normalisation, mock switch",
    talks: "FastAPI routes",
  },
  routes: {
    kicker: "Transport",
    title: "FastAPI routes",
    body: "Three route groups: chat, documents and health. Routes stay thin — they validate input, call a service, and map typed exceptions to the shared error envelope.",
    file: "api/routes/chat.py · documents.py · health.py",
    owns: "HTTP endpoints, status codes, error mapping",
    talks: "Services and Pydantic schemas",
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
    title: "Local embeddings",
    body: "Loads sentence-transformers/all-MiniLM-L6-v2 once per process on CPU and normalises vectors. The same cached model embeds both chunks and questions.",
    file: "embeddings/embedding_model.py",
    owns: "384-dimension vectors for text",
    talks: "ChromaDB and the retriever",
  },
  chroma: {
    kicker: "Storage",
    title: "ChromaDB collection",
    body: "Stores vectors, chunk text and metadata in a persistent local collection. Replacement upserts new chunk IDs first, then prunes stale ones.",
    file: "vectorstore/chroma_store.py",
    owns: "Upsert, list, count, delete and similarity search",
    talks: "Retriever and document service",
  },
  retriever: {
    kicker: "Retrieval",
    title: "Retriever",
    body: "Creates a similarity retriever with a configurable k and an optional metadata filter for the documents the user selected.",
    file: "retrieval/retriever.py",
    owns: "Top-k selection and document scoping",
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
    body: "The response carries the question, answer, retrieved chunk count and each chunk with its content and metadata. The UI renders these as an expandable sources section.",
    file: "api/schemas/chat.py · frontend/js/app.js",
    owns: "Answer payload and source presentation",
    talks: "Browser",
  },
  uploads: {
    kicker: "Storage",
    title: "Uploaded files",
    body: "Each upload is streamed into its own directory under data/uploads. Failed uploads are cleaned up; deleting a document removes its stored file as well.",
    file: "data/uploads/ · services/document_service.py",
    owns: "Original file retention",
    talks: "Ingestion pipeline",
  },
  chromadb: {
    kicker: "Storage",
    title: "Vector database on disk",
    body: "Chroma persists its SQLite-backed collection under data/chroma_db. This is why the library survives a server restart without re-embedding every file.",
    file: "data/chroma_db/ · config/settings.py",
    owns: "Durable vectors and metadata",
    talks: "Chroma store wrapper",
  },
  settings: {
    kicker: "Configuration",
    title: "Settings",
    body: "One settings object reads environment variables and the project .env file: model names, chunk sizes, upload limits, top-k bounds, paths and log level.",
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
