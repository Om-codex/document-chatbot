/**
 * Real HTTP client for the FastAPI backend described in docs/API_CONTRACT.md.
 * All functions return plain promises and throw `ApiError` for every failure,
 * so the UI never has to deal with raw fetch/XHR semantics.
 */

import { CONFIG } from "./config.js";

export class ApiError extends Error {
  constructor(message, { code = "UNKNOWN", status = 0, details = null } = {}) {
    super(message || "Request failed");
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }

  get retryAfter() {
    return this.details && typeof this.details === "object" ? this.details.retry_after ?? null : null;
  }
}

const NETWORK_MESSAGE =
  "Cannot reach the API. Is the FastAPI server running? (Set useMock: true in js/config.js to preview without it.)";

function buildApiError(payload, status) {
  const detail = payload && typeof payload === "object" ? payload.detail : null;

  // Our contract: { detail: { code, message, details? } }
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    return new ApiError(detail.message || `Request failed (HTTP ${status})`, {
      code: detail.code || `HTTP_${status}`,
      status,
      details: detail.details ?? detail,
    });
  }

  // FastAPI request-validation shape: { detail: [{ loc, msg, type }, ...] }
  if (Array.isArray(detail)) {
    const message = detail
      .map((item) => {
        const where = Array.isArray(item.loc) ? item.loc.join(".") : "";
        return where ? `${where}: ${item.msg}` : item.msg;
      })
      .filter(Boolean)
      .join("; ");
    return new ApiError(message || "Request validation failed", {
      code: "VALIDATION_ERROR",
      status,
      details: detail,
    });
  }

  if (typeof detail === "string") {
    return new ApiError(detail, { code: `HTTP_${status}`, status });
  }

  return new ApiError(`Request failed (HTTP ${status})`, {
    code: `HTTP_${status}`,
    status,
  });
}

async function parseJson(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text.slice(0, 300) };
  }
}

async function request(path, { method = "GET", body, signal, timeoutMs = CONFIG.requestTimeoutMs } = {}) {
  const controller = new AbortController();
  let timedOut = false;

  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const forwardAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", forwardAbort, { once: true });
  }

  const headers = { Accept: "application/json" };
  let payload;
  if (body instanceof FormData) {
    payload = body; // Let the browser set the multipart boundary.
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  try {
    const response = await fetch(CONFIG.apiBase + path, {
      method,
      headers,
      body: payload,
      signal: controller.signal,
    });

    const data = await parseJson(response);
    if (!response.ok) throw buildApiError(data, response.status);
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (timedOut) {
      throw new ApiError("The server took too long to respond.", { code: "TIMEOUT", status: 0 });
    }
    if (signal && signal.aborted) {
      throw new ApiError("Request cancelled.", { code: "ABORTED", status: 0 });
    }
    if (error && error.name === "AbortError") {
      throw new ApiError("Request cancelled.", { code: "ABORTED", status: 0 });
    }
    throw new ApiError(NETWORK_MESSAGE, {
      code: "NETWORK_ERROR",
      status: 0,
      details: { cause: String(error && error.message ? error.message : error) },
    });
  } finally {
    clearTimeout(timer);
    if (signal) signal.removeEventListener("abort", forwardAbort);
  }
}

/**
 * fetch() cannot report upload progress, so multipart uploads use XHR.
 * The response/error shape is identical to `request()`.
 */
function upload(path, files, onProgress, timeoutMs = CONFIG.uploadTimeoutMs) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", CONFIG.apiBase + path);
    xhr.timeout = timeoutMs;
    xhr.setRequestHeader("Accept", "application/json");

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && typeof onProgress === "function") {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      let data = null;
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        data = { detail: xhr.responseText ? xhr.responseText.slice(0, 300) : null };
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data);
      } else {
        reject(buildApiError(data, xhr.status));
      }
    };

    xhr.onerror = () => reject(new ApiError(NETWORK_MESSAGE, { code: "NETWORK_ERROR" }));
    xhr.ontimeout = () =>
      reject(new ApiError("The upload timed out.", { code: "TIMEOUT" }));
    xhr.onabort = () => reject(new ApiError("Upload cancelled.", { code: "ABORTED" }));

    const form = new FormData();
    for (const file of files) form.append("files", file, file.name);
    xhr.send(form);
  });
}

export function createRealApi() {
  return {
    health() {
      return request("/api/health", { timeoutMs: CONFIG.healthTimeoutMs });
    },

    listDocuments() {
      return request("/api/documents");
    },

    uploadDocuments(files, onProgress) {
      return upload("/api/documents/upload", files, onProgress);
    },

    addTextDocument(title, content) {
      return request("/api/documents/text", {
        method: "POST",
        body: { title, content },
        timeoutMs: CONFIG.uploadTimeoutMs,
      });
    },

    deleteDocument(docId) {
      return request(`/api/documents/${encodeURIComponent(docId)}`, { method: "DELETE" });
    },

    chat({ question, documentIds = null, topK = null, signal }) {
      return request("/api/chat", {
        method: "POST",
        body: {
          question,
          document_ids: documentIds,
          ...(topK ? { top_k: topK } : {}),
        },
        signal,
        timeoutMs: CONFIG.requestTimeoutMs,
      });
    },
  };
}
