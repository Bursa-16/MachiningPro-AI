# MachiningPro AI

MachiningPro AI is an AI-assisted machining engineering platform that combines deterministic engineering calculations, structured process knowledge, interactive engineering visualization, and explainable decision support.

## Core Principle

> Deterministic engineering calculations are authoritative.

AI acts as an advisory, explainable, and traceable layer. It surfaces evidence-oriented recommendations and explanations. It does not silently override validated engineering results.

## Current Release

**Public Alpha Engineering / Research Preview**

Current public branch: `main`

MachiningPro AI remains under active engineering validation and is not a
production-qualified manufacturing decision system.

---

## Current Engineering Capabilities

The following deterministic engineering cores are implemented and closed:

- **Machining Math Foundation** (Stage 3A) — cutting speed ↔ spindle speed, feed relationships, MRR, machining time, power, torque
- **Turning Core** (Stage 3B) — external turning, boring, facing, pass count, volume removal, turning MRR
- **Milling Core** (Stage 3C) — feed per rev, engagement ratios, milling time, milling MRR, validation rules
- **Drilling Core** (Stage 3D) — drilling-specific deterministic calculations and rules
- **Threading and Tapping Core** (Stage 3E) — deterministic threading and tapping calculations
- **Hole Finishing Core** (Stage 3F) — reaming and boring / hole-finishing calculations
- **Empirical Engineering Data Foundation** (Stage 3G) — provenance-mandatory empirical parameter records, material and tooling applicability, deterministic lookup semantics

All calculations are deterministic, reproducible, unit-safe, and fail closed on invalid inputs.

---

## Engineering Workstation

MachiningPro AI includes a premium engineering workstation interface with:

- Separate landing page and engineering workspace
- **Model / Process Tree** — hierarchical view of parts, features, and process steps
- **Engineering Viewport** — interactive 3D visualization (see below)
- **Properties Panel** — context-sensitive engineering properties
- **AI Engineering Assistant** — advisory, traceable, citation-aware
- **Process Timeline** — operation sequencing view
- **Operation Workflow** — structured engineering decision flow

---

## Interactive 3D Engineering Viewport

The engineering viewport is powered by Three.js / WebGL and provides:

- **Orbit / Pan / Zoom** camera controls
- **Fit View** and **Reset View** commands
- **View Cube** — standard engineering orientations (Front, Back, Top, Bottom, Left, Right, Isometric)
- **XYZ Trihedron** — axis orientation indicator
- **Display Modes** — Shaded, Shaded with Edges, Wireframe, Transparent / X-Ray
- **Object Picking** — click geometry to select and cross-reference with Model Tree
- **Model Tree ↔ 3D Synchronization** — selection state is shared between tree and viewport
- **Process / Toolpath Preview** — foundation for visualizing machining operations
- **Basic Clipping / Section Foundation** — sectional view capability
- **Graceful WebGL Fallback** — degrades safely when GPU acceleration is unavailable

The 3D viewport is a visualization and engineering decision support layer. It does not yet provide a full CAD kernel, production STEP topology editing, production CAM toolpath generation, full machine kinematics, production collision detection, or a full measurement suite.

---

## Product Architecture

```
User Experience / Engineering Workstation
          ↓
Engineering Application / Workflow Layer
          ↓
   Deterministic Engineering Core          ← authoritative
          ↓
  Knowledge / Rules / Engineering Data
          ↓
       AI Advisory Layer                   ← advisory only
          ↓
  Interoperability / Geometry / External Data
```

**Deterministic engineering calculations are always authoritative.** AI and visualization layers sit above or alongside the engineering core and may not override it.

---

## Engineering Principles

1. Deterministic where deterministic.
2. Engineering results must be reproducible.
3. Units and assumptions must be explicit.
4. Invalid physical inputs must fail clearly.
5. AI must be explainable and traceable.
6. AI availability must never be required for core machining calculations.
7. Rules may validate or warn but must not silently modify authoritative calculations.
8. Scientific research should support product capabilities, not automatically become product scope.
9. New functionality must demonstrate practical manufacturing value.
10. Architecture must remain modular and independently testable.

---

## Current Development Status

Deterministic process cores through Stage 3G are established and closed. Engineering interoperability architecture (Stage 4 series) is in definition. The current public preview includes the engineering workstation and interactive 3D viewport foundations.

MachiningPro AI remains in active alpha development and is not production-ready.

---

## Future Capability Areas

The following represent long-term product direction. They are not yet implemented.

- CAD / STEP geometry integration
- Manufacturing feature recognition
- DFM / manufacturability analysis
- CAPP / process planning
- Tooling and machine selection
- Measurement and inspection planning
- Collision detection and machine kinematics
- Cost and cycle time optimization
- Quality validation
- AI-assisted engineering decisions at production depth

These capabilities require further engineering foundation work before they can be introduced.

---

## Product Boundary

MachiningPro AI is a standalone product with its own:

- repository
- architecture
- roadmap
- versioning
- documentation
- engineering domain
- product identity

## Public Release Status

MachiningPro AI is currently an **alpha engineering/research preview**. It is
intended for engineering evaluation, research, software verification, and
controlled demonstrations. It is not a production-qualified manufacturing
decision system.

### Implemented capabilities

The current public preview contains deterministic engineering foundations for
machining analysis, including tool-life and surface-roughness modules,
technical-drawing interoperability foundations, setup/changeover-aware
planning, and the MachiningPro AI web application shell. Some backend
capabilities are intentionally exposed in the UI as integration-pending rather
than represented by placeholder calculations.

### Installation and verification

Use the dependency definitions included in the repository for the Python
environment. The principal verification commands are:

```text
py -m pytest tests/unit/machining tests/unit/interoperability tests/unit/planning
py -m ruff check backend/machining backend/interoperability backend/planning tests/unit/machining tests/unit/interoperability tests/unit/planning
```

For the web application:

```text
cd frontend/app
npm install
npm run build
```

### Validation status

`PRODUCTION_MODEL_APPROVED=NO`

`PQ03_ENTRY_READY=NO`

Engineering calculations and software behavior are under staged verification
and qualification. Public availability does not imply customer-specific,
production-process, regulatory, or safety approval.

### Known limitations

- This release is an alpha engineering/research preview, not a production-qualified release.
- Production qualification and acceptance limits remain outside the public-preview approval state.
- Dataset redistribution is limited to material with documented publication rights.
- UI integrations that are not yet backed by a verified public workflow are marked as integration-pending.
- Users remain responsible for engineering review of inputs, assumptions, machine limits, tooling limits, and final manufacturing decisions.

### Public-data and asset policy

Private validation workbooks, local research collections, development patches,
and other internal working material are not part of the public release.
Machining assets are included only when their source and license are documented.
