/**
 * High-level authentication operations.
 *
 * This is the only module the UI should call for registration, login, logout
 * and session validation. Token storage lives in session.js; the HTTP details
 * live in api.js/mock.js. No module here ever sends a role or stores a password.
 */

import { CONFIG } from "./config.js";
import { createRealApi, ApiError } from "./api.js";
import { createMockApi } from "./mock.js";
import {
  getAccessToken,
  getStoredUser,
  saveSession,
  clearSession,
  isAuthenticated as hasToken,
  endSession,
  redirectToLogin,
  loginUrl,
  chatUrl,
} from "./session.js";

const api = CONFIG.useMock ? createMockApi() : createRealApi();

export { getAccessToken, redirectToLogin, loginUrl, chatUrl, getStoredUser };

/** Synchronous token-presence check. Not proof of validity. */
export function isAuthenticated() {
  return hasToken();
}

function isSessionError(error) {
  return Boolean(
    error &&
      (error.status === 401 ||
        error.code === "AUTH_REQUIRED" ||
        error.code === "SESSION_EXPIRED")
  );
}

/**
 * Register a new account. Registration succeeds but does NOT sign the user in:
 * the login page is shown so the user authenticates explicitly.
 * The role is always assigned by the backend and is never part of this request.
 */
export async function registerUser({ email, password } = {}) {
  const cleanEmail = String(email || "").trim().toLowerCase();
  return api.register({ email: cleanEmail, password });
}

/** Log in and persist the backend-issued token plus public user details. */
export async function loginUser({ email, password } = {}) {
  const cleanEmail = String(email || "").trim().toLowerCase();
  const response = await api.login({ email: cleanEmail, password });

  if (!response || typeof response.access_token !== "string" || !response.access_token) {
    throw new ApiError("The server did not return a valid session.", {
      code: "INVALID_LOGIN_RESPONSE",
      status: 502,
    });
  }

  saveSession({ token: response.access_token, user: response.user || null });
  return response.user || null;
}

/**
 * Validate the stored token with GET /api/auth/me and refresh the cached user.
 * Returns null when there is no valid session. Network/server errors are
 * re-thrown so the caller can show a message without destroying a possibly
 * still-valid session.
 */
export async function getCurrentUser() {
  const token = getAccessToken();
  if (!token) return null;

  try {
    const user = await api.me();
    if (user && typeof user === "object") {
      saveSession({ token, user });
    }
    return user || null;
  } catch (error) {
    if (isSessionError(error)) {
      clearSession();
      return null;
    }
    throw error;
  }
}

/**
 * Guard for protected pages. Returns the validated user, or null after the
 * invalid session has been cleared and the browser redirected to login.
 */
export async function requireAuthentication() {
  const user = await getCurrentUser();
  if (!user) {
    endSession();
    return null;
  }
  return user;
}

/** Frontend-only logout: no backend endpoint exists or is required. */
export function logoutUser() {
  endSession();
}
