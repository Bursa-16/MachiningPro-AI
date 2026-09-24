# Technical Drawing Intelligence Phase 1D Implementation Plan

Planning document. It governs implementation of
`docs/superpowers/specs/2026-09-24-technical-drawing-phase-1d-design.md` (approved decisions
D1–D3 and approved v1 operational defaults). It creates no production or test code by itself.

Baseline: `main` @ `191a325344d32fee527e4e56bf27e23c7102b580` plus the Task 0 Phase 1C hotfix
in the working tree (uncommitted, pending independent review).

## Scope gate

Implement only the advisory AI/VLM stage defined in the design. Preserve every Phase 1A–1C API,
status, provenance, security and determinism contract, including the post-Task-0 behavior.
AI/VLM never modifies `CanonicalDrawing` (D1). `parse()`, the `DrawingParser` ABC and
`pdf_drawing.__all__` stay unchanged (D2). No remote adapter; remote use disabled (D3).
No dependency change.

## Out of scope

DXF/DWG; CAM; feature recognition; machining strategy; feeds/speeds; CAD-face association or
modification; drawing redesign; surface finish and weld symbols; heat-treatment and coating
semantics; OEM/customer templates; database, route, frontend or UI; IGES; autonomous decisions;
acceptance/rejection disposition; process planning; tool selection; tolerance redesign;
vector-page rendering; standalone raster inputs; canonical promotion; vendor adapters; remote
enablement; audit persistence; the P1/P2 items in design §22 unless a task below names them.

## Recorded test baseline (container run, 2026-09-24)

Environment used for verification: Linux container, Python 3.11, pdfplumber 0.11.10,
Pillow 12.3.0 (pdfplumber 0.11.10 requires Pillow ≥ 12.2; see design §22), pytesseract 0.3.13,
Tesseract 5.3.4. The Windows workstation (Python 3.14, Tesseract 5.5.3) must repeat the gates.

- Before Task 0: `tests/unit/interoperability` → 895 passed, 42 failed.
- After Task 0 and its independent-review corrections: `tests/unit/interoperability` →
  950 passed, 42 failed (the same 42; no new failures). Drawing/PDF/OCR/GD&T suites:
  392 passed, 1 failed (the same pre-existing test).
- Pre-existing failures (unrelated, not to be fixed in Phase 1D): 41 in `test_population.py`
  (`ExchangeDocumentStatus.UNSUPPORTED` missing) and
  `test_pdf_drawing.py::TestGdtPositiveE2EAndErrorVisibility::test_ocr_gdt_e2e_produces_nonempty_gdt_references`
  (`DrawingRasterSource` built without `parser_identity`).

Every Phase 1D gate is "no new failures against this baseline".

## Task 0 — Phase 1C hotfix (COMPLETE in working tree; pending review and commit)

- Changed: `backend/interoperability/pdf_drawing.py`, `backend/interoperability/gdt_drawing.py`,
  `tests/unit/interoperability/test_pdf_drawing.py` (class `TestPhase1CTask0Hotfix`),
  `tests/unit/interoperability/test_gdt_drawing.py` (two tests).
- Delivered: `_DIAMETER_PREFIXES` for the vector and OCR paths; `PDF_DIMENSION_CONFLICT` warning
  with PARTIAL / INSUFFICIENT_DATA; GD&T diagnostics surfaced (all except
  `GDT_UNSUPPORTED_CHARACTERISTIC`) with PARTIAL; `GDT_CANDIDATE_LIMIT` → FAILED, no document;
  OCR bare numbers rejected; OCR identifier-line context rejection.
- Commit boundary: one independent commit, for example
  `fix(interoperability): report phase 1c conflicts and harden ocr dimensions`.
- Governing decision applied after independent review: `GDT_CANDIDATE_LIMIT` → FAILED.
  Known consequence: vector drawings above 5,000 non-space characters fail closed (design §22).
- Rollback: revert the single commit.
- **Every task below depends on Task 0 being reviewed and committed.**

## Task 1 — AI/VLM evidence contracts

- Objective: typed, immutable evidence, region, finding, report, config, audit-event and
  limits contracts.
- Files: new `backend/interoperability/vlm_drawing.py` (types only in this task).
- Tests: new `tests/unit/interoperability/test_vlm_drawing.py` (contract section).
- Depends on: Task 0; Task 2 for `VlmModelIdentity` (implement Task 2 first or commit together).
- Notes: reuse `DrawingSourceLocation`, `DrawingBoundingBox`, `DrawingParserIdentity`,
  `DrawingDimension`, `DrawingDatumReference`, `DrawingGdtCharacteristic`,
  `DrawingIngestionStatus`; enforce ADVISORY authority in `__post_init__`; sorted tuples only;
  no timestamps in deterministic types; bounded strings. `VlmLimits` carries the approved
  defaults exactly (design §16). `DrawingVlmAssistConfig(enabled=False, mode=BLIND,
  allow_remote=False, …)`.
- Non-goals: no behavior; no provider calls; no `drawing.py` change.
- Acceptance: invalid inputs raise; `asdict`/`repr` contain no bytes or paths; FAILED/UNSUPPORTED
  reports cannot carry evidence; the config fingerprint is stable across `PYTHONHASHSEED`
  values; defaults equal the approved table.
- Gates: `py -m pytest tests/unit/interoperability/test_vlm_drawing.py -q`; Ruff on new files.
- Rollback: delete the new module and tests. Independently committable: yes (with Task 2).

## Task 2 — Provider-neutral interface and fakes

- Objective: `VlmProvider` Protocol, request/response/identity/capabilities/errors/
  cancellation/retry policy; test fakes.
- Files: new `backend/interoperability/vlm_provider.py`; new
  `tests/unit/interoperability/vlm_fixtures.py`; new
  `tests/unit/interoperability/test_vlm_provider.py`.
- Depends on: Task 0.
- Notes: no vendor code or HTTP client; pinned-version validation (reject empty and alias
  versions); `VlmProviderError` carries a code only; injected sleeper and clock; retry defaults
  `max_attempts=2`, TRANSIENT and RATE_LIMITED only.
- Non-goals: no real adapter.
- Acceptance: fakes satisfy the Protocol; retries bounded; cancellation observable.
- Gates: `py -m pytest tests/unit/interoperability/test_vlm_provider.py -q`; Ruff.
- Rollback: delete. Independently committable: yes.

## Task 3 — Region planning and crop worker

- Objective: deterministic regions from evidence; spawned crop worker producing bounded
  grayscale PNG crops and pixel hashes.
- Files: `backend/interoperability/vlm_drawing.py`; tests in `test_vlm_drawing.py`.
- Depends on: Task 1.
- Notes: reuse `prepare_raster_ocr_inputs` inside the worker; crop↔PDF-point mapping identical
  to `ocr_drawing._map_box`; approved caps (10 pages, 16 regions per page, 64 total, 2,048 px
  edge, 4,194,304 px, 4 MiB, 8 px padding, 30 s worker timeout); module-level worker entry
  point (Windows spawn); terminate→kill cleanup as in `_stop_worker`; PNG without ancillary
  chunks; a rotated-fixture test documents the inherited 1C mapping limitation.
- Non-goals: no vector-page rendering; IMAGE_OVERVIEW disabled by default.
- Acceptance: identical regions and pixel hashes on repeat runs; caps truncate
  deterministically with a diagnostic; worker timeout fails closed; no decoding in the parent.
- Gates: `py -m pytest tests/unit/interoperability/test_vlm_drawing.py -q -k "region or crop"`.
- Rollback: revert the task commit. Independently committable: yes.

## Task 4 — Strict response validation

- Objective: parse and validate provider payloads exactly per the v1 contract.
- Files: `vlm_drawing.py` (schema constant `machiningpro.drawing-vlm.v1`, prompt text constant,
  validator); tests in `test_vlm_drawing.py`.
- Depends on: Tasks 1–2.
- Notes: size check (256 KiB) before decoding; strict UTF-8; `json.loads` with duplicate-key
  rejection, `parse_constant` rejection and `parse_float=Decimal`; exact key sets; enum checks;
  at most 200 items; crop-relative `[0, 1]` box validation; NFC and control-character checks;
  256-character raw candidate cap; request and model identity checks.
- Non-goals: no repair of malformed responses.
- Acceptance: every design §13 schema case yields its constant code; no exception text escapes.
- Gates: `-k "schema or validation"`; Ruff.
- Rollback: revert. Independently committable: yes.

## Task 5 — Normalization, provenance and confidence

- Objective: convert validated items into `DrawingVlmEvidence` using repository grammars.
- Files: `vlm_drawing.py` (`DrawingGrammarAdapter` Protocol, normalizer);
  `backend/interoperability/pdf_drawing.py` (`_PdfGrammarAdapter` delegating to existing
  private functions only, including `_DIAMETER_PREFIXES` and `_starts_with_identifier_label`);
  tests in `test_vlm_drawing.py` (stub adapter) and one adapter-conformance test in
  `test_pdf_drawing_vlm.py`.
- Depends on: Task 4.
- Notes: model values are never used; ADVISORY locations; confidence quantized to 1e-6;
  design §14 controls implemented as rejection rationales.
- Non-goals: no change to existing grammar functions or their behavior.
- Acceptance: all hallucination tests pass; importing `vlm_drawing` does not import
  `pdf_drawing`.
- Gates: `-k "normalize or hallucination"`; Ruff on changed files.
- Rollback: revert (the `pdf_drawing.py` diff is additive). Independently committable: yes.

## Task 6 — Deterministic reconciliation

- Objective: implement the design §12 matrix and findings.
- Files: `vlm_drawing.py`; tests in `test_vlm_drawing.py`.
- Depends on: Task 5.
- Notes: adjacency and containment reuse the existing rules via the adapter; digit-sequence
  decimal check; duplicate suppression; UNSTABLE on sample disagreement; GUIDED mode downgraded
  to ADVISORY_ONLY; deterministic omissions (including `PDF_DIMENSION_CONFLICT` cases) stay
  omitted.
- Non-goals: no canonical mutation, no promotion.
- Acceptance: all reconciliation tests pass; findings are independent of input order.
- Gates: `-k "reconcile"`.
- Rollback: revert. Independently committable: yes.

## Task 7 — PdfDrawingParser integration behind opt-in

- Objective: `parse_with_assistance`, evidence re-gathering, policy gate (REMOTE always
  rejected in Phase 1D), orchestration, audit sink, advisory report.
- Files: `backend/interoperability/pdf_drawing.py` (new method + helper; `parse()` and
  `__all__` untouched); `vlm_drawing.py` (orchestrator, policy gate, audit types); new
  `tests/unit/interoperability/test_pdf_drawing_vlm.py`.
- Depends on: Tasks 1–6.
- Notes: gate order per design §18; second OCR run with `OcrLimits(minimum_confidence=0.50)`;
  30 s request timeout; 120 s total budget; 64 requests maximum; cancellation checks between
  requests; `base_result_fingerprint`.
- Non-goals: no remote adapter; no route or UI.
- Acceptance: `result == parse(...)` for all fixtures and provider behaviors, including
  status, warnings and errors; disabled paths make zero calls.
- Gates: `py -m pytest tests/unit/interoperability/test_pdf_drawing_vlm.py -q`, plus the full
  drawing regression command below.
- Rollback: revert; `parse()` is never modified. Independently committable: yes.

## Task 8 — Hallucination, security and resource-limit suite

- Objective: complete the design §19 matrix; add the autouse network guard and the
  `PYTHONHASHSEED` subprocess determinism test.
- Files: `test_vlm_drawing.py`, `test_pdf_drawing_vlm.py`, `vlm_fixtures.py`.
- Depends on: Task 7.
- Acceptance: every named design §19 test exists and passes; no live API; no sockets.
- Rollback: tests only. Independently committable: yes.

## Task 9 — Phase 1A–1D regression and closeout

Commands (Windows, repository root):

```text
py -m pytest tests/unit/interoperability/test_drawing.py tests/unit/interoperability/test_pdf_drawing.py tests/unit/interoperability/test_ocr_drawing.py tests/unit/interoperability/test_gdt_drawing.py -q
py -m pytest tests/unit/interoperability/test_vlm_provider.py tests/unit/interoperability/test_vlm_drawing.py tests/unit/interoperability/test_pdf_drawing_vlm.py -q
py -m pytest tests/unit/interoperability -q
py -m ruff check backend/interoperability/pdf_drawing.py backend/interoperability/vlm_provider.py backend/interoperability/vlm_drawing.py tests/unit/interoperability/vlm_fixtures.py tests/unit/interoperability/test_vlm_provider.py tests/unit/interoperability/test_vlm_drawing.py tests/unit/interoperability/test_pdf_drawing_vlm.py
git diff --check -- backend/interoperability/pdf_drawing.py backend/interoperability/vlm_provider.py backend/interoperability/vlm_drawing.py tests/unit/interoperability/vlm_fixtures.py tests/unit/interoperability/test_vlm_provider.py tests/unit/interoperability/test_vlm_drawing.py tests/unit/interoperability/test_pdf_drawing_vlm.py docs/superpowers/specs/2026-09-24-technical-drawing-phase-1d-design.md docs/superpowers/plans/2026-09-24-technical-drawing-phase-1d.md
git grep -n -e "Ã" -e "â€" -- backend/interoperability tests/unit/interoperability
git diff --stat -- pyproject.toml backend/interoperability/drawing.py backend/interoperability/ocr_drawing.py backend/interoperability/raster_drawing.py backend/interoperability/gdt_drawing.py
```

Acceptance:
- The first three commands show no new failures against the recorded baseline.
- Ruff passes.
- The encoding grep is empty for new and changed files.
- The last command shows no Phase 1D changes.
- The closeout lists changed and untracked files and confirms that no frontend, database,
  IGES, DXF or vendor-adapter file was touched and no unrelated dirty file was modified.
- Commit: closeout note only.

## Dependencies

T0 (committed) → T2 → T1 → T3 → T4 → T5 → T6 → T7 → T8 → T9.

## Commit boundaries

One commit per task (T1 and T2 may be combined). Stage explicit paths only; never
`git add .`, `git add -A`, reset, restore, clean or stash. No task changes `pyproject.toml`.

## Rollback concerns

All Phase 1D changes are additive: two new modules, one additive method and adapter in
`pdf_drawing.py`, and new tests. Reverting T7 → T1 restores the post-Task-0 state exactly.
Task 0 is a separate behavioral change with its own commit and rollback.

## Plan-level acceptance

Design §23 criteria 1–10 are met, and every task's acceptance criteria and quality gates pass.
