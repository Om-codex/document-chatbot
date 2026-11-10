/**
 * Mock adapter. Implements the same method surface as `createRealApi()` so
 * app.js does not branch on "mock vs real". Enable it with `?mock=1`.
 *
 * Deliberate demo triggers:
 *  - a file whose name contains "fail"  -> upload error (INVALID_FILE_TYPE)
 *  - a question containing "rate limit" -> 429 LLM_RATE_LIMIT with retry_after
 *  - deleting all documents             -> NO_DOCUMENTS on chat
 */

import { CONFIG } from "./config.js";
import { ApiError } from "./api.js";

const now = () => new Date().toISOString();

let sequence = 0;

function nextId() {
  sequence += 1;
  return sequence.toString(16).padStart(64, "0");
}

function seedDocuments() {
  return [
    {
      doc_id: "a".repeat(64),
      filename: "lecture-notes.pdf",
      total_pages: 4,
      total_chunks: 12,
      size_bytes: 1_048_576,
      created_at: "2026-11-03T09:15:00Z",
    },
    {
      doc_id: "b".repeat(64),
      filename: "getting-started.txt",
      total_pages: null,
      total_chunks: 5,
      size_bytes: 12_288,
      created_at: "2026-11-03T09:20:00Z",
    },
  ];
}

let documents = seedDocuments();

const EXTENSION_TO_TYPE = {
  ".pdf": "pdf",
  ".txt": "txt",
  ".docx": "docx",
};

function extensionOf(filename) {
  const dot = filename.lastIndexOf(".");
  return dot >= 0 ? filename.slice(dot).toLowerCase() : "";
}

function wait(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal && signal.aborted) {
      reject(new ApiError("Request cancelled.", { code: "ABORTED" }));
      return;
    }

    const timer = setTimeout(() => {
      if (signal) signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);

    function onAbort() {
      clearTimeout(timer);
      reject(new ApiError("Request cancelled.", { code: "ABORTED" }));
    }

    if (signal) signal.addEventListener("abort", onAbort, { once: true });
  });
}

function publicDocument(doc) {
  return {
    doc_id: doc.doc_id,
    filename: doc.filename,
    total_pages: doc.total_pages,
    total_chunks: doc.total_chunks,
  };
}

function makeDoc({ filename, sizeBytes, chunkCount }) {
  return {
    doc_id: nextId(),
    filename,
    total_pages: /\.pdf$/i.test(filename) ? Math.max(1, Math.ceil(chunkCount / 4)) : null,
    total_chunks: chunkCount,
    size_bytes: sizeBytes,
    created_at: now(),
  };
}

function selectedDocuments(documentIds) {
  if (documentIds === null || documentIds === undefined) return documents;

  if (!Array.isArray(documentIds) || documentIds.length === 0) {
    throw new ApiError("Select at least one document to search.", {
      code: "NO_DOCUMENTS_SELECTED",
      status: 400,
    });
  }

  const known = new Set(documents.map((doc) => doc.doc_id));
  const unknown = documentIds.filter((id) => !known.has(id));
  if (unknown.length > 0) {
    throw new ApiError("Some selected documents no longer exist. Refresh the library.", {
      code: "INVALID_DOCUMENT_SELECTION",
      status: 400,
      details: { unknown_ids: unknown },
    });
  }

  return documents.filter((doc) => documentIds.includes(doc.doc_id));
}

function pickChunks(docs, topK) {
  const chunks = [];

  for (const doc of docs) {
    const count = Math.min(2, Math.max(1, topK - chunks.length));
    for (let index = 0; index < count; index += 1) {
      chunks.push({
        chunk_id: `${doc.doc_id}_${index}`,
        content:
          `Mock passage ${index + 1} from “${doc.filename}”. ` +
          "Real chunks retrieved from ChromaDB appear here when the backend is running.",
        metadata: {
          doc_id: doc.doc_id,
          filename: doc.filename,
          chunk_index: index,
          page: doc.total_pages ? index : null,
          page_number: doc.total_pages ? index + 1 : null,
          page_label: null,
          total_pages: doc.total_pages,
        },
      });
      if (chunks.length >= topK) break;
    }
    if (chunks.length >= topK) break;
  }

  return chunks;
}

export function createMockApi() {
  return {
    async health() {
      await wait(180);
      return {
        status: "ok",
        app_name: "Document Chatbot API (mock)",
        app_version: "1.0.0",
        llm_model: "mock / openai/gpt-oss-20b",
        embedding_model: "mock / all-MiniLM-L6-v2",
        collection: "mock_collection",
        document_count: documents.length,
      };
    },

    async listDocuments() {
      await wait(180);
      return {
        total_documents: documents.length,
        documents: documents.map(publicDocument),
      };
    },

    async uploadDocument(file, onProgress) {
      if (!file) {
        throw new ApiError("Choose a file to upload.", { code: "NO_FILES", status: 400 });
      }

      onProgress?.(18);
      await wait(200);
      onProgress?.(62);
      await wait(220);

      const ext = extensionOf(file.name);
      const sourceType = EXTENSION_TO_TYPE[ext];
      const maxBytes = CONFIG.maxFileMb * 1024 * 1024;

      if (!sourceType) {
        throw new ApiError(`Unsupported file type: ${ext || "unknown"}`, {
          code: "INVALID_FILE_TYPE",
          status: 415,
        });
      }
      if (file.name.toLowerCase().includes("fail")) {
        throw new ApiError("Mock failure triggered by the filename (contains “fail”).", {
          code: "INVALID_FILE_TYPE",
          status: 415,
        });
      }
      if (file.size === 0) {
        throw new ApiError("This file is empty.", { code: "EMPTY_DOCUMENT", status: 422 });
      }
      if (file.size > maxBytes) {
        throw new ApiError(`File is larger than ${CONFIG.maxFileMb} MB.`, {
          code: "FILE_TOO_LARGE",
          status: 413,
        });
      }
      if (documents.some((doc) => doc.filename === file.name)) {
        throw new ApiError("A document with this filename is already indexed.", {
          code: "DUPLICATE_DOCUMENT",
          status: 409,
        });
      }

      const chunkCount = Math.max(1, Math.ceil(file.size / 1200));
      const doc = makeDoc({
        filename: file.name,
        sizeBytes: file.size,
        chunkCount,
      });
      documents.unshift(doc);

      onProgress?.(100);
      await wait(100);

      return {
        message: "Document uploaded and indexed successfully.",
        filename: doc.filename,
        doc_id: doc.doc_id,
        total_chunks: doc.total_chunks,
        file_size_bytes: doc.size_bytes,
      };
    },

    async deleteDocument(docId) {
      await wait(260);
      const index = documents.findIndex((doc) => doc.doc_id === docId);
      if (index < 0) {
        throw new ApiError("Document not found. It may have already been deleted.", {
          code: "DOCUMENT_NOT_FOUND",
          status: 404,
        });
      }

      const [doc] = documents.splice(index, 1);
      return {
        message: "Document deleted successfully.",
        doc_id: doc.doc_id,
        filename: doc.filename,
        deleted_files: 1,
        vectors_deleted: true,
        warnings: [],
      };
    },

    async chat({ question, documentIds = null, topK = CONFIG.defaultTopK, signal } = {}) {
      const cleanQuestion = String(question || "").trim();
      if (!cleanQuestion) {
        throw new ApiError("Enter a question first.", { code: "INVALID_REQUEST", status: 400 });
      }
      if (cleanQuestion.length > CONFIG.maxQuestionChars) {
        throw new ApiError("Question is too long.", { code: "INVALID_REQUEST", status: 400 });
      }

      await wait(CONFIG.mockLatencyMs, signal);

      if (documents.length === 0) {
        throw new ApiError("No documents are indexed yet. Upload one first.", {
          code: "NO_DOCUMENTS",
          status: 400,
        });
      }

      if (/rate\s*limit/i.test(cleanQuestion)) {
        throw new ApiError("Groq rate limit reached. Wait a few seconds and retry.", {
          code: "LLM_RATE_LIMIT",
          status: 429,
          details: { retry_after: 5 },
        });
      }

      const selected = selectedDocuments(documentIds);
      const primary = selected[0];
      const topic = cleanQuestion.replace(/\s+/g, " ").slice(0, 70);

      const answer =
        `Here is what the selected documents say about “${topic}”:\n\n` +
        `The most relevant passage comes from “${primary.filename}”. ` +
        "It describes the core concept and connects it to the surrounding material [1]. " +
        "A second passage provides supporting detail and context [2].\n\n" +
        "This answer is produced by the mock adapter. Run the FastAPI backend " +
        "to generate answers from real retrieved chunks.";

      const retrieved = pickChunks(selected, Math.max(1, Number(topK) || 1));

      return {
        question: cleanQuestion,
        answer,
        total_chunks_retrieved: retrieved.length,
        retrieved_chunks: retrieved,
      };
    },
  };
}
