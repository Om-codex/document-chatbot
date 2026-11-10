/**
 * Frontend configuration.
 *
 * The UI talks to the real FastAPI backend by default. To preview it without a
 * running backend, append `?mock=1` to the URL.
 * Do NOT put API keys here — the browser must never see them.
 */

const params = new URLSearchParams(window.location.search);
const mockParam = params.get("mock");

const mockEnabled =
  mockParam !== null && ["1", "true", "on", "yes"].includes(mockParam.toLowerCase());

export const CONFIG = {
  apiBase: params.get("apiBase") || "",
  useMock: mockEnabled,
  requestTimeoutMs: 120_000,
  healthTimeoutMs: 8_000,
  uploadTimeoutMs: 300_000,
  maxFileMb: 10,
  maxFilesPerUpload: 10,
  maxQuestionChars: 4000,
  maxTextChars: 100_000,
  maxTitleChars: 120,
  mockLatencyMs: 600,
  allowedExtensions: [".pdf", ".txt", ".docx"],
  minTopK: 1,
  maxTopK: 20,
  defaultTopK: 3,
  topKStorageKey: "document-chatbot.topK",
  themeStorageKey: "document-chatbot.theme",
};
