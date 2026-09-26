/* MachiningPro AI — public compact-menu behaviour (PUBLIC-01B).
 *
 * The compact header menu (<details class="mp-pub-menu">) already works
 * without JavaScript: native <details>/<summary> is keyboard operable
 * (Enter/Space toggles it, Tab reaches its links) and needs no script to
 * open or close. This file only adds progressive-enhancement niceties:
 *
 * 1. Keeps `aria-expanded` on the summary in sync with the open state, for
 *    assistive tech that expects it explicitly.
 * 2. Closes the menu on Escape or on an outside click, and returns focus
 *    to the summary so keyboard users aren't left inside a hidden panel.
 *
 * Every access is guarded; if anything is missing this simply no-ops.
 */
(function () {
  "use strict";

  function initCompactMenu() {
    var menu = document.querySelector(".mp-pub-menu");
    if (!menu) return;
    var summary = menu.querySelector("summary");
    if (!summary) return;

    function sync() {
      summary.setAttribute("aria-expanded", menu.open ? "true" : "false");
    }

    sync();
    menu.addEventListener("toggle", sync);

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && menu.open) {
        menu.open = false;
        summary.focus();
      }
    });

    document.addEventListener("click", function (event) {
      if (menu.open && !menu.contains(event.target)) {
        menu.open = false;
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCompactMenu);
  } else {
    initCompactMenu();
  }
})();
