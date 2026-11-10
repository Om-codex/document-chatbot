/**
 * Shared light/dark theme controller for the marketing pages.
 *
 * This is a classic (non-module) script loaded in <head> so it applies the
 * saved theme before first paint. It uses event delegation, so it keeps
 * working even if a page module fails to load. The chatbot page keeps its own
 * inline copy so its existing behaviour is untouched.
 */
(function () {
  "use strict";

  document.documentElement.classList.add("js");

  var STORAGE_KEY = "document-chatbot.theme";
  var root = document.documentElement;

  function readStored() {
    try {
      var value = localStorage.getItem(STORAGE_KEY);
      return value === "light" || value === "dark" ? value : null;
    } catch (error) {
      return null;
    }
  }

  function preferred() {
    return window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function syncButton(theme) {
    var button = document.getElementById("theme-toggle");
    if (!button) return;
    var dark = theme === "dark";
    button.setAttribute("aria-pressed", String(dark));
    button.setAttribute(
      "title",
      dark ? "Switch to light mode" : "Switch to dark mode"
    );
    button.setAttribute("aria-label", dark ? "Light mode" : "Dark mode");
  }

  function applyTheme(theme, persist) {
    var next = theme === "dark" ? "dark" : "light";
    root.dataset.theme = next;
    if (persist) {
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch (error) {
        // Storage can be unavailable; the theme still applies for this session.
      }
    }
    syncButton(next);
  }

  applyTheme(readStored() || preferred(), false);

  document.addEventListener("click", function (event) {
    var target = event.target;
    var button = target && target.closest ? target.closest("#theme-toggle") : null;
    if (!button) return;
    applyTheme(root.dataset.theme === "dark" ? "light" : "dark", true);
  });

  document.addEventListener("DOMContentLoaded", function () {
    syncButton(root.dataset.theme);
  });

  if (window.matchMedia) {
    var query = window.matchMedia("(prefers-color-scheme: dark)");
    if (query.addEventListener) {
      query.addEventListener("change", function (event) {
        if (readStored() === null) {
          applyTheme(event.matches ? "dark" : "light", false);
        }
      });
    }
  }
})();
