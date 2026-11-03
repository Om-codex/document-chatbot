/**
 * Frontend configuration.
 *
 * `useMock` defaults to true so the UI works before the backend exists (M1).
 * Flip it to false in M6, or append `?mock=0` to the URL while developing.
 * Do NOT put API keys here — the browser must never see them.
 */

const params = new URLSearchParams(window.location.search);
const mockParam = params.get("mock");

const mockDisabled = mockParam !== null && ["0", "false", "off"].includes(mockParam.toLowerCase());

export const CONFIG = {
  apiBase: params.get("apiBase") || "",
  useMock: !mockDisabled,
  requestTimeoutMs: 120_000,
  healthTimeoutMs: 8_000,
  uploadTimeoutMs: 300_000,
  maxFileMb: 20,
  maxFilesPerUpload: 10,
  maxQuestionChars: 2000,
  maxTextChars: 100_000,
  mockLatencyMs: 600,
  allowedExtensions: [".pdf", ".txt", ".md", ".docx"],
};
