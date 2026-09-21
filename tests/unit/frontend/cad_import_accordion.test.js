"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const scriptPath = path.resolve(
  __dirname,
  "../../../frontend/static/js/cad-import.js"
);

function bootAccordion(initiallyExpanded, initiallyHidden) {
  const listeners = {};
  const attributes = new Map([
    ["aria-controls", "cad-import-advanced-panel"],
    ["aria-expanded", String(initiallyExpanded)],
  ]);
  const button = {
    addEventListener(eventName, listener) {
      listeners[eventName] = listener;
    },
    click() {
      listeners.click();
    },
    getAttribute(name) {
      return attributes.get(name) ?? null;
    },
    setAttribute(name, value) {
      attributes.set(name, String(value));
    },
  };
  const panel = { hidden: initiallyHidden };
  const document = {
    readyState: "complete",
    getElementById(id) {
      return id === "cad-import-advanced-panel" ? panel : null;
    },
    querySelectorAll(selector) {
      return selector === "[data-cad-import-accordion]" ? [button] : [];
    },
  };

  const source = fs.readFileSync(scriptPath, "utf8");
  vm.runInNewContext(source, { document });

  return { button, panel };
}

{
  const { button, panel } = bootAccordion(false, true);

  button.click();

  assert.equal(button.getAttribute("aria-expanded"), "true");
  assert.equal(panel.hidden, false);
}

{
  const { button, panel } = bootAccordion(true, false);

  button.click();

  assert.equal(button.getAttribute("aria-expanded"), "false");
  assert.equal(panel.hidden, true);
}
