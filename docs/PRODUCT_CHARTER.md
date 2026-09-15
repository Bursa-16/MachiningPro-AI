# Product Charter — MachiningPro AI

**Status:** Active
**Sources:** Stage 0 platform research reports (Programlar/), updated through v0.1.0-alpha.4.

---

## 1. Mission

Build an **independent, closed-loop machining intelligence platform** covering the engineering decision chain from CAD/technical-drawing understanding to profitable delivery.

MachiningPro AI is a standalone product. It has its own repository, architecture, roadmap, versioning, documentation, and product identity. It is not a module of, derivative of, or dependent on any other system.

The platform's governing engineering principles — deterministic authority, explainability, traceability, fail-closed behavior — are fundamental to sound machining engineering and are applied here as first-principles design decisions, not inherited from any external system.

---

## 2. The eleven disciplines on one part record

1. CAD & technical drawing understanding
2. Manufacturability analysis (DFM)
3. Computer-aided process planning (CAPP)
4. Tooling & cutting-parameter engineering
5. Fixture & clamping planning
6. CAM strategy creation & validation
7. Machine capability & finite capacity planning
8. CNC/MES shop-floor data collection
9. Quality planning & result verification
10. Quoting & predicted cost calculation
11. Actual cost, deviation & profitability analysis

The value is the **coupling**: tolerance drives sequence → sequence drives setups → setups drive fixture/quality cost → machine capacity drives due-date risk → actual cycle time corrects the next quote.

---

## 3. MVP scope (first sellable slice)

| Item | Decision |
|---|---|
| Input formats | STEP AP242 + PDF technical drawings |
| Part class | 3-axis prismatic CNC parts |
| Customer segment | Automotive/defense suppliers, high-variety low/medium volume |
| Outputs | DFM risk list, process-plan draft, tool + cutting-parameter suggestion, estimated cycle time, quote draft |
| Guarantee | Every decision carries source + revision; engineer approval required |

---

## 4. Phase-1 non-goals

- Translating native CAD formats with own code.
- Writing a new CAM kernel or postprocessors (integrate with existing CAM instead).
- Enabling material / heat-treatment suggestions without design requirement + engineer approval.
- Closed-loop optimization (later phase after core validation).

---

## 5. Governing principles

Deterministic calculations are **authoritative** · Explainable · Traceable · Revision-controlled · Human approval gates · Fail-closed on missing/invalid data.

---

## 6. Key risks and controls

Scope too large → narrow MVP · Wrong CAD/PMI reading → confidence score, overlay, human verification, fail-closed · Unlicensed catalog/web data → licensed APIs + provenance policy · AI hallucination → deterministic engine + rule registry + mandatory sourcing · Post/NC errors → mature CAM + virtual validation + signed release · Catalog-vs-real-machine gap → site-specific validated capability models · Estimate/accounting confusion → estimated/planned/actual ledger separation · Defense-sector security → on-prem option, RBAC, encryption, OT segmentation · Per-customer code drift → configuration + rule registry + adapter architecture.

---

## 7. Open engineering decisions

- CAD geometry kernel selection
- Feature recognition approach (rule-based vs. ML-assisted)
- Material and tooling catalog data sourcing and licensing
- Deployment model (on-premises vs. cloud-first)
- CAM system integration priority
- Measurable MVP exit criteria (benchmark part set, quoting accuracy target)
