/* MachiningPro AI — application shell behaviour (UX-01A).
 *
 * 1. Remembers which sidebar groups the viewer opened or closed.
 *    The group containing the current page is always shown open.
 * 2. Turns the sidebar into an off-canvas drawer on narrow viewports.
 *
 * Progressive enhancement only: without this script the sidebar still works
 * (native <details>) and the server opens the active group.
 * Browser storage is a per-viewer convenience; every access is guarded.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "machiningpro-ai.sidebar.groups.v1";

  function readState() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      var parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function writeState(state) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      /* storage unavailable: keep default behaviour */
    }
  }

  function initGroups() {
    var groups = document.querySelectorAll("details[data-nav-group]");
    if (!groups.length) return;
    var state = readState();

    groups.forEach(function (group) {
      var id = group.getAttribute("data-nav-group");
      var isActive = group.hasAttribute("data-nav-group-active");
      if (!isActive && Object.prototype.hasOwnProperty.call(state, id)) {
        group.open = state[id] === true;
      }
      group.addEventListener("toggle", function () {
        if (isActive && !group.open) {
          // Respect an explicit collapse of the active group for this page view,
          // but do not persist it: the active group reopens on navigation.
          return;
        }
        var next = readState();
        next[id] = group.open;
        writeState(next);
      });
    });
  }

  function initDrawer() {
    var shell = document.querySelector("[data-mp-shell]");
    var toggle = document.querySelector("[data-mp-nav-toggle]");
    var sidebar = document.getElementById("mp-sidebar");
    var backdrop = document.querySelector("[data-mp-nav-close]");
    if (!shell || !toggle || !sidebar) return;

    function setOpen(open) {
      shell.classList.toggle("mp-shell--nav-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      if (backdrop) backdrop.hidden = !open;
      if (open) {
        // Wait one frame so the drawer is visible (focusable) before moving focus.
        window.requestAnimationFrame(function () {
          var first = sidebar.querySelector("a, summary");
          if (first) first.focus();
        });
      }
    }

    toggle.addEventListener("click", function () {
      setOpen(!shell.classList.contains("mp-shell--nav-open"));
    });
    if (backdrop) {
      backdrop.addEventListener("click", function () { setOpen(false); });
    }
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && shell.classList.contains("mp-shell--nav-open")) {
        setOpen(false);
        toggle.focus();
      }
    });
    // Leaving the narrow layout closes the drawer so desktop state is clean.
    if (window.matchMedia) {
      var mq = window.matchMedia("(min-width: 901px)");
      var onChange = function (e) { if (e.matches) setOpen(false); };
      if (mq.addEventListener) mq.addEventListener("change", onChange);
      else if (mq.addListener) mq.addListener(onChange);
    }
  }

  function init() {
    initGroups();
    initDrawer();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
