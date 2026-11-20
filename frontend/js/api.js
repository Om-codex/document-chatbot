/**
 * Real HTTP client for the FastAPI backend.
 * All functions return plain promises and throw `ApiError` for every failure,
 * so the UI never has to deal with raw fetch/XHR semantics.
 */

import { CONFIG } from "./config.js";
import { getAccessToken, endSession } from "./session.js";

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
  "Cannot reach the API. Is the FastAPI server running? (Append ?mock=1 to preview without it.)";

const SESSION_MESSAGE = "Your session has expired. Please sign in again.";
const AUTH_REQUIRED_MESSAGE = "Authentication required. Please sign in.";
const FORBIDDEN_MESSAGE =
  "Access denied. You do not have permission to perform this action.";

/** 401 always invalidates the local session; 403 never does. */
function unauthorizedError() {
  return new ApiError(SESSION_MESSAGE, { code: "SESSION_EXPIRED", status: 401 });
}

function forbiddenError(error) {
  const message =
    error && error.message && !error.message.includes("HTTP 403")
      ? error.message
      : FORBIDDEN_MESSAGE;
  return new ApiError(message, {
    code: "FORBIDDEN",
    status: 403,
    details: error ? error.details : null,
  });
}

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

/**
 * Every backend call goes through here. `auth` defaults to true so protected
 * endpoints cannot accidentally be called without the Bearer token. Public
 * endpoints (health, register, login) opt out explicitly.
 */
async function request(
  path,
  {
    method = "GET",
    body,
    signal,
    timeoutMs = CONFIG.requestTimeoutMs,
    auth = true,
    redirectOnUnauthorized = true,
  } = {}
) {
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
  if (auth) {
    const token = getAccessToken();
    if (!token) {
      endSession({ redirect: redirectOnUnauthorized });
      throw new ApiError(AUTH_REQUIRED_MESSAGE, {
        code: "AUTH_REQUIRED",
        status: 401,
      });
    }
    // The token is only ever placed in this header, never in a URL or log.
    headers["Authorization"] = `Bearer ${token}`;
  }

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
    if (!response.ok) {
      const error = buildApiError(data, response.status);
      if (response.status === 401 && auth) {
        endSession({ redirect: redirectOnUnauthorized });
        throw unauthorizedError();
      }
      if (response.status === 403) throw forbiddenError(error);
      throw error;
    }
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
function upload(path, file, onProgress, timeoutMs = CONFIG.uploadTimeoutMs) {
  return new Promise((resolve, reject) => {
    const token = getAccessToken();
    if (!token) {
      endSession();
      reject(new ApiError(AUTH_REQUIRED_MESSAGE, {
        code: "AUTH_REQUIRED",
        status: 401,
      }));
      return;
    }

    const xhr = new XMLHttpRequest();
    xhr.open("POST", CONFIG.apiBase + path);
    xhr.timeout = timeoutMs;
    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    // Deliberately no Content-Type: the browser sets the multipart boundary.

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
        const error = buildApiError(data, xhr.status);
        if (xhr.status === 401) {
          endSession();
          reject(unauthorizedError());
        } else if (xhr.status === 403) {
          reject(forbiddenError(error));
        } else {
          reject(error);
        }
      }
    };

    xhr.onerror = () => reject(new ApiError(NETWORK_MESSAGE, { code: "NETWORK_ERROR" }));
    xhr.ontimeout = () =>
      reject(new ApiError("The upload timed out.", { code: "TIMEOUT" }));
    xhr.onabort = () => reject(new ApiError("Upload cancelled.", { code: "ABORTED" }));

    const form = new FormData();
    form.append("file", file, file.name);
    xhr.send(form);
  });
}

export function createRealApi() {
  return {
    /* ------------------------------- authentication (public except /me) */

    register({ email, password }) {
      return request("/api/auth/register", {
        method: "POST",
        body: { email, password },
        auth: false, // never send a role; the backend assigns it
      });
    },

    login({ email, password }) {
      return request("/api/auth/login", {
        method: "POST",
        body: { email, password },
        auth: false,
      });
    },

    me() {
      // auth.js decides what a 401 means, so no automatic redirect here.
      return request("/api/auth/me", { redirectOnUnauthorized: false });
    },

    health() {
      return request("/api/health", {
        timeoutMs: CONFIG.healthTimeoutMs,
        auth: false,
      });
    },

    listDocuments() {
      return request("/api/documents/");
    },

    uploadDocument(file, onProgress) {
      return upload("/api/documents/upload", file, onProgress);
    },

    deleteDocument(docId) {
      return request(`/api/documents/${encodeURIComponent(docId)}`, { method: "DELETE" });
    },

    chat({ question, documentIds = null, topK = CONFIG.defaultTopK, signal }) {
      return request("/api/chat/", {
        method: "POST",
        body: {
          question,
          doc_ids: documentIds,
          k: topK,
        },
        signal,
        timeoutMs: CONFIG.requestTimeoutMs,
      });
    },
  };
}
