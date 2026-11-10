/**
 * Tour chooser page controller.
 *
 * Starts either tour from a card or a `?tour=rag|app` link, shows saved status,
 * and records an explicit "skip tours" choice. It never opens a tour on its own
 * beyond an explicit link or button press.
 */

import { ragTour } from "./tours/rag-tour.js";
import { appTour } from "./tours/app-tour.js";
import {
  createTourEngine,
  readTourState,
  writeTourState,
} from "./tour-engine.js";

const tours = { rag: ragTour, app: appTour };
const dialog = document.getElementById("tour-dialog");
const pageStatus = document.getElementById("tour-page-status");

const engine = createTourEngine({
  dialog,
  onStatusChange(tour, status) {
    renderCard(tour.id);
    if (pageStatus && (status === "completed" || status === "skipped")) {
      pageStatus.textContent = `${tour.title} marked as ${status}.`;
    }
  },
});

function announce(message) {
  if (!pageStatus) return;
  pageStatus.textContent = "";
  window.setTimeout(() => {
    pageStatus.textContent = message;
  }, 30);
}

function stepNumber(tour, stored) {
  if (!stored) return 0;
  return Math.min(stored.step, tour.steps.length - 1);
}

function renderCard(tourId) {
  const tour = tours[tourId];
  if (!tour) return;

  const card = document.querySelector(`[data-tour-card="${tourId}"]`);
  const statusEl = document.querySelector(`[data-status="${tourId}"]`);
  const label = card ? card.querySelector("[data-start-label]") : null;
  const stored = readTourState(tour.storageKey);

  if (!statusEl || !label) return;

  statusEl.removeAttribute("data-state");

  if (!stored) {
    statusEl.textContent = "Not started";
    label.textContent = tourId === "rag" ? "Start engine tour" : "Start app tour";
    return;
  }

  if (stored.state === "completed") {
    statusEl.textContent = "Completed";
    statusEl.setAttribute("data-state", "completed");
    label.textContent = "Replay tour";
    return;
  }

  if (stored.state === "skipped") {
    statusEl.textContent = "Skipped";
    statusEl.setAttribute("data-state", "skipped");
    label.textContent = "Start tour";
    return;
  }

  const current = Math.min(stored.step + 1, tour.steps.length);
  statusEl.textContent = `In progress · step ${current} of ${tour.steps.length}`;
  statusEl.setAttribute("data-state", "in-progress");
  label.textContent = "Resume tour";
}

function startTour(tourId) {
  const tour = tours[tourId];
  if (!tour) return;
  const stored = readTourState(tour.storageKey);
  const resume = stored && stored.state === "in-progress" ? stepNumber(tour, stored) : 0;
  engine.open(tour, { step: resume });
}

Object.keys(tours).forEach(function (tourId) {
  const card = document.querySelector(`[data-tour-card="${tourId}"]`);
  if (!card) return;
  const button = card.querySelector("[data-start]");
  if (button) {
    button.addEventListener("click", function () {
      startTour(tourId);
    });
  }
  renderCard(tourId);
});

/* --------------------------------------------------- explicit ?tour= links */

const params = new URLSearchParams(window.location.search);
const requested = params.get("tour");

if (requested && tours[requested]) {
  startTour(requested);

  // Drop the parameter so a refresh does not reopen the tour unexpectedly.
  const url = new URL(window.location.href);
  url.searchParams.delete("tour");
  window.history.replaceState(null, "", url.pathname + url.search + url.hash);
}

/* ------------------------------------------------------------ skip all tours */

const skipAll = document.querySelector("[data-skip-all]");

if (skipAll) {
  skipAll.addEventListener("click", function () {
    Object.keys(tours).forEach(function (tourId) {
      const tour = tours[tourId];
      const stored = readTourState(tour.storageKey);
      if (stored && stored.state === "completed") return;
      writeTourState(tour.storageKey, "skipped", 0);
    });
    announce("Tours skipped. Opening the chatbot.");
    window.location.href = "chat.html";
  });
}

/* --------------------------------------------------------- cross-tab updates */

window.addEventListener("storage", function (event) {
  Object.keys(tours).forEach(function (tourId) {
    if (event.key === tours[tourId].storageKey) renderCard(tourId);
  });
});
