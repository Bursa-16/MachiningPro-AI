/**
 * MachiningPro AI â€” 3D Engineering Viewport Engine (UI-VISUAL-1E)
 * Lightweight, zero-dependency engineering viewport using WebGL and Three.js.
 * Fully interactive 3D scene representing workpieces, chucks, tools, and toolpaths.
 */

(function () {
  "use strict";

  // Public Namespace
  var MP3D = {
    state: {
      displayMode: "shaded", // shaded, edges, wireframe, transparent
      showAxes: true,
      showToolpath: true,
      showGrid: true,
      showDims: false,
      showSection: false,
      selectedObject: null,
      activeOp: "turning",
      viewName: "iso",
      isDragging: false,
      dragMode: null,
      lastX: 0,
      lastY: 0,
      downX: 0,
      downY: 0
    },
    scene: null,
    camera: null,
    renderer: null,
    container: null,
    canvas: null,

    // Objects
    workpiece: null,
    chuck: null,
    tool: null,
    toolpath: null,
    grid: null,
    axes: null,
    edgeGroup: null,
    objects: null,
    raycaster: null,
    pointerNdc: null,
    animationId: null,
    reduceMotion: false,

    // Custom Orbit/Pan/Zoom Orbit State
    target: new THREE.Vector3(0, 0, 0),
    radius: 7.0,
    theta: Math.PI / 4, // Horizontal rotation
    phi: Math.PI / 3,   // Vertical angle

    init: function (containerId) {
      this.container = document.getElementById(containerId);
      if (!this.container) return;

      // Three.js engine dependency guard
      if (typeof window.THREE === "undefined") {
        this.showFallback();
        return;
      }

      // Check WebGL support
      if (!this.checkWebGL()) {
        this.showFallback();
        return;
      }

      try {
        this.setupRenderer();
        this.setupScene();
        this.setupCamera();
        this.setupLights();
        this.buildSceneObjects();

        // Raycaster for object picking
        this.raycaster = new THREE.Raycaster();
        this.pointerNdc = new THREE.Vector2();

        this.setupEventListeners();
        this.animate();
        this.syncWithState();

        // Object registry used by tree <-> 3D synchronization
        this.objects = {
          geometry: this.workpiece,
          chuck: this.chuck,
          tooling: this.tool,
          tool: this.tool,
          toolpath: this.toolpath,
          features: this.workpiece,
          face: this.workpiece,
          groove: this.workpiece
        };

        // Mark as active so the static SVG prerender layer is hidden
        this.container.classList.add("mp-3d-viewport--active");

        // Respect user motion preferences
        this.reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

        // Re-measure so the canvas exactly matches the visible viewport
        this.onResize();

        // Dispatch loaded event
        window.dispatchEvent(new CustomEvent("mp-3d-viewport-ready"));
      } catch (err) {
        console.error("Three.js Init Failed:", err);
        this.showFallback();
      }
    },

    checkWebGL: function () {
      try {
        var canvas = document.createElement("canvas");
        return !!(window.WebGLRenderingContext && (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")));
      } catch (e) {
        return false;
      }
    },

    showFallback: function () {
      if (!this.container) return;
      this.container.innerHTML =
        '<div class="mp-viewport-fallback">' +
        '  <div class="mp-viewport-fallback__icon">\u26a0\ufe0f</div>' +
        '  <div class="mp-viewport-fallback__title">3D Viewport Offline</div>' +
        '  <div class="mp-viewport-fallback__desc">WebGL acceleration is disabled or unsupported. Rerouting to deterministic 2D telemetry.</div>' +
        '</div>';
      this.container.setAttribute("data-fallback", "true");
    },

    setupRenderer: function () {
      this.canvas = document.createElement("canvas");
      this.canvas.className = "mp-viewport-canvas";
      this.container.appendChild(this.canvas);

      this.renderer = new THREE.WebGLRenderer({
        canvas: this.canvas,
        antialias: true,
        alpha: false
      });
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      var rect = this.container.getBoundingClientRect();
      this.renderer.setSize(rect.width, rect.height);
      this.renderer.setClearColor(0x060a12, 1); // Exact match for --mp-ws-viewport background
      this.renderer.shadowMap.enabled = true;
    },

    setupScene: function () {
      this.scene = new THREE.Scene();
      this.scene.background = new THREE.Color(0x060a12);
    },

    setupCamera: function () {
      var rect = this.container.getBoundingClientRect();
      this.camera = new THREE.PerspectiveCamera(45, rect.width / rect.height, 0.1, 100);
      this.updateCameraPosition();
    },

    updateCameraPosition: function () {
      if (!this.camera) return;

      // Keep phi within safe boundaries to avoid Gimbal lock
      this.phi = Math.max(0.01, Math.min(Math.PI - 0.01, this.phi));

      var x = this.target.x + this.radius * Math.sin(this.phi) * Math.cos(this.theta);
      var y = this.target.y + this.radius * Math.cos(this.phi);
      var z = this.target.z + this.radius * Math.sin(this.phi) * Math.sin(this.theta);

      this.camera.position.set(x, y, z);
      this.camera.lookAt(this.target);
    },

    setupLights: function () {
      var ambient = new THREE.AmbientLight(0x384252, 0.8);
      this.scene.add(ambient);

      var dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
      dirLight1.position.set(5, 10, 7);
      dirLight1.castShadow = true;
      this.scene.add(dirLight1);

      var dirLight2 = new THREE.DirectionalLight(0x1d4ed8, 0.4); // Blue fill light matching brand
      dirLight2.position.set(-5, -5, -5);
      this.scene.add(dirLight2);
    },

    buildSceneObjects: function () {
      // 1. Grid Helper (Ground)
      this.grid = new THREE.GridHelper(10, 20, 0x1e293b, 0x0f172a);
      this.grid.position.y = -2.0;
      this.scene.add(this.grid);

      // 2. Axes Helper (Trihedron in corner / origin)
      this.axes = new THREE.AxesHelper(2.5);
      this.axes.position.set(-4, -1.9, -4);
      this.scene.add(this.axes);

      // 3. Chuck (Spindle head holding workpiece)
      this.chuck = new THREE.Group();
      this.chuck.name = "chuck";
      this.chuck.userData = { id: "chuck", label: "Spindle Chuck" };

      var chuckBodyGeo = new THREE.CylinderGeometry(1.4, 1.4, 0.8, 32);
      var chuckBodyMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        metalness: 0.8,
        roughness: 0.3
      });
      var chuckBody = new THREE.Mesh(chuckBodyGeo, chuckBodyMat);
      chuckBody.rotation.z = Math.PI / 2;
      chuckBody.position.x = -2.0;
      chuckBody.castShadow = true;
      chuckBody.receiveShadow = true;
      this.chuck.add(chuckBody);

      // 3 Jaws
      var jawGeo = new THREE.BoxGeometry(0.4, 0.5, 0.6);
      var jawMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        metalness: 0.7,
        roughness: 0.4
      });
      for (var i = 0; i < 3; i++) {
        var jaw = new THREE.Mesh(jawGeo, jawMat);
        var angle = (i * Math.PI * 2) / 3;
        jaw.position.set(-1.6, Math.cos(angle) * 1.0, Math.sin(angle) * 1.0);
        jaw.rotation.x = -angle;
        this.chuck.add(jaw);
      }
      this.scene.add(this.chuck);

      // 4. Workpiece (Stepped Cylinder)
      this.workpiece = new THREE.Group();
      this.workpiece.name = "workpiece";
      this.workpiece.userData = { id: "geometry", label: "Stepped Workpiece" };

      var wpMat = new THREE.MeshStandardMaterial({
        color: 0x64748b, // Steel/Metal color
        metalness: 0.8,
        roughness: 0.3
      });

      // Larger Step
      var segment1Geo = new THREE.CylinderGeometry(0.9, 0.9, 1.5, 32);
      var segment1 = new THREE.Mesh(segment1Geo, wpMat);
      segment1.rotation.z = Math.PI / 2;
      segment1.position.x = -0.75;
      segment1.castShadow = true;
      segment1.receiveShadow = true;
      this.workpiece.add(segment1);

      // Smaller Step
      var segment2Geo = new THREE.CylinderGeometry(0.6, 0.6, 2.5, 32);
      var segment2 = new THREE.Mesh(segment2Geo, wpMat);
      segment2.rotation.z = Math.PI / 2;
      segment2.position.x = 1.25;
      segment2.castShadow = true;
      segment2.receiveShadow = true;
      this.workpiece.add(segment2);

      this.scene.add(this.workpiece);

      // 5. Tool
      this.tool = new THREE.Group();
      this.tool.name = "tool";
      this.tool.userData = { id: "tooling", label: "Carbide Cutting Tool" };

      // Shank / Holder
      var shankGeo = new THREE.BoxGeometry(0.4, 0.4, 1.5);
      var shankMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        metalness: 0.6,
        roughness: 0.5
      });
      var shank = new THREE.Mesh(shankGeo, shankMat);
      shank.position.set(0.8, 1.2, 0.5);
      this.tool.add(shank);

      // Golden Carbide Insert
      var insertGeo = new THREE.ConeGeometry(0.15, 0.3, 4);
      var insertMat = new THREE.MeshStandardMaterial({
        color: 0xf59e0b, // Amber/Gold insert
        metalness: 0.9,
        roughness: 0.2
      });
      var insert = new THREE.Mesh(insertGeo, insertMat);
      insert.rotation.x = Math.PI;
      insert.position.set(0.8, 0.95, 1.25);
      this.tool.add(insert);

      this.scene.add(this.tool);

      // 6. Toolpath (Interactive 3D spiral curve)
      var points = [];
      for (var t = 0; t < 100; t++) {
        var angle = t * 0.4;
        var r = 0.65;
        var x = 2.4 - (t * 0.035);
        if (x < -1.4) break;
        var y = Math.cos(angle) * r;
        var z = Math.sin(angle) * r;
        points.push(new THREE.Vector3(x, y, z));
      }

      var toolpathGeo = new THREE.BufferGeometry().setFromPoints(points);
      var toolpathMat = new THREE.LineBasicMaterial({
        color: 0x06b6d4, // Cyan toolpath
        linewidth: 2
      });
      this.toolpath = new THREE.Line(toolpathGeo, toolpathMat);
      this.toolpath.name = "toolpath";
      this.scene.add(this.toolpath);
    },

    setupEventListeners: function () {
      if (!this.canvas) return;
      var self = this;
      var canvas = this.canvas;

      canvas.style.touchAction = "none";

      canvas.addEventListener("pointerdown", function (e) { self.onPointerDown(e); });
      canvas.addEventListener("pointermove", function (e) { self.onPointerMove(e); });
      canvas.addEventListener("pointerup", function (e) { self.onPointerUp(e); });
      canvas.addEventListener("pointerleave", function () { self.state.isDragging = false; });
      canvas.addEventListener("wheel", function (e) { self.onWheel(e); }, { passive: false });
      canvas.addEventListener("dblclick", function () { self.fitToScene(); });
      canvas.addEventListener("contextmenu", function (e) { e.preventDefault(); });

      window.addEventListener("resize", function () { self.onResize(); });

      // Global delegation: toolbar tools, display modes, view cube, tree rows, operation ribbon
      document.addEventListener("click", function (e) {
        var el = e.target && e.target.closest
          ? e.target.closest("[data-vp-tool], [data-vp-mode], [data-vp-view], [data-tree-row], [data-op]")
          : null;
        if (!el) return;
        if (el.hasAttribute("data-vp-tool")) { self.onToolbarTool(el); e.preventDefault(); }
        else if (el.hasAttribute("data-vp-mode")) { self.onToolbarMode(el); }
        else if (el.hasAttribute("data-vp-view")) { self.setView(el.getAttribute("data-vp-view")); }
        else if (el.hasAttribute("data-tree-row")) { self.onTreeRowClick(el); }
        else if (el.hasAttribute("data-op")) { self.onOperationClick(el); e.preventDefault(); }
      });
    },

    onPointerDown: function (e) {
      this.state.downX = e.clientX;
      this.state.downY = e.clientY;
      this.state.lastX = e.clientX;
      this.state.lastY = e.clientY;
      this.state.dragMode = (e.button === 1 || e.button === 2 || e.shiftKey) ? "pan" : "orbit";
      this.state.isDragging = true;
      if (this.canvas.setPointerCapture) this.canvas.setPointerCapture(e.pointerId);
      if (this.container) this.container.classList.add("is-dragging");
    },

    onPointerMove: function (e) {
      if (!this.state.isDragging) return;
      var dx = e.clientX - this.state.lastX;
      var dy = e.clientY - this.state.lastY;
      this.state.lastX = e.clientX;
      this.state.lastY = e.clientY;
      if (this.state.dragMode === "pan") this.panBy(dx, dy);
      else this.orbitBy(dx, dy);
    },

    onPointerUp: function (e) {
      if (!this.state.isDragging) return;
      this.state.isDragging = false;
      if (this.container) this.container.classList.remove("is-dragging");
      var travelled = Math.abs(e.clientX - this.state.downX) + Math.abs(e.clientY - this.state.downY);
      if (this.state.dragMode === "orbit" && travelled < 5) this.pick(e);
      this.state.dragMode = null;
    },

    onWheel: function (e) {
      e.preventDefault();
      var factor = Math.exp(e.deltaY * 0.001);
      this.zoomBy(factor);
    },

    orbitBy: function (dx, dy) {
      this.theta -= dx * 0.006;
      this.phi -= dy * 0.006;
      this.updateCameraPosition();
    },

    panBy: function (dx, dy) {
      if (!this.camera) return;
      var h = (this.container && this.container.clientHeight) || 1;
      var fov = this.camera.fov * Math.PI / 180;
      var worldPerPx = (2 * this.radius * Math.tan(fov / 2)) / h;
      var right = new THREE.Vector3(1, 0, 0).applyQuaternion(this.camera.quaternion);
      var up = new THREE.Vector3(0, 1, 0).applyQuaternion(this.camera.quaternion);
      this.target.addScaledVector(right, -dx * worldPerPx);
      this.target.addScaledVector(up, dy * worldPerPx);
      this.updateCameraPosition();
    },

    zoomBy: function (factor) {
      this.radius = Math.max(1.2, Math.min(40, this.radius * factor));
      this.updateCameraPosition();
    },

    onResize: function () {
      if (!this.renderer || !this.camera || !this.container) return;
      var rect = this.container.getBoundingClientRect();
      var w = Math.max(1, rect.width);
      var h = Math.max(1, rect.height);
      this.renderer.setSize(w, h);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
    },

    // â”€â”€ Picking / raycasting â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    pick: function (e) {
      if (!this.raycaster || !this.camera || !this.canvas) return;
      var rect = this.canvas.getBoundingClientRect();
      this.pointerNdc.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this.pointerNdc.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      this.raycaster.setFromCamera(this.pointerNdc, this.camera);

      var candidates = [this.workpiece, this.chuck, this.tool, this.toolpath].filter(Boolean);
      var hits = this.raycaster.intersectObjects(candidates, true);
      var root = hits.length ? this._findRoot(hits[0].object) : null;
      this.selectObject(root ? root.userData.id : null);
    },

    _findRoot: function (obj) {
      var cur = obj;
      while (cur) {
        if (cur.userData && cur.userData.id) return cur;
        cur = cur.parent;
      }
      return null;
    },

    selectObject: function (id) {
      this._clearHighlight();
      this.state.selectedObject = id || null;
      var matched = this.objects ? this.objects[id] : null;
      if (matched) {
        matched.traverse(function (c) {
          if (c.isMesh && c.material && c.material.emissive) {
            c.material.emissive.setHex(0x2563eb);
            c.material.emissiveIntensity = 0.75;
          }
        });
      }
      this._syncTreeFromSelection(id || "");
    },

    _clearHighlight: function () {
      var self = this;
      Object.keys(this.objects || {}).forEach(function (key) {
        var obj = self.objects[key];
        if (!obj) return;
        obj.traverse(function (c) {
          if (c.isMesh && c.material && c.material.emissive) {
            c.material.emissive.setHex(0x000000);
            c.material.emissiveIntensity = 1.0;
          }
        });
      });
    },

    _syncTreeFromSelection: function (id) {
      var rows = document.querySelectorAll("[data-tree-row][data-target]");
      for (var i = 0; i < rows.length; i++) {
        var row = rows[i];
        if (row.getAttribute("data-target") === id) row.classList.add("mp-tree-row--active");
        else row.classList.remove("mp-tree-row--active");
      }
      window.dispatchEvent(new CustomEvent("mp-3d-select", { detail: { id: id || null } }));
    },

    onTreeRowClick: function (row) {
      var target = row.getAttribute("data-target");
      if (!target) return;
      this.selectObject(target);
    },

    // â”€â”€ Display modes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    setDisplayMode: function (mode) {
      var valid = ["shaded", "edges", "wireframe", "transparent"];
      this.state.displayMode = valid.indexOf(mode) !== -1 ? mode : "shaded";
      this._rebuildEdges();

      var wantWireframe = this.state.displayMode === "wireframe";
      var wantTransparent = this.state.displayMode === "transparent";
      [this.workpiece, this.chuck, this.tool].forEach(function (group) {
        if (!group) return;
        group.traverse(function (c) {
          if (!c.isMesh || !c.material) return;
          var mats = Array.isArray(c.material) ? c.material : [c.material];
          for (var m = 0; m < mats.length; m++) {
            mats[m].wireframe = wantWireframe;
            mats[m].transparent = wantTransparent;
            mats[m].opacity = wantTransparent ? 0.5 : 1.0;
            mats[m].depthWrite = !wantTransparent;
            mats[m].needsUpdate = true;
          }
        });
      });
      this._updateToolbarModes();
      if (this.container) this.container.setAttribute("data-display-mode", this.state.displayMode);
    },

    _rebuildEdges: function () {
      if (this.edgeGroup) {
        this.scene.remove(this.edgeGroup);
        this._disposeGroup(this.edgeGroup);
        this.edgeGroup = null;
      }
      if (this.state.displayMode !== "edges") return;

      this.edgeGroup = new THREE.Group();
      this.edgeGroup.name = "edges-overlay";
      var self = this;
      [this.workpiece, this.chuck, this.tool].forEach(function (group) {
        if (!group) return;
        group.traverse(function (c) {
          if (c.isMesh && c.geometry) {
            var edgeGeo = new THREE.EdgesGeometry(c.geometry, 20);
            var edgeMat = new THREE.LineBasicMaterial({ color: 0x4b8aff, transparent: true, opacity: 0.65 });
            self.edgeGroup.add(new THREE.LineSegments(edgeGeo, edgeMat));
          }
        });
      });
      this.scene.add(this.edgeGroup);
    },

    _disposeGroup: function (group) {
      group.traverse(function (c) {
        if (c.geometry) c.geometry.dispose();
        if (c.material) {
          if (Array.isArray(c.material)) c.material.forEach(function (m) { m.dispose(); });
          else c.material.dispose();
        }
      });
    },

    _updateToolbarModes: function () {
      var btns = document.querySelectorAll("[data-vp-mode]");
      for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle("mp-vp-tool-btn--active", btns[i].getAttribute("data-vp-mode") === this.state.displayMode);
      }
    },

    onToolbarMode: function (btn) {
      this.setDisplayMode(btn.getAttribute("data-vp-mode"));
    },

    // â”€â”€ Standard orientations / View Cube â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    setView: function (name) {
      var views = {
        iso: { theta: Math.PI / 4, phi: Math.PI / 3 },
        front: { theta: 0, phi: Math.PI / 2 },
        back: { theta: Math.PI, phi: Math.PI / 2 },
        right: { theta: Math.PI / 2, phi: Math.PI / 2 },
        left: { theta: -Math.PI / 2, phi: Math.PI / 2 },
        top: { theta: Math.PI / 4, phi: 0.01 },
        bottom: { theta: Math.PI / 4, phi: Math.PI - 0.01 }
      };
      var v = views[name];
      if (!v) return;
      this.state.viewName = name;
      this.theta = v.theta;
      this.phi = v.phi;
      this.updateCameraPosition();
      this._updateViewCube(name);
    },

    _updateViewCube: function (name) {
      var btns = document.querySelectorAll("[data-vp-view]");
      for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle("mp-vp-view--active", btns[i].getAttribute("data-vp-view") === name);
      }
    },

    fitToScene: function () {
      if (!this.camera) return;
      var box = new THREE.Box3();
      [this.workpiece, this.chuck, this.tool, this.toolpath].forEach(function (obj) {
        if (obj) box.expandByObject(obj);
      });
      if (box.isEmpty()) return;
      var center = box.getCenter(new THREE.Vector3());
      var size = box.getSize(new THREE.Vector3());
      var radius = size.length() / 2;
      this.target.copy(center);
      this.radius = Math.max(1.5, radius * 2.4);
      this.updateCameraPosition();
    },

    resetView: function () {
      this.state.viewName = "iso";
      this.target.set(0, 0, 0);
      this.radius = 7.0;
      this.theta = Math.PI / 4;
      this.phi = Math.PI / 3;
      this.updateCameraPosition();
      this._updateViewCube("iso");
    },

    // â”€â”€ Toolbar toggles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    onToolbarTool: function (btn) {
      var tool = btn.getAttribute("data-vp-tool");
      if (tool === "fit") { this.fitToScene(); return; }
      if (tool === "reset") { this.resetView(); return; }

      var isActive = btn.classList.contains("mp-vp-tool-btn--active");
      if (tool === "axes") this.state.showAxes = !isActive;
      else if (tool === "toolpath") this.state.showToolpath = !isActive;
      else if (tool === "dims") this.state.showDims = !isActive;
      else if (tool === "section") this.state.showSection = !isActive;

      this._applyTools();
      this._updateToolbarToggles();
    },

    _applyTools: function () {
      if (this.axes) this.axes.visible = this.state.showAxes;
      if (this.toolpath) this.toolpath.visible = this.state.showToolpath;
      if (this.grid) this.grid.visible = this.state.showGrid;

      var dimsEl = document.querySelector("[data-3d-dims]");
      if (dimsEl) dimsEl.style.display = this.state.showDims ? "flex" : "none";

      this._applySection();
    },

    _applySection: function () {
      if (!this.renderer) return;
      var plane = null;
      if (this.state.showSection) {
        // Clip along the mid-vertical plane to reveal interior structure.
        plane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 1.6);
        this.renderer.localClippingEnabled = true;
      }
      [this.workpiece, this.chuck].forEach(function (group) {
        if (!group) return;
        group.traverse(function (c) {
          if (!c.isMesh || !c.material) return;
          var mats = Array.isArray(c.material) ? c.material : [c.material];
          for (var m = 0; m < mats.length; m++) {
            mats[m].clippingPlanes = plane ? [plane] : null;
            mats[m].needsUpdate = true;
          }
        });
      });
    },

    _updateToolbarToggles: function () {
      var self = this;
      var buttons = document.querySelectorAll("[data-vp-tool]");
      for (var i = 0; i < buttons.length; i++) {
        var btn = buttons[i];
        var tool = btn.getAttribute("data-vp-tool");
        if (tool === "fit" || tool === "reset") continue;
        var active = (tool === "axes" && self.state.showAxes) ||
                     (tool === "toolpath" && self.state.showToolpath) ||
                     (tool === "dims" && self.state.showDims) ||
                     (tool === "section" && self.state.showSection);
        btn.classList.toggle("mp-vp-tool-btn--active", active);
      }
    },

    // â”€â”€ Process / operation switching â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    onOperationClick: function (btn) {
      var op = btn.getAttribute("data-op");
      if (!op) return;
      var items = document.querySelectorAll(".mp-operation-item[data-op]");
      for (var i = 0; i < items.length; i++) {
        items[i].classList.toggle("mp-operation-item--active", items[i] === btn);
      }
      this.setOperation(op);
    },

    setOperation: function (op) {
      op = op || "turning";
      this.state.activeOp = op;
      if (this.container) this.container.setAttribute("data-operation", op);

      this._buildToolpath(op);
      this._positionToolForOp(op);

      var hud = document.querySelector("[data-3d-hud]");
      if (hud) hud.textContent = op.toUpperCase() + " \u00b7 3D";

      window.dispatchEvent(new CustomEvent("mp-3d-operation", { detail: { op: op } }));
    },

    _buildToolpath: function (op) {
      if (!this.toolpath) return;
      var points = [];
      var i, t, x, y, z, angle, z0;

      if (op === "milling") {
        // Zig-zag face-mill passes on the top surface
        for (i = 0; i < 4; i++) {
          z0 = -0.6 + i * 0.4;
          for (t = 0; t <= 1.0001; t += 0.05) {
            x = -1.6 + t * 4.6;
            y = 0.95;
            z = z0 + (i % 2 ? 0.04 : -0.04);
            points.push(new THREE.Vector3(x, y, z));
          }
        }
      } else if (op === "drilling") {
        // Vertical pecking pattern along the spindle axis
        for (t = 0; t <= 1.0001; t += 0.03) {
          x = 0.2;
          y = 2.2 - t * 4.0;
          z = 0.0;
          points.push(new THREE.Vector3(x, y, z));
        }
      } else {
        // Turning: helical glide path along the workpiece axis
        for (t = 0; t < 100; t++) {
          angle = t * 0.4;
          x = 2.4 - (t * 0.035);
          if (x < -1.4) break;
          y = Math.cos(angle) * 0.65;
          z = Math.sin(angle) * 0.65;
          points.push(new THREE.Vector3(x, y, z));
        }
      }

      if (this.toolpath.geometry) this.toolpath.geometry.dispose();
      this.toolpath.geometry = new THREE.BufferGeometry().setFromPoints(points);
    },

    _positionToolForOp: function (op) {
      if (!this.tool) return;
      if (op === "milling") {
        this.tool.position.set(0.6, 1.7, 0.4);
        this.tool.rotation.set(Math.PI / 2, 0, 0);
      } else if (op === "drilling") {
        this.tool.position.set(0.2, 1.9, 0);
        this.tool.rotation.set(Math.PI / 2, 0, 0);
      } else {
        this.tool.position.set(0, 0, 0);
        this.tool.rotation.set(0, 0, 0);
      }
    },

    syncWithState: function () {
      this._applyTools();
      this._updateToolbarToggles();
      this._updateToolbarModes();
      this._updateViewCube(this.state.viewName);
    },

    animate: function () {
      var self = this;
      function frame() {
        if (self.renderer && self.renderer.render) self.renderer.render(self.scene, self.camera);
        self.animationId = requestAnimationFrame(frame);
      }
      this.animationId = requestAnimationFrame(frame);
    },

    dispose: function () {
      if (this.animationId) cancelAnimationFrame(this.animationId);
      if (this.renderer) this.renderer.dispose();
      if (this.scene) this._disposeGroup(this.scene);
    }
  };

  // Public export BEFORE bootstrap: deferred scripts evaluate in
  // readyState "interactive" (not "loading"), so the bootstrap below runs
  // synchronously at evaluation time and the namespace must already exist.
  window.MP3D = MP3D;

  // Self-bootstrap when the engineering viewport container is present.
  // Uses the in-scope MP3D closure reference (not window.MP3D) so that
  // bootstrap ordering can never silently skip initialization.
  function bootstrapMP3D() {
    var mount = document.querySelector("[data-3d-viewport]");
    if (mount) {
      MP3D.init(mount.id || mount.getAttribute("data-3d-viewport") || "mp-3d-viewport");
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrapMP3D);
  } else {
    bootstrapMP3D();
  }
})();
