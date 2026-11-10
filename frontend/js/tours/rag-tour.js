/**
 * Tour A — Under the Hood: How This RAG Engine Works.
 *
 * Every technical claim in this file is taken from the actual backend source:
 * `ingestion/`, `embeddings/`, `vectorstore/chroma_store.py`,
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
        "The browser sends the file as multipart form data to POST /api/documents/upload. FastAPI receives it as an UploadFile and hands the stream to the document service.",
      what:
        "The upload endpoint validates the extension, streams the file to a per-upload directory, enforces the size limit while writing, and checks the file signature before any parsing happens.",
      why:
        "Streaming avoids holding a whole file in memory, and validating before ingestion means an oversized or mislabelled file is rejected before it can leave partial vectors behind.",
      tech:
        "FastAPI + python-multipart. The service sanitises the filename, allows .pdf, .txt and .docx, and caps uploads at 10 MB.",
      input: "One multipart file field from the browser.",
      output: "A validated file on disk plus a JSON response with doc_id, chunk count and size.",
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
        "The document ID is a SHA-256 hash of the file bytes. Every chunk is tagged with that ID, the filename and its chunk index.",
      what:
        "Because the ID is derived from content, re-uploading the same file produces the same doc_id. New chunks are upserted by deterministic chunk IDs, and only stale trailing chunks are removed.",
      why:
        "Content-based IDs prevent accidental duplicates and make replacement predictable. Upsert-then-prune also means a failed update does not delete the previously working version first.",
      tech:
        "hashlib SHA-256 for the document ID; chunk IDs combine the document ID with the chunk index.",
      input: "Split chunks plus the original filename.",
      output: "Chunks with doc_id, filename and chunk_index metadata.",
      next:
        "The chunk text is converted into vectors by the local embedding model.",
    },
    {
      id: "embeddings",
      kicker: "Stage 5 · Ingestion",
      title: "Local embeddings turn text into vectors",
      visual: "embeddings",
      summary:
        "Each chunk is embedded with sentence-transformers/all-MiniLM-L6-v2, producing a 384-dimensional vector on the local CPU.",
      what:
        "The model is loaded once per process and reused. Vectors are normalised before being stored, so similar meanings land close together in the same vector space.",
      why:
        "Running embeddings locally means ingestion has no per-chunk API cost and does not depend on a second provider key. Only chat generation calls an external service.",
      tech:
        "langchain-huggingface HuggingFaceEmbeddings with device=cpu and normalize_embeddings=true.",
      input: "Chunk text.",
      output: "One 384-dimension float vector per chunk.",
      next:
        "Vectors, text and metadata are written to the persistent Chroma collection.",
    },
    {
      id: "chroma",
      kicker: "Stage 6 · Ingestion",
      title: "ChromaDB persists the vector library",
      visual: "chroma",
      summary:
        "Vectors are stored in the document_collection_v2 collection under data/chroma_db, together with the chunk text and metadata.",
      what:
        "Chroma keeps a persistent local collection. Listing documents groups stored chunks by doc_id, and deleting a document removes every vector whose metadata matches that ID.",
      why:
        "Persistence means the library survives a server restart without re-embedding every file. Metadata filtering is also what makes document-scoped questions possible later.",
      tech:
        "ChromaDB in persistent mode via langchain-chroma, configured in config/settings.py.",
      input: "Chunk vectors, text and metadata.",
      output: "A persistent collection that can be queried by similarity or filtered by doc_id.",
      next:
        "The ingestion path is finished. The next stage starts when a user asks a question.",
    },
    {
      id: "query-embedding",
      kicker: "Stage 7 · Retrieval",
      title: "The question is embedded too",
      visual: "query-embedding",
      summary:
        "The user's question is embedded with the same MiniLM model that embedded the chunks.",
      what:
        "The question text is passed through the same normalisation and model settings. It becomes a query vector in the exact same 384-dimensional space as the stored chunks.",
      why:
        "Similarity only means something if both sides use the same model and preprocessing. Reusing the embedding function guarantees that alignment.",
      tech:
        "The same cached HuggingFaceEmbeddings instance used during ingestion.",
      input: "The question string from the chat request.",
      output: "A 384-dimension query vector.",
      next:
        "Chroma compares that vector against the stored chunk vectors.",
    },
    {
      id: "retrieval",
      kicker: "Stage 8 · Retrieval",
      title: "Similarity search selects context",
      visual: "retrieval",
      summary:
        "The retriever returns the top-k most similar chunks, optionally restricted to the documents the user selected.",
      what:
        "The default is k=3, configurable from 1 to 20. If the request includes doc_ids, Chroma applies a metadata filter so only chunks from those documents can be returned.",
      why:
        "A small, relevant context keeps the prompt focused and within token limits. Scoping retrieval lets a user ask about one document without answers drifting in from another.",
      tech:
        "Chroma as_retriever with search_type=\"similarity\" and an optional {\"doc_id\": {\"$in\": [...]}} filter.",
      input: "Query vector, k and an optional list of document IDs.",
      output: "The retrieved Document chunks, ranked by similarity.",
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
        "Every source includes a chunk ID, the chunk content, and metadata such as doc_id, filename, chunk_index, and page or page_label when the loader supplied them. The UI renders these in an expandable sources section.",
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
        "Uploads flow through API routes, document service, loaders, splitter, embeddings and Chroma. Questions flow through the chat route, chat service, retriever, prompt, Groq and back as a cited response. Settings and structured errors are shared by both.",
      why:
        "Keeping ingestion, retrieval, generation and transport separate makes each stage testable in isolation. The tour you just took maps one-to-one onto those module boundaries.",
      tech:
        "FastAPI · LangChain LCEL · ChromaDB · sentence-transformers · Groq · vanilla HTML/CSS/JS.",
      input: "Documents and questions.",
      output: "A searchable local library and grounded, source-backed answers.",
      next:
        "Open the chatbot to try it, or take the app tour for a walkthrough of the interface.",
    },
  ],
};
