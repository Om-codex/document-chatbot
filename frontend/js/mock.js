/**
 * Mock adapter (M1). Implements the same method surface as `createRealApi()`
 * so app.js does not branch on "mock vs real". See docs/API_CONTRACT.md §9.
 *
 * Deliberate demo triggers:
 *  - a file whose name contains "fail"  -> per-file error in the upload response
 *  - a question containing "rate limit" -> 429 LLM_RATE_LIMIT with retry_after
 *  - deleting all documents            -> NO_DOCUMENTS on chat
 */

import { CONFIG } from "./config.js";
import { ApiError } from "./api.js";

const now = () => new Date().toISOString();

function seedDocuments() {
  return [
    {
      doc_id: "mock-pdf-01",
      filename: "lecture-notes.pdf",
      source_type: "pdf",
      chunk_count: 12,
      page_count: 4,
      size_bytes: 1_048_576,
      created_at: "2026-11-03T09:15:00Z",
    },
    {
      doc_id: "mock-md-01",
      filename: "getting-started.md",
      source_type: "markdown",
      chunk_count: 5,
      page_count: null,
      size_bytes: 12_288,
      created_at: "2026-11-03T09:20:00Z",
    },
  ];
}

let documents = seedDocuments();
let sequence = 0;

const EXTENSION_TO_TYPE = {
  ".pdf": "pdf",
  ".txt": "txt",
  ".md": "markdown",
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

function clone(doc) {
  return { ...doc };
}

function nextId() {
  sequence += 1;
  return `mock-${Date.now().toString(36)}-${sequence}`;
}

function makeDoc({ filename, sourceType, sizeBytes, chunkCount }) {
  return {
    doc_id: nextId(),
    filename,
    source_type: sourceType,
    chunk_count: chunkCount,
    page_count: sourceType === "pdf" ? Math.max(1, Math.ceil(chunkCount / 4)) : null,
    size_bytes: sizeBytes,
    created_at: now(),
  };
}

function currentDocs(documentIds) {
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
      code: "INVALID_REQUEST",
      status: 400,
      details: { unknown_ids: unknown },
    });
  }

  return documents.filter((doc) => documentIds.includes(doc.doc_id));
}

function pickSources(docs) {
  return docs.slice(0, 2).map((doc, index) => ({
    doc_id: doc.doc_id,
    filename: doc.filename,
    page: doc.source_type === "pdf" ? index + 2 : null,
    chunk_index: index === 0 ? 4 : 7,
    score: index === 0 ? 0.91 : 0.78,
    snippet:
      `Mock passage ${index + 1} from “${doc.filename}”. ` +
      "Real chunks retrieved from ChromaDB will appear here after the backend " +
      "milestones are wired up in M6.",
  }));
}

export function createMockApi() {
  return {
    async health() {
      await wait(180);
      return {
        status: "ok",
        llm_model: "mock / openai-gpt-oss-120b",
        embedding_model: "mock / all-MiniLM-L6-v2",
        collection: "mock_collection",
        document_count: documents.length,
      };
    },

    async listDocuments() {
      await wait(180);
      return { documents: documents.map(clone) };
    },

    async uploadDocuments(files, onProgress) {
      if (!files || files.length === 0) {
        throw new ApiError("Choose at least one file to upload.", {
          code: "NO_FILES",
          status: 400,
        });
      }

      onProgress?.(12);
      await wait(220);
      onProgress?.(46);
      await wait(240);

      const added = [];
      const errors = [];
      const maxBytes = CONFIG.maxFileMb * 1024 * 1024;

      for (const file of files) {
        const ext = extensionOf(file.name);
        const sourceType = EXTENSION_TO_TYPE[ext];
        const alreadyExists = documents.some((doc) => doc.filename === file.name);

        let code = "";
        let message = "";

        if (!sourceType) {
          code = "INVALID_FILE_TYPE";
          message = `Unsupported file type: ${ext || "unknown"}`;
        } else if (file.name.toLowerCase().includes("fail")) {
          code = "INVALID_FILE_TYPE";
          message = "Mock failure triggered by the filename (contains “fail”).";
        } else if (file.size === 0) {
          code = "EMPTY_DOCUMENT";
          message = "This file is empty.";
        } else if (file.size > maxBytes) {
          code = "FILE_TOO_LARGE";
          message = `File is larger than ${CONFIG.maxFileMb} MB.`;
        } else if (alreadyExists) {
          code = "DUPLICATE_DOCUMENT";
          message = "A document with this filename is already indexed.";
        }

        if (code) {
          errors.push({ filename: file.name, code, message });
          continue;
        }

        const chunkCount = Math.max(1, Math.ceil(file.size / 1200));
        const doc = makeDoc({
          filename: file.name,
          sourceType,
          sizeBytes: file.size,
          chunkCount,
        });
        documents.unshift(doc);
        added.push(clone(doc));
      }

      onProgress?.(100);
      await wait(120);
      return { documents: added, errors };
    },

    async addTextDocument(title, content) {
      await wait(380);

      const cleanTitle = String(title || "").trim();
      const cleanContent = String(content || "").trim();

      if (!cleanTitle) {
        throw new ApiError("A title is required.", { code: "INVALID_REQUEST", status: 422 });
      }
      if (cleanTitle.length > 120) {
        throw new ApiError("Title must be 120 characters or fewer.", {
          code: "INVALID_REQUEST",
          status: 422,
        });
      }
      if (!cleanContent) {
        throw new ApiError("The text content is empty.", { code: "EMPTY_DOCUMENT", status: 422 });
      }
      if (cleanContent.length > CONFIG.maxTextChars) {
        throw new ApiError("Text is too long.", { code: "INVALID_REQUEST", status: 422 });
      }

      const doc = makeDoc({
        filename: cleanTitle,
        sourceType: "text",
        sizeBytes: cleanContent.length,
        chunkCount: Math.max(1, Math.ceil(cleanContent.length / 1000)),
      });
      documents.unshift(doc);
      return { document: clone(doc) };
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
      documents.splice(index, 1);
      return { deleted: true, doc_id: docId };
    },

    async chat({ question, documentIds = null, signal } = {}) {
      const cleanQuestion = String(question || "").trim();
      if (!cleanQuestion) {
        throw new ApiError("Enter a question first.", { code: "INVALID_REQUEST", status: 400 });
      }
      if (cleanQuestion.length > CONFIG.maxQuestionChars) {
        throw new ApiError("Question is too long.", { code: "INVALID_REQUEST", status: 400 });
      }

      await wait(CONFIG.mockLatencyMs, signal);

      if (documents.length === 0) {
        throw new ApiError("No documents are indexed yet. Upload or paste one first.", {
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

      const selected = currentDocs(documentIds);
      const primary = selected[0];
      const topic = cleanQuestion.replace(/\s+/g, " ").slice(0, 70);

      const answer =
        `Here is what the selected documents say about “${topic}”:\n\n` +
        `The most relevant passage comes from “${primary.filename}”. ` +
        "It describes the core concept and connects it to the surrounding material [1]. " +
        "A second passage provides supporting detail and context [2].\n\n" +
        "This answer is produced by the M1 mock adapter. Once the retrieval and LCEL " +
        "chain milestones are complete, it will be generated from real retrieved chunks " +
        `with ${selected.length === 1 ? "a single document" : "the documents"} you selected.`;

      return {
        answer,
        sources: pickSources(selected),
        model: "mock-model",
      };
    },
  };
}
