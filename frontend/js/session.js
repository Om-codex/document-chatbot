/**
 * Centralized browser session storage.
 *
 * The backend issues a JWT access token in the login response. Until cookie
 * based auth is supported by the backend, the token is kept in one place so no
 * other module has to know where it lives. Never store passwords here, never
 * log the token, and never put it in a URL.
 *
 * localStorage is readable by JavaScript, so this is NOT protection against
 * XSS. See README.md for the trade-off and production considerations.
 */

const SESSION_KEY = "document-chatbot.session";
const FORWARDED_PARAMS = ["apiBase", "mock"];

function read() {
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (!raw) return null;

    const value = JSON.parse(raw);
    if (!value || typeof value !== "object") return null;
    if (typeof value.token !== "string" || value.token.length === 0) return null;

    return {
      token: value.token,
      user: value.user && typeof value.user === "object" ? value.user : null,
    };
  } catch {
    // Corrupt or unavailable storage is treated as "no session".
    return null;
  }
}

/** Return the stored session ({ token, user }) or null. */
export function getSession() {
  return read();
}

/** Persist the token and the public user returned by the backend. */
export function saveSession({ token, user = null }) {
  if (typeof token !== "string" || token.length === 0) {
    throw new Error("A token is required to save a session.");
  }

  const session = { token, user };
  try {
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    // Storage may be disabled; the session then lasts only for this page load.
  }
  return session;
}

/** Remove all authentication data. Passwords are never stored in the first place. */
export function clearSession() {
  try {
    window.localStorage.removeItem(SESSION_KEY);
  } catch {
    // Nothing to clear if storage is unavailable.
  }
}

export function getAccessToken() {
  const session = read();
  return session ? session.token : null;
}

export function getStoredUser() {
  const session = read();
  return session ? session.user : null;
}

/**
 * Synchronous "do we have a token?" check. This is NOT proof that the token is
 * valid: use getCurrentUser()/requireAuthentication() from auth.js for that.
 */
export function isAuthenticated() {
  return Boolean(getAccessToken());
}

function pageUrl(filename) {
  const url = new URL(filename, window.location.href);
  const current = new URL(window.location.href);
  for (const key of FORWARDED_PARAMS) {
    const value = current.searchParams.get(key);
    if (value !== null) url.searchParams.set(key, value);
  }
  return url.pathname + url.search;
}

/** URL helpers keep ?apiBase / ?mock working across the auth redirects. */
export function loginUrl() {
  return pageUrl("login.html");
}

export function chatUrl() {
  return pageUrl("chat.html");
}

export function redirectToLogin() {
  window.location.assign(loginUrl());
}

/**
 * Clear the session and, by default, return to the login screen.
 * Pass { redirect: false } when the caller only wants to invalidate stale data
 * (for example a failed /api/auth/me check while already on the login page).
 */
export function endSession({ redirect = true } = {}) {
  clearSession();
  if (redirect) redirectToLogin();
}
