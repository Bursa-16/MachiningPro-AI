/**
 * MachineryPro AI — Machining Visuals (UI-MEDIA-0A)
 *
 * Original SVG-based technical machining animations.
 * All assets are project-owned originals — zero external dependencies.
 *
 * VISUAL ASSET POLICY: All SVGs generated in-code. No external images.
 * LICENSE: Project-owned original work.
 */

(function () {
  "use strict";

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ── SVG builder helpers ─────────────────────────────────────────── */

  function el(tag, attrs, ...children) {
    const ns = "http://www.w3.org/2000/svg";
    const e = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
    for (const c of children) {
      if (typeof c === "string") e.textContent = c;
      else if (c) e.appendChild(c);
    }
    return e;
  }

  function svg(w, h, vb, ...children) {
    const s = el("svg", { width: w, height: h, viewBox: vb, xmlns: "http://www.w3.org/2000/svg" });
    for (const c of children) if (c) s.appendChild(c);
    return s;
  }

  /* ── COLOR TOKENS ────────────────────────────────────────────────── */

  const C = {
    steel:    "#64748b",
    steelLt:  "#94a3b8",
    brand:    "#2563eb",
    brandLt:  "#93c5fd",
    surface:  "#e2e8f0",
    cut:      "#ef4444",
    cutLt:    "#fca5a5",
    success:  "#10b981",
    warn:     "#f59e0b",
    bg:       "#f4f6f8",
    workpiece:"#cbd5e1",
    tool:     "#475569",
  };

  /* ── MILLING VISUAL ─────────────────────────────────────────────── */

  function buildMillingVisual() {
    const g = el("g");
    // Workpiece
    g.appendChild(el("rect", { x:40, y:100, width:220, height:60, rx:2, fill:C.workpiece, stroke:C.steel, "stroke-width":1 }));
    // Cut groove
    g.appendChild(el("rect", { x:90, y:95, width:80, height:10, rx:1, fill:C.bg, stroke:C.steelLt, "stroke-width":0.5 }));
    // Tool (end mill)
    g.appendChild(el("rect", { x:120, y:30, width:16, height:65, rx:2, fill:C.tool, stroke:C.steel, "stroke-width":1 }));
    // Flutes
    g.appendChild(el("line", { x1:124, y1:50, x2:132, y2:90, stroke:C.steelLt, "stroke-width":0.8 }));
    g.appendChild(el("line", { x1:132, y1:50, x2:124, y2:90, stroke:C.steelLt, "stroke-width":0.8 }));
    // Spindle housing
    g.appendChild(el("rect", { x:112, y:10, width:32, height:24, rx:3, fill:C.steel, stroke:C.tool, "stroke-width":1 }));
    // Toolpath
    g.appendChild(el("path", { d:"M60 80 H90 V95 H170 V80 H240", fill:"none", stroke:C.brand, "stroke-width":1.5, "stroke-dasharray":"4 3", opacity:0.7 }));
    // Feed arrow
    g.appendChild(el("polygon", { points:"165,80 158,76 158,84", fill:C.brand, opacity:0.8 }));
    // Label
    g.appendChild(el("text", { x:150, y:180, "text-anchor":"middle", "font-size":"10", fill:C.steel, "font-family":"Inter,sans-serif" }, "Milling — End Mill Face Cut"));
    // Rotation indicator
    if (!reducedMotion) {
      const arc = el("path", { d:"M122 22 A8 8 0 1 1 134 22", fill:"none", stroke:C.brandLt, "stroke-width":1.2 });
      const arrowHead = el("polygon", { points:"134,22 131,19 131,25", fill:C.brandLt });
      g.appendChild(arc);
      g.appendChild(arrowHead);
    }
    return svg("100%", "100%", "0 0 300 190", g);
  }

  /* ── TURNING VISUAL ─────────────────────────────────────────────── */

  function buildTurningVisual() {
    const g = el("g");
    // Workpiece (cylindrical side view)
    g.appendChild(el("rect", { x:60, y:60, width:180, height:70, rx:4, fill:C.workpiece, stroke:C.steel, "stroke-width":1 }));
    // Center line
    g.appendChild(el("line", { x1:50, y1:95, x2:250, y2:95, stroke:C.steelLt, "stroke-width":0.6, "stroke-dasharray":"6 3" }));
    // Chuck jaws
    g.appendChild(el("rect", { x:40, y:55, width:22, height:80, rx:2, fill:C.steel, stroke:C.tool, "stroke-width":1 }));
    // Tool insert
    g.appendChild(el("polygon", { points:"230,80 250,90 250,100 230,110 220,95", fill:C.tool, stroke:C.steel, "stroke-width":1 }));
    // Cutting edge highlight
    g.appendChild(el("line", { x1:230, y1:80, x2:230, y2:110, stroke:C.cut, "stroke-width":2 }));
    // Feed arrow
    g.appendChild(el("line", { x1:255, y1:95, x2:235, y2:95, stroke:C.brand, "stroke-width":1.5, "marker-end":"none" }));
    g.appendChild(el("polygon", { points:"235,95 240,91 240,99", fill:C.brand }));
    // Depth of cut
    g.appendChild(el("line", { x1:200, y1:60, x2:200, y2:52, stroke:C.warn, "stroke-width":1 }));
    g.appendChild(el("line", { x1:200, y1:130, x2:200, y2:138, stroke:C.warn, "stroke-width":1 }));
    g.appendChild(el("text", { x:205, y:50, "font-size":"8", fill:C.warn, "font-family":"Inter,sans-serif" }, "ap"));
    // Rotation
    if (!reducedMotion) {
      g.appendChild(el("path", { d:"M75 50 A16 16 0 1 1 75 140", fill:"none", stroke:C.brandLt, "stroke-width":1, "stroke-dasharray":"3 2" }));
    }
    g.appendChild(el("text", { x:150, y:175, "text-anchor":"middle", "font-size":"10", fill:C.steel, "font-family":"Inter,sans-serif" }, "Turning — External Longitudinal"));
    return svg("100%", "100%", "0 0 300 185", g);
  }

  /* ── DRILLING VISUAL ────────────────────────────────────────────── */

  function buildDrillingVisual() {
    const g = el("g");
    // Workpiece
    g.appendChild(el("rect", { x:60, y:90, width:180, height:60, rx:2, fill:C.workpiece, stroke:C.steel, "stroke-width":1 }));
    // Drilled hole
    g.appendChild(el("rect", { x:140, y:90, width:14, height:45, fill:C.bg, stroke:C.steelLt, "stroke-width":0.5 }));
    // Drill bit
    g.appendChild(el("rect", { x:142, y:20, width:10, height:72, fill:C.tool, stroke:C.steel, "stroke-width":0.8 }));
    // Point
    g.appendChild(el("polygon", { points:"142,92 152,92 147,100", fill:C.tool, stroke:C.steel, "stroke-width":0.5 }));
    // Flutes
    g.appendChild(el("line", { x1:144, y1:30, x2:150, y2:85, stroke:C.steelLt, "stroke-width":0.6 }));
    g.appendChild(el("line", { x1:150, y1:30, x2:144, y2:85, stroke:C.steelLt, "stroke-width":0.6 }));
    // Feed arrow (downward)
    g.appendChild(el("line", { x1:165, y1:35, x2:165, y2:75, stroke:C.brand, "stroke-width":1.5 }));
    g.appendChild(el("polygon", { points:"165,75 161,68 169,68", fill:C.brand }));
    // Spindle
    g.appendChild(el("rect", { x:135, y:5, width:24, height:18, rx:3, fill:C.steel }));
    g.appendChild(el("text", { x:150, y:175, "text-anchor":"middle", "font-size":"10", fill:C.steel, "font-family":"Inter,sans-serif" }, "Drilling — Through Hole"));
    return svg("100%", "100%", "0 0 300 185", g);
  }

  /* ── VALIDATION VISUAL ──────────────────────────────────────────── */

  function buildValidationVisual() {
    const g = el("g");
    // Workpiece outline
    g.appendChild(el("rect", { x:40, y:30, width:220, height:120, rx:4, fill:"none", stroke:C.steel, "stroke-width":1.5 }));
    // Gradient contour bands (thermal-style, horizontal)
    const colors = ["#3b82f6","#60a5fa","#93c5fd","#fde68a","#fbbf24","#f59e0b","#ef4444"];
    colors.forEach((c, i) => {
      g.appendChild(el("rect", { x:45, y:35 + i * 15, width:210, height:15, fill:c, opacity:0.25, rx:1 }));
    });
    // Cross-section lines
    g.appendChild(el("line", { x1:100, y1:30, x2:100, y2:150, stroke:C.steelLt, "stroke-width":0.5, "stroke-dasharray":"3 2" }));
    g.appendChild(el("line", { x1:200, y1:30, x2:200, y2:150, stroke:C.steelLt, "stroke-width":0.5, "stroke-dasharray":"3 2" }));
    // Checkmarks
    g.appendChild(el("circle", { cx:65, cy:165, r:8, fill:C.success, opacity:0.15 }));
    g.appendChild(el("path", { d:"M61 165 L64 168 L70 162", fill:"none", stroke:C.success, "stroke-width":1.5 }));
    g.appendChild(el("text", { x:78, y:168, "font-size":"9", fill:C.success, "font-family":"Inter,sans-serif" }, "Pass"));
    // Warning
    g.appendChild(el("circle", { cx:145, cy:165, r:8, fill:C.warn, opacity:0.15 }));
    g.appendChild(el("text", { x:143, y:168, "text-anchor":"middle", "font-size":"10", fill:C.warn, "font-family":"Inter,sans-serif", "font-weight":"bold" }, "!"));
    g.appendChild(el("text", { x:158, y:168, "font-size":"9", fill:C.warn, "font-family":"Inter,sans-serif" }, "Review"));
    // Label
    g.appendChild(el("text", { x:150, y:188, "text-anchor":"middle", "font-size":"9", fill:C.steelLt, "font-family":"Inter,sans-serif", "font-style":"italic" }, "Conceptual Validation Visual"));
    return svg("100%", "100%", "0 0 300 198", g);
  }

  /* ── HERO ANIMATION ─────────────────────────────────────────────── */

  function buildHeroVisual(container) {
    const g = el("g");
    // Grid
    for (let x = 0; x <= 400; x += 20) {
      g.appendChild(el("line", { x1:x, y1:0, x2:x, y2:200, stroke:C.surface, "stroke-width":0.3 }));
    }
    for (let y = 0; y <= 200; y += 20) {
      g.appendChild(el("line", { x1:0, y1:y, x2:400, y2:y, stroke:C.surface, "stroke-width":0.3 }));
    }
    // Workpiece
    g.appendChild(el("rect", { x:60, y:60, width:280, height:80, rx:3, fill:C.workpiece, stroke:C.steel, "stroke-width":1.2 }));
    // Toolpath
    const tp = el("path", {
      d:"M40 100 H80 L90 70 H200 L210 100 H340 L350 70 H360",
      fill:"none", stroke:C.brand, "stroke-width":2, "stroke-dasharray":"6 4",
      opacity:0.8,
    });
    g.appendChild(tp);
    // Cutter
    const cutter = el("g", { class:"mp-hero-cutter" });
    cutter.appendChild(el("rect", { x:-8, y:-30, width:16, height:30, rx:2, fill:C.tool, stroke:C.steel, "stroke-width":1 }));
    cutter.appendChild(el("rect", { x:-12, y:-42, width:24, height:14, rx:3, fill:C.steel }));
    g.appendChild(cutter);
    // Status indicators
    g.appendChild(el("circle", { cx:50, y:175, cy:175, r:4, fill:C.success }));
    g.appendChild(el("text", { x:60, y:178, "font-size":"9", fill:C.steel, "font-family":"Inter,sans-serif" }, "Deterministic"));
    g.appendChild(el("circle", { cx:170, cy:175, r:4, fill:C.brand }));
    g.appendChild(el("text", { x:180, y:178, "font-size":"9", fill:C.steel, "font-family":"Inter,sans-serif" }, "Traceable"));
    g.appendChild(el("circle", { cx:270, cy:175, r:4, fill:C.warn }));
    g.appendChild(el("text", { x:280, y:178, "font-size":"9", fill:C.steel, "font-family":"Inter,sans-serif" }, "Validated"));

    const s = svg("100%", "100%", "0 0 400 200", g);
    s.style.maxWidth = "480px";
    container.appendChild(s);

    // Animate cutter along path if motion allowed
    if (!reducedMotion && tp.getTotalLength) {
      let t = 0;
      const len = tp.getTotalLength();
      function frame() {
        t = (t + 0.4) % len;
        const p = tp.getPointAtLength(t);
        cutter.setAttribute("transform", `translate(${p.x},${p.y})`);
        requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    } else {
      cutter.setAttribute("transform", "translate(200,70)");
    }
  }

  /* ── CAM TOOLPATH VISUAL ──────────────────────────────────────────── */

  function buildCamVisual() {
    const g = el("g");
    g.appendChild(el("rect", { x:40, y:30, width:220, height:130, rx:3, fill:C.workpiece, stroke:C.steel, "stroke-width":1 }));
    g.appendChild(el("rect", { x:60, y:45, width:180, height:100, rx:4, fill:C.bg, stroke:C.steelLt, "stroke-width":0.8 }));
    g.appendChild(el("path", { d:"M70 55 H230 V65 H70 V75 H230 V85 H70 V95 H230 V105 H70 V115 H230 V125 H70 V135 H230", fill:"none", stroke:C.brand, "stroke-width":1.8, "stroke-linecap":"round" }));
    g.appendChild(el("path", { d:"M30 20 L70 50", fill:"none", stroke:C.success, "stroke-width":1.5, "stroke-dasharray":"3 2" }));
    g.appendChild(el("circle", { cx:30, cy:20, r:3, fill:C.success }));
    g.appendChild(el("path", { d:"M230 135 L270 20", fill:"none", stroke:C.cut, "stroke-width":1.5, "stroke-dasharray":"3 2" }));
    g.appendChild(el("circle", { cx:270, cy:20, r:3, fill:C.cut }));
    g.appendChild(el("line", { x1:40, y1:170, x2:55, y2:170, stroke:C.success, "stroke-width":1.5, "stroke-dasharray":"3 2" }));
    g.appendChild(el("text", { x:60, y:173, "font-size":"8", fill:C.steel, "font-family":"Inter,sans-serif" }, "Approach"));
    g.appendChild(el("line", { x1:110, y1:170, x2:125, y2:170, stroke:C.brand, "stroke-width":1.5 }));
    g.appendChild(el("text", { x:130, y:173, "font-size":"8", fill:C.steel, "font-family":"Inter,sans-serif" }, "Cut"));
    g.appendChild(el("line", { x1:160, y1:170, x2:175, y2:170, stroke:C.cut, "stroke-width":1.5, "stroke-dasharray":"3 2" }));
    g.appendChild(el("text", { x:180, y:173, "font-size":"8", fill:C.steel, "font-family":"Inter,sans-serif" }, "Retract"));
    g.appendChild(el("text", { x:150, y:190, "text-anchor":"middle", "font-size":"10", fill:C.steel, "font-family":"Inter,sans-serif" }, "CAM Toolpath — Zigzag Pocket Clearing"));
    return svg("100%", "100%", "0 0 300 198", g);
  }

  /* ── PROCESS SELECTOR ───────────────────────────────────────────── */

  const PROCESSES = {
    milling:    { title:"Milling",      desc:"End mill face cutting with programmed toolpath, spindle speed, and feed rate.", build: buildMillingVisual },
    turning:    { title:"Turning",      desc:"External longitudinal turning with controlled depth of cut and feed direction.", build: buildTurningVisual },
    drilling:   { title:"Drilling",     desc:"Through-hole drilling with axial feed, spindle rotation, and chip evacuation.", build: buildDrillingVisual },
    cam:        { title:"CAM Toolpath", desc:"Zigzag pocket clearing strategy with approach, cutting, and retract paths.", build: buildCamVisual },
    validation: { title:"Validation",   desc:"Thermal/stress-inspired contour visualization for engineering verification.", build: buildValidationVisual },
  };

  function initProcessSelector() {
    const container = document.getElementById("mp-process-selector");
    if (!container) return;

    const tabs = container.querySelector("[data-process-tabs]");
    const visual = container.querySelector("[data-process-visual]");
    const title = container.querySelector("[data-process-title]");
    const desc = container.querySelector("[data-process-desc]");
    if (!tabs || !visual || !title || !desc) return;

    function select(key) {
      const p = PROCESSES[key];
      if (!p) return;
      // Update tabs
      tabs.querySelectorAll("[data-process]").forEach(btn => {
        btn.classList.toggle("mp-process-tab--active", btn.dataset.process === key);
        btn.setAttribute("aria-selected", btn.dataset.process === key ? "true" : "false");
      });
      // Update visual
      visual.innerHTML = "";
      visual.appendChild(p.build());
      // Update text
      title.textContent = p.title;
      desc.textContent = p.desc;
    }

    tabs.addEventListener("click", e => {
      const btn = e.target.closest("[data-process]");
      if (btn) select(btn.dataset.process);
    });

    select("milling");
  }

  const WS = { activeOp: 'turning', activeNode: 'rough-turning', propsMode: 'properties', overlays: { axes: true, toolpath: true, dims: false, section: false }, activeStep: 'process' };

  function setActiveTimelineStep(step) {
    document.querySelectorAll('.mp-process-timeline__step').forEach(function(el) {
      el.classList.remove('mp-process-timeline__step--active');
      if (el.dataset.step === step) el.classList.add('mp-process-timeline__step--active');
    });
  }

  function initModelTree() {
    var tree = document.querySelector('[data-tree]');
    if (!tree) return;
    tree.addEventListener('click', function(e) {
      var expand = e.target.closest('.mp-tree-expand');
      if (expand) {
        var node = expand.closest('.mp-tree-node');
        var children = node.querySelector('.mp-tree-children');
        if (children) { children.classList.toggle('mp-tree-children--open'); expand.classList.toggle('mp-tree-expand--open'); }
        return;
      }
      var row = e.target.closest('[data-tree-row]');
      if (row) {
        tree.querySelectorAll('.mp-tree-row--active').forEach(function(r) { r.classList.remove('mp-tree-row--active'); });
        row.classList.add('mp-tree-row--active');
        WS.activeNode = row.dataset.target;
        var label = document.querySelector('.mp-viewport-label');
        if (label) { var m = { 'rough-turning': 'TURNING \xb7 ROUGHING', 'groove': 'FEATURE \xb7 GROOVE', 'face': 'FEATURE \xb7 FACE', 'drilling': 'DRILLING \xb7 THROUGH' }; if (m[row.dataset.target]) label.textContent = m[row.dataset.target]; }
        var sm = { 'rough-turning': 'process', 'groove': 'feature', 'drilling': 'tool', 'face': 'feature' };
        if (sm[row.dataset.target]) setActiveTimelineStep(sm[row.dataset.target]);
      }
    });
  }

  function initViewportToolbar() {
    var tb = document.querySelector('[data-viewport-toolbar]');
    if (!tb) return;
    tb.addEventListener('click', function(e) {
      var btn = e.target.closest('[data-vp-tool]');
      if (!btn) return;
      btn.classList.toggle('mp-vp-tool-btn--active');
      WS.overlays[btn.dataset.vpTool] = btn.classList.contains('mp-vp-tool-btn--active');
      var svg = document.querySelector('.mp-engineering-svg');
      if (!svg) return;
      var tp = svg.querySelector('.mp-anim-toolpath');
      if (tp) tp.style.opacity = WS.overlays.toolpath ? '0.8' : '0';
    });
  }

  function initPanelTabs() {
    var tabs = document.querySelector('[data-panel-tabs]');
    if (!tabs) return;
    tabs.addEventListener('click', function(e) {
      var tab = e.target.closest('[data-tab]');
      if (!tab) return;
      WS.propsMode = tab.dataset.tab;
      tabs.querySelectorAll('.mp-tab').forEach(function(t) { t.classList.remove('mp-tab--active'); });
      tab.classList.add('mp-tab--active');
      document.querySelectorAll('[data-tab-panel]').forEach(function(p) { p.classList.toggle('mp-tab-content--active', p.dataset.tabPanel === tab.dataset.tab); });
    });
  }

  function initOperationRibbon() {
    var ribbon = document.querySelector('.mp-operation-ribbon');
    if (!ribbon) return;
    ribbon.addEventListener('click', function(e) {
      var item = e.target.closest('[data-op]');
      if (!item || item.classList.contains('mp-operation-item--planned')) return;
      e.preventDefault();
      ribbon.querySelectorAll('.mp-operation-item--active').forEach(function(i) { i.classList.remove('mp-operation-item--active'); });
      item.classList.add('mp-operation-item--active');
      WS.activeOp = item.dataset.op;
      var label = document.querySelector('.mp-viewport-label');
      if (label) { var m = { turning: 'TURNING \xb7 ROUGHING', milling: 'MILLING \xb7 FACE', drilling: 'DRILLING \xb7 THROUGH', cam: 'CAM TOOLPATH', validation: 'VALIDATION \xb7 CHECK' }; if (m[item.dataset.op]) label.textContent = m[item.dataset.op]; }
    });
  }

  function initTimeline() {
    var tl = document.querySelector('[data-timeline]');
    if (!tl) return;
    tl.addEventListener('click', function(e) {
      var step = e.target.closest('[data-step]');
      if (!step) return;
      setActiveTimelineStep(step.dataset.step);
      WS.activeStep = step.dataset.step;
      var tree = document.querySelector('[data-tree]');
      if (!tree) return;
      var m = { cad: 'project', geometry: 'geometry', feature: 'features', process: 'rough-turning', tool: 'drilling', parameters: 'rough-turning', validation: 'validation' };
      if (m[step.dataset.step]) {
        tree.querySelectorAll('.mp-tree-row--active').forEach(function(r) { r.classList.remove('mp-tree-row--active'); });
        var row = tree.querySelector('[data-target="' + m[step.dataset.step] + '"]');
        if (row) row.classList.add('mp-tree-row--active');
      }
    });
  }

  function initAIAssistant() {
    document.querySelectorAll('.mp-ai-rec-actions').forEach(function(c) {
      c.addEventListener('click', function(e) {
        var btn = e.target.closest('.mp-ai-btn');
        if (!btn) return;
        var rec = btn.closest('.mp-ai-rec');
        if (btn.classList.contains('mp-ai-btn--accept')) {
          rec.style.opacity = '0.5'; rec.style.pointerEvents = 'none';
          var ev = rec.querySelector('.mp-ai-rec-evidence');
          if (ev) ev.textContent = 'Accepted for scenario comparison.';
        } else if (btn.classList.contains('mp-ai-btn--dismiss')) {
          rec.style.display = 'none';
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function() {
    var hero = document.getElementById("mp-hero-visual");
    if (hero) buildHeroVisual(hero);
    initProcessSelector();
    initModelTree();
    initViewportToolbar();
    initPanelTabs();
    initOperationRibbon();
    initTimeline();
    initAIAssistant();
  });
})();
