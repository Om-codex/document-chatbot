/**
 * Reusable tour engine.
 *
 * One accessible <dialog> renders any tour object with the shape used in
 * `js/tours/*.js`. The engine owns navigation, progress, focus and persistence;
 * the tour content and the visual renderers stay in separate modules.
 *
 * Storage is per tour and deliberately small:
 *   { state: "in-progress" | "completed" | "skipped", step: number }
 */

import { renderTourVisual } from "./tour-visuals.js";

const DEFAULT_LABELS = {
  what: "What happens",
  why: "Why it matters",
  tech: "Technology",
  input: "Input",
  output: "Output",
  next: "Next",
};

export function readTourState(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    if (!["in-progress", "completed", "skipped"].includes(parsed.state)) return null;
    const step = Number.isInteger(parsed.step) ? parsed.step : 0;
    return { state: parsed.state, step: Math.max(0, step) };
  } catch (error) {
    return null;
  }
}

export function writeTourState(key, state, step) {
  try {
    localStorage.setItem(
      key,
      JSON.stringify({ state, step: Math.max(0, step), updatedAt: Date.now() })
    );
  } catch (error) {
    // Private mode or full storage: the tour still works for this session.
  }
}

export function clearTourState(key) {
  try {
    localStorage.removeItem(key);
  } catch (error) {
    // Ignore unavailable storage.
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function createTourEngine({ dialog, onStatusChange } = {}) {
  if (!dialog) throw new Error("Tour engine requires a dialog element.");

  const shell = dialog.querySelector("[data-tour-shell]");
  const completeView = dialog.querySelector("[data-tour-complete]");
  const kicker = dialog.querySelector("[data-tour-kicker]");
  const title = dialog.querySelector("[data-tour-title]");
  const subtitle = dialog.querySelector("[data-tour-subtitle]");
  const progressFill = dialog.querySelector("[data-tour-fill]");
  const progressBar = dialog.querySelector("[data-tour-progressbar]");
  const progressLabel = dialog.querySelector("[data-tour-label]");
  const copy = dialog.querySelector("[data-tour-copy]");
  const visual = dialog.querySelector("[data-tour-visual]");
  const prevButton = dialog.querySelector("[data-tour-prev]");
  const nextButton = dialog.querySelector("[data-tour-next]");
  const skipButton = dialog.querySelector("[data-tour-skip]");
  const closeButton = dialog.querySelector("[data-tour-close]");
  const announcer = dialog.querySelector("[data-tour-announcer]");
  const completeTitle = dialog.querySelector("[data-tour-complete-title]");
  const completeCopy = dialog.querySelector("[data-tour-complete-copy]");
  const replayButton = dialog.querySelector("[data-tour-replay]");
  const doneButton = dialog.querySelector("[data-tour-done]");

  const state = {
    tour: null,
    index: 0,
    status: null,
    lastFocus: null,
    open: false,
    // A completed tour stays completed if the user replays it and closes early.
    replayingCompleted: false,
  };

  function announce(message) {
    if (!announcer) return;
    announcer.textContent = "";
    window.setTimeout(() => {
      announcer.textContent = message;
    }, 30);
  }

  function setStatus(status) {
    if (!state.tour) return;
    state.status = status;
    writeTourState(state.tour.storageKey, status, state.index);
    if (typeof onStatusChange === "function") {
      onStatusChange(state.tour, status, state.index);
    }
  }

  function labels() {
    return Object.assign({}, DEFAULT_LABELS, state.tour.labels || {});
  }

  function renderCopy(step) {
    const names = labels();
    const blocks = [];

    if (step.what) {
      blocks.push(
        `<div class="tour-block"><h3>${escapeHtml(names.what)}</h3><p>${escapeHtml(step.what)}</p></div>`
      );
    }
    if (step.why) {
      blocks.push(
        `<div class="tour-block"><h3>${escapeHtml(names.why)}</h3><p>${escapeHtml(step.why)}</p></div>`
      );
    }
    if (step.tech) {
      blocks.push(
        `<div class="tour-block"><h3>${escapeHtml(names.tech)}</h3><p>${escapeHtml(step.tech)}</p></div>`
      );
    }

    const facts = [
      [names.input, step.input],
      [names.output, step.output],
      [names.next, step.next],
    ].filter(([, value]) => Boolean(value));

    const factsHtml = facts.length
      ? `<div class="tour-facts">${facts
          .map(
            ([label, value]) =>
              `<div class="tour-fact"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`
          )
          .join("")}</div>`
      : "";

    copy.innerHTML =
      `<p class="tour-lead">${escapeHtml(step.summary || "")}</p>` +
      blocks.join("") +
      factsHtml;
  }

  function render() {
    if (!state.tour) return;

    const steps = state.tour.steps;
    const atEnd = state.index >= steps.length;

    shell.hidden = atEnd;
    completeView.hidden = !atEnd;

    if (atEnd) {
      if (state.status !== "completed") setStatus("completed");
      if (completeTitle) {
        completeTitle.textContent = `Tour complete: ${state.tour.title}`;
        completeTitle.focus({ preventScroll: true });
      }
      if (completeCopy) {
        completeCopy.textContent =
          state.tour.id === "rag"
            ? "You have seen every stage of the pipeline. Open the chatbot to try it, or take the app tour for a walkthrough of the interface."
            : "You have seen the full workflow. Open the chatbot to upload a document, or replay this tour whenever you need a refresher.";
      }
      announce("Tour complete.");
      return;
    }

    const step = steps[state.index];
    const total = steps.length;

    kicker.textContent = step.kicker || `Step ${state.index + 1}`;
    title.textContent = step.title;
    subtitle.textContent = state.tour.title;

    const percent = Math.round(((state.index + 1) / total) * 100);
    progressFill.style.width = `${percent}%`;
    progressLabel.textContent = `Step ${state.index + 1} of ${total}`;
    if (progressBar) {
      progressBar.setAttribute("aria-valuenow", String(percent));
      progressBar.setAttribute("aria-valuetext", `Step ${state.index + 1} of ${total}`);
    }

    renderCopy(step);
    visual.innerHTML = renderTourVisual(step);

    prevButton.disabled = state.index === 0;
    nextButton.textContent = state.index === total - 1 ? "Finish" : "Next";

    if (!state.replayingCompleted) setStatus("in-progress");

    title.focus({ preventScroll: true });
    copy.scrollTop = 0;
    visual.scrollTop = 0;
    announce(`Step ${state.index + 1} of ${total}: ${step.title}`);
  }

  function next() {
    if (!state.tour) return;
    if (state.index >= state.tour.steps.length) return;
    state.index += 1;
    render();
  }

  function previous() {
    if (!state.tour || state.index === 0) return;
    state.index -= 1;
    render();
  }

  function open(tour, options = {}) {
    if (!tour || !Array.isArray(tour.steps) || tour.steps.length === 0) return;
    state.lastFocus = document.activeElement;
    state.tour = tour;
    state.index = Math.min(Math.max(0, options.step || 0), tour.steps.length);
    state.status = null;
    state.replayingCompleted =
      state.index === 0 && readTourState(tour.storageKey)?.state === "completed";
    state.open = true;

    document.documentElement.classList.add("tour-open");
    if (!dialog.open) dialog.showModal();
    render();
  }

  function finishAndClose(status) {
    if (!state.tour) return;
    if (status) {
      state.status = status;
      writeTourState(state.tour.storageKey, status, state.index);
      if (typeof onStatusChange === "function") {
        onStatusChange(state.tour, status, state.index);
      }
    }
    dialog.close();
  }

  function skip() {
    if (!state.tour) return;
    state.index = Math.min(state.index, state.tour.steps.length - 1);
    finishAndClose("skipped");
  }

  function replay() {
    if (!state.tour) return;
    state.index = 0;
    state.status = null;
    state.replayingCompleted = true;
    render();
  }

  prevButton.addEventListener("click", previous);
  nextButton.addEventListener("click", next);
  skipButton.addEventListener("click", skip);
  closeButton.addEventListener("click", () => finishAndClose());
  if (replayButton) replayButton.addEventListener("click", replay);
  if (doneButton) {
    doneButton.addEventListener("click", () => finishAndClose());
  }

  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    finishAndClose();
  });

  dialog.addEventListener("click", (event) => {
    // Clicking the backdrop (outside the dialog's content) closes the tour.
    if (event.target === dialog) finishAndClose();
  });

  dialog.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const tag = event.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    event.preventDefault();
    if (event.key === "ArrowRight") next();
    else previous();
  });

  dialog.addEventListener("close", () => {
    state.open = false;
    document.documentElement.classList.remove("tour-open");

    if (
      state.tour &&
      !state.replayingCompleted &&
      state.status !== "completed" &&
      state.status !== "skipped"
    ) {
      const step = Math.min(state.index, state.tour.steps.length - 1);
      writeTourState(state.tour.storageKey, "in-progress", step);
      if (typeof onStatusChange === "function") {
        onStatusChange(state.tour, "in-progress", step);
      }
    }

    if (state.lastFocus && typeof state.lastFocus.focus === "function") {
      state.lastFocus.focus({ preventScroll: true });
    }
  });

  return {
    open,
    close: () => finishAndClose(),
    next,
    previous,
    replay,
    skip,
    get isOpen() {
      return dialog.open;
    },
    get currentTour() {
      return state.tour;
    },
  };
}
