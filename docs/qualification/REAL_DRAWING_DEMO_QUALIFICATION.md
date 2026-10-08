# MachiningPro AI - Real Drawing Demo Qualification Specification

**Task:** REAL_DRAWING_QUALIFICATION_01, normalized by REAL_DRAWING_QUALIFICATION_01B
**Status:** DECISIONS FROZEN (01B). Execution is NOT yet permitted: the execution gates in
section 17 are not all satisfied.
**Baseline:** HEAD f19adce5347465065ce019cd30dabe58c6dbaa53
**Scope:** design and baseline only. No production code, no AI inference, no customer data.
**Initial demo platform scope:** DESKTOP_ONLY (primary viewport 1440x900); see section 11.
**Frozen decisions:** the numeric thresholds P1-P7 and the recall-gain gate in this document
are MachiningPro AI internal engineering/product qualification thresholds. They are not
industry standards and cite no external source. Changing any value requires a new recorded
decision; a normalization task must not change them.

---

## 1. Objective

Decide, with evidence, whether the current system is reliable enough for **controlled desktop
customer demonstrations**, and rank the next fixes by value.

The system under qualification is the committed flow:

```
PDF upload -> deterministic ingestion -> explicit "Analyze with Local AI" job
-> R3D bounded request -> OllamaVlmProvider (granite3.2-vision:2b, CPU, loopback)
-> R3B v2 validation -> advisory evidence (box_basis = REGION_EXTENT)
-> Human Confirmation UI (Accept / Edit / Reject)
```

Non-goals: production accuracy claims, industry-standard benchmarking, mobile or tablet
qualification, model comparison, any change to R3B acceptance rules or to deterministic
authority.

### 1.1 Fixed authority rules (not under test, only monitored)

- AI authority is ADVISORY; there is no auto-promotion.
- Spatial authority is the deterministic region extent chosen by the caller (R3D region).
  A region extent is "supported by this region", never "exactly here".
- Deterministic evidence is never overwritten by AI or by a human review.
- R3B v1 and v2 acceptance rules are unchanged by this campaign.

---

## 2. System facts the campaign must respect

Taken from the committed code at the baseline HEAD (re-verify before each campaign):

| Fact | Value | Source |
|---|---|---|
| Accepted upload | PDF, at most 16 MiB | `backend/api/drawing_analysis.py` |
| AI input | first image of the first page that has a raster image, analysed as ONE region | UI + API |
| AI on a vector-only PDF | not possible (no raster image): start returns `INVALID_REGION` | API |
| R3D crop limits | longest edge <= 2048 px, <= 4,194,304 px, PNG <= 4 MiB | `VlmLimits` |
| Response limits | <= 256 KiB, <= 200 items, value <= 256 chars | `VlmLimits`, R3B |
| Model profile | granite3.2-vision:2b, num_gpu=0, num_ctx=8192, temperature=0, stream=false | `vlm_ollama.py` |
| Job timing limits | request timeout 600 s, assist budget 900 s, single attempt (no retry) | API |
| AI task | TRANSCRIBE only (the GD&T task kind exists but is not selected by the API) | API |
| v2 evidence | candidate_type, value, legibility, confidence, evidence_reference (always null today) | R3B v2 |
| Evidence kinds | TEXT, TITLE_FIELD, DIMENSION, DATUM_LABEL, GDT_CHARACTERISTIC, NOTE | `DrawingVlmEvidenceKind` |
| Deterministic dimension grammar | one OCR/vector token: optional prefix (DIA, RAD, R, O-stroke or the diameter sign), a number, then a unit (mm, inch, in, deg, degree or the degree sign); tolerance forms +/-, +a/-b, +a/0 and +0/-b | `pdf_drawing.py` |
| Deterministic GD&T allowlist | FLATNESS, CIRCULARITY, POSITION, SYMMETRY | `DrawingGdtCharacteristic` |
| Deterministic outputs exposed by the API | dimensions only (id, type, text, source) | API summary |

Consequences used throughout this plan:

1. Qualification drawings **must be PDFs containing an embedded raster image** to exercise the
   AI path. A vector-only PDF is used only as a probe (section 4.3).
2. A deterministic miss on a synthetic fixture is not a deterministic defect until the fixture
   is shown to match the grammar above. The earlier synthetic drawing used "100 MM" as two
   words; whether OCR emitted one token or two is an **open question, RQ06, which stays OPEN**.
   Deterministic-dimension recall cannot be meaningfully scored until a valid fixture or real
   drawing exercises the parser's exact accepted dimension grammar (section 9, RQ06).
3. Title-block and GD&T deterministic results are not in the API summary. Their metrics are
   collected by a read-only harness that calls `PdfDrawingParser` directly (no code change).

---

## 3. Drawing selection, licensing and provenance rules

### 3.1 Allowed sources (in order of preference)

1. **Self-created** by the project team, with the author dedicating the drawing to the project
   (CC0 or equivalent written statement).
2. **Programmatically generated** synthetic drawings (such as the repository fixture builders),
   with the generator script version recorded.
3. **Public domain** drawings with a verifiable public-domain basis.
4. **Permissively licensed** drawings (for example CC0, CC-BY) where the licence allows
   redistribution and modification, with attribution recorded.

### 3.2 Forbidden

- Any customer, OEM or Tier-1 drawing, or any drawing under NDA.
- Standards-body sheets and vendor catalogue pages, unless a written reuse permission exists.
- Anything scraped without a stated licence.
- Any drawing containing real personal data. Names, dates and company names in title blocks
  must be fictional and marked as such.
- Any drawing whose licence cannot be recorded in full.

### 3.3 Provenance record (mandatory, one per drawing, before the first analysis)

```
QUAL_ID, title, author_or_origin, source_url_or_"self-created",
license_spdx_or_statement, attribution_text, date_acquired,
file_name, sha256, size_bytes, page_count, image_px_wxh,
modifications_made, personal_data_check (NONE), confidential_check (NONE),
drawing_author {identifier, date},
ground_truth_reviewer {identifier, date},
provenance_approver {identifier, date},
role_overlap_note (free text; "none" if three different people)
```

A drawing without an approved record is not run. Provenance records are stored beside the
ground truth: `docs/qualification/ground_truth/<QUAL_ID>.provenance.json` (section 16).

### 3.4 Roles and governance (frozen for the initial internal controlled-demo qualification)

Every qualification drawing needs all of the following, each recorded in its own field:

| Role | Responsibility |
|---|---|
| DRAWING_AUTHOR | creates the drawing from a written spec, or names the origin and licence of an existing one |
| GROUND_TRUTH_REVIEWER | checks the frozen ground truth against the drawing before any AI run |
| PROVENANCE_APPROVER | confirms licence or permission, and that no confidential, proprietary or personal data is present |

- **ROLE_SEPARATION_REQUIRED = NO** for this initial internal controlled-demo qualification.
  One person MAY hold more than one role, but the three roles must still be recorded
  separately in the qualification record, even when the same identifier appears in all of them.
- No customer-confidential or proprietary drawing is allowed under any role arrangement.
- This relaxation applies only to the initial internal demo qualification. Any later external
  or production qualification must revisit it.

---

## 4. Qualification matrix

Initial set: **minimum 5, maximum 10 drawings**. The five CORE drawings (Q01, Q02, Q05, Q06, Q07)
are mandatory. Q09 and Q10 are EXT-GATE drawings: they feed the P4, P5 and G2 decisions and
therefore follow the same 3-run baseline as CORE (section 7.1). Q03, Q04 and Q08 are EXT
drawings with one run each.

### 4.1 Drawings

Target counts below are authoring targets; the frozen ground truth (section 5) is the truth.

| QUAL_ID | Set | SOURCE_TYPE | LICENSE_OR_PERMISSION | IMAGE_SIZE (px) | PAGE_COUNT | EXPECTED_DIMENSIONS | EXPECTED_TEXT | EXPECTED_GDT | EXPECTED_TITLE_BLOCK_FIELDS | DIFFICULTY | PURPOSE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Q01 | CORE | self-created / generated | project CC0 statement | 480x320 | 1 | 3 linear (100, 60, 20 mm style) | 3 labels | none | none | EASY | Control; repeats the smoke fixture; run-to-run stability (RQ01) |
| Q02 | CORE | self-created | project CC0 statement | about 800x600 | 1 | 2 diameter callouts, 1 linear | hole notes | none | none | EASY | Diameter / hole callouts |
| Q03 | EXT | self-created | project CC0 statement | about 800x600 | 1 | 3 radius (R) | none | none | none | MEDIUM | Radius notation |
| Q04 | EXT | self-created | project CC0 statement | about 800x600 | 1 | 2 angular (degrees) + 2 linear | none | none | none | MEDIUM | Angular notation and chamfers |
| Q05 | CORE | self-created | project CC0 statement | about 1200x900 | 1 | 8 mixed in one view | few labels | none | none | MEDIUM | Several dimensions in one region (RQ02) |
| Q06 | CORE | self-created | project CC0 statement | about 1200x900 | 1 | 2 linear | notes + fictional title block | none | part name, drawing number, material, scale, sheet, revision, date, units | MEDIUM | Title-block text and notes |
| Q07 | CORE | self-created | project CC0 statement | about 1200x900 | 1 | 6 with tolerances (+/-, +a/-b, unilateral) | none | none | none | HARD | Tolerance notation |
| Q08 | EXT | self-created | project CC0 statement | about 1200x900 | 1 | 2 linear | datum labels | 4 frames (flatness, position, circularity, symmetry) + 1 non-allowlisted frame as a negative | none | HARD | GD&T supported vs unsupported; no false claim |
| Q09 | EXT-GATE | self-created | project CC0 statement | about 1800x1300 | 1 | 25 or more mixed, inch and mm views | notes | none | fictional title block | HARD | Dense drawing (RQ03) |
| Q10 | EXT-GATE | self-created | project CC0 statement | 2000x1400 (2.8 MP, inside both R3D limits) | 1 | 12 mixed | notes | none | none | HARD | High resolution near the supported limit; latency (RQ05) |

### 4.2 Authoring rules

- Each drawing is authored from a written spec, rendered, then packaged as a **PDF with one
  embedded raster image** (the page contains the image; text is not also present as vector text,
  so the AI path and the OCR path are both exercised and not shortcut).
- Dimension text on the image is chosen to match the deterministic grammar (section 2) in at
  least one CORE drawing (for example the diameter-callout drawing Q02, written as single tokens
  such as the diameter prefix, a number and a unit), so deterministic recall can become
  measurable (see RQ06). Where a drawing intentionally uses another style, record that in the
  ground truth. Until such a drawing exists, RQ06 stays OPEN and DET_DIMENSION_* metrics are
  reported as NOT SCORABLE, never as zero.
- Fonts: at least 12 px cap height after rasterisation for the CORE set. Smaller text appears
  only in Q09/Q10 and is flagged as such.
- Mixed-case: at least one drawing uses lower-case units ("mm") and one uses upper-case ("MM").

### 4.3 Probes (derived runs, not extra drawings)

These reuse an existing drawing's provenance and do not count toward the 5-10 limit:

| PROBE_ID | Derived from | Purpose | Expected behaviour |
|---|---|---|---|
| P-VEC | Q01 re-exported as a vector PDF (no embedded image) | AI path with no raster | Job refused with `INVALID_REGION`; deterministic result still shown |
| P-OVER | Q10 up-scaled to more than 2048 px or more than 4.19 MP | Over-limit whole-image behaviour | Job `FAILED` with `INVALID_REGION` before any model inference; deterministic result still shown (RQ07) |
| P-CROP | A drawing triggering the G2 precondition (section 10) split into 4 external crops, each saved as its own PDF; Q09 is the planned first candidate | Estimate the benefit of region selection without building the UI | Compare pooled recall of the crops against the pooled whole-image recall, using the same number of runs on each side (section 10) |
| P-DOWN | Any drawing with Ollama stopped | Failure UX | `OLLAMA_UNAVAILABLE`, deterministic panel intact, no retry |

---

## 5. Ground truth

### 5.1 Rule

Ground truth is authored by a person **before any AI run**, from the drawing specification
that produced the picture, never from Granite output, and then frozen (SHA-256 recorded).
Later corrections are errata entries with a reason and date; the original stays in the file.

### 5.2 Format (one JSON file per drawing, stored with the provenance record)

```json
{
  "qual_id": "Q01",
  "drawing_sha256": "<hex>",
  "authored_by": "<person>",
  "authored_at": "<ISO-8601>",
  "frozen_sha256": "<hex of this file at freeze>",
  "items": [
    {
      "item_id": "Q01-001",
      "expected_value": "100 MM",
      "expected_type": "DIMENSION",
      "expected_unit": "mm",
      "nominal": "100",
      "tolerance": null,
      "expected_region": {"page": 1, "px": [150, 20, 270, 45], "note": "top horizontal dimension"},
      "required_for_demo": "YES"
    }
  ],
  "errata": []
}
```

Field rules:

- `expected_value`: the text exactly as printed, including case and spacing.
- `expected_type`: one of DIMENSION, TEXT, TITLE_FIELD, DATUM_LABEL, GDT_CHARACTERISTIC, NOTE.
- `expected_unit`: mm, inch, deg or null.
- `expected_region`: a human-readable pixel box used only by the reviewer to judge whether an
  item lies inside an analysed region. It is **never** compared with any AI geometry (the AI
  provides none).
- `required_for_demo`: YES for items a demo narrative depends on (the principal dimensions and
  the labels a presenter would point at); NO otherwise. At least one third of items per CORE
  drawing are YES.

---

## 6. Metrics

All metrics are computed per drawing, per run, and aggregated. The three families are kept
separate and never blended into one score.

### 6.1 Matching rules (AI value versus ground truth)

An AI finding matches a ground-truth item at one of these levels, checked in order:

1. **EXACT** - identical after Unicode NFC and trimming (the same normalisation R3C uses).
2. **NORMALISED** - equal after case folding and collapsing whitespace.
3. **SEMANTIC** - the same quantity in another notation (for example `100mm` versus `100 MM`);
   decided by the reviewer by reading, not by a similarity score.
4. **NO MATCH** - anything else. A near miss that changes a digit is a WRONG_VALUE, never a match.

Reported matching levels: strict = EXACT only; working = EXACT + NORMALISED + SEMANTIC.
Each ground-truth item can be matched at most once; each AI finding at most once.
`candidate_type` produced by the model is advisory and is evaluated only in TYPE_ACCURACY.

### 6.2 AI_ADVISORY_METRICS

| Metric | Definition |
|---|---|
| TEXT_RECALL | matched expected items (all types) / expected items |
| TEXT_PRECISION | matched AI findings / AI findings |
| DIMENSION_RECALL | matched expected DIMENSION items / expected DIMENSION items |
| DIMENSION_PRECISION | AI findings matched to a DIMENSION item / AI findings that look like a dimension (by value pattern, not by model type) |
| TYPE_ACCURACY | matched findings whose candidate_type equals expected_type / matched findings |
| FALSE_POSITIVE_COUNT | AI findings matching no ground-truth item (includes hallucinated and wrong values) |
| WRONG_VALUE_COUNT | AI findings that clearly refer to an expected item but differ in content |
| MISSED_CRITICAL_DIMENSION_COUNT | expected items with required_for_demo = YES and no match |
| R3B_REJECTION_COUNT | jobs ending `R3B_VALIDATION_FAILURE`, with the diagnostic code breakdown |
| NO_FINDINGS_COUNT | jobs COMPLETED with zero findings |
| ITEM_STABILITY | across repeated runs of one drawing: items found in every run / items found in any run |

### 6.3 DETERMINISTIC_RESULT_METRICS

Collected from the upload summary (dimensions) and from a read-only `PdfDrawingParser` harness
(title fields, GD&T frames):

| Metric | Definition |
|---|---|
| DET_DIMENSION_RECALL / DET_DIMENSION_PRECISION | as above, over the deterministic dimension list |
| DET_TITLE_FIELD_RECALL | expected title-block fields recovered / expected fields |
| DET_GDT_RECALL / DET_GDT_FALSE_FRAME_COUNT | allowlisted frames recovered; frames reported that are not in the truth |
| DET_STATUS_DISTRIBUTION | counts of VALID, PARTIAL, INSUFFICIENT_DATA, UNSUPPORTED, FAILED |
| DET_AI_COMPLEMENT | expected items found by AI but not by the deterministic path, and the reverse |

### 6.4 HUMAN_REVIEW_METRICS

Reviewers act as an engineer would, **without** seeing the ground truth; the comparison is made
afterwards.

| Metric | Definition |
|---|---|
| HUMAN_ACCEPT_COUNT / HUMAN_EDIT_COUNT / HUMAN_REJECT_COUNT | final decision per finding |
| HUMAN_CORRECTION_RATE | (edited + rejected) / reviewed findings |
| HUMAN_EDIT_RATE | edited / reviewed findings (RQ04) |
| ACCEPTED_WRONG_COUNT | findings accepted although they do not match ground truth (reviewer miss) |
| REJECTED_CORRECT_COUNT | findings rejected although they match ground truth |
| REVIEW_SECONDS_PER_FINDING | wall time from card shown to decision |

### 6.5 PERFORMANCE_METRICS

| Metric | Definition |
|---|---|
| INFERENCE_TIME_SECONDS | job `started_at` to `completed_at` from the API |
| MEDIAN / P90 / WORST inference time | per drawing and overall (RQ05) |
| JOB_FAILURE_RATE | FAILED jobs / jobs, excluding intentional probes |
| UPLOAD_SECONDS | upload request duration (includes deterministic ingestion) |
| STATE_OBSERVED | the job states the UI actually showed |

---

## 7. Execution procedure

Execution may start only when every gate in section 17 is satisfied.

1. **Freeze the build.** Record HEAD, clean worktree, and hardware (CPU model, RAM, OS).
2. **Pre-flight.** Ollama reachable; model `granite3.2-vision:2b` listed; backend started with
   the dev-login variables and `MACHININGPRO_AI_PROVIDER=ollama`.
3. **Capture the OCR environment (execution prerequisite, every run).** The deterministic OCR
   backend and its environment affect deterministic results and must be recorded for every
   run: OCR engine name and version, whether the executable is resolved from the backend
   process PATH or from a default install location, language data present, and the resulting
   availability (OCR_AVAILABLE or OCR_UNAVAILABLE). No OCR software is installed or changed by
   the campaign; the environment is recorded as found. The sanitized record goes in the run log
   (no absolute paths).
4. **Approve inputs.** Every drawing has an approved provenance record and a frozen ground truth.
5. **Per drawing, per run** (run counts in section 7.1):
   1. Start the UI, log in, open Technical Drawing Intelligence.
   2. Upload the PDF through the UI; save the upload summary JSON.
   3. Click "Analyze with Local AI" once. Record observed states and the job id.
   4. Do not click again and do not restart; **no automatic retry**. A failed job is recorded
      as failed; a deliberate re-run is a new numbered run with a stated reason.
   5. When COMPLETED, save the job JSON from the API (findings, reviews, timings).
   6. Review every finding with Accept / Edit / Reject as an engineer would; save the final
      review records.
6. **Probes** (section 4.3) as planned in section 7.1.
7. **Score** with the scoring script (a required execution gate; interface: ground-truth JSON +
   job JSON + review JSON in, metric tables out).
8. **Store** results per section 16: large runtime artifacts outside Git in a local working
   directory (not written into committed files), compact sanitized logs and scored summaries
   under `docs/qualification/`.
9. **Stop servers**, delete temporary files, confirm the repository contains only the intended
   qualification files.

### 7.1 Run plan and volume

| Group | Drawings | Runs per drawing | Inferences |
|---|---|---|---|
| CORE | Q01, Q02, Q05, Q06, Q07 | CORE_RUNS_PER_DRAWING = 3 | 15 |
| EXT-GATE | Q09, Q10 | 3 (same CORE baseline) | 6 |
| EXT | Q03, Q04, Q08 | 1 | 3 |
| **Formal baseline total** | | | **24** |

Conditional additions, accounted for separately:

| Addition | Rule | Inferences |
|---|---|---|
| ESCALATION | A CORE or EXT-GATE drawing with **unstable or borderline** results is raised from 3 to ESCALATION_RUNS_PER_DRAWING = 5 runs (+2). "Unstable": a required_for_demo item found in some but not all of the 3 runs. "Borderline": a threshold decision (P1-P7, G2) that would flip if one finding or one run were counted differently. | at most +2 for each of the 7 drawings = +14 |
| P-CROP | Per drawing that triggers the G2 precondition (section 10): 4 crops x 3 runs each | 12 per triggered drawing; at most 3 drawings (Q05, Q09, Q10) = 36 |
| P-VEC, P-OVER, P-DOWN | no model inference (refused or failed before the model, or the model is stopped) | 0 |

Planning range: 24 (baseline only) to 74 (baseline + all escalations + P-CROP on three drawings).

How the totals are used:

- P-CROP, P-VEC, P-OVER and P-DOWN runs are probes: they are excluded from P4, P5 and every
  formal pooled metric, but they are counted in the planning volume above.
- Escalation runs are non-probe runs. They are reported with their drawing and are included in
  P4 and P5. P1 is always evaluated on the first three runs of a drawing; escalation runs are
  supplementary diagnostics for the owner's classification and do not change how P1 is counted.
- Time: no campaign timing has been measured. As arithmetic only, four earlier single-run
  observations took 146 to 177 s each. At that range the 24-run baseline is about 58 to 71
  minutes and the 74-run maximum about 3.0 to 3.6 hours of model time. Drawings with larger
  images (Q09, Q10) may take longer; the campaign measures the real values (RQ05).

---

## 8. Demo acceptance thresholds (FROZEN)

These are MachiningPro AI internal engineering/product qualification thresholds, approved in
REAL_DRAWING_QUALIFICATION_01B. They are not industry standards and no external source is
cited for any value. Each threshold is labelled P1..P7 so results can be recorded against it.
The numeric values below must not be changed without a new recorded decision.

### 8.1 BLOCKER (any one makes the build NOT demo ready)

| ID | Condition |
|---|---|
| B1 | An application, upload or job failure on a drawing inside the supported class (PDF with a raster image inside R3D limits) that is not an intentional probe |
| B2 | Invalid or unvalidated evidence shown as validated (anything not produced by R3B v2 reaching a review card) |
| B3 | Deterministic evidence overwritten or altered by AI output or by a review action |
| B4 | A model-supplied pixel box (or any AI geometry) becomes authoritative, or the UI describes the region extent as an exact detection box |
| B5 | Confidential or external data leakage: any network call outside loopback during a run, any use of a cloud or paid service, a local path or Ollama detail shown in the UI |
| B6 | Any automatic acceptance or automatic retry |

### 8.2 MAJOR (any one blocks an unscripted demo; may be mitigated by a scripted demo)

| ID | Condition (frozen) |
|---|---|
| P1 / M1 | Required-for-demo item missed in at least 2 of 3 runs on at least 2 different CORE drawings |
| P2 / M2 | Overall DIMENSION_RECALL (working match, CORE drawings) below 0.70 |
| P3 / M3 | Overall TEXT_PRECISION below 0.75, or any systematic wrong value (same wrong value in 2 or more runs) |
| P4 / M4 | R3B rejections or failed jobs above 20 percent of non-probe jobs |
| P5 / M5 | Median inference time above 240 s, or any run above 480 s |
| P6 / M6 | HUMAN_CORRECTION_RATE above 40 percent on CORE drawings |
| P7 / M7 | Any ACCEPTED_WRONG_COUNT greater than zero caused by a misleading presentation rather than by the reviewer |

### 8.2.1 Scope of each MAJOR threshold (normalization of the evaluated set)

| ID | Evaluated over | Notes |
|---|---|---|
| P1 | CORE drawings, first 3 runs of each | Escalation runs are supplementary (section 7.1) |
| P2 | Pooled CORE runs: matched expected DIMENSION items / expected DIMENSION items summed over all CORE runs | Working match (section 6.1); Q09, Q10 are reported but do not enter P2 |
| P3 | Two parts. **(a) Overall TEXT_PRECISION below 0.75:** an aggregate qualification-performance measure, evaluated over the pooled CORE runs (matched AI findings / AI findings summed over all CORE runs). **(b) Systematic wrong value (same wrong value in 2 or more runs):** a per-drawing property, evaluated separately for each drawing that has at least 2 runs (CORE and EXT-GATE; not applicable to single-run EXT drawings) | The numeric values 0.75 and "2 or more runs" are unchanged |
| P4 | All non-probe jobs actually executed (CORE, EXT-GATE, EXT and escalation runs) | Probes excluded |
| P5 | All non-probe inference runs (baseline and escalation); the median is over runs, the 480 s limit applies to each run | P-CROP runs are excluded because crops are smaller and would lower the median |
| P6 | Pooled CORE reviewed findings | Q09, Q10 reported separately |
| P7 | Any run | Not a rate |

### 8.3 MINOR

- Isolated non-critical recognition miss (required_for_demo = NO).
- Wording, layout or translation issues on desktop.
- Presentation defects at tablet width (1024x768), and any mobile presentation defect:
  neither is a formal blocker of the initial controlled demo (section 11).
- Dev-only controls visible in a development build.

### 8.4 Overall classification

| Result | Meaning |
|---|---|
| DEMO_READY | No BLOCKER and no MAJOR |
| DEMO_READY_SCRIPTED | No BLOCKER; MAJOR items exist but each has a written demo-script mitigation (supported drawing class, pre-checked drawings, explicit "AI suggestions may miss items" statement) approved by the owner |
| NOT_READY | Any BLOCKER, or a MAJOR with no accepted mitigation |

---

## 9. Research questions and decision rules

| ID | Question | Evidence | Decision rule |
|---|---|---|---|
| RQ01 | Does the repeated "60 MM" miss reproduce on other drawings? | Q01 x3 runs, Q02 x3 runs, Q05 x3 runs: miss rate per item by position, size and notation | If misses cluster by (small text, right edge, vertical dimension), record the pattern as a MAJOR candidate and propose a prompt/crop experiment; if random run-to-run, report ITEM_STABILITY and use repeated analysis only as a later idea |
| RQ02 | How does Granite perform with several dimensions in one region? | Q05, Q07, Q09 recall versus item count | Plot recall against items per image; the knee informs RQ03 and RQ07 |
| RQ03 | At what complexity does whole-image analysis become unreliable? | Q01, Q05, Q09, Q10: recall and time versus pixels and item count | Record the largest (pixels, items) combination that still meets P2 |
| RQ04 | What share of findings need Human Edit? | HUMAN_EDIT_RATE per drawing | Above P6 means value normalisation or prompt work before the demo |
| RQ05 | Median and worst-case CPU inference time? | INFERENCE_TIME_SECONDS across all runs | Compare with P5; if exceeded consider smaller crops, not cloud |
| RQ06 **(OPEN)** | Does deterministic OCR contribute useful evidence on real drawings? | DET_* metrics and DET_AI_COMPLEMENT on every drawing, including at least one CORE drawing written in the exact grammar of section 2. **Deterministic-dimension recall cannot be meaningfully scored until a valid fixture or real drawing exercises the parser's exact accepted dimension grammar; until then DET_DIMENSION_* is NOT SCORABLE.** The OCR environment of every run is recorded (section 7, step 3) | If deterministic recall is near zero on grammar-conformant drawings, escalate as a deterministic-path defect; if only non-conformant fixtures fail, record a fixture note. No parser change is made by the qualification spec |
| RQ07 | When is explicit region/crop selection necessary? | P-OVER, P-CROP and the RQ03 knee | Apply the gate in section 10 |

---

## 10. Region-selection decision gate

The crop/region selector UI is **not** built before this gate is evaluated.

```
REGION_SELECTOR_REQUIRED_FOR_DEMO = YES
  if any of:
    G1  a drawing class the demo intends to show exceeds R3D limits
        (more than 2048 px on the long edge, or more than 4,194,304 px)
        and therefore fails with INVALID_REGION  (P-OVER or a real demo drawing);
    G2  for any drawing d in {Q05, Q09, Q10}:
          whole-image recall(d) is below P2 (0.70), AND
          crop recall(d) - whole-image recall(d) >= 0.15 absolute
        (RECALL_GAIN_GATE, approved);
    G3  whole-image median inference time exceeds P5 AND crops of the same drawing
        are materially faster in total;
otherwise
  REGION_SELECTOR_REQUIRED_FOR_DEMO = NO   (defer; document the supported drawing class)
```

G2 sample definition (matches the approved 3-run baseline):

- **whole-image recall(d)** = matched expected DIMENSION items summed over all executed
  whole-image runs of d (the 3 baseline runs, plus escalation runs if they were executed),
  divided by the expected DIMENSION items summed over the same runs.
- **crop recall(d)** = the same quantity over the P-CROP runs of d: 4 external crops, 3 runs
  each, with each expected item counted once per run in the crop that contains it. The number
  of runs on each side is therefore the same, and no single-run denominator is used.
- The P-CROP experiment is run for a drawing only when its whole-image recall is already below
  P2, so G2 never requires crop runs for a drawing that passes.
- Q05 is a CORE drawing and Q09, Q10 are EXT-GATE drawings, so all three have the 3-run
  baseline needed for this definition.

The P-CROP experiment is done outside the application by cropping and re-uploading, so no
code is needed to decide.

---

## 11. Demo platform scope and known UX item

### 11.1 Platform scope (frozen)

- **CONTROLLED_DEMO_PLATFORM_SCOPE = DESKTOP_ONLY.**
- **Primary validation viewport: 1440x900.** All demo-readiness judgements are made there.
- **1024x768** may remain supported and observed, but is not a formal blocker of the initial
  controlled customer demo.
- **390x844 (mobile) is explicitly OUT OF SCOPE** for the initial controlled demo.
- Including tablet or mobile in a demo requires a new written decision and its own
  qualification.

### 11.2 MOBILE-01 (known, non-blocking UX issue)

- **Observation:** at 390 px, after the sidebar preference was saved as expanded on a desktop
  width and the viewport was then narrowed on the same page without reloading, the content
  column is about 182 px wide and some finding-card detail cells overflow their container. The
  page itself does not scroll horizontally. A fresh load at phone width starts with the sidebar
  collapsed and was clean in the earlier validation.
- **Class:** MINOR (non-blocking known UX issue) because mobile is out of scope.
- **MOBILE_OVERFLOW_DEMO_BLOCKER = NO.**
- Not fixed by the qualification work. Candidate fixes for later: re-evaluate the saved sidebar
  state at narrow widths; break long values in detail cells.

---

## 12. Defect classification

Every finding during a campaign is logged as:

```
DEFECT_ID, severity (BLOCKER|MAJOR|MINOR), component
(DETERMINISTIC|AI_PROMPT_SCHEMA|R3B|JOB_API|UI|PERFORMANCE|FIXTURE|DOCS),
QUAL_ID/run, observed, expected, reproducible (n of m runs), proposed owner
```

`FIXTURE` defects (the drawing does not match its own spec or the grammar) are separated from
product defects and corrected through errata, not by changing scoring.

---

## 13. Result tables (templates)

### 13.1 Per-run

| QUAL_ID | Run | Job id | States seen | Inference s | Status | Findings | TP | FP | Missed critical | R3B code | Accept | Edit | Reject |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | | | | |

### 13.2 Per-drawing aggregate

| QUAL_ID | Runs | TEXT_RECALL | TEXT_PRECISION | DIMENSION_RECALL | DIMENSION_PRECISION | ITEM_STABILITY | Median s | DET_DIMENSION_RECALL | HUMAN_CORRECTION_RATE |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |

### 13.3 Campaign summary

| Metric | Value | Threshold | Class |
|---|---|---|---|
| Overall DIMENSION_RECALL (CORE) | | P2 | |
| Overall TEXT_PRECISION | | P3 | |
| JOB_FAILURE_RATE | | P4 | |
| Median / worst inference s | | P5 | |
| HUMAN_CORRECTION_RATE | | P6 | |
| Blockers found | | none | |
| REGION_SELECTOR_REQUIRED_FOR_DEMO | | section 10 | |
| MOBILE_OVERFLOW_DEMO_BLOCKER | | section 11 | |
| Overall classification | | section 8.4 | |

---

## 14. Recommendation rules

| Outcome | Recommendation |
|---|---|
| BLOCKER found | Stop; fix before any demo; re-run the affected drawings |
| High miss rate on small or edge text (RQ01) | Prompt/schema experiment first, then region selection if G2 holds |
| Dense or large drawings fail (RQ03, G1) | Build the region selector; keep the supported-class statement in the demo script |
| Deterministic path recovers little on conformant drawings (RQ06) | Treat as a deterministic-parser/OCR defect; do not compensate with AI |
| Inference time over P5 | Reduce region size or content per call; evaluate local GPU only as a separate, qualified change; no cloud fallback |
| High human edit rate (RQ04) | Add value normalisation guidance in the review UI; do not auto-correct |
| All thresholds met | Mark DEMO_READY for the stated drawing class and record the class |
| Mixed | DEMO_READY_SCRIPTED with the mitigations written down |

Never recommended: weakening R3B, trusting a model box, auto-accepting findings, cloud or paid
inference, or using a customer drawing to "improve" the score.

---

## 15. Decision record (frozen in REAL_DRAWING_QUALIFICATION_01B)

| # | Decision | Frozen value |
|---|---|---|
| D1 | Thresholds | P1-P7 numeric values exactly as in section 8.2; RECALL_GAIN_GATE = at least 0.15 absolute recall gain; all are internal engineering/product qualification thresholds, not industry standards |
| D2 | Run count | CORE_RUNS_PER_DRAWING = 3; ESCALATION_RUNS_PER_DRAWING = 5 for unstable or borderline drawings; Q09 and Q10 follow the 3-run baseline |
| D3 | Provenance governance | Author/source, licence status, provenance record, ground-truth reviewer and provenance approval required for every drawing; ROLE_SEPARATION_REQUIRED = NO for the initial internal demo qualification, with the roles still recorded separately; no confidential or proprietary drawings |
| D4 | Platform scope | DESKTOP_ONLY; primary viewport 1440x900; 1024x768 observed only; 390x844 out of scope; MOBILE_OVERFLOW_DEMO_BLOCKER = NO |
| D5 | Result storage | Everything under `docs/qualification/` as in section 16; large runtime artifacts stay outside Git |

Open items that remain outside this specification: the people who hold the three roles are
recorded in each provenance record, not here.

---

## 16. File locations (normalized)

All qualification outputs live under one structure:

```
docs/qualification/
    REAL_DRAWING_DEMO_QUALIFICATION.md      this specification
    fixtures/                               small qualification assets
    ground_truth/                           frozen ground truth and provenance records
    results/                                compact scored result summaries
    run_logs/                               compact sanitized run logs
```

| Path | Content | Rules |
|---|---|---|
| `docs/qualification/fixtures/` | Only self-authored, public-domain, or explicitly redistributable **small** qualification assets, or generator scripts that reproduce them | Every committed fixture needs provenance metadata (section 3.3). The repository ignores `*.pdf`; committing a fixture PDF needs a deliberate, recorded exception. The preferred form is the generator script plus the recorded SHA-256 of the output. Customer or proprietary material is never placed here |
| `docs/qualification/ground_truth/` | `<QUAL_ID>.json` (section 5) and `<QUAL_ID>.provenance.json` | Manually authored and frozen before any AI run |
| `docs/qualification/results/` | `<campaign-id>-results.md` (and an optional CSV) holding the scored tables of section 13 | Compact, suitable for version control, produced from reviewed runs |
| `docs/qualification/run_logs/` | `<campaign-id>-run_log.csv`: one row per run | Compact and sanitized only: no binary payloads, no base64 images, no secrets, no local absolute paths, no customer data |

Run log columns: `run_id, qual_id, run_number, run_class (CORE|EXT-GATE|EXT|ESCALATION|PROBE),
head_sha, started_at, completed_at, status, job_id, inference_seconds, states_seen,
finding_count, ocr_engine, ocr_version, ocr_resolution (PATH|DEFAULT_LOCATION|NONE),
ocr_availability (OCR_AVAILABLE|OCR_UNAVAILABLE), note`.

**Large generated runtime artifacts remain outside Git.** Raw job and review JSON, screenshots,
uploaded PDFs and similar working files are kept in a local working directory outside the
repository for the campaign; that directory is recorded in the campaign record by an
identifier, never as an absolute path in a committed file.

Related architecture: `docs/TECHNICAL_DRAWING_INTELLIGENCE_FOUNDATION.md`.

---

## 17. Execution gates

Qualification execution cannot start until **all** of the following are satisfied.

| Gate | Meaning | Status at the 01B freeze |
|---|---|---|
| THRESHOLDS_FROZEN | Section 8 values and RECALL_GAIN_GATE approved and unchanged | YES |
| DRAWINGS_READY | Every drawing in the planned set authored and stored per section 16 | NO |
| PROVENANCE_RECORDS_READY | One approved provenance record per drawing, roles recorded | NO |
| GROUND_TRUTH_FROZEN | Ground truth authored by the author, reviewed, and hashed before any AI run | NO |
| SCORING_SCRIPT_READY | Scoring script exists and reproduces the section 6 definitions | NO |
| RESULT_STORAGE_READY | The section 16 directories exist and sanitization rules are in force | NO (structure defined, directories not yet created) |
| OCR_ENVIRONMENT_RECORDED | OCR environment capture (section 7, step 3) is in place for the run | NO (captured per run at execution time) |

The remaining NO entries are expected at this point and are not a failure of the freeze.
