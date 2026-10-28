# MachiningPro AI — Customer Demo Guide
Version: 0.5.0-demo | Branch: work/next-stage

## Product Overview
MachiningPro AI transforms engineering drawings and CAD models into traceable, deterministic manufacturing plans with inspection and control plan generation. Every result is REFERENCE_ONLY and requires engineer validation before manufacturing use.

## Supported Inputs
| Format | Support Level | Notes |
|--------|--------------|-------|
| DXF 2D | FULL | Geometric feature recognition |
| Vector PDF | FULL | Text/annotation extraction |
| STEP AP203/214 | LEVEL_1 | Entity inventory; Level 2 requires pythonocc-core |
| Manual req_set JSON | FULL | All pages accept structured JSON input |
| STL / OBJ / 3MF | VIEWER_ONLY | 3D mesh viewer; no feature extraction |

## Demo Part — MP-DEMO-001 (Precision Hydraulic Valve Spool)
- Material: 42CrMo4 alloy steel
- Drawing number: MP-DEMO-001, Revision A
- Features: Main OD ⌀40 f7, Land OD ⌀38 h6, Groove 6 ±0.015, OAL 120 ±0.1
- GD&T: Circular runout ⌀0.005/A, Port position ⌀0.1/A/B
- Surface finish: Ra 0.4 µm (main OD), Ra 0.8 µm (land)
- Thread: G1/4 BSP (port)
- CUSTOMER_DATA_USED=NO — fully synthetic

## 5-Minute Demo Script
1. **Login** — enter credentials → Dashboard
2. **Manufacturing Plan page** → click "Load Demo Part (Hydraulic Spool)"
3. Show DRAFT status + characteristics count + REFERENCE_ONLY disclaimer
4. **Inspection Plan tab** — show method coverage (CMM, surface roughness tester, ring gauge)
5. **Control Plan tab** — show sampling frequency, reaction plan
6. **Review tab** → Review → Approve (gate enforcement demonstration)
7. **Export tab** → Download HTML → show traceability fingerprint

## 10-Minute Demo Script
1. Login → Dashboard (explain deterministic philosophy)
2. Resources: Machines → show INTEGREX i-200S detail
3. Engineering: Compatibility Check → select machine + holder + tool → COMPATIBLE
4. Planning: Drawing Parser → describe spool drawing → confirm detections
5. Process Routes → enter features → generate BALANCED strategy → compare routes
6. Click "Generate Manufacturing Plan →"
7. Manufacturing Plan (pipeline prefill) → all 8 tabs
8. Approve → Export HTML

## 20-Minute Technical Demo
1. Login + positioning statement
2. Machine + Tool + Holder catalog exploration
3. Compatibility and Configuration Selection
4. Technical Drawing Intelligence (PDF upload, Ollama optional)
5. Drawing Parser (DXF upload, confirm requirements)
6. CAD Features (STEP Level 1 / DXF, feature tree, fusion)
7. Route Optimization (BALANCED vs LOWEST_RISK strategy comparison)
8. Generate Manufacturing Plan (pipeline handoff)
9. All 8 Manufacturing Plan tabs
10. Process Capability (tolerance evaluation, IT grade)
11. GD&T Intelligence (FCF validation, bonus tolerance, VC)
12. Export HTML + JSON + NC Handoff package
13. Safety summary (FABRICATED_*=NO, AUTO_GENERATED_PLAN_MARKED_APPROVED=NO)

## Pipeline Navigation
Drawing Parser → CAD Features → Process Routes → Manufacturing Plan → Export

Handoff buttons appear automatically when a session/requirements are confirmed.
Pipeline context persists within the browser session (cleared on refresh).

## Sidebar Navigation
All pipeline pages are accessible from the sidebar under:
- CAD & Drawing: CAD Import, Technical Drawing Intelligence, CAD Features
- Planning & Quality: Drawing Parser, GD&T Intelligence, Route Optimization, Process Capability, Manufacturing Plan

## Demo Credentials
Ask your MachiningPro demo operator for the current credentials.
Never commit credentials to the repository.

## Review Gates (Required Human Actions)
- Drawing extraction detections: confirm/edit/reject each
- GD&T interpretation: PENDING_REVIEW (engineer must approve)
- Feature associations: confirm/reject
- Route selection: engineer selects preferred route
- Manufacturing plan approval: explicit /review then /approve (never auto-approved)

## Safety Boundaries
- AUTO_GENERATED_PLAN_MARKED_APPROVED=NO — always DRAFT on generation
- KEY_CHARACTERISTIC — engineer-only designation, never auto-assigned
- INSUFFICIENT_DATA returned for unknowns — never fabricated
- No production release authorization in this system
- All exports marked REFERENCE_ONLY

## Known Limitations
- In-memory storage only (restart clears all sessions)
- STEP Level 2 feature recognition requires pythonocc-core (see STEP_LEVEL2_DEPENDENCY.md)
- XLSX export deferred
- Playwright browser tests require: cd frontend/app && npx playwright install --with-deps chromium
- VLM/OCR analysis requires local Ollama with granite3.2-vision:2b
- PipelineContext is in-memory: browser refresh loses pipeline state
- No multi-user authentication on most endpoints

## Deployment
See DEPLOYMENT.md and render.yaml. Deploy to Render from `main` branch after merging work/next-stage.

## Version
0.5.0-demo — includes EPIC_04A through EPIC_05 capabilities.
