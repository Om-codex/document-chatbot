/**
 * Tour A — Under the Hood: How This RAG Engine Works.
 *
 * Every technical claim in this file is taken from the actual backend source:
 * `auth/`, `database/`, `ingestion/`, `embeddings/`, `vectorstore/qdrant_store.py`,
 * `retrieval/retriever.py`, `chains/`, `generation/llm.py`,
 * `services/chat_service.py` and `config/settings.py`.
 *
 * The system prompt in step 9 is reproduced from `chains/prompt_template.py`.
 * Do not reword it; the tour is meant to show the real instructions.
 */

export const SYSTEM_PROMPT = `You are an intelligent document question-answering assistant.
Answer the user's question using only the provided context.

Follow these rules:
1. Do not use external knowledge or invent information.
2. If the answer is not available in the context, clearly state that you don't know based on the provided documents.
3. Provide clear, accurate and well-structured explanation and answers to the user's question.
4. Keep the response relevant to the user's question.
5. Do not mention information that is not supported by the context.

Context:
{context}`;

export const HUMAN_PROMPT = "{question}";

export const ragTour = {
  id: "rag",
  storageKey: "document-chatbot.tour.rag",
  kicker: "Engine tour",
  title: "Under the Hood: How This RAG Engine Works",
  subtitle:
    "Twelve steps through ingestion, retrieval and generation — with the real models, settings and prompt used by this project.",
  intro:
    "This tour follows a document from upload to cited answer. It explains what each stage does, why it exists, which library implements it, and what it hands to the next stage.",
  steps: [
    {
      id: "upload",
      kicker: "Stage 1 · Ingestion",
      title: "Upload reaches the API",
      visual: "upload",
      summary:
        "The signed-in browser sends the file as multipart form data to POST /api/documents/upload with Authorization: Bearer <token>. The browser leaves Content-Type unset so the multipart boundary is generated correctly.",
      what:
        "FastAPI validates the JWT, resolves the user, receives the file as an UploadFile, validates the extension, streams it to a per-upload temporary directory, enforces the size limit while writing, and checks the file signature before parsing.",
      why:
        "The Bearer token ties the upload to one account. Streaming avoids holding a whole file in memory, and validating before ingestion means an oversized or mislabelled file is rejected before it can leave partial vectors behind.",
      tech:
        "FastAPI + python-multipart + JWT dependency. The service sanitises the filename, allows .pdf, .txt and .docx, and caps uploads at 10 MB.",
      input: "One multipart file field plus the signed-in user's Bearer token.",
      output: "A validated temporary file plus a JSON response with doc_id, chunk count and size.",
      next:
        "The saved file path is passed to the ingestion pipeline, which chooses a loader based on the extension.",
    },
    {
      id: "loaders",
      kicker: "Stage 2 · Ingestion",
      title: "Loaders extract readable text",
      visual: "loaders",
      summary:
        "Each format gets a loader that understands its structure. PDF pages, DOCX paragraphs and plain text all become LangChain Document objects.",
      what:
        "PyPDFLoader reads PDFs, Docx2txtLoader reads Word files and TextLoader reads .txt. The pipeline rejects formats it cannot load and raises a readable error if extraction produces nothing.",
      why:
        "Loaders preserve page metadata where the format provides it. That metadata is what later lets an answer point back to a specific page instead of only a filename.",
      tech:
        "langchain-community loaders, with pypdf and docx2txt as the underlying parsers.",
      input: "The validated file path.",
      output: "A list of Document objects containing page text and loader metadata.",
      next:
        "Those page-level documents are split into smaller, overlapping chunks.",
    },
    {
      id: "chunking",
      kicker: "Stage 3 · Ingestion",
      title: "Documents are split into chunks",
      visual: "chunking",
      summary:
        "A RecursiveCharacterTextSplitter breaks the text into chunks of at most 1,000 characters with 200 characters of overlap.",
      what:
        "The splitter tries paragraph breaks first, then line breaks, then spaces, and only then hard character boundaries. Overlap repeats the tail of one chunk at the start of the next.",
      why:
        "Embedding a whole document would blur many topics into one vector, and a retrieved chunk would be too large to use as focused context. Overlap keeps sentences that straddle a boundary from being lost.",
      tech:
        "LangChain RecursiveCharacterTextSplitter with separators [\"\\n\\n\", \"\\n\", \" \", \"\"].",
      input: "Page-level Document objects.",
      output: "Smaller Document chunks with the original metadata preserved.",
      next:
        "Each chunk gets a stable document ID and a position before it is embedded.",
    },
    {
      id: "metadata",
      kicker: "Stage 4 · Ingestion",
      title: "Stable IDs and chunk metadata",
      visual: "metadata",
      summary:
        "The document ID is a SHA-256 hash of the file bytes. Every chunk is tagged with that ID, the filename, its chunk index and the authenticated user_id.",
      what:
        "Because the ID is derived from content, re-uploading the same file produces the same doc_id. New chunks are upserted by deterministic chunk IDs that include the owner, and only stale trailing chunks are removed.",
      why:
        "Content-based IDs prevent accidental duplicates, and user_id makes ownership part of the vector itself. Upsert-then-prune also means a failed update does not delete the previously working version first.",
      tech:
        "hashlib SHA-256 for the document ID; chunk IDs combine the owner, document ID and chunk index.",
      input: "Split chunks, the original filename and the authenticated user_id.",
      output: "Chunks with user_id, doc_id, filename and chunk_index metadata.",
      next:
        "The chunk text is converted into vectors by the Gemini Embedding API.",
    },
    {
      id: "embeddings",
      kicker: "Stage 5 · Ingestion",
      title: "Google Gemini Embedding API",
      visual: "embeddings",
      summary:
        "Each chunk is embedded via the Google Gemini Embedding API (gemini-embedding-2), producing 768-dimensional vectors.",
      what:
        "The chunk text is sent to the Gemini Embedding API. Vectors are normalized and sent to Qdrant Cloud.",
      why:
        "A hosted embedding model avoids downloading a large local model, but it adds a network dependency, an API key and provider rate limits. Reusing the same model on both sides keeps vectors and questions in one space.",
        tech: "Google Gemini Embedding API · 768 dimensions · normalized output",
      input: "Chunk text.",
      output: "One 768-dimension vector per chunk.",
      next:
        "Vectors, text and metadata are written to Qdrant Cloud.",
    },
    {
      id: "qdrant",
      kicker: "Stage 6 · Ingestion",
      title: "Qdrant Cloud",
      visual: "qdrant",
      summary:
        "Vectors are stored in the document_collection_v2_gemini collection together with chunk text and metadata, including metadata.user_id.",
      what:
        "Qdrant Cloud keeps vectors in the cloud. Payload indexes on metadata.user_id and metadata.doc_id support owner-scoped listing, counting, deletion and similarity search.",
      why:
        "Persistence means the library survives a backend restart without re-embedding every file. The owner filter is applied by Qdrant itself, so one account's chunks are not returned to another even if a doc_id is known.",
      tech: "Qdrant Cloud · Cosine distance · payload indexes on user_id and doc_id",
      input: "Chunk vectors, text and metadata from the signed-in owner.",
      output: "A cloud collection that can be queried by similarity and filtered by owner or document.",
      next:
        "The ingestion path is finished. The next stage starts when a user asks a question.",
    },
    {
      id: "query-embedding",
      kicker: "Stage 7 · Retrieval",
      title: "The question is embedded too",
      visual: "query-embedding",
      summary:
        "The user's question is embedded via Google Gemini Embedding API, producing a 768-dimensional query vector.",
      what:
        "The question text is sent to the Gemini Embedding API using the same model as ingestion. It becomes a query vector in the same 768-dimensional space as the stored chunks.",
      why:
        "Similarity only means something if both sides use the same model and preprocessing. Reusing the same embedding model guarantees alignment.",
      tech: "Google Gemini Embedding API · Qdrant Cloud",
      input: "The question string from the chat request.",
      output: "A 768-dimension query vector.",
      next:
        "Qdrant compares that vector against the stored chunk vectors.",
    },
    {
      id: "retrieval",
      kicker: "Stage 8 · Retrieval",
      title: "Similarity search selects context",
      visual: "retrieval",
      summary:
        "The retriever returns the top-k most similar chunks from the signed-in user's library, optionally restricted to the documents selected in the UI.",
      what:
        "The default is k=3, configurable from 1 to 20. Qdrant always applies a metadata.user_id filter from the JWT and adds a metadata.doc_id filter when doc_ids are supplied.",
      why:
        "A small, relevant context keeps the prompt focused and within token limits. Owner scoping is a hard filter, so a user can only ask about their own documents.",
      tech:
        "Qdrant similarity search with a metadata.user_id filter and an optional metadata.doc_id subset filter.",
      input: "Query vector, authenticated user_id, k and an optional list of document IDs.",
      output: "The user's retrieved Document chunks, ranked by similarity.",
      next:
        "The chunks are joined into a context block and placed in the prompt.",
    },
    {
      id: "prompt",
      kicker: "Stage 9 · Generation",
      title: "The real prompt sets the rules",
      visual: "prompt",
      systemPrompt: SYSTEM_PROMPT,
      humanPrompt: HUMAN_PROMPT,
      summary:
        "Retrieved chunks are joined with blank lines into {context}. The question becomes the human message. This is the actual prompt template used by the project.",
      what:
        "The system message tells the model to answer only from the provided context, to admit when the answer is absent, and not to introduce unsupported information. The human message carries the user's question.",
      why:
        "Grounding is a prompt-level constraint, not a guarantee. Clear rules reduce invented answers, while the UI still asks users to verify important details against the source.",
      tech:
        "LangChain ChatPromptTemplate in chains/prompt_template.py; format_docs joins chunk text with \"\\n\\n\".",
      input: "The question plus the retrieved chunks.",
      output: "A system message containing the context and a human message containing the question.",
      next:
        "The prompt is sent to the Groq chat model for generation.",
    },
    {
      id: "generation",
      kicker: "Stage 10 · Generation",
      title: "Groq generates the answer",
      visual: "generation",
      summary:
        "ChatGroq calls openai/gpt-oss-20b at temperature 0 with a 1,024-token output limit and up to two SDK retries.",
      what:
        "The chain sends the prompt, parses the returned text, and maps provider failures into readable errors. If retrieval returned no chunks, the LLM is skipped entirely.",
      why:
        "Temperature 0 makes answers as consistent as the provider allows. Skipping the model on empty retrieval avoids paying for a call that could only hallucinate.",
      tech:
        "langchain-groq ChatGroq: model openai/gpt-oss-20b, temperature 0.0, timeout 60 s, max_retries 2, max_tokens 1,024.",
      input: "The formatted chat prompt.",
      output: "Answer text, or the deterministic no-context message when nothing was retrieved.",
      next:
        "The answer is packaged with the retrieved chunks so the UI can show its sources.",
    },
    {
      id: "sources",
      kicker: "Stage 11 · Response",
      title: "Sources travel with the answer",
      visual: "sources",
      summary:
        "The chat response returns the question, the answer, the number of chunks retrieved, and each retrieved chunk with its metadata.",
      what:
        "Every source includes a chunk ID, the chunk content, and metadata such as user_id, doc_id, filename, chunk_index, and page or page_label when the loader supplied them. The UI renders these in an expandable sources section.",
      why:
        "Citations turn the answer from an opaque claim into something a reader can check. If a source looks unrelated, that is a visible signal that retrieval or the question needs adjustment.",
      tech:
        "Pydantic response models in api/schemas/chat.py; source normalisation in frontend/js/app.js.",
      input: "The generated answer and the retrieved chunks.",
      output: "A JSON response: question, answer, total_chunks_retrieved and retrieved_chunks.",
      next:
        "The next step zooms out to the full architecture that connects both paths.",
    },
    {
      id: "architecture",
      kicker: "Stage 12 · System",
      title: "The full architecture",
      visual: "architecture",
      summary:
        "Ingestion and question answering are two paths through one modular backend, served alongside a static frontend by the same FastAPI process.",
      what:
        "After a JWT is validated, uploads flow through API routes, the user-scoped document service, loaders, splitter, Gemini embeddings and Qdrant. Questions flow through the authenticated chat route, chat service, owner-filtered retriever, prompt, Groq and back as a cited response. User records live in Neon PostgreSQL, with SQLite as a local fallback. Settings and structured errors are shared by both.",
      why:
        "Keeping identity, ingestion, retrieval, generation and transport separate makes each stage testable in isolation. The owner filter runs at the storage boundary rather than relying on the UI.",
      tech:
        "JWT auth · FastAPI · Neon PostgreSQL (psycopg v3) · LangChain LCEL · Qdrant Cloud · Google Gemini · Groq · vanilla HTML/CSS/JS.",
      input: "Authenticated users, documents and questions.",
      output: "A private, per-user library and grounded, source-backed answers.",
      next:
        "Open the chatbot to try it, or take the app tour for a walkthrough of the interface.",
    },
  ],
};
