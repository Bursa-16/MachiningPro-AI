# Changelog

All notable changes to MachineryPro AI will be documented in this file.

## [0.1.0-alpha.4] - 2026-09-12

### Added

- Three.js / WebGL interactive 3D engineering viewport
- Machining workpiece, chuck, and tool geometry visualization
- Orbit, pan, and zoom camera controls
- Fit View and Reset View commands
- View Cube with standard engineering orientations (Front, Back, Top, Bottom, Left, Right, Isometric)
- XYZ trihedron axis indicator
- Shaded display mode
- Shaded with Edges display mode
- Wireframe display mode
- Transparent / X-Ray display mode
- 3D object picking — click to select geometry
- Model Tree ↔ 3D viewport synchronization
- Process / toolpath preview foundation
- Basic clipping / section plane foundation
- Responsive viewport resizing
- Graceful WebGL fallback for environments without GPU acceleration

### Engineering

- 3D viewport is a visualization and engineering decision support layer
- No full CAD kernel, production STEP topology editing, or production CAM toolpath generation
- No full machine kinematics, production collision detection, or full measurement suite in this release
- Deterministic engineering authority is unchanged; viewport is advisory/visual only

---

## [0.1.0-alpha.3] - 2026-09-08

### Added

- Separate landing page and engineering workspace routing
- Premium engineering workstation layout
- Model / Process Tree panel
- Context bar
- Command strip
- Operation ribbon
- Properties panel
- AI Engineering Assistant panel structure
- Process timeline
- Machining-specific visual identity
- Layout and viewport sizing corrections
- Frontend interaction synchronization

### Engineering

- Workstation is a structural and visual foundation; no production CAD/CAM data pipeline yet
- Engineering authority layer is unchanged; UI is advisory and display-only at this stage

---

## [0.1.0-alpha.2] - 2026-09-05

### Added

- Stage 3C deterministic milling engineering core
- Stage 3D deterministic drilling engineering core
- Stage 3E deterministic threading and tapping engineering core
- Stage 3F deterministic reaming and boring / hole-finishing core
- Stage 3G empirical engineering data foundation
- Provenance-mandatory empirical parameter records
- Deterministic applicability, lookup, conflict and duplicate semantics
- Unit-safe empirical parameter ranges
- Material and tooling applicability scaffolding

### Engineering

- Preserves deterministic-first engineering authority
- Unsourced empirical data fails closed
- Multiple matching empirical records are not silently ranked or averaged
- CAM tutorial/example values are not production seed data
- AI remains advisory and non-authoritative

---

## [0.1.0-alpha.1] - 2026-09-03

### Added

- MachineryPro AI standalone GitHub repository history
- Deterministic machining math foundation
- Deterministic turning engineering core
- Engineering validation rules and tests
- Initial public alpha release documentation

### Engineering

- Stage 3A: deterministic machining math foundation
- Stage 3B: deterministic turning core
- Deterministic-first, explainable-AI engineering authority model
