# MachiningPro AI — Customer Demo Guide

**Release:** v0.1.0-alpha.10  
**Status:** Alpha Engineering Preview  
**Audience:** Customer-facing demonstration

---

## 1. Before the Demo

### Prerequisites

- Backend running: `py -m uvicorn backend.main:app --reload`
- Frontend running: `cd frontend/app && npm run dev`
- Browser at `http://localhost:5173`
- No external AI service required (Drawing Intelligence uses local Ollama if configured)

### Key Safety Flags (always in effect)

| Flag | Value |
|------|-------|
| `PRODUCTION_MODEL_APPROVED` | NO |
| `NC_FILE_EXECUTED` | NO |
| `HASH_EQUALS_DIGITAL_SIGNATURE` | NO |
| `FALSE_AI_CAPABILITY_CLAIM` | NO |

---

## 2. What to Show

### Fully Implemented (demo-ready)

| Module | Route | Notes |
|--------|-------|-------|
| Machine Catalog | `/app/resources/machines` | 15 machines, 4 manufacturers |
| Cutting Tool Catalog | `/app/resources/cutting-tools` | 18 tools, ISO material groups |
| Tool Holder Catalog | `/app/resources/tool-holders` | 17 holders, 5 interfaces |
| Cutting Parameters | `/app/engineering/cutting-parameters` | REFERENCE_ONLY evidence |
| Compatibility Check | `/app/engineering/compatibility` | 3-state engine: COMPATIBLE / INCOMPATIBLE / INSUFFICIENT_DATA |
| Configuration Selection | `/app/engineering/configuration-selection` | Deterministic RPM-margin selection |
| Process Planning / NC | `/app/planning-quality/process-planning` | Full NC engineering review, export, traceability |
| CAD Import | `/app/cad-drawing/cad-import` | DXF, STEP, IGES, STL, NC |
| Drawing Intelligence | `/app/cad-drawing/technical-drawing-intelligence` | Advisory AI (local Ollama only) |
| Tool Life Explorer | `/app/engineering/tool-life` | Empirical dataset (requires `MACHININGPRO_TOOLLIFE968_SOURCE_PATH`) |

### Engineering Preview (stub routes — backend capability only)

Machining Analysis, Surface Roughness, Turning, Milling, Drilling, Threading, Hole Finishing, Honing, Lapping, Materials, Libraries, DFM, Machine Capability, Validation

These routes show a clear "Engineering Preview" label. Do not present them as complete workflows.

---

## 3. Recommended Demo Workflow (Scenarios A–E)

### Step 01 — Catalog

1. Open **Machines** → select a machine (e.g. INTEGREX i-200S)
2. Note spindle RPM limit
3. Open **Cutting Tools** → select an end mill
4. Open **Tool Holders** → select a matching holder

**Key point:** All catalog data has provenance. Show the "Source" section on any detail card.

### Step 02 — Compatibility Check

1. Open **Compatibility Check**
2. Select the machine, holder, and tool from step 01
3. Choose an operation and ISO material group
4. Run evaluation → show COMPATIBLE result and rule trace

**Key point:** Every rule is deterministic and traceable. Show the rule ID and reason code.

### Step 03 — Configuration Selection

1. Open **Configuration Selection**
2. Enter operation, ISO group, cutting speed, diameter
3. Run → show ranked candidates with RPM margin criterion
4. Show rejected candidates and their disqualification reasons

**Key point:** No black-box ranking. Every criterion is shown explicitly.

### Step 04 — Process Planning with NC Review

1. Open **Process Planning**
2. Enter part name, material group, add 2–3 operations
3. Generate plan → show PLANNED steps with tooling and cutting parameters
4. Paste a sample NC program (G0/G1 linear, M3/M6):
   ```
   %
   O0001
   G21 G90 G94
   M6 T1
   M3 S3500
   G0 X0 Y0 Z5.
   G1 Z-2. F200.
   G1 X50. F300.
   G1 Y50.
   G1 X0.
   G1 Y0.
   G0 Z5.
   M5
   M30
   ```
5. Click **Analyze NC** → show engineering review (PASS_WITH_EVIDENCE or PASS_WITH_ADVISORIES)
6. Show traceability section: SHA-256 fingerprints, audit log

### Step 05 — Export & Traceability

1. Export findings as **CSV** → show formula-injection safety (tab-prefix on flagged cells)
2. Export **JSON** → show `schema_version`, safety flags
3. Open **Print** → show "NOT AN APPROVAL DOCUMENT" disclaimer
4. Show **NC Change Review**: load the prior JSON export as baseline, modify one S-word, re-analyze, compare

---

## 4. Tool Life Explorer (if dataset configured)

- Set `MACHININGPRO_TOOLLIFE968_SOURCE_PATH` to the dataset path
- Restart backend
- Open **Tool Life** → empirical exploration with lifecycle charts
- If dataset not configured: page shows "Dataset Not Configured" message (not a crash)

---

## 5. Drawing Intelligence (if Ollama configured)

- Requires local Ollama with a vision-capable model
- Upload a technical drawing (PDF, JPEG, PNG, DXF, STEP, NC, STL)
- All AI suggestions require human review before use
- Drawing Intelligence is advisory only — deterministic results take precedence

---

## 6. Language Switch (EN/TR)

- Use the language toggle in the top bar
- All customer-visible strings translate
- Verify: NC review labels, catalog headers, compatibility result text

---

## 7. Responsive Layout

- Test at 390px (mobile), 1024px (tablet), 1440px (desktop)
- Process Planning NC section stacks vertically on mobile
- No horizontal scroll at any tested width

---

## 8. What NOT to Claim

| Do Not Say | Reason |
|------------|--------|
| "The NC program was executed" | Text is parsed as data only |
| "This is production-approved" | Alpha preview only |
| "AI made the decision" | All decisions are deterministic; AI is advisory |
| "The hashes are digital signatures" | SHA-256 detects change; not a PKI signature |
| "The change review is an approval" | Explicitly labeled NOT AN APPROVAL DOCUMENT |
| "Feed rates are verified against the machine" | Machine feed_rate_max not in catalog (deferred) |

---

## 9. Known Demo Limitations

- G96 CSS RPM derivation: deferred
- R-format arcs (G2/G3 R…): not parsed (use IJK format)
- M98/M99 subprograms: UNSUPPORTED_SEMANTICS
- Macro variables (#): UNSUPPORTED_SEMANTICS
- Machine feed-rate limit check: deferred (no feed_rate_max in catalog)
- Cycle time = feed-distance only (no rapid, tool-change, or acceleration time)

---

*See [`docs/nc/NC_MODULE_RELEASE.md`](nc/NC_MODULE_RELEASE.md) for the full NC feature matrix and demo scenarios A–J.*
