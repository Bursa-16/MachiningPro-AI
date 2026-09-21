(function () {
  "use strict";

  function initializeAccordions() {
    var triggers = document.querySelectorAll("[data-cad-import-accordion]");

    triggers.forEach(function (trigger) {
      var panelId = trigger.getAttribute("aria-controls");
      var panel = panelId ? document.getElementById(panelId) : null;
      if (!panel) return;

      function setExpanded(expanded) {
        trigger.setAttribute("aria-expanded", String(expanded));
        panel.hidden = !expanded;
      }

      setExpanded(trigger.getAttribute("aria-expanded") === "true");
      trigger.addEventListener("click", function () {
        setExpanded(trigger.getAttribute("aria-expanded") !== "true");
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeAccordions);
  } else {
    initializeAccordions();
  }
})();
