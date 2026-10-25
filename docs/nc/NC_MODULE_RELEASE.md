# NC Program Analysis Module — Customer Demo Release

**Module:** NC_PROGRAM_ANALYSIS  
**Release maturity:** CUSTOMER_DEMO_READY  
**Schema version:** 1.0  
**Parser profile:** GENERIC_ISO_GCODE_SUBSET  
**Parser version:** 3.0.0  
**Application version:** 0.1.0-alpha.10

---

## 1. What This Module Does

The NC Program Analysis module parses NC / G-code program text as **data only** and produces deterministic engineering analysis results. It does **not** execute NC programs, simulate machine motion, or produce toolpaths.

Key outputs:
- Motion distance summary (feed and rapid, in mm)
- Feed/spindle validation against machine and tool catalog limits
- Engineering review with findings (BLOCKING / WARNING / ADVISORY / INFO)
- Traceability fingerprints (SHA-256 of program, configuration, analysis)
- Block-level change review between two NC program revisions
- Export: JSON, CSV (findings, segments, coverage, config), Print/PDF

---

## 2. Immutable Safety Flags

These flags are always constant. They are present in every API response and export for explicit audit.

| Flag | Value |
|------|-------|
| NC_FILE_EXECUTED | NO |
| NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING | NO |
| ARC_AS_CHORD_APPROXIMATION | NO |
| NC_FEED_AUTOMATICALLY_PROMOTED_TO_CUTTING_PATH | NO |
| NC_COMMANDED_SPINDLE_SPEED_EQUALS_ACTUAL_RPM | NO |
| NC_COMMANDED_FEED_EQUALS_ACTUAL_FEED | NO |
| MACHINE_FEED_LIMIT_VALIDATION_IMPLEMENTED | NO |
| FALSE_CHANGE_APPROVAL_CLAIM | NO |
| FALSE_SAFE_CHANGE_CLAIM | NO |
| FALSE_CONTROLLER_CERTIFICATION_CLAIM | NO |
| NC_CHANGE_REVIEW_IS_NOT_APPROVAL | YES |
| NC_CHANGE_REVIEW_IS_NOT_SAFETY_CERTIFICATION | YES |
| HASH_EQUALS_DIGITAL_SIGNATURE | NO |
| PARTIAL_TIME_MISLABELED_TOTAL | NO |
| COLLISION_CHECK_PERFORMED | NO |

---

## 3. NC Feature Support Matrix

### SUPPORTED (full deterministic output)

| Feature | G-codes / M-codes |
|---------|-------------------|
| Rapid motion | G0 |
| Linear feed motion | G1 |
| Arc motion (IJK format only) | G2, G3 |
| Plane selection | G17, G18, G19 |
| Unit selection | G20 (inch), G21 (mm) |
| Absolute / incremental positioning | G90, G91 |
| Feed-per-minute mode | G94 |
| Constant RPM mode | G97 |
| Spindle CW / CCW / stop | M3, M4, M5 |
| Tool change | M6 |
| Canned cycle cancel | G80 |
| Canned cycle return modes | G98 (to initial plane), G99 (to R plane) |

### BOUNDED (parsed and counted; specific semantics not fully expanded)

| Feature | G-codes | Limitation |
|---------|---------|-----------|
| Drill cycle | G81 | Point-to-point distance counted; retract rapid omitted |
| Countersink / spot face | G82 | Same as G81 |
| Peck drill | G83 | Peck sequence not expanded; total depth counted |
| Tapping | G84 | Path only; no thread-pitch kinematics |
| Boring | G85 | Point-to-point distance; fine-boring semantics not modeled |
| Cutter compensation | G41, G42 | Detected and flagged; offset path not computed |
| Back boring / fine boring | G86, G87, G88, G89 | Detected; not expanded |

Analysis status for bounded features: `PARTIAL` (not `COMPLETE`).

### DEFERRED — returns `BLOCKED_BY_KNOWN_LIMIT`

| Feature | Reason |
|---------|--------|
| G96 (CSS — constant surface speed) | Machine catalog has no feed_rate_max field; diameter required for RPM derivation |
| G93 (inverse-time feed mode) | Distance-per-block requires inverse-time integration; not yet implemented |
| R-format arcs (G2/G3 R…) | Only IJK center-vector arcs are parsed; R-format arcs are skipped |
| G91 in canned cycles | Incremental-mode cycle accumulation deferred |
| L-repeat (L word) | Repeat-count expansion deferred |
| Machine feed-rate limit check | No `feed_rate_max` in machine catalog — spindle RPM limit only |

### UNSUPPORTED — returns `UNSUPPORTED_SEMANTICS`

| Feature | Reason |
|---------|--------|
| M98 / M99 (subprogram calls) | Subprogram resolution requires file system context; not supported |
| `#` macro variables | Variable substitution not evaluated |
| `WHILE` / `IF` flow control | Conditional branching not evaluated |
| O-word labels (beyond program number) | Jump targets not resolved |

---

## 4. Engineering Review Status Values

| Status | Meaning |
|--------|---------|
| `PASS_WITH_EVIDENCE` | All checks passed with catalog evidence |
| `PASS_WITH_ADVISORIES` | Passed with non-blocking advisories |
| `REVIEW_REQUIRED` | One or more findings require engineering review |
| `BLOCKED_BY_KNOWN_LIMIT` | A deferred feature is present; results are incomplete |
| `INSUFFICIENT_DATA` | Required catalog context not supplied |
| `UNSUPPORTED_FEATURES_PRESENT` | Unsupported semantics detected |

---

## 5. Customer-Visible Limitations

These limitations are shown in the UI (NC Parser Scope & Limitations panel) and apply to all analyses:

1. **Not a controller simulation.** Results describe programmed intent as text; they do not simulate actual machine motion, acceleration, or controller behavior.
2. **RPM limit check requires catalog.** Machine, cutting tool, and tool holder must be selected to enable RPM validation. Machine feed-rate limit validation is deferred (no `feed_rate_max` in catalog).
3. **G96 CSS not supported.** Programs using constant surface speed require per-block diameter for RPM derivation — currently deferred.
4. **R-format arcs not parsed.** Only IJK center-vector arc format is recognized. R-format arcs (G2/G3 R…) are skipped.
5. **Subprograms not resolved.** M98/M99 subprogram calls are flagged as UNSUPPORTED_SEMANTICS; nested program content is not analyzed.
6. **Macro variables not evaluated.** Programs using `#` variables or WHILE/IF logic return UNSUPPORTED_SEMANTICS for those blocks.
7. **Cycle time is feed-distance only.** Cycle time = feed_distance_mm / commanded_feed_rate_mm_min. Rapid travel time, tool change time, and acceleration time are not included.
8. **Arc geometry is IJK only.** G2/G3 arcs must use center-offset (I, J, K) format.
9. **Traceability hashes are not digital signatures.** SHA-256 fingerprints detect accidental change; they are not cryptographically certified.
10. **Change review is not approval.** The NC change review report does not constitute engineering approval, safety certification, or controller verification.

---

## 6. Demo Scenarios (A–J)

### Scenario A — Supported Linear NC Program
**Goal:** Show baseline analysis for a complete supported program.  
**Program type:** G0/G1 linear motion, G20/G21, G90, M3/M6, no unsupported features.  
**Expected result:** `analysis_status=COMPLETE`, `review_status=PASS_WITH_EVIDENCE` or `PASS_WITH_ADVISORIES`.  
**Key outputs to show:** feed distance, rapid distance, supported motion count, engineering review summary.

### Scenario B — IJK Arc Program
**Goal:** Show arc motion parsing.  
**Program type:** G2/G3 with I/J/K center offsets, G17 plane selection.  
**Expected result:** `analysis_status=COMPLETE`, `arc_motion_count > 0`.  
**Key outputs to show:** arc motion count, feed distance includes arc contribution.

### Scenario C — Machine/Tool RPM Hard-Limit Case
**Goal:** Show RPM over-limit detection.  
**Setup:** Select a machine and cutting tool with known spindle limits. Write an NC program with S word exceeding limits.  
**Expected result:** Finding `RPM_LIMIT_MACHINE_RPM` or `RPM_LIMIT_TOOL_RPM` with `severity=BLOCKING`, `review_status=REVIEW_REQUIRED`.  
**Key outputs to show:** finding code, observed_value vs. limit_value, source.

### Scenario D — Advisory-Only Case
**Goal:** Show non-blocking engineering guidance.  
**Setup:** NC program with feed/spindle within limits but no material group supplied.  
**Expected result:** `review_status=PASS_WITH_ADVISORIES`, advisory findings only (INFO/WARNING severity).  
**Key outputs to show:** advisory findings, no BLOCKING items, engineering review status.

### Scenario E — Bounded G83 Canned-Cycle Case
**Goal:** Show bounded canned-cycle behavior.  
**Program type:** G81/G83 peck drill.  
**Expected result:** `analysis_status=PARTIAL`, `BOUNDED_CANNED_CYCLE` finding, drilling motion counted.  
**Key outputs to show:** PARTIAL status, finding explaining bounded behavior, motion count.

### Scenario F — Deferred/Unsupported Feature Case
**Goal:** Show transparent deferred and unsupported feature reporting.  
**Program type:** NC program with M98 subprogram call, or `#` macro variables.  
**Expected result:** `analysis_status=UNSUPPORTED_SEMANTICS`, finding flagging unsupported construct.  
**Key outputs to show:** analysis status, unsupported feature list, finding detail.

### Scenario G — Engineering Report Export
**Goal:** Show export workflow.  
**Steps:** Complete analysis → Export JSON, Export findings CSV, Export print PDF.  
**Key outputs to show:** exported file schema_version, safety flags in JSON, CSV formula-injection safety (tab-prefixed cells), print HTML with NOT AN APPROVAL DOCUMENT disclaimer.

### Scenario H — Traceability
**Goal:** Show SHA-256 fingerprint chain.  
**Steps:** Analyze NC program → open Traceability section.  
**Key outputs to show:** program_fingerprint, config_fingerprint, analysis_fingerprint, audit event log (analyze, export), HASH_EQUALS_DIGITAL_SIGNATURE=NO.

### Scenario I — NC Revision Change Comparison
**Goal:** Show block-level change review.  
**Steps:** Analyze two versions of the same NC program (modify one G-code value) → run Change Review.  
**Key outputs to show:** overall_change_status, change_severity, block-level diff (MODIFIED rows), segment delta, review_required flag, NC_CHANGE_REVIEW_IS_NOT_APPROVAL=YES.

### Scenario J — Mobile + EN/TR + Privacy
**Goal:** Show responsive layout and internationalization.  
**Steps:** Resize to 390px width → verify NC analysis section stacks vertically. Switch to TR locale → verify all NC labels translate. Verify no private file paths in any API response.  
**Key outputs to show:** stacked layout, Turkish UI labels, PRIVATE_PATH_IN_API_RESPONSE=NO.

---

## 7. Release Notes — NC Program Analysis Module

### v0.1.0-alpha.10 (2026-10-25)

**Initial customer demo release of the NC Program Analysis module.**

#### Added
- NC program text parser (GENERIC_ISO_GCODE_SUBSET, parser version 3.0.0)
- Feed and rapid motion distance extraction (PathEvidence)
- Feed/spindle validation against machine, tool, and holder catalog limits
- Engineering review synthesis (5 status levels, finding categories)
- IJK arc parsing (G2/G3) with analytic geometry
- Canned cycle support (G80–G85, G98/G99)
- Traceability: SHA-256 program, config, and analysis fingerprints + audit log
- Block-level NC change review (deterministic diff engine)
- Export: JSON, CSV (findings, segments, coverage, config, block changes), Print/PDF
- EN/TR internationalization (1107 keys, full parity)
- CSV formula-injection guard (OWASP tab-prefix mitigation)
- HTML injection protection in change review print output
- NC parser scope & limitations panel in UI
- Responsive layout (mobile 390px, tablet 1024px, desktop 1440px)

#### Known Deferred (BLOCKED_BY_KNOWN_LIMIT)
- G96 CSS RPM derivation
- G93 inverse-time feed mode
- R-format arcs (G2/G3 R…)
- G91 in canned cycles
- L-repeat expansion
- Machine feed-rate limit check (no `feed_rate_max` in catalog)

#### Not Supported (UNSUPPORTED_SEMANTICS)
- M98/M99 subprograms
- `#` macro variables
- WHILE/IF flow control

#### Security
- CSV formula injection: OWASP tab-prefix guard on all string cells
- HTML injection: `esc()` helper applied to all user-controlled fields in print output
- Path traversal: source_name validated to filename only, no absolute paths

---

## 8. Claim Safety Reference

The following claims are NEVER made by this module:

| False Claim | Status |
|-------------|--------|
| NC program was executed | NO |
| Feed move = confirmed cutting path | NO |
| Commanded RPM = actual spindle RPM | NO |
| Commanded feed = actual machine feed | NO |
| Analysis is a production approval | NO |
| Change review is an approval document | NO |
| Traceability hashes are digital signatures | NO |
| Collision or gouge verification was performed | NO |
| Controller compatibility was verified | NO |
| Machine feed limit was checked | NO (deferred) |
| Cycle time is total program time | NO (feed distance only) |

---

*This document reflects the state of the NC module as of commit c1da5c4 on branch work/next-stage.*
