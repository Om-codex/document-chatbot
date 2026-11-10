/**
 * Shared behaviour for the marketing pages.
 *
 * Classic script (loaded with `defer`) so it also works when the site is opened
 * directly from disk. It only handles progressive enhancement: navigation,
 * scroll state and reveal-on-scroll. Nothing here is required to read the page.
 */
(function () {
  "use strict";

  var header = document.getElementById("site-header");
  var nav = document.getElementById("site-nav");
  var navToggle = document.getElementById("nav-toggle");
  var reduceMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ------------------------------------------------------------ mobile nav */

  function setNavOpen(open) {
    if (!header || !navToggle) return;
    header.classList.toggle("is-open", open);
    navToggle.setAttribute("aria-expanded", String(open));
    navToggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  }

  if (navToggle) {
    navToggle.addEventListener("click", function () {
      setNavOpen(!header.classList.contains("is-open"));
    });

    if (nav) {
      nav.addEventListener("click", function (event) {
        if (event.target.closest("a")) setNavOpen(false);
      });
    }

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && header.classList.contains("is-open")) {
        setNavOpen(false);
        navToggle.focus();
      }
    });

    document.addEventListener("click", function (event) {
      if (!header.classList.contains("is-open")) return;
      if (!header.contains(event.target)) setNavOpen(false);
    });

    window.addEventListener("resize", function () {
      if (window.innerWidth > 900) setNavOpen(false);
    });
  }

  /* -------------------------------------------------------- sticky header */

  function syncHeader() {
    if (!header) return;
    header.classList.toggle("is-scrolled", window.scrollY > 8);
  }

  syncHeader();
  window.addEventListener("scroll", syncHeader, { passive: true });

  /* ------------------------------------------------------ reveal on scroll */

  var revealItems = Array.prototype.slice.call(
    document.querySelectorAll("[data-reveal]")
  );

  if (reduceMotion || !("IntersectionObserver" in window)) {
    revealItems.forEach(function (item) {
      item.classList.add("is-visible");
    });
  } else {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
    );

    revealItems.forEach(function (item) {
      observer.observe(item);
    });
  }

  /* ---------------------------------------------------------------- footer */

  var year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());
})();
