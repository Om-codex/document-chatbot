/**
 * Login / registration page controller.
 *
 * Client-side checks are for UX only; the backend remains the authority for
 * validation and authentication. No password is ever stored in the browser.
 */

import {
  registerUser,
  loginUser,
  getCurrentUser,
  isAuthenticated,
  chatUrl,
} from "./auth.js";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const dom = {
  banner: document.getElementById("auth-banner"),

  loginSection: document.getElementById("login-section"),
  loginForm: document.getElementById("login-form"),
  loginEmail: document.getElementById("login-email"),
  loginPassword: document.getElementById("login-password"),
  loginError: document.getElementById("login-error"),
  loginSubmit: document.getElementById("login-submit"),

  registerSection: document.getElementById("register-section"),
  registerForm: document.getElementById("register-form"),
  registerEmail: document.getElementById("register-email"),
  registerPassword: document.getElementById("register-password"),
  registerConfirm: document.getElementById("register-confirm"),
  registerError: document.getElementById("register-error"),
  registerSubmit: document.getElementById("register-submit"),
};

const state = { mode: "login", submitting: false };

/* ------------------------------------------------------------------ utils */

function showError(node, message) {
  if (!node) return;
  node.textContent = message;
  node.hidden = false;
}

function hideError(node) {
  if (!node) return;
  node.textContent = "";
  node.hidden = true;
}

function showBanner(message, { error = false } = {}) {
  if (!dom.banner) return;
  dom.banner.textContent = message;
  dom.banner.className = error ? "auth-banner auth-banner--error" : "auth-banner";
  dom.banner.hidden = false;
}

function hideBanner() {
  if (!dom.banner) return;
  dom.banner.hidden = true;
  dom.banner.textContent = "";
}

function setSubmitting(form, button, submitting) {
  state.submitting = submitting;
  if (!form || !button) return;

  for (const control of form.querySelectorAll("input, button")) {
    control.disabled = submitting;
  }

  const label = button.querySelector(".btn-label");
  if (label) {
    if (submitting) {
      if (!label.dataset.original) label.dataset.original = label.textContent;
      label.textContent = "Please wait…";
    } else if (label.dataset.original) {
      label.textContent = label.dataset.original;
    }
  }

  const spinner = button.querySelector(".btn-spinner");
  if (spinner) spinner.hidden = !submitting;
  form.setAttribute("aria-busy", String(submitting));
}

function validationMessage(error) {
  const details = error && error.details;
  const items = Array.isArray(details)
    ? details
    : details && Array.isArray(details.errors)
      ? details.errors
      : [];

  for (const item of items) {
    const field = Array.isArray(item && item.loc)
      ? String(item.loc[item.loc.length - 1])
      : "";
    if (field === "email") return "Enter a valid email address.";
    if (field === "password") return "Password must be between 8 and 128 characters.";
    if (item && item.msg) return item.msg;
  }
  return null;
}

function friendlyError(error) {
  if (!error) return "Something went wrong.";
  if (error.status === 409) return "That email is already registered. Try signing in instead.";
  if (error.status === 401) return "Incorrect email or password.";
  if (error.status === 403) return "Access denied. You do not have permission to do that.";
  if (error.status === 422 || error.code === "VALIDATION_ERROR") {
    return validationMessage(error) || error.message || "Check the details and try again.";
  }
  if (error.code === "NETWORK_ERROR") {
    return "Cannot reach the server. Check your connection and try again.";
  }
  return error.message || "Something went wrong.";
}

/* --------------------------------------------------------------- validation */

function validateEmail(email) {
  if (!email) return "Enter your email address.";
  if (!EMAIL_RE.test(email)) return "Enter a valid email address.";
  return null;
}

function validatePassword(password) {
  if (!password) return "Enter your password.";
  if (password.length < 8 || password.length > 128) {
    return "Password must be between 8 and 128 characters.";
  }
  return null;
}

function validateLogin(email, password) {
  return validateEmail(email) || validatePassword(password);
}

function validateRegistration(email, password, confirmation) {
  return (
    validateEmail(email) ||
    validatePassword(password) ||
    (!confirmation ? "Confirm your password." : null) ||
    (password !== confirmation ? "Passwords do not match." : null)
  );
}

/* -------------------------------------------------------------- mode / tabs */

function setMode(mode, { focus = true, keepBanner = false } = {}) {
  state.mode = mode;
  dom.loginSection.hidden = mode !== "login";
  dom.registerSection.hidden = mode !== "register";
  document.title = mode === "login"
    ? "Sign in — Document Chatbot"
    : "Create account — Document Chatbot";

  hideError(dom.loginError);
  hideError(dom.registerError);
  if (!keepBanner) hideBanner();

  if (focus) {
    const first = mode === "login" ? dom.loginEmail : dom.registerEmail;
    first?.focus();
  }
}

/* ------------------------------------------------------------------ submits */

async function submitLogin(event) {
  event.preventDefault();
  if (state.submitting) return;

  const email = dom.loginEmail.value.trim().toLowerCase();
  const password = dom.loginPassword.value;
  const problem = validateLogin(email, password);
  if (problem) {
    showError(dom.loginError, problem);
    return;
  }

  hideError(dom.loginError);
  hideBanner();
  setSubmitting(dom.loginForm, dom.loginSubmit, true);

  try {
    await loginUser({ email, password });
    window.location.assign(chatUrl());
  } catch (error) {
    showError(dom.loginError, friendlyError(error));
  } finally {
    setSubmitting(dom.loginForm, dom.loginSubmit, false);
  }
}

async function submitRegistration(event) {
  event.preventDefault();
  if (state.submitting) return;

  const email = dom.registerEmail.value.trim().toLowerCase();
  const password = dom.registerPassword.value;
  const confirmation = dom.registerConfirm.value;
  const problem = validateRegistration(email, password, confirmation);
  if (problem) {
    showError(dom.registerError, problem);
    return;
  }

  hideError(dom.registerError);
  hideBanner();
  setSubmitting(dom.registerForm, dom.registerSubmit, true);

  try {
    const user = await registerUser({ email, password });
    dom.registerPassword.value = "";
    dom.registerConfirm.value = "";
    dom.loginEmail.value = user && user.email ? user.email : email;
    showBanner(`Account created for ${dom.loginEmail.value}. Sign in to continue.`);
    setMode("login", { focus: false, keepBanner: true });
    dom.loginPassword.focus();
  } catch (error) {
    showError(dom.registerError, friendlyError(error));
  } finally {
    setSubmitting(dom.registerForm, dom.registerSubmit, false);
  }
}

/* -------------------------------------------------------------------- events */

function bindEvents() {
  dom.loginForm.addEventListener("submit", submitLogin);
  dom.registerForm.addEventListener("submit", submitRegistration);

  dom.loginForm.addEventListener("input", () => hideError(dom.loginError));
  dom.registerForm.addEventListener("input", () => hideError(dom.registerError));

  for (const button of document.querySelectorAll("[data-mode]")) {
    button.addEventListener("click", () => setMode(button.dataset.mode));
  }

  for (const button of document.querySelectorAll("[data-password-toggle]")) {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.passwordToggle);
      if (!input) return;
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.textContent = show ? "Hide" : "Show";
      button.setAttribute("aria-label", show ? "Hide password" : "Show password");
      button.setAttribute("aria-pressed", String(show));
      input.focus();
    });
  }
}

/* ---------------------------------------------------------------------- init */

async function init() {
  bindEvents();
  setMode("login", { focus: false });

  // An already authenticated visitor goes straight to the dashboard.
  if (isAuthenticated()) {
    try {
      const user = await getCurrentUser();
      if (user) {
        window.location.assign(chatUrl());
        return;
      }
    } catch {
      // A transient backend failure must not block the login form.
    }
  }
}

init();
