/**
 * UI controller (M1).
 *
 * Rules of the house:
 *  - every string that came from a file, a model or the API is rendered with
 *    textContent (never innerHTML) to avoid XSS;
 *  - all network failures surface as a readable message, never an alert;
 *  - the UI talks to the mock adapter or the real API via the same interface.
 */

import { CONFIG } from "./config.js";
import { createRealApi, ApiError } from "./api.js";
import { createMockApi } from "./mock.js";

const api = CONFIG.useMock ? createMockApi() : createRealApi();

const dom = {
  healthPill: document.getElementById("health-pill"),

  dropzone: document.getElementById("dropzone"),
  fileInput: document.getElementById("file-input"),
  uploadBtn: document.getElementById("upload-btn"),
  pasteBtn: document.getElementById("paste-btn"),
  uploadProgress: document.getElementById("upload-progress"),
  progressBar: document.getElementById("progress-bar"),
  progressPercent: document.getElementById("progress-percent"),
  progressLabel: document.getElementById("progress-label"),
  progressTrack: document.getElementById("progress-track"),
  uploadFeedback: document.getElementById("upload-feedback"),

  docCount: document.getElementById("doc-count"),
  selectAll: document.getElementById("select-all"),
  refreshDocs: document.getElementById("refresh-docs"),
  docList: document.getElementById("doc-list"),

  scopeSummary: document.getElementById("scope-summary"),
  chatLog: document.getElementById("chat-log"),
  chatForm: document.getElementById("chat-form"),
  question: document.getElementById("question"),
  questionCount: document.getElementById("question-count"),
  sendBtn: document.getElementById("send-btn"),
  composerHint: document.getElementById("composer-hint"),
  topK: document.getElementById("top-k"),
  clearChat: document.getElementById("clear-chat"),

  banner: document.getElementById("banner"),
  bannerText: document.getElementById("banner-text"),
  bannerClose: document.getElementById("banner-close"),
  toast: document.getElementById("toast"),
  announcer: document.getElementById("sr-announcer"),

  textDialog: document.getElementById("text-dialog"),
  textForm: document.getElementById("text-form"),
  textTitle: document.getElementById("text-title"),
  textContent: document.getElementById("text-content"),
  textCount: document.getElementById("text-count"),
  textError: document.getElementById("text-error"),
  textClose: document.getElementById("text-close"),
  textCancel: document.getElementById("text-cancel"),
  textSave: document.getElementById("text-save"),

  confirmDialog: document.getElementById("confirm-dialog"),
  confirmDocName: document.getElementById("confirm-doc-name"),
  confirmCancel: document.getElementById("confirm-cancel"),
  confirmDelete: document.getElementById("confirm-delete"),
  confirmClose: document.getElementById("confirm-close"),
};

const state = {
  documents: [],
  scope: "all", // "all" | "selected"
  selected: new Set(),
  deleting: new Set(),
  messages: [],
  busy: false,
  uploading: false,
  chatController: null,
  loaded: false,
  health: null,
  topK: readStoredTopK(),
};

let progressHideTimer = null;
let toastTimer = null;

/* ------------------------------------------------------------------ utils */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function extensionOf(filename) {
  const dot = String(filename).lastIndexOf(".");
  return dot >= 0 ? String(filename).slice(dot).toLowerCase() : "";
}

function plural(count, singular, pluralForm) {
  return count === 1 ? singular : pluralForm || `${singular}s`;
}

function safeFilename(title) {
  const cleaned = String(title)
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
    .replace(/[. ]+$/g, "")
    .trim();
  return cleaned || "pasted-text";
}

function clampTopK(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return CONFIG.defaultTopK;
  return Math.min(CONFIG.maxTopK, Math.max(CONFIG.minTopK, Math.round(numeric)));
}

function readStoredTopK() {
  try {
    const stored = window.localStorage.getItem(CONFIG.topKStorageKey);
    return stored === null ? CONFIG.defaultTopK : clampTopK(stored);
  } catch {
    return CONFIG.defaultTopK;
  }
}

function storeTopK(value) {
  try {
    window.localStorage.setItem(CONFIG.topKStorageKey, String(value));
  } catch {
    // Storage can be unavailable (private mode / blocked cookies). The value
    // still applies to the current session.
  }
}

function applyTopKFromInput({ commit = false } = {}) {
  const raw = dom.topK.value.trim();

  if (raw !== "") {
    const value = Number(raw);
    if (Number.isInteger(value) && value >= CONFIG.minTopK && value <= CONFIG.maxTopK) {
      state.topK = value;
      storeTopK(value);
    }
  }

  if (commit) {
    state.topK = clampTopK(raw === "" ? state.topK : raw);
    dom.topK.value = String(state.topK);
    storeTopK(state.topK);
  }

  updateComposer();
}

function errorText(error) {
  if (error instanceof ApiError) {
    const retry = error.retryAfter ? ` Retry in about ${error.retryAfter}s.` : "";
    return `${error.message}${retry}`;
  }
  return (error && error.message) || "Something went wrong.";
}

function typeLabel(sourceType) {
  return { pdf: "PDF", txt: "TXT", docx: "DOCX", text: "TEXT" }[sourceType] || "FILE";
}

function documentType(doc) {
  const ext = extensionOf(doc && doc.filename ? doc.filename : "");
  return { ".pdf": "pdf", ".txt": "txt", ".docx": "docx" }[ext] || "text";
}

function scrollToBottom() {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  dom.chatLog.scrollTo({ top: dom.chatLog.scrollHeight, behavior: reduced ? "auto" : "smooth" });
}

/**
 * Render markdown text as sanitized HTML for assistant answers.
 * Uses marked.js for parsing and DOMPurify for XSS sanitization.
 * Falls back to plain text if either library is unavailable.
 */
function renderMarkdown(text) {
  if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
    return text || "";
  }
  const html = marked.parse(text || "");
  return DOMPurify.sanitize(html);
}

function announce(message) {
  dom.announcer.textContent = "";
  setTimeout(() => {
    dom.announcer.textContent = message;
  }, 30);
}

/* --------------------------------------------------------------- health UI */

function renderMode() {
  if (CONFIG.useMock) {
    dom.healthPill.className = "pill pill--mock";
    dom.healthPill.textContent = "Mock mode";
    dom.healthPill.title = "The UI is running against the mock adapter. Remove ?mock=1 from the URL to use the real API.";
  } else {
    dom.healthPill.className = "pill pill--pending";
    dom.healthPill.textContent = "Connecting…";
    dom.healthPill.title = "Checking the backend…";
  }
}

function renderHealth() {
  if (!state.health) return;
  const isMock = CONFIG.useMock;
  const degraded = !isMock && state.health.status && state.health.status !== "ok";
  dom.healthPill.className = isMock
    ? "pill pill--mock"
    : degraded
      ? "pill pill--error"
      : "pill pill--ok";
  dom.healthPill.textContent = isMock ? "Mock mode" : degraded ? "Degraded" : "Connected";
  dom.healthPill.title =
    `LLM: ${state.health.llm_model}\nEmbeddings: ${state.health.embedding_model}` +
    `\nCollection: ${state.health.collection}\nDocuments: ${state.health.document_count}`;
}

function renderHealthError(error) {
  dom.healthPill.className = "pill pill--error";
  dom.healthPill.textContent = CONFIG.useMock ? "Mock error" : "API offline";
  dom.healthPill.title = errorText(error);
}

/* ----------------------------------------------------------------- banner */

function setBanner(message) {
  if (!message) {
    dom.banner.hidden = true;
    dom.bannerText.textContent = "";
    return;
  }
  dom.bannerText.textContent = message;
  dom.banner.hidden = false;
}

function showToast(message) {
  dom.toast.textContent = message;
  dom.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    dom.toast.hidden = true;
  }, 2600);
}

/* -------------------------------------------------------------- data layer */

function normalizeSelection() {
  const valid = new Set(state.documents.map((doc) => doc.doc_id));
  for (const id of state.selected) {
    if (!valid.has(id)) state.selected.delete(id);
  }
  if (state.scope === "all") state.selected.clear();
}

async function refreshDocuments({ addIds = [], silent = false } = {}) {
  try {
    const data = await api.listDocuments();
    state.documents = Array.isArray(data && data.documents) ? data.documents : [];
    state.loaded = true;
    normalizeSelection();

    if (state.scope === "selected") {
      const valid = new Set(state.documents.map((doc) => doc.doc_id));
      for (const id of addIds) if (valid.has(id)) state.selected.add(id);
    }

    renderLibrary();
    updateScopeUI();
    updateComposer();
    return true;
  } catch (error) {
    if (!silent) setBanner(errorText(error));
    if (!state.loaded) {
      state.loaded = true;
      renderLibraryError(errorText(error));
      updateScopeUI();
      updateComposer();
    }
    return false;
  }
}

async function loadInitial() {
  const [healthResult, docsResult] = await Promise.allSettled([api.health(), api.listDocuments()]);

  if (healthResult.status === "fulfilled") {
    state.health = healthResult.value;
    renderHealth();
  } else {
    renderHealthError(healthResult.reason);
    setBanner(errorText(healthResult.reason));
  }

  if (docsResult.status === "fulfilled") {
    state.documents = Array.isArray(docsResult.value && docsResult.value.documents)
      ? docsResult.value.documents
      : [];
    state.loaded = true;
    normalizeSelection();
    renderLibrary();
  } else {
    state.loaded = true;
    renderLibraryError(errorText(docsResult.reason));
    if (healthResult.status === "fulfilled") setBanner(errorText(docsResult.reason));
  }

  updateScopeUI();
  updateComposer();
}

/* --------------------------------------------------------- document library */

function isSelected(doc) {
  return state.scope === "all" || state.selected.has(doc.doc_id);
}

function renderLibrary() {
  dom.docCount.textContent = String(state.documents.length);
  dom.selectAll.disabled = state.documents.length === 0;
  dom.selectAll.checked = state.scope === "all" && state.documents.length > 0;
  dom.selectAll.indeterminate = state.scope === "selected" && state.selected.size > 0;

  dom.docList.replaceChildren();

  if (state.documents.length === 0) {
    const empty = el("p", "empty-note");
    empty.append(
      el("strong", null, "No documents yet"),
      document.createTextNode("Upload a PDF, TXT or DOCX file, or paste text to begin.")
    );
    dom.docList.append(empty);
    if (state.messages.length === 0) renderEmptyChat({ replace: true });
    return;
  }

  const fragment = document.createDocumentFragment();

  for (const doc of state.documents) {
    const deleting = state.deleting.has(doc.doc_id);
    const row = el("article", "doc-row");
    if (deleting) row.classList.add("is-deleting");

    const check = document.createElement("input");
    check.type = "checkbox";
    check.className = "doc-check";
    check.checked = isSelected(doc);
    check.disabled = deleting;
    check.setAttribute("aria-label", `Include “${doc.filename}” in search`);
    check.addEventListener("change", () => toggleDocument(doc, check.checked));

    const main = el("div", "doc-main");
    const titleRow = el("div", "doc-title-row");
    const name = el("span", "doc-name", doc.filename);
    name.title = doc.filename;
    const safeType = documentType(doc);
    const badge = el("span", `type-badge type-badge--${safeType}`, typeLabel(safeType));
    titleRow.append(name, badge);

    const chunkCount = Number(doc.total_chunks) || 0;
    const pageCount = Number(doc.total_pages);
    const metaParts = [`${chunkCount} ${plural(chunkCount, "chunk")}`];
    if (Number.isFinite(pageCount) && pageCount > 0) {
      metaParts.push(`${pageCount} ${plural(pageCount, "page")}`);
    }
    const meta = el("p", "doc-meta", metaParts.join(" · "));

    main.append(titleRow, meta);

    const del = el("button", "icon-btn icon-btn--danger");
    del.type = "button";
    del.disabled = deleting;
    del.title = "Delete document";
    del.setAttribute("aria-label", `Delete “${doc.filename}”`);
    del.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/>' +
      '<path d="M8 6V4h8v2"/><path d="m6 6 1 14h10l1-14"/><path d="M10 11v6M14 11v6"/></svg>';
    del.addEventListener("click", () => deleteDocument(doc));

    row.append(check, main, del);
    fragment.append(row);
  }

  dom.docList.append(fragment);
  if (state.messages.length === 0) renderEmptyChat({ replace: true });
}

function renderLibraryError(message) {
  dom.docCount.textContent = "—";
  dom.docList.replaceChildren();
  const empty = el("p", "empty-note");
  empty.append(
    el("strong", null, "Could not load documents"),
    document.createTextNode(message)
  );
  dom.docList.append(empty);
}

function toggleDocument(doc, checked) {
  if (checked) {
    if (state.scope === "all") {
      // All documents are already included; an explicit check changes nothing.
      renderLibrary();
      return;
    }
    state.selected.add(doc.doc_id);
    if (state.selected.size === state.documents.length) {
      state.scope = "all";
      state.selected.clear();
    }
  } else {
    if (state.scope === "all") {
      state.scope = "selected";
      state.selected = new Set(state.documents.map((item) => item.doc_id));
    }
    state.selected.delete(doc.doc_id);
  }

  renderLibrary();
  updateScopeUI();
  updateComposer();
}

function setSelectAll(checked) {
  if (checked) {
    state.scope = "all";
    state.selected.clear();
  } else {
    state.scope = "selected";
    state.selected.clear();
  }
  renderLibrary();
  updateScopeUI();
  updateComposer();
}

function removeDocumentLocally(docId) {
  state.documents = state.documents.filter((doc) => doc.doc_id !== docId);
  state.selected.delete(docId);
}

async function deleteDocument(doc) {
  if (state.deleting.has(doc.doc_id)) return;

  // Show confirmation dialog instead of native window.confirm.
  const confirmed = await confirmDeletion(doc.filename);
  if (!confirmed) return;

  state.deleting.add(doc.doc_id);
  renderLibrary();

  try {
    await api.deleteDocument(doc.doc_id);
    removeDocumentLocally(doc.doc_id);
    showToast(`“${doc.filename}” deleted`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      removeDocumentLocally(doc.doc_id);
      showToast("Document was already removed.");
    } else {
      setBanner(errorText(error));
    }
  } finally {
    state.deleting.delete(doc.doc_id);
    renderLibrary();
    updateScopeUI();
    updateComposer();
  }
}

/**
 * Show a confirmation dialog for document deletion.
 * Resolves to true if the user confirms, false if they cancel or close.
 */
function confirmDeletion(filename) {
  return new Promise((resolve) => {
    dom.confirmDocName.textContent = filename;

    const onCancel = () => {
      cleanup();
      resolve(false);
    };
    const onConfirm = () => {
      cleanup();
      resolve(true);
    };
    const onClose = () => {
      cleanup();
      resolve(false);
    };

    function cleanup() {
      dom.confirmCancel.removeEventListener("click", onCancel);
      dom.confirmDelete.removeEventListener("click", onConfirm);
      dom.confirmClose.removeEventListener("click", onClose);
      dom.confirmDialog.close();
    }

    dom.confirmCancel.addEventListener("click", onCancel, { once: true });
    dom.confirmDelete.addEventListener("click", onConfirm, { once: true });
    dom.confirmClose.addEventListener("click", onClose, { once: true });

    dom.confirmDialog.showModal();
  });
}

async function manualRefresh() {
  dom.refreshDocs.disabled = true;
  setBanner(null);
  try {
    const ok = await refreshDocuments();
    if (ok) showToast("Library refreshed");
  } finally {
    dom.refreshDocs.disabled = false;
  }
}

/* ------------------------------------------------------------------ upload */

function openPicker() {
  dom.fileInput.click();
}

function renderFeedback(items) {
  dom.uploadFeedback.replaceChildren();

  if (!items || items.length === 0) {
    dom.uploadFeedback.hidden = true;
    return;
  }

  for (const item of items) {
    const li = document.createElement("li");
    if (item.code === "DUPLICATE_DOCUMENT") li.classList.add("is-warning");

    const copy = el("div");
    copy.append(
      el("strong", null, item.filename || "File"),
      el("span", null, item.message || "Could not process this item.")
    );

    const dismiss = el("button", "feedback-dismiss", "×");
    dismiss.type = "button";
    dismiss.setAttribute("aria-label", "Dismiss upload messages");
    dismiss.addEventListener("click", () => renderFeedback([]));

    li.append(copy, dismiss);
    dom.uploadFeedback.append(li);
  }

  dom.uploadFeedback.hidden = false;
}

function showProgress(percent, label) {
  clearTimeout(progressHideTimer);

  const value = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
  dom.uploadProgress.hidden = false;
  dom.progressBar.style.width = `${value}%`;
  dom.progressPercent.textContent = `${value}%`;
  dom.progressLabel.textContent = label || "Uploading…";
  dom.progressTrack.setAttribute("aria-valuenow", String(value));
}

function hideProgress(delay = 0) {
  clearTimeout(progressHideTimer);
  progressHideTimer = setTimeout(() => {
    dom.uploadProgress.hidden = true;
    dom.progressBar.style.width = "0%";
  }, delay);
}

async function uploadFiles(files, initialProblems = []) {
  state.uploading = true;
  setBanner(null);
  renderFeedback([]);
  dom.uploadBtn.disabled = true;
  updateComposer();

  // The backend accepts one file per request, so upload sequentially. This also
  // keeps progress meaningful and isolates one bad file from the rest.
  const total = files.length;
  const added = [];
  const errors = [...initialProblems];

  try {
    for (let index = 0; index < total; index += 1) {
      const file = files[index];
      const label =
        total === 1
          ? `Uploading “${file.name}”…`
          : `Uploading ${index + 1} of ${total}: “${file.name}”…`;

      showProgress(Math.round((index / total) * 100), label);

      try {
        const result = await api.uploadDocument(file, (percent) => {
          const overall = Math.round(((index + percent / 100) / total) * 100);
          showProgress(
            overall,
            percent >= 100 ? `Indexing “${file.name}”…` : label
          );
        });

        if (result && result.doc_id) added.push(result);
      } catch (error) {
        errors.push({
          filename: file.name,
          code: error instanceof ApiError ? error.code : "UPLOAD_FAILED",
          message: errorText(error),
        });
      }
    }

    showProgress(100, "Upload complete");

    if (state.scope === "selected") {
      for (const doc of added) state.selected.add(doc.doc_id);
    }

    await refreshDocuments({ addIds: added.map((doc) => doc.doc_id), silent: true });

    if (state.scope === "selected" && state.selected.size === state.documents.length) {
      state.scope = "all";
      state.selected.clear();
      renderLibrary();
      updateScopeUI();
    }

    renderFeedback(errors);

    if (added.length > 0) {
      showToast(`${added.length} ${plural(added.length, "document")} added`);
    } else if (errors.length === 0) {
      setBanner("Upload finished, but the server returned no documents.");
    }
  } finally {
    state.uploading = false;
    dom.uploadBtn.disabled = false;
    hideProgress(600);
    updateComposer();
  }
}

async function handleFiles(fileList) {
  const files = Array.from(fileList || []);
  if (files.length === 0) return;

  const accepted = [];
  const problems = [];
  const maxBytes = CONFIG.maxFileMb * 1024 * 1024;

  if (files.length > CONFIG.maxFilesPerUpload) {
    problems.push({
      filename: "Selection",
      code: "TOO_MANY_FILES",
      message: `Choose at most ${CONFIG.maxFilesPerUpload} files at a time. Extra files were ignored.`,
    });
  }

  for (const file of files.slice(0, CONFIG.maxFilesPerUpload)) {
    const ext = extensionOf(file.name);

    if (!CONFIG.allowedExtensions.includes(ext)) {
      problems.push({
        filename: file.name,
        code: "INVALID_FILE_TYPE",
        message: `Unsupported file type${ext ? `: ${ext}` : ""}. Allowed: ${CONFIG.allowedExtensions.join(", ")}.`,
      });
    } else if (file.size === 0) {
      problems.push({ filename: file.name, code: "EMPTY_DOCUMENT", message: "This file is empty." });
    } else if (file.size > maxBytes) {
      problems.push({
        filename: file.name,
        code: "FILE_TOO_LARGE",
        message: `File is larger than ${CONFIG.maxFileMb} MB.`,
      });
    } else {
      accepted.push(file);
    }
  }

  if (accepted.length === 0) {
    renderFeedback(problems);
    return;
  }

  await uploadFiles(accepted, problems);
}

/* --------------------------------------------------------------- paste text */

function openTextDialog() {
  dom.textForm.reset();
  dom.textError.hidden = true;
  dom.textError.textContent = "";
  dom.textCount.textContent = `0 / ${CONFIG.maxTextChars.toLocaleString()} characters`;
  dom.textSave.disabled = false;
  dom.textSave.textContent = "Add to library";
  dom.textDialog.showModal();
  dom.textTitle.focus();
}

function showTextError(message) {
  dom.textError.textContent = message;
  dom.textError.hidden = false;
}

async function submitText(event) {
  event.preventDefault();

  const title = dom.textTitle.value.trim();
  const content = dom.textContent.value;

  if (!title) return showTextError("Add a title so citations are readable.");
  if (!content.trim()) return showTextError("Paste some text first.");
  if (content.length > CONFIG.maxTextChars) return showTextError("Text is too long.");

  dom.textSave.disabled = true;
  dom.textSave.textContent = "Adding…";
  dom.textError.hidden = true;

  try {
    // The backend only accepts files, so paste-text is uploaded as a .txt file.
    const base = safeFilename(title);
    const filename = base.toLowerCase().endsWith(".txt") ? base : `${base}.txt`;
    const file = new File([content.trim()], filename, { type: "text/plain" });
    const result = await api.uploadDocument(file, null);

    dom.textDialog.close();
    showToast(`“${title}” added to the library`);

    await refreshDocuments({ addIds: result && result.doc_id ? [result.doc_id] : [], silent: true });

    if (state.scope === "selected" && state.selected.size === state.documents.length) {
      state.scope = "all";
      state.selected.clear();
      renderLibrary();
      updateScopeUI();
    }
  } catch (error) {
    showTextError(errorText(error));
  } finally {
    dom.textSave.disabled = false;
    dom.textSave.textContent = "Add to library";
  }
}

/* ------------------------------------------------------------------ chat UI */

function removeEmptyState() {
  const empty = dom.chatLog.querySelector(".chat-empty");
  if (empty) empty.remove();
}

function renderEmptyChat({ replace = false } = {}) {
  if (replace) dom.chatLog.replaceChildren();
  if (dom.chatLog.querySelector(".chat-empty")) return;

  const hasDocs = state.documents.length > 0;
  const wrapper = el("div", "chat-empty");
  const inner = el("div", "chat-empty-inner");

  const icon = el("div", "chat-empty-icon");
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" ' +
    'stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>' +
    '<path d="M14 2v6h6"/><path d="M9 13h6M9 17h4"/></svg>';

  inner.append(
    icon,
    el("h3", null, hasDocs ? "Ask your first question" : "Add your first document"),
    el(
      "p",
      null,
      hasDocs
        ? "Answers are grounded in the documents currently selected in the library."
        : "Upload a PDF, TXT or DOCX file, or paste text. Then ask a question about it."
    )
  );

  if (hasDocs) {
    const examples = el("div", "example-list");
    for (const text of [
      "Summarize the key points",
      "What are the main definitions?",
      "Explain the conclusion in simple terms",
    ]) {
      const button = el("button", "example-btn", text);
      button.type = "button";
      button.dataset.example = text;
      examples.append(button);
    }
    inner.append(examples);
  }

  wrapper.append(inner);
  dom.chatLog.append(wrapper);
}

function normalizeSources(chunks) {
  if (!Array.isArray(chunks)) return [];

  return chunks.map((chunk) => {
    const metadata = (chunk && chunk.metadata) || {};
    const pageNumber =
      metadata.page_number ??
      (Number.isInteger(metadata.page) ? metadata.page + 1 : null);

    return {
      filename: metadata.filename || "Unknown",
      page: pageNumber,
      chunk_index: metadata.chunk_index,
      snippet: chunk && chunk.content ? chunk.content : "",
    };
  });
}

function buildSources(sources) {
  const details = el("details", "sources");
  details.append(el("summary", null, `${sources.length} ${plural(sources.length, "source")}`));

  const list = el("ol", "source-list");

  for (const source of sources) {
    const item = el("li", "source");
    const top = el("div", "source-top");
    top.append(el("span", "source-file", source.filename || "Untitled"));

    const metaParts = [];
    if (source.page !== null && source.page !== undefined) metaParts.push(`Page ${source.page}`);
    if (source.chunk_index !== null && source.chunk_index !== undefined) {
      metaParts.push(`Chunk ${source.chunk_index}`);
    }

    item.append(top);
    if (metaParts.length > 0) item.append(el("p", "source-meta", metaParts.join(" · ")));
    if (source.snippet) item.append(el("p", "source-snippet", source.snippet));

    list.append(item);
  }

  details.append(list);
  return details;
}

function buildMessage(message) {
  const wrapper = el("div", `message message--${message.role}`);
  if (message.error) wrapper.classList.add("message--error");

  const avatar = el("div", "avatar", message.role === "user" ? "YOU" : "AI");
  avatar.setAttribute("aria-hidden", "true");

  const body = el("div", "message-body");

  if (message.pending) {
    const line = el("div", "message-text");
    const typing = el("span", "typing");
    typing.append(el("span"), el("span"), el("span"));
    const label = el("span", "typing-label", "Searching your documents…");
    line.append(typing, label);
    body.append(line);
  } else {
    const messageText = el("p", "message-text");
    if (message.role === "assistant" && !message.error) {
      messageText.innerHTML = renderMarkdown(message.content);
    } else {
      messageText.textContent = message.content;
    }
    body.append(messageText);

    if (message.error) {
      if (message.code) {
        const meta = el("div", "message-meta");
        meta.append(el("span", "error-code", message.code));
        body.append(meta);
      }

      if (message.retryQuestion) {
        const retry = el("button", "retry-btn", "Try again");
        retry.type = "button";
        retry.addEventListener("click", () => retryMessage(message));
        body.append(retry);
      }
    } else if (message.role === "assistant") {
      if (Array.isArray(message.sources) && message.sources.length > 0) {
        body.append(buildSources(message.sources));
      } else {
        body.append(el("p", "message-meta", "No matching sources were returned."));
      }
    }
  }

  wrapper.append(avatar, body);
  return wrapper;
}

function appendMessage(message) {
  removeEmptyState();
  const node = buildMessage(message);
  message._node = node;
  dom.chatLog.append(node);
  scrollToBottom();
}

function replaceMessage(previous, next) {
  const index = state.messages.indexOf(previous);
  if (index !== -1) state.messages[index] = next;

  const node = buildMessage(next);
  next._node = node;

  if (previous._node && previous._node.parentNode) {
    previous._node.replaceWith(node);
  } else {
    dom.chatLog.append(node);
  }

  scrollToBottom();
}

function removeMessage(message) {
  const index = state.messages.indexOf(message);
  if (index !== -1) state.messages.splice(index, 1);

  if (message._node && message._node.parentNode) message._node.remove();

  if (state.messages.length === 0 && !dom.chatLog.querySelector(".chat-empty")) {
    renderEmptyChat();
  }
}

function canAsk() {
  if (state.documents.length === 0) return false;
  if (state.scope === "selected" && state.selected.size === 0) return false;
  return true;
}

function updateScopeUI() {
  const total = state.documents.length;

  if (!state.loaded) {
    dom.scopeSummary.textContent = "Loading documents…";
  } else if (total === 0) {
    dom.scopeSummary.textContent = "No documents indexed yet";
  } else if (state.scope === "all") {
    dom.scopeSummary.textContent = `Searching all ${total} ${plural(total, "document")}`;
  } else {
    dom.scopeSummary.textContent = `Searching ${state.selected.size} of ${total} ${plural(total, "document")}`;
  }

  dom.selectAll.checked = state.scope === "all" && total > 0;
  dom.selectAll.indeterminate = state.scope === "selected" && state.selected.size > 0;
}

function updateComposer() {
  const value = dom.question.value;
  dom.questionCount.textContent = `${value.length} / ${CONFIG.maxQuestionChars}`;

  const askable = canAsk();
  const hasText = value.trim().length > 0;

  dom.sendBtn.disabled = state.busy || !askable || !hasText;
  dom.sendBtn.textContent = state.busy ? "Sending…" : "Send";

  if (!state.loaded) {
    dom.composerHint.textContent = "Loading documents…";
  } else if (state.documents.length === 0) {
    dom.composerHint.textContent = "Add a document to start.";
  } else if (state.scope === "selected" && state.selected.size === 0) {
    dom.composerHint.textContent = "Select at least one document.";
  } else if (state.busy) {
    dom.composerHint.textContent = "Searching your documents…";
  } else {
    dom.composerHint.textContent = "Answers cite sources · Enter to send";
  }
}

async function sendQuestion(raw) {
  const question = String(raw || "").trim();
  if (!question || state.busy || !canAsk()) {
    updateComposer();
    return;
  }

  setBanner(null);

  const userMessage = { role: "user", content: question };
  state.messages.push(userMessage);
  appendMessage(userMessage);

  dom.question.value = "";
  autoGrow();
  updateComposer();

  await requestAnswer(question);
}

async function requestAnswer(question) {
  const pending = { role: "assistant", pending: true };
  state.messages.push(pending);
  appendMessage(pending);

  state.busy = true;
  updateComposer();

  const controller = new AbortController();
  state.chatController = controller;

  try {
    const documentIds = state.scope === "all" ? null : Array.from(state.selected);
    const result = await api.chat({
      question,
      documentIds,
      topK: state.topK,
      signal: controller.signal,
    });

    const finalMessage = {
      role: "assistant",
      content: (result && result.answer) || "The model returned an empty answer.",
      sources: normalizeSources(result && result.retrieved_chunks),
    };

    replaceMessage(pending, finalMessage);
    announce("Assistant replied.");
  } catch (error) {
    if (error instanceof ApiError && error.code === "ABORTED") {
      removeMessage(pending);
    } else {
      const failed = {
        role: "assistant",
        error: true,
        content: errorText(error),
        code: error instanceof ApiError ? error.code : "UNKNOWN",
        retryQuestion: question,
      };
      replaceMessage(pending, failed);
      announce(`Assistant error: ${failed.content}`);
    }
  } finally {
    state.busy = false;
    state.chatController = null;
    updateComposer();
  }
}

function retryMessage(message) {
  if (state.busy || !message.retryQuestion) return;

  const index = state.messages.indexOf(message);
  if (index !== -1) state.messages.splice(index, 1);
  if (message._node && message._node.parentNode) message._node.remove();

  requestAnswer(message.retryQuestion);
}

function clearChat() {
  if (state.chatController) state.chatController.abort();

  state.messages = [];
  state.busy = false;
  state.chatController = null;

  dom.chatLog.replaceChildren();
  renderEmptyChat();
  updateComposer();
  announce("Chat cleared.");
}

/* ------------------------------------------------------------------ events */

function bindEvents() {
  dom.bannerClose.addEventListener("click", () => setBanner(null));

  dom.uploadBtn.addEventListener("click", openPicker);
  dom.pasteBtn.addEventListener("click", openTextDialog);
  dom.refreshDocs.addEventListener("click", manualRefresh);
  dom.clearChat.addEventListener("click", clearChat);

  dom.dropzone.addEventListener("click", openPicker);
  dom.dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openPicker();
    }
  });

  dom.fileInput.addEventListener("change", async () => {
    const files = Array.from(dom.fileInput.files || []);
    dom.fileInput.value = "";
    await handleFiles(files);
  });

  dom.dropzone.addEventListener("dragenter", (event) => {
    event.preventDefault();
    dom.dropzone.classList.add("is-dragover");
  });
  dom.dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dom.dropzone.classList.add("is-dragover");
  });
  dom.dropzone.addEventListener("dragleave", (event) => {
    if (!dom.dropzone.contains(event.relatedTarget)) {
      dom.dropzone.classList.remove("is-dragover");
    }
  });
  dom.dropzone.addEventListener("drop", async (event) => {
    event.preventDefault();
    dom.dropzone.classList.remove("is-dragover");
    await handleFiles(event.dataTransfer ? event.dataTransfer.files : []);
  });

  // Prevent the browser from navigating away when a file is dropped outside.
  document.addEventListener("dragover", (event) => event.preventDefault());
  document.addEventListener("drop", (event) => event.preventDefault());

  dom.selectAll.addEventListener("change", () => setSelectAll(dom.selectAll.checked));

  dom.topK.addEventListener("input", () => applyTopKFromInput());
  dom.topK.addEventListener("change", () => applyTopKFromInput({ commit: true }));
  dom.topK.addEventListener("blur", () => applyTopKFromInput({ commit: true }));

  dom.question.addEventListener("input", () => {
    autoGrow();
    updateComposer();
  });
  dom.question.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      if (!dom.sendBtn.disabled) dom.chatForm.requestSubmit();
    }
  });

  dom.chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendQuestion(dom.question.value);
  });

  dom.chatLog.addEventListener("click", (event) => {
    const example = event.target.closest("[data-example]");
    if (example) {
      dom.question.value = example.dataset.example || "";
      autoGrow();
      updateComposer();
      dom.question.focus();
    }
  });

  dom.textClose.addEventListener("click", () => dom.textDialog.close());
  dom.textCancel.addEventListener("click", () => dom.textDialog.close());
  dom.textDialog.addEventListener("click", (event) => {
    if (event.target === dom.textDialog) dom.textDialog.close();
  });
  dom.textDialog.addEventListener("close", () => dom.pasteBtn.focus());

  dom.textTitle.addEventListener("input", () => {
    dom.textError.hidden = true;
  });
  dom.textContent.addEventListener("input", () => {
    dom.textCount.textContent = `${dom.textContent.value.length.toLocaleString()} / ${CONFIG.maxTextChars.toLocaleString()} characters`;
    dom.textError.hidden = true;
  });
  dom.textForm.addEventListener("submit", submitText);

  window.addEventListener("beforeunload", () => {
    if (state.chatController) state.chatController.abort();
  });
}

function autoGrow() {
  dom.question.style.height = "auto";
  dom.question.style.height = `${Math.min(dom.question.scrollHeight, 160)}px`;
}

/* -------------------------------------------------------------------- init */

async function init() {
  renderMode();
  dom.topK.value = String(state.topK);
  bindEvents();
  renderEmptyChat({ replace: true });
  updateScopeUI();
  updateComposer();
  autoGrow();
  await loadInitial();
}

init();
