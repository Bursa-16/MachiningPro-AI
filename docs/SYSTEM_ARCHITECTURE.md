# System Architecture — MachiningPro AI

**Document type:** Living architecture reference
**Last updated:** v0.1.0-alpha.4

---

## 1. Value chain (target product)

CAD/Drawing → Feature Recognition → DFM → Process Planning → Machine Selection → Fixture →
Tool Selection → Cutting Parameters → CAM Strategy → Simulation → Quality Plan → Cost & Quote →
Scheduling → Execution → Monitoring → Actual Cost → Profitability → Continuous Learning

Not all stages are implemented. See implementation status below.

---

## 2. Layer view

```text
+--------------------------------------------------------------+
| User Experience / Engineering Workstation     IMPLEMENTED    |
|   landing page · workspace · Model/Process Tree              |
|   Properties panel · AI Assistant panel                      |
+--------------------------------------------------------------+
| Engineering Application / Workflow Layer      IMPLEMENTED    |
|   FastAPI application · Jinja2 templates                     |
|   static frontend assets · interaction layer                 |
+--------------------------------------------------------------+
| Interactive 3D Engineering Viewport           IMPLEMENTED    |
|   Three.js / WebGL · orbit / pan / zoom                      |
|   View Cube · XYZ trihedron · display modes                  |
|   object picking · tree ↔ 3D sync                            |
+--------------------------------------------------------------+
| Deterministic Engineering Core                IMPLEMENTED    |
|   units · validation · fail-closed engine                    |
|   machining math · turning · milling · drilling              |
|   threading · hole finishing                                  |
+--------------------------------------------------------------+
| Knowledge / Rules / Engineering Data          IMPLEMENTED    |
|   empirical data foundation · provenance-gated records       |
|   material and tooling scaffolding · rule registry           |
+--------------------------------------------------------------+
| AI Advisory Layer                             FOUNDATION     |
|   RAG over curated corpus — ADVISORY ONLY, cites sources     |
|   AI Engineering Assistant (structure implemented)           |
+--------------------------------------------------------------+
| Interoperability / Geometry / External Data   PLANNED        |
|   CAD kernel · STEP / IGES · feature recognition             |
|   CAM adapter · NC parser · format fidelity                  |
+--------------------------------------------------------------+
```

### Implementation status key

| Status | Meaning |
|---|---|
| IMPLEMENTED | Functional in current release (v0.1.0-alpha.4) |
| FOUNDATION | Architecture defined or partially built; not production-ready |
| PLANNED | Design exists; implementation not yet started |

---

## 3. Module map ↔ backend packages

| Package | Responsibility | Status |
|---|---|---|
| `backend.core` | units, validation, fail-closed engine | IMPLEMENTED |
| `backend.machining` | deterministic force/power/time/MRR calculators (3A–3F) | IMPLEMENTED |
| `backend.materials` | material registry (schema-first; provenance-gated values) | FOUNDATION |
| `backend.tooling` | ISO 13399-style tool model | FOUNDATION |
| `backend.cutting_parameters` | empirical recommendation + limit validation (3G) | FOUNDATION |
| `backend.machines` | machine capability models | PLANNED |
| `backend.process_planning` | op sequencing drafts + approval gate | PLANNED |
| `backend.quality` | inspection planning, Cp/Cpk | PLANNED |
| `backend.costing` | cycle time, should-cost, quote ledgers | PLANNED |
| `backend.ai` | RAG assistant, defect diagnosis, NLQ (advisory) | PLANNED |
| `backend.interop` | universal engineering interoperability (Stage 4 series) | PLANNED |

---

## 4. Frontend architecture

| Component | Status |
|---|---|
| FastAPI application serving | IMPLEMENTED |
| Jinja2 template rendering | IMPLEMENTED |
| Static frontend asset pipeline | IMPLEMENTED |
| Landing page | IMPLEMENTED |
| Engineering workspace | IMPLEMENTED |
| Model / Process Tree | IMPLEMENTED |
| Properties panel | IMPLEMENTED |
| AI Engineering Assistant panel | IMPLEMENTED |
| Process timeline | IMPLEMENTED |
| Three.js / WebGL viewport | IMPLEMENTED |
| View Cube, XYZ trihedron | IMPLEMENTED |
| Orbit / pan / zoom controls | IMPLEMENTED |
| Object picking | IMPLEMENTED |
| Tree ↔ 3D synchronization | IMPLEMENTED |
| Process / toolpath preview | FOUNDATION |
| Clipping / section planes | FOUNDATION |
| Full CAD kernel integration | PLANNED |
| Production CAM toolpath display | PLANNED |
| Machine kinematics visualization | PLANNED |
| Collision display | PLANNED |
| Full measurement suite | PLANNED |

---

## 5. Decision flow (fail-closed)

```
request
  → input completeness check  (missing ⇒ refuse with gap list)
  → approved-rule lookup
  → deterministic calculation
  → limit validation
  → result envelope:
      { value, unit, rule_id@revision, inputs-hash, citations, approval_state }
  → human approval gate
```

---

## 6. AI boundaries

- **A — Deterministic Core** (authoritative): machining math, tolerance math, SPC/Cp/Cpk, engineering limit checks. AI may not override these results.
- **B — AI-Assisted** (advisory, with citations): engineering explanations, plan and tool suggestions, defect diagnosis, natural-language assistant. All AI outputs are traceable and source-attributed.
- **C — Future ML** (not yet implemented): Ra/tool-life/cycle-time prediction, anomaly and load prediction — scientific grounding exists; training data does not yet exist.

---

## 7. Traceability contract

Every numeric output carries rule/model id + revision, hashed input snapshot, source references and timestamp. This is the platform's core IP: traceable, auditable engineering recommendations.

---

## 8. Interoperability architecture

The universal engineering interoperability layer (Stage 4 series) is defined in `MachineryPro_AI_Universal_Interoperability_Architecture_Roadmap.md`. It covers:

- Canonical Engineering Representation (CER)
- Format adapters (STEP, IGES, DXF, CAD native, CAM native, G-code)
- Feature recognition from B-rep
- PMI / GD&T extraction
- Conversion fidelity reporting

Stage 4 implementation has not yet begun.

---

## 9. Persistence

- SQLite for development and alpha.
- PostgreSQL migration planned for production deployment.
- Object storage for CAD and drawing files (planned).

---

## 10. Open engineering decisions

- CAD geometry kernel selection (OpenCASCADE vs. commercial SDK)
- Feature recognition algorithm approach (rule-based B-rep vs. ML-assisted)
- Material and tooling catalog data sourcing and licensing
- On-premises vs. cloud-first deployment model
- CAM system integration priority (Mastercam, NX, Fusion)
