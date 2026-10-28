# MachiningPro AI — End-to-End Demo Guide

## Supported Input Formats
- Vector PDF (deterministic token extraction)
- DXF 2D (geometric feature recognition)
- STEP (Level 0/1 entity inventory; Level 2 requires pythonocc-core — see STEP_LEVEL2_DEPENDENCY.md)
- Manual req_set JSON input (for all pages)

## Demo Workflow (12 Steps)
1. Upload drawing → /app/cad-drawing/technical-drawing-intelligence
2. Semantic extraction → /app/planning-quality/drawing-parser
3. Engineer review of extractions (confirm/edit/reject each detection)
4. CAD feature recognition → /app/cad-drawing/cad-features
5. Drawing/CAD fusion (link requirements to features)
6. Process route alternatives → /app/planning-quality/process-routes
7. Route comparison and selection
8. Machine/tool/holder selection → /app/engineering/configuration-selection
9. Capability + cycle time → /app/planning-quality/process-capability
10. Generate manufacturing plan → /app/planning-quality/manufacturing-plan
11. Inspection + control plan review (tabs in ManufacturingPlanPage)
12. Review, approve, export (JSON / CSV / HTML / NC handoff)

## Demo Part — Precision Hydraulic Valve Spool (MP-DEMO-001)
- Synthetic part, not based on any real customer design
- Exercises: OD turning, stepped diameter, groove, position GD&T, circular runout, Ra 0.4 sealing face, G1/4 thread
- Load via "Load Demo Part" button on ManufacturingPlanPage, or use the req_set in frontend/app/src/data/demoSpool.ts

## Review Gates (mandatory human engineer actions)
- Extracted drawing semantics: confirm/edit/reject each detection
- GD&T interpretation: PENDING_REVIEW — engineer must approve
- Feature associations: confirm/reject; manual re-association available
- Route selection: engineer selects preferred route
- Manufacturing plan approval: explicit /review then /approve (never auto-approved)

## Limitations
- Drawing geometry not parsed (no automated leader line / arrow detection)
- Title block not auto-parsed (supply drawing_number/revision manually)
- STEP Level 2 feature recognition requires pythonocc-core (see STEP_LEVEL2_DEPENDENCY.md)
- VLM/OCR analysis requires local Ollama with granite3.2-vision:2b
- All stores in-memory only (restart clears all sessions)
- XLSX export deferred
- Spindle acceleration cycle time component deferred

## Safety Boundaries
- AUTO_GENERATED_PLAN_MARKED_APPROVED=NO — plans are always DRAFT
- KEY_CHARACTERISTIC never auto-assigned (engineer-only designation)
- INSUFFICIENT_DATA returned for unknowns — never fabricated or defaulted silently
- No production release authorization in this system
- All exports marked REFERENCE_ONLY

## Known Gaps
- No cross-page pipeline context before EPIC_04H Phase 2 (fixed in this release)
- STEP Level 2 needs pythonocc-core
- No database persistence (in-memory only)
- No multi-user authentication on most endpoints
