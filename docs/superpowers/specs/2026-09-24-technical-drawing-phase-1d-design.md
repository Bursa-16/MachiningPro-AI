# Technical Drawing Intelligence Phase 1D Design — AI/VLM-Assisted Advisory Evidence

Status: APPROVED DESIGN (decisions D1–D3 and the v1 operational defaults approved
2026-09-24). Planning document only; it authorizes no Phase 1D production code by itself.
Implementation follows `docs/superpowers/plans/2026-09-24-technical-drawing-phase-1d.md`.

Date: 2026-09-24
Baseline: `main` @ `191a325344d32fee527e4e56bf27e23c7102b580` (Phase 1C committed:
"feat(interoperability): complete raster OCR and GD&T drawing intelligence") plus the
Task 0 Phase 1C hotfix in the working tree (§4.2), pending independent review and commit.

## 1. Context

Phases 1A–1C deliver a deterministic, fail-closed `PdfDrawingParser`: vector text, title
block, dimensions and tolerances (1B), embedded-raster OCR and a four-characteristic GD&T
grammar (1C). The Foundation roadmap assigns "VLM-based drawing interpretation" to Phase 1D
with the constraint "results always labelled ADVISORY; never override DECLARED or EXTRACTED".

Phase 1D adds an optional, provider-neutral AI/VLM stage that proposes evidence and
cross-checks OCR. Deterministic engineering logic remains the sole authority over canonical
output. In Phase 1D the AI/VLM stage never modifies `CanonicalDrawing` (D1).

## 2. Evidence reviewed

- Code: `backend/interoperability/drawing.py`, `pdf_drawing.py`, `raster_drawing.py`,
  `ocr_drawing.py`, `gdt_drawing.py`; drawing references checked in `enums.py`, `models.py`,
  `normalization.py`, `population.py`, `orchestrator.py`, `frontend/routers/ui.py`. There is
  no production caller of `PdfDrawingParser` (no route, orchestrator or UI).
- Tests: `tests/unit/interoperability/test_drawing.py`, `test_pdf_drawing.py`,
  `test_ocr_drawing.py`, `test_gdt_drawing.py`, `ocr_fixtures.py`, `pdf_fixtures.py`, and the
  full `tests/unit/interoperability` suite.
- Documents: `docs/TECHNICAL_DRAWING_INTELLIGENCE_FOUNDATION.md` (and the root copy), the
  1B and 1C specs and plans under `docs/superpowers/`, `docs/SYSTEM_ARCHITECTURE.md`,
  `docs/PRODUCT_CHARTER.md`, `docs/DATA_GOVERNANCE.md`,
  `docs/UNIVERSAL_ENGINEERING_INTEROPERABILITY.md`,
  `Programlar/MachiningPro_AI_Proje_Plani_16.9.2026.md`.
- Dependencies: `pyproject.toml` (runtime: fastapi, uvicorn, jinja2, python-multipart,
  `pdfplumber>=0.11.10,<0.12`, `Pillow>=10.4,<12`, `pytesseract>=0.3.13,<0.4`; no HTTP
  client, no AI SDK).

## 3. Governing baseline

### 3.1 Precedence

Approved phase-specific spec (1B, 1C, this document) > Foundation phase table >
architecture/roadmap documents > project plan. Code is the de facto contract where a spec is
silent or stale. Spec intent governs where code contradicts an explicit security or
fail-closed requirement.

### 3.2 Approved decisions

- **D1 — Advisory only; canonical invariance (APPROVED).** Phase 1D AI/VLM output is advisory
  only and never modifies `CanonicalDrawing`. For identical source input,
  `parse_with_assistance(...).result == parse(...)`, under every provider behavior,
  including status, warnings, errors and document.
- **D2 — Assisted entry point (APPROVED).** `PdfDrawingParser.parse_with_assistance(...)` is
  a new additive, opt-in method. `parse()`, the `DrawingParser` ABC and
  `pdf_drawing.__all__ == ["PdfDrawingLimits", "PdfDrawingParser"]` remain unchanged. This
  specification explicitly supersedes the Phase 1B §4.3 statement "There is no second
  convenience parsing function" for this one method only.
- **D3 — Remote processing (APPROVED).** Provider-neutral local/remote policy infrastructure
  may be built. No real remote-provider adapter ships in Phase 1D. Remote use remains
  disabled. No drawing or image data may be sent to a third party until
  `docs/DATA_GOVERNANCE.md` contains an approved third-party processing policy.
- **Operational defaults (APPROVED).** The §16 values are initial, configurable v1
  operational/resource defaults. They are not engineering truth thresholds.

### 3.3 Recorded document conflicts

| # | Files / sections | Conflict | Governs | Phase 1D consequence |
|---|---|---|---|---|
| C1 | Foundation §2 vs §6; 1B §2; 1C §2 | DXF annotation parser in 1B vs `DxfDrawingParser` in 1C vs deferred | 1C spec | DXF/DWG excluded |
| C2 | Foundation §6 vs original Phase 1D brief | "always ADVISORY" vs "populate canonical after validation" | Foundation | Resolved by D1 |
| C3 | Project plan Faz 1.1 vs Foundation/1C | VLM + OCR + Ra/Rz + heat treatment in one phase | Foundation + 1C | Surface finish, heat treatment, coating excluded |
| C4 | `drawing.py` header and `DrawingParser` docstring | Lists PyMuPDF and nonexistent parser classes | Code + 1B/1C | Single parser + one method; no parser-class family |
| C5 | 1B §6, 1C §3.1 vs `ocr_drawing.extract_ocr_from_pdf` | pdfplumber/Pillow decoding runs in the parent process | Spec | Phase 1D crops run in a spawned worker; existing gap is P1 |
| C6 | 1C §3.1 vs `raster_drawing` | Raster IDs are `page-N:image-M`, not the 1B scheme | Code (tests assert it) | Phase 1D uses the code format |
| C7 | 1C §3.4 vs `ocr_drawing` | Rotation normalization / downscaling not applied | Spec intent | Phase 1D inherits the OCR mapping; rotated fixtures required |
| C8 | 1C §5 vs `_merge_dimension_candidates`, `_apply_gdt` | Conflicts and GD&T diagnostics were lost silently | Spec | Fixed by Task 0 (§4.2) |
| C9 | 1C §3.3/§6 vs `_apply_gdt` | `GDT_CANDIDATE_LIMIT` ignored | Spec | Fixed by Task 0: FAILED, no document (§4.2) |
| C10 | 1B §4.3 | No second parsing function | This spec (D2) | Superseded for `parse_with_assistance` only |
| C11 | SYSTEM_ARCHITECTURE §7 vs 1B §11 | Timestamp on outputs vs no wall-clock time in results | 1B for results | Timestamps are audit-only |
| C12 | SYSTEM_ARCHITECTURE §8; UNIVERSAL… §3.6/§5.2 | "Stage 4 not begun", `backend/interop/cer/…`, MarkItDown | Code + phase specs | Ignore stale paths and tools |
| C13 | 1C spec and plan headers | "design-only" although committed | Commit history | Closeout note recommended |
| C14 | `docs/` vs root Foundation copy | `docs/` copy is double-encoded (mojibake) | Content equal | Encoding gate in Phase 1D quality gates |
| C15 | PRODUCT_CHARTER vs DATA_GOVERNANCE | Defense segment and on-prem option, but no third-party processing policy | Governance | Resolved by D3 |

## 4. Existing contracts

### 4.1 Contracts relied upon

- Model: frozen dataclasses, `Decimal`, `DrawingBoundingBox` (PDF points, top-left origin),
  `DrawingSourceLocation` (11 fields; exact `asdict` frozen by `test_drawing.py`),
  `DrawingParserIdentity`, `DrawingRasterSource`, `DrawingOcrTextEvidence`
  (WORD/LINE/BLOCK), `DrawingFeatureControlFrame` (FLATNESS/CIRCULARITY/POSITION/SYMMETRY,
  modifier NONE, datum `[A-Z]`), `DrawingIngestionResult` fail-closed invariants.
- Authority: `DrawingExtractionAuthority.ADVISORY` exists and is unused by production code.
- Statuses: `DrawingIngestionStatus` (VALID, PARTIAL, INSUFFICIENT_DATA, UNSUPPORTED,
  FAILED), reused by `OcrResult`, `GdtRecognitionResult` and `RasterInspectionResult`.
- Confidence: OCR normalized to `[0, 1]`, quantized to 1e-6; OCR canonical gate 0.80; GD&T
  frame gate 0.90; merges take the minimum; vector items carry `None`.
- IDs: vector `pdf-p{page:04d}-{kind}-{sha16}-{ordinal:04d}`; raster `page-{n}:image-{i}`;
  OCR `…:word-b-p-l-w`, `…:line-b-p-l`, `…:block-b`; frames `gdt-{sha24}`; drawing
  `pdf-drawing-{sha256(content)[:24]}`.
- Limits: `PdfDrawingLimits` (exact `asdict` frozen by `test_pdf_drawing.py`),
  `RasterLimits`, `OcrLimits`, GD&T constants; diagnostics 50 × 240 characters.
- Security: bytes-only input, spawned workers for the vector snapshot and OCR, constant
  diagnostic codes, no network code.
- API freeze: `pdf_drawing.__all__ == ["PdfDrawingLimits", "PdfDrawingParser"]`.

### 4.2 Post-Task-0 deterministic behavior (Phase 1C hotfix)

Task 0 changed only `backend/interoperability/pdf_drawing.py` and
`backend/interoperability/gdt_drawing.py` (plus focused tests). Phase 1D builds on this state:

1. **Diameter prefix.** The OCR path had a double-encoded prefix set, so OCR `Ø`/`⌀`
   dimensions were typed LINEAR. Both vector and OCR paths now use
   `_DIAMETER_PREFIXES = frozenset({"DIA", "Ø", "⌀"})`, written as escapes. A test
   guards the module source against double-encoded text.
2. **Vector/OCR dimension conflict.** Conflicting candidates are still both omitted
   (confidence never picks a winner), but `_merge_dimension_candidates` now reports the
   conflict. `parse()` emits the constant warning `PDF_DIMENSION_CONFLICT`: PARTIAL when other
   canonical content remains, INSUFFICIENT_DATA (no document) when nothing remains. No new
   status was introduced.
3. **GD&T diagnostics.** `_apply_gdt` returns the grammar's constant diagnostic codes, sorted.
   Every code except `GDT_UNSUPPORTED_CHARACTERISTIC` is surfaced as a warning and downgrades
   a document-bearing result to PARTIAL. `GDT_UNSUPPORTED_CHARACTERISTIC` marks ordinary text
   bands (not frame candidates). To make that distinction exact, `_build_frame` now classifies
   the characteristic before the group-size check, so `GDT_FRAME_GRAMMAR_REJECTED` always
   means a rejected characteristic-led candidate.
   `GDT_CANDIDATE_LIMIT` (the global GD&T token limit, 5,000) is a fail-closed resource-limit
   breach per 1C §3.3/§6 (governing decision, 2026-09-24): `parse()` returns FAILED with
   `errors == ("GDT_CANDIDATE_LIMIT",)` and no document.
   Measured consequence (independent review): vector GD&T tokens are one per non-space PDF
   character (`_vector_gdt_tokens` iterates `page.chars` runs), and every OCR WORD, LINE and
   BLOCK item is also a token. A vector drawing with more than 5,000 non-space characters
   therefore fails closed. See §22 (P1).
4. **OCR bare numbers.** A bare OCR number never becomes a dimension, because raster OCR has
   no vector dimension-line geometry cue; a fallback unit alone is not sufficient. OCR tokens
   whose own text, or whose containing OCR LINE, begins with one of the 27 approved
   title/identifier labels (drawing/part number, revision, date, scale, sheet, …) are rejected
   as dimensions. The vector path is unchanged.

Phase 1D reconciliation treats this post-Task-0 canonical output as the authority.

## 5. Goals

- G1 Optional AI/VLM stage, disabled by default, with zero provider calls when disabled.
- G2 Vendor-neutral provider contract; no vendor SDK or dependency.
- G3 Strictly typed, schema-validated AI evidence with complete provenance.
- G4 Deterministic reconciliation against vector/OCR/canonical evidence, producing explicit
  CORROBORATED / RECOVERY_CANDIDATE / CONFLICT / ADVISORY_ONLY / REJECTED / UNSTABLE findings.
- G5 Canonical invariance (D1): deterministic canonical output is unaffected by model variance.
- G6 Bounded, minimized, auditable request payloads; local-first; remote disabled (D3).
- G7 Full Phase 1A–1C regression, including the Task 0 behavior, is unchanged.

## 6. Non-goals

DXF/DWG annotation extraction; CAM generation; manufacturing feature recognition; machining
strategy; feeds/speeds; CAD-face association; automatic CAD modification; automatic drawing
redesign; surface-finish and weld symbols; heat-treatment and coating semantics;
customer/OEM templates; database, route, frontend or UI changes; IGES changes; autonomous
engineering decisions; acceptance/rejection disposition; process planning; tool selection;
tolerance redesign; vector-page rendering (pypdfium2, pulled in transitively by pdfplumber
0.11, must remain unused); standalone PNG/JPG/TIFF inputs; promotion of AI evidence into
canonical output; any real vendor adapter; enabling remote mode; audit persistence; new GD&T
characteristics or modifiers; dimension-to-feature association beyond the existing grammar's
nominal/tolerance pairing.

Ambiguous items: notes are transcribed only as ADVISORY_ONLY evidence (no deterministic note
extractor exists, so notes can never corroborate). "Symbol/text disambiguation" is limited to
the four GD&T characteristics and the diameter prefix.

## 7. Architecture

### 7.1 Pipeline

```
content bytes
 ├─► PdfDrawingParser.parse()  (Phase 1A–1C + Task 0, UNCHANGED) ──► base: DrawingIngestionResult
 └─► parse_with_assistance only; gate: config.enabled ∧ provider ∧ base.status eligible
      1 Evidence gathering (deterministic)
          vector snapshot via _run_spawned_worker → _vector_gdt_tokens
          OCR at review floor via extract_ocr_from_pdf(limits=OcrLimits(minimum_confidence=floor))
      2 Region planning (pure)            → DrawingVlmRegion[]
      3 Crop preparation (spawned worker) → bounded grayscale PNG crops + pixel SHA-256
      4 Policy gate                        → locality, allowlist, region-kind policy, byte caps, audit
      5 Provider call                      → timeout, cancellation, bounded retries
      6 Strict response validation         → schema, sizes, IDs, boxes, model identity
      7 Normalization + provenance         → existing 1B/1C grammars via adapter; ADVISORY locations
      8 Reconciliation                     → findings vs base.document + deterministic evidence
      9 DrawingAdvisoryReport
 ▼
DrawingAssistedIngestionResult(result=base, advisory=report | None)
```

### 7.2 Layer responsibilities

| Layer | Owns | Must not |
|---|---|---|
| Deterministic parser (1A–1C) | Canonical result | See AI output |
| Evidence gathering | Reproducing deterministic evidence, including sub-threshold OCR | Alter the base result |
| Region planning | Which raster regions may be sent; sorted and capped | Let the model choose regions |
| Crop worker | Decode, crop, re-encode inside a spawned process | Return anything except bounded crops |
| Policy gate | Local/remote rules, allowlist, payload minimization | Be bypassable by provider code |
| Provider adapter | Transport only | Parse, normalize or reconcile |
| Validation | Strict schema, bounds, identity | Repair malformed responses |
| Normalization | Recompute values with repository grammars | Trust model-normalized values |
| Reconciliation | Classify each proposal | Modify canonical output |
| Report | Typed, bounded, deterministic advisory output | Carry timestamps or raw payloads |

### 7.3 Dependency direction

`drawing.py` ← `vlm_provider.py` ← `vlm_drawing.py` ← `pdf_drawing.py`.
`vlm_drawing.py` never imports `pdf_drawing.py`. Grammar functions are injected through a
`DrawingGrammarAdapter` Protocol implemented in `pdf_drawing.py`. `vlm_drawing.py` may call
`raster_drawing.prepare_raster_ocr_inputs` inside its crop worker (precedent: `ocr_drawing.py`).

### 7.4 Module decisions

- `vlm_provider.py` (new): vendor-neutral contract, importable by future adapters without
  drawing internals.
- `vlm_drawing.py` (new): evidence contracts, config and limits, region planning, crop worker,
  validation, normalization, reconciliation, orchestration, report. Split out
  `vlm_reconciliation.py` only if the module exceeds about 1,500 lines.
- `pdf_drawing.py` (modified, additive only): `parse_with_assistance`, the grammar adapter and
  an evidence-gathering helper.
- `drawing.py` (unchanged): AI evidence is not canonical and does not belong in the canonical
  module; this also keeps the `asdict` freeze tests untouched.
- Rejected names: `ai_drawing.py` (too broad), `ai_provider.py` (collides with the planned
  `backend.ai` RAG layer), `ai_reconciliation.py` (reconciliation is drawing-specific).

## 8. Provider abstraction (`vlm_provider.py`)

```python
class VlmLocality(StrEnum): LOCAL = "LOCAL"; REMOTE = "REMOTE"
class VlmTaskKind(StrEnum): TRANSCRIBE = "TRANSCRIBE"; GDT_CHARACTERISTIC = "GDT_CHARACTERISTIC"
class VlmErrorCode(StrEnum):
    UNAVAILABLE; DISABLED; TIMEOUT; CANCELLED; RATE_LIMITED; TRANSIENT;
    REQUEST_REJECTED; UNSUPPORTED; RESPONSE_TOO_LARGE

@dataclass(frozen=True)
class VlmModelIdentity:
    provider_id: str            # stable; must be allowlisted in config
    model_id: str
    model_version: str          # pinned snapshot; aliases such as "latest" rejected
    locality: VlmLocality

@dataclass(frozen=True)
class VlmCapabilities:
    task_kinds: tuple[VlmTaskKind, ...]
    max_image_bytes: int
    max_image_pixels: int
    structured_output: bool

@dataclass(frozen=True)
class VlmSamplingHints:
    temperature: Decimal = Decimal("0")
    max_output_tokens: int = 2048          # approved v1 default
    seed: int | None = None                # hint only; never assumed honored

@dataclass(frozen=True)
class VlmRequest:
    request_id: str                         # deterministic, opaque (§17)
    prompt_contract_version: str            # "machiningpro.drawing-vlm.v1"
    task_kind: VlmTaskKind
    model: VlmModelIdentity                 # requested (pinned)
    image_png: bytes = field(repr=False)
    image_width_px: int
    image_height_px: int
    context_text: tuple[str, ...] = ()      # empty in BLIND mode
    sampling: VlmSamplingHints = VlmSamplingHints()
    max_response_bytes: int = 262_144       # approved v1 default

@dataclass(frozen=True)
class VlmResponse:
    request_id: str
    reported_model: VlmModelIdentity
    payload: bytes = field(repr=False)      # raw UTF-8 JSON; parsed only by the core
    provider_request_ref: str | None = None # audit-only; never part of report identity

class VlmCancellation:                      # wraps threading.Event
    def cancel(self) -> None: ...
    def is_cancelled(self) -> bool: ...

class VlmProviderError(Exception):
    code: VlmErrorCode                      # message text is never surfaced

class VlmProvider(Protocol):
    def identity(self) -> VlmModelIdentity: ...
    def capabilities(self) -> VlmCapabilities: ...
    def infer(self, request: VlmRequest, *, deadline_seconds: float,
              cancellation: VlmCancellation) -> VlmResponse: ...

@dataclass(frozen=True)
class VlmRetryPolicy:
    max_attempts: int = 2                   # approved v1 default (one retry)
    retry_on: tuple[VlmErrorCode, ...] = (VlmErrorCode.TRANSIENT, VlmErrorCode.RATE_LIMITED)
    backoff_seconds: tuple[Decimal, ...] = (Decimal("1"),)   # fixed, no jitter
```

Rules:

- The orchestrator enforces timeouts: it passes a deadline and discards late responses.
  Timeouts are not retried by default. In-process providers cannot be hard-killed (P1); an
  adapter wrapping a heavy or untrusted runtime should isolate itself in a subprocess.
- `reported_model != requested model` rejects the response (`VLM_MODEL_MISMATCH`).
- Provider exceptions other than `VlmProviderError` map to `VLM_PROVIDER_FAILURE`; their text
  is never retained.
- A request whose task kind, pixel count or byte size exceeds the provider's capabilities is
  not sent (`VLM_PROVIDER_UNSUPPORTED`).
- Sleeper and clock are injected; tests use no-op implementations.
- Providers are called from the parent process. They are not passed to spawned workers
  (Windows spawn pickling).

## 9. AI evidence model (`vlm_drawing.py`)

```python
class DrawingEvidenceOrigin(StrEnum): VECTOR; OCR; AI_VLM
class DrawingVlmMode(StrEnum): BLIND; GUIDED
class DrawingVlmRegionKind(StrEnum): OCR_REVIEW; TITLE_BLOCK; GDT_CANDIDATE; IMAGE_OVERVIEW
class DrawingVlmEvidenceKind(StrEnum): TEXT; TITLE_FIELD; DIMENSION; DATUM_LABEL; GDT_CHARACTERISTIC; NOTE
class DrawingVlmLegibility(StrEnum): CLEAR; DEGRADED; ILLEGIBLE
class DrawingVlmValidationStatus(StrEnum): VALID; REJECTED
class DrawingVlmReconciliationStatus(StrEnum):
    CORROBORATED; RECOVERY_CANDIDATE; CONFLICT; ADVISORY_ONLY; REJECTED; UNSTABLE
class DrawingVlmRationale(StrEnum):   # computed by MachiningPro, never supplied by the model
    EXACT_MATCH; OCR_BELOW_THRESHOLD; DETERMINISTIC_OMITTED; NO_DETERMINISTIC_EVIDENCE;
    VALUE_MISMATCH; DECIMAL_MISMATCH; UNIT_MISMATCH; TYPE_MISMATCH; TOLERANCE_MISMATCH;
    CHARACTER_MISMATCH; GRAMMAR_REJECTED; UNIT_NOT_EVIDENCED; BARE_NUMBER;
    INSIDE_TITLE_BLOCK; IDENTIFIER_CONTEXT; LABEL_NOT_EVIDENCED; OUTSIDE_REGION;
    UNSUPPORTED_KIND; SAMPLE_DISAGREEMENT

@dataclass(frozen=True)
class DrawingVlmRegion:
    region_id: str                    # "vlm-region-" + sha256(...)[:24]
    kind: DrawingVlmRegionKind
    page_number: int
    raster_source: DrawingRasterSource
    crop_px: tuple[int, int, int, int]            # x0, y0, x1, y1 in image pixels
    pdf_box: DrawingBoundingBox
    trigger_evidence_ids: tuple[str, ...]         # sorted

@dataclass(frozen=True)
class DrawingVlmEvidence:
    evidence_id: str
    evidence_kind: DrawingVlmEvidenceKind
    raw_candidate: str                            # model transcription, NFC, ≤ 256 chars
    legibility: DrawingVlmLegibility
    normalized_candidate: str | None              # computed by MachiningPro only
    field_key: str | None                         # one of the 12 title field keys
    normalized_dimension: DrawingDimension | None # evidence-scoped ID; never canonical
    normalized_characteristic: DrawingGdtCharacteristic | None
    normalized_datum: DrawingDatumReference | None
    source_location: DrawingSourceLocation        # authority=ADVISORY (§10)
    parser_identity: DrawingParserIdentity        # ("machiningpro.vlm-assist", "1.0.0", "vlm-crop-v1")
    model: VlmModelIdentity
    prompt_contract_version: str
    region_id: str
    request_id: str
    sample_index: int
    reported_confidence: Decimal | None           # [0, 1], quantized 1e-6
    validation_status: DrawingVlmValidationStatus
    rejection_rationale: DrawingVlmRationale | None

@dataclass(frozen=True)
class DrawingVlmFinding:
    finding_id: str
    status: DrawingVlmReconciliationStatus
    rationale: DrawingVlmRationale
    ai_evidence_ids: tuple[str, ...]
    deterministic_support_ids: tuple[str, ...]   # canonical item IDs / OCR evidence IDs / vector object IDs
    deterministic_origins: tuple[DrawingEvidenceOrigin, ...]
    conflict_ids: tuple[str, ...]

@dataclass(frozen=True)
class DrawingAdvisoryReport:
    status: DrawingIngestionStatus                # reused (precedent: OcrResult)
    prompt_contract_version: str
    model: VlmModelIdentity | None
    config_fingerprint: str                       # sha256 of canonical config repr
    base_result_fingerprint: str                  # binds the report to the exact base result
    regions: tuple[DrawingVlmRegion, ...]
    evidence: tuple[DrawingVlmEvidence, ...]
    findings: tuple[DrawingVlmFinding, ...]
    diagnostics: tuple[str, ...]                  # constant codes, ≤ 50 × 240
    request_count: int

@dataclass(frozen=True)
class DrawingAssistedIngestionResult:
    result: DrawingIngestionResult
    advisory: DrawingAdvisoryReport | None
```

Mapping to the requested fields: `evidence_id`, `evidence_kind`, `raw_candidate`,
`normalized_candidate`; page, box and `source_object_ids` via `source_location`; `confidence`
(`reported_confidence`, mirrored into `source_location.confidence`); `source_kind` (implicit by
type, plus `DrawingEvidenceOrigin.AI_VLM` on findings); provider/model/version (`model`);
`prompt_contract_version`; `rationale_category` (`DrawingVlmRationale`); `validation_status`.
`reconciliation_status`, `deterministic_support_ids` and `conflict_ids` live on
`DrawingVlmFinding`, so each evidence record stays immutable.

Invariants: FAILED and UNSUPPORTED reports carry no evidence or findings; every ID is unique
within a report; tuples are sorted (§17); no timestamps; no raw payloads, image bytes, paths
or exception text.

Timestamps are excluded from every deterministic type. The audit sink (§15.5) receives
`DrawingVlmAuditEvent` values carrying injected-clock timestamps; they never enter results.

## 10. Provenance

- `source_location = DrawingSourceLocation(source_id, sheet_number=page, page_number=page,
  original_text=raw_candidate, adapter_id="machiningpro.vlm-assist",
  adapter_version=f"{model_id}@{model_version}", confidence=reported_confidence,
  authority=ADVISORY, bounding_box=<mapped by MachiningPro>,
  source_object_ids=(image_object_id, region_id, evidence_id))`.
- AI evidence is a distinct type, always carries ADVISORY authority, and is never stored in
  `CanonicalDrawing`. `GdtTokenSource` is intentionally not extended with an AI value, so
  `recognize_feature_control_frames` cannot receive AI tokens by construction.
  `DrawingVlmEvidence` must not subclass `DrawingOcrTextEvidence`.
- The relationship to deterministic evidence is expressed only through findings
  (`deterministic_support_ids` + `deterministic_origins`).
- Existing location, box, identity and authority types are reused. No new location type and
  no new field on `DrawingSourceLocation`.

## 11. Confidence policy

1. Model-reported confidence is uncalibrated metadata. It is stored, quantized to 1e-6 and
   range-checked. Values outside `[0, 1]`, NaN, infinity, booleans or non-numeric strings
   reject the item (`VLM_INVALID_CONFIDENCE`).
2. It is never combined arithmetically with OCR confidence, never breaks a tie, and never
   chooses between conflicting values.
3. Optional `min_reported_confidence` (default `None` = record only) may suppress proposals
   from the report but can never create findings stronger than ADVISORY_ONLY.
4. Existing deterministic gates are unchanged: OCR canonical 0.80; GD&T frame 0.90.
5. OCR review floor `ocr_review_floor = 0.50` (approved v1 default): OCR LINE evidence with
   confidence in `[0.50, 0.80)` creates OCR_REVIEW regions. It is obtained by a second OCR run
   with `OcrLimits(minimum_confidence=floor)` and kept separate from canonical evidence.
6. OCR + AI agreement yields RECOVERY_CANDIDATE (sub-threshold OCR) or CORROBORATED (accepted
   deterministic item). Canonical confidence never changes (D1).
7. AI-only evidence is at best ADVISORY_ONLY. AI disagreement produces CONFLICT and never
   removes or edits OCR/vector evidence.

### 11.5 Future promotion criteria (not implemented; out of Phase 1D by D1)

A later phase may consider promoting a RECOVERY_CANDIDATE only if all of these hold: BLIND
mode; at least 2 agreeing samples; exact grammar-normalized equality with OCR evidence at or
above the review floor; spatial adjacency; no conflict in the region; the evidence kind is on
an allowlist excluding GD&T characteristics, datums and units; and canonical authority
`INFERRED`, never `EXTRACTED`. Such a phase requires its own approved specification.

## 12. Reconciliation matrix

Spatial match: same page and boxes adjacent under the existing 2 pt rule
(`_boxes_are_adjacent`), or center-inside for region containment. Value match: exact equality
after the repository grammar normalizes both sides (Decimal nominal, unit, dimension type,
tolerance upper/lower; NFC and whitespace-collapsed text for TEXT and TITLE_FIELD).

| Combination | Authority | Canonical effect | Advisory finding | Conflict | Rejected | Insufficient | Diagnostics | Provenance retained |
|---|---|---|---|---|---|---|---|---|
| VECTOR vs OCR | Vector + 1C rules (post-Task-0) | Agreement merges; conflict omits both | — | Both omitted | — | — | `PDF_DIMENSION_CONFLICT` / GD&T codes → PARTIAL (INSUFFICIENT_DATA if nothing remains) | Union of IDs |
| VECTOR vs AI | Vector | None | CORROBORATED on equality | CONFLICT on any mismatch | Invalid AI item | — | `VLM_CONFLICT_DETECTED` | Vector IDs + AI evidence ID |
| OCR (≥ 0.80, canonical) vs AI | OCR via grammar | None | CORROBORATED | CONFLICT | Invalid AI item | — | As above | OCR IDs + AI ID |
| OCR (0.50–0.80) vs AI | None (not canonical) | None | RECOVERY_CANDIDATE on equality | CONFLICT (both kept) | Invalid AI item | Neither parses → ADVISORY_ONLY / REJECTED | `VLM_RECOVERY_CANDIDATE` | OCR review IDs + AI ID |
| Deterministically omitted (conflict or grammar) vs AI | Omission stands | None | ADVISORY_ONLY (`DETERMINISTIC_OMITTED`) | — | — | — | — | All IDs |
| VECTOR + OCR vs AI | Merged deterministic item | None | CORROBORATED | CONFLICT | Invalid AI item | — | As above | Union IDs + AI ID |
| AI only | None | None | ADVISORY_ONLY (`NO_DETERMINISTIC_EVIDENCE`) | — | Failed §14 controls | Region with no valid items | `VLM_ADVISORY_ONLY` | AI ID only |
| AI vs AI (samples) | None | None | Unchanged if all samples agree | — | — | — | Disagreement → UNSTABLE, `VLM_SAMPLE_DISAGREEMENT` | All sample IDs |

Duplicate suppression key: `(page, evidence_kind, field_key, normalized_candidate,
adjacency cluster)`. Merged findings take the union of IDs, ordered by the §17 sort key.
Conflicts are never resolved by confidence, sample count or source order.

## 13. Failure and status semantics

The base result is never changed by any case below. The advisory status reuses
`DrawingIngestionStatus`.

| Case | Advisory | Provider called | Diagnostic |
|---|---|---|---|
| Assistance disabled, config `None` or provider `None` | `None` | No | — |
| Base FAILED or UNSUPPORTED | `None` | No | — |
| Base INSUFFICIENT_DATA, not opted in | `None` | No | — |
| No eligible raster regions | INSUFFICIENT_DATA | No | `VLM_NO_ELIGIBLE_REGIONS` |
| Remote provider (always in Phase 1D, D3), not allowlisted, or unpinned model | UNSUPPORTED | No | `VLM_PROVIDER_NOT_ALLOWED` |
| Capability mismatch for every request | UNSUPPORTED | No | `VLM_PROVIDER_UNSUPPORTED` |
| Evidence re-gathering or crop worker fails / times out | FAILED | No | `VLM_EVIDENCE_FAILURE` / `VLM_CROP_FAILURE` |
| Provider unavailable on every request | FAILED | Attempted | `VLM_PROVIDER_UNAVAILABLE` |
| Timeout (per request) | Request dropped; PARTIAL if others valid, else FAILED | Yes | `VLM_TIMEOUT` |
| Cancellation | Stop remaining; PARTIAL if any valid, else FAILED | Stops | `VLM_CANCELLED` |
| Total assist budget exceeded | As cancellation | Stops | `VLM_TIME_BUDGET` |
| Retries exhausted | Request dropped | Yes | `VLM_RETRY_EXHAUSTED` |
| Malformed JSON, duplicate keys, NaN, non-UTF-8 | Response rejected | — | `VLM_SCHEMA_INVALID` |
| Unexpected field | Response rejected | — | `VLM_SCHEMA_EXTRA_FIELD` |
| Missing required field | Response rejected | — | `VLM_SCHEMA_MISSING_FIELD` |
| Request ID, contract or model mismatch | Response rejected | — | `VLM_IDENTITY_MISMATCH` / `VLM_MODEL_MISMATCH` |
| Response too large | Rejected before parsing | — | `VLM_RESPONSE_LIMIT` |
| Too many items in one response | Response rejected | — | `VLM_CANDIDATE_LIMIT` |
| Invalid box, page or confidence | Item REJECTED | — | `VLM_INVALID_BOX` / `VLM_INVALID_PAGE` / `VLM_INVALID_CONFIDENCE` |
| Duplicate item in one response | Response rejected | — | `VLM_DUPLICATE_EVIDENCE` |
| Unsupported evidence kind (e.g. surface finish) | Item REJECTED | — | `VLM_UNSUPPORTED_KIND` |
| Region, request or evidence caps exceeded | Deterministic truncation after sorting; PARTIAL | — | `VLM_REGION_LIMIT` / `VLM_REQUEST_LIMIT` / `VLM_EVIDENCE_LIMIT` |
| Audit required but sink fails | Requests not sent; FAILED | No | `VLM_AUDIT_UNAVAILABLE` |
| All requests complete and validated | VALID (INSUFFICIENT_DATA if zero valid items) | Yes | — |

Advisory caps truncate explicitly (diagnostic + PARTIAL) rather than FAIL, because the
advisory stage cannot corrupt canonical output and the caps exist to bound exposure. This
deliberately differs from the canonical fail-closed truncation rule of Phase 1B.

## 14. Hallucination controls

Core rule: the model transcribes and classifies; MachiningPro parses. The response schema has
no numeric-value, unit, zone, rationale or free-text explanation fields.

| Risk | Deterministic control |
|---|---|
| Invented dimension values | DIMENSION items must parse with the 1B token/tolerance grammar from `raw_candidate`; bare numbers rejected (`BARE_NUMBER`, same rule as post-Task-0 OCR); CORROBORATED/RECOVERY_CANDIDATE only when deterministic evidence agrees |
| Invented tolerance values | Tolerance must come from the same raw token via the 1B tolerance grammar; separate tolerance-only items rejected |
| Decimal-point hallucination | Digit-sequence comparison: same digits with a different decimal position → CONFLICT (`DECIMAL_MISMATCH`), never recovery |
| Decimal separator changes | `_parse_dimension_decimal` rules (mixed separators and `,ddd` rejected); normalized forms compared, not strings |
| Invented units | Unit or angle symbol must appear literally in `raw_candidate` (`UNIT_NOT_EVIDENCED`) |
| Unit conversion | Never performed; different units → CONFLICT (`UNIT_MISMATCH`) |
| Invented datum letters | `^[A-Z]$` only; must lie inside a GDT_CANDIDATE region; ADVISORY_ONLY without deterministic support; never creates a canonical `DrawingDatumReference` |
| Invented GD&T characteristics | 4-item allowlist; only within GDT_CANDIDATE regions; UNKNOWN produces no evidence |
| Invented feature-control frames | No frame construction from AI; AI tokens cannot enter the GD&T grammar (type-level) |
| Wrong tolerance↔dimension association | Association only inside one transcribed token parsed by the grammar; cross-item association never accepted |
| Note text read as a dimension | NOTE and TEXT kinds never produce dimensions; the dimension grammar is anchored (`fullmatch`) |
| Revision/date/part number read as geometry | Items centered inside any title region → REJECTED (`INSIDE_TITLE_BLOCK`); items in, or starting with, an identifier-label line → REJECTED (`IDENTIFIER_CONTEXT`, reusing the post-Task-0 `_starts_with_identifier_label` rule) |
| OCR correction that changes meaning | TEXT disagreement is always CONFLICT (`CHARACTER_MISMATCH` / `DECIMAL_MISMATCH`); OCR evidence is never rewritten |
| Hallucinated title-block fields | Field key must be one of the 12 keys; value must pass `_normalize_title_value`; item must lie in a TITLE_BLOCK region; a deterministic label alias for that field must exist within 72 pt (`LABEL_NOT_EVIDENCED`) |
| Hallucinated drawing zones | No zone field in the schema; extra fields reject the whole response |
| Hallucinated page associations | Page is taken from the request, never the response; boxes are crop-relative `[0, 1]`, validated and mapped by MachiningPro |
| Prompt injection in drawing text | Output is schema-bound data only; transcribed text is never executed or used as instructions |

## 15. Security and privacy

### 15.1 Modes

- **A. Local/offline** (`VlmLocality.LOCAL`): the same payload minimization and limits apply.
  Locality is self-declared by the adapter, so the real control is the provider allowlist plus
  adapter code review.
- **B. Remote** (`VlmLocality.REMOTE`): the policy code exists (`allow_remote`, allowlist,
  pinned model, audit precondition) but, per D3, remote use is disabled in Phase 1D. The policy
  gate rejects every REMOTE provider with `VLM_PROVIDER_NOT_ALLOWED` regardless of
  configuration until `docs/DATA_GOVERNANCE.md` contains an approved third-party processing
  policy and a later phase enables it. No remote adapter ships in Phase 1D.

### 15.2 Payload rules

- No silent upload: zero provider calls unless `enabled=True` and a provider is passed.
- Only grayscale PNG crops re-encoded from decoded pixels (no EXIF, ICC or text chunks), the
  prompt contract ID, task kind, crop dimensions and an opaque request ID.
- Never sent: PDF bytes, full pages (IMAGE_OVERVIEW off by default), filename, `source_id`,
  `drawing_id`, filesystem paths, environment values, secrets, PDF Info/XMP metadata, vector
  geometry, or pages that were not selected.
- BLIND mode (default): no OCR or vector text in the request. GUIDED mode may include only
  region-local bounded text, and agreement in GUIDED mode never yields CORROBORATED or
  RECOVERY_CANDIDATE, only ADVISORY_ONLY, because it is not independent evidence.
- Title-block regions contain personal names (author, checker, approver).
  `remote_allow_title_block=False` by default for any future remote phase. There is no pixel
  redaction in Phase 1D; minimization works by excluding regions.

### 15.3 Data classification

Must remain local (always in Phase 1D): all drawing and image data. For a future remote phase,
only OCR_REVIEW and GDT_CANDIDATE grayscale crops within limits may be considered, and only
after the D3 governance policy exists.

### 15.4 Isolation

Crop preparation runs in a spawned worker (module-level entry point, pickleable arguments).
The Phase 1D core contains no network code. Credentials would be held by adapters only and are
never part of requests, reports, diagnostics or audit events.

### 15.5 Audit

`DrawingVlmAuditSink.record(DrawingVlmAuditEvent)` receives: request ID, provider/model
identity, prompt contract version, region IDs, crop pixel SHA-256, byte counts, attempt count,
outcome code, durations and an injected-clock timestamp. It never receives image bytes, raw
response text (only its SHA-256) or exception messages. Persistence is out of scope.

## 16. Resource limits (`VlmLimits`, separate from `PdfDrawingLimits`)

All values are approved initial, configurable v1 operational defaults, not engineering truth
thresholds. `PdfDrawingLimits` is not extended (its exact `asdict` is frozen by tests).

| Limit | v1 default |
|---|---:|
| OCR review floor | 0.50 |
| Pages considered | 10 |
| Regions per page | 16 |
| Regions total | 64 |
| Crop longest edge | 2,048 px |
| Crop pixels | 4,194,304 |
| Crop PNG bytes | 4 MiB |
| Requests per document (regions × samples) | 64 |
| Samples per region | 1 (max 3) |
| Attempts per request | 2 |
| Response bytes | 256 KiB |
| Output token hint | 2,048 |
| Items per response | 200 |
| Evidence items total | 5,000 |
| `raw_candidate` length | 256 characters |
| Request timeout | 30 s |
| Total assist budget | 120 s |
| Crop worker timeout | 30 s |
| Region padding | 8 px, clipped to the image |
| Diagnostics | 50 × 240 characters (existing) |

`__post_init__` rejects booleans, non-positive values and per-page limits above totals, following
the existing limit classes. `samples_per_region` above 3 is rejected.

## 17. Determinism

Deterministic: canonical result (D1); evidence re-gathering; region planning; crop pixels;
IDs; validation; normalization; reconciliation given identical responses; ordering;
diagnostics; fingerprints.
Not deterministic: provider responses, latency, audit timestamps, provider request references.

- `request_id = "vlm-req-" + sha256(prompt_contract_version | provider_id | model_id |
  model_version | region_id | sha256(raw grayscale crop pixels) | width | height | task_kind |
  mode | sample_index)[:24]`. Pixel hashes are used instead of PNG bytes because zlib builds
  can change PNG bytes.
- `evidence_id = "vlm-ev-" + sha256(request_id | kind | NFC raw_candidate | field_key |
  plain-decimal mapped box)[:24]`; `finding_id` hashes its sorted member IDs.
- Sort key for regions, evidence and findings: `(page, top, x0, bottom, x1, kind, field_key,
  normalized_candidate, id)`.
- Only sorted tuples, never sets or frozensets, appear in fingerprinted or serialized values
  (string hash randomization changes set iteration order across processes).
- Sampling hints request temperature 0; determinism is never assumed from them.
- Repeated-inference variance: optional multi-sampling; disagreement gives UNSTABLE.
- Caching: in-memory per `parse_with_assistance` call, keyed by `request_id`. No cross-call
  persistence in Phase 1D.
- A `ReplayVlmProvider` (tests only) keyed by `request_id` reproduces reports exactly.
- A model or version change changes `request_id` and therefore every advisory ID; the
  canonical result is unaffected.

## 18. Parser integration

```python
class PdfDrawingParser(DrawingParser):
    def parse_with_assistance(
        self, source_id: str, file_name: str, content: bytes, notes: str | None = None, *,
        assistance: DrawingVlmAssistConfig | None = None,
        provider: VlmProvider | None = None,
        cancellation: VlmCancellation | None = None,
        audit_sink: DrawingVlmAuditSink | None = None,
    ) -> DrawingAssistedIngestionResult: ...
```

- Invocation: `base = self.parse(...)` runs first and is returned unchanged. Assistance runs
  only if `assistance is not None and assistance.enabled and provider is not None` and the base
  status is VALID or PARTIAL, or INSUFFICIENT_DATA with `assist_on_insufficient_data=True`.
- Configuration is call-scoped: no environment variables, globals or config files. Default:
  disabled.
- Visual input: cropped regions of embedded raster images only; never full vector pages.
- OCR and vector text are not sent in BLIND mode; they are used locally for reconciliation.
- Existing deterministic candidates are never sent; they are compared locally.
- Evidence gathering reuses `_run_spawned_worker` + `_vector_gdt_tokens` and
  `extract_ocr_from_pdf(..., limits=OcrLimits(minimum_confidence=floor))`. Title regions come
  from `_ocr_title_candidates`. GDT_CANDIDATE groups come from GD&T spatial groups rejected
  with a characteristic-led code (post-Task-0 semantics), obtained through the grammar adapter.
- Grammar injection: `_PdfGrammarAdapter` implements `DrawingGrammarAdapter` (dimension and
  tolerance parsing, diameter prefixes, title alias/value normalization,
  `_starts_with_identifier_label`, adjacency, GD&T grouping) by delegating to existing private
  functions. No refactor of 1B/1C code.
- Canonical output: never updated (D1). Advisory output: `DrawingAssistedIngestionResult.advisory`.
- No circular import: `pdf_drawing` → `vlm_drawing` → `vlm_provider` → `drawing`.

## 19. Testing strategy

No live vendor calls. Fakes live in `tests/unit/interoperability/vlm_fixtures.py`:
`ScriptedVlmProvider`, `ReplayVlmProvider`, `FailingVlmProvider(code)`, `SlowVlmProvider`,
`SpyVlmProvider`, response-JSON builders, and raster PDFs from `SyntheticRasterPdfBuilder` /
`SyntheticRasterDrawingBuilder` and mixed PDFs from `SyntheticPdfBuilder(include_image=True)`.
OCR is monkeypatched as in the existing suites. An autouse fixture blocks
`socket.socket.connect` in all new test modules.

- Foundation (`test_vlm_provider.py`, `test_vlm_drawing.py`):
  `test_disabled_config_makes_no_provider_call`, `test_missing_provider_returns_no_advisory`,
  `test_provider_unavailable_is_failed_advisory_and_base_unchanged`,
  `test_timeout_discards_late_response`, `test_cancellation_stops_remaining_requests`,
  `test_malformed_json_duplicate_keys_nan_rejected`,
  `test_unexpected_schema_field_rejects_response`,
  `test_missing_required_field_rejects_response`, `test_missing_provenance_rejected`,
  `test_model_identity_mismatch_rejected`, `test_invalid_confidence_rejected`,
  `test_invalid_bbox_rejected`, `test_page_is_taken_from_request_not_response`,
  `test_duplicate_evidence_rejects_response`, `test_retry_only_on_transient_and_bounded`,
  `test_limits_validation_and_approved_defaults`.
- Hallucination: `test_invented_dimension_is_advisory_only`,
  `test_invented_tolerance_is_not_accepted`, `test_decimal_shift_is_decimal_mismatch_conflict`,
  `test_decimal_separator_ambiguity_rejected`, `test_unit_not_literal_is_rejected`,
  `test_conflicting_unit_is_conflict_without_conversion`,
  `test_invented_datum_is_advisory_only`,
  `test_invented_gdt_characteristic_outside_allowlist_rejected`,
  `test_ai_tokens_cannot_enter_gdt_grammar`, `test_wrong_title_field_without_label_rejected`,
  `test_numeric_note_is_not_a_dimension`,
  `test_revision_date_part_number_identifier_context_rejected`, `test_bare_number_rejected`.
- Reconciliation: `test_vector_wins_over_unsupported_ai`,
  `test_ocr_below_threshold_plus_ai_is_recovery_candidate`,
  `test_vector_plus_ai_corroborated_canonical_unchanged`,
  `test_ocr_vs_ai_conflict_retains_both`, `test_vector_plus_ocr_vs_ai_conflict`,
  `test_ai_only_is_advisory`, `test_deterministic_omission_stays_omitted`,
  `test_duplicate_findings_suppressed_with_union_ids`,
  `test_repeated_samples_disagree_unstable`, `test_repeated_normalized_result_is_stable`,
  `test_guided_mode_never_corroborates`.
- Security (`test_pdf_drawing_vlm.py`): `test_no_network_or_provider_call_when_disabled`,
  `test_no_request_for_vector_only_pages`, `test_no_request_for_excluded_page`,
  `test_request_payload_has_no_path_filename_source_id_or_metadata`,
  `test_png_crop_has_no_ancillary_chunks`, `test_region_minimization_and_padding_bounds`,
  `test_remote_provider_always_rejected_in_phase_1d`,
  `test_remote_title_block_regions_excluded_by_default`, `test_request_count_limit`,
  `test_payload_byte_limit`, `test_response_size_limit`,
  `test_crop_worker_timeout_fails_closed`,
  `test_audit_sink_receives_no_image_bytes_or_raw_text`,
  `test_report_repr_has_no_raw_payloads`.
- Regression: `test_parse_with_assistance_result_equals_parse` (parameterized over
  vector-only, raster-only, mixed, GD&T, title and Task 0 conflict fixtures and every provider
  behavior); `test_parse_unchanged_when_module_imported`; the existing `test_drawing.py`,
  `test_pdf_drawing.py` (including `TestPhase1CTask0Hotfix`), `test_ocr_drawing.py` and
  `test_gdt_drawing.py` pass unmodified; the `asdict` and `__all__` freeze assertions stay
  green; vector-only PDFs, the OCR-only flow and GD&T output are unchanged when VLM is disabled.
- Determinism: `test_advisory_report_identical_under_replay_provider`,
  `test_ids_independent_of_process_hash_seed` (subprocess with a different `PYTHONHASHSEED`).

## 20. Backward compatibility

No change to `drawing.py`, the `DrawingParser` ABC, `parse()`, `PdfDrawingLimits`,
`pdf_drawing.__all__`, `ocr_drawing.py`, `raster_drawing.py`, `gdt_drawing.py` or
`pyproject.toml`. New behavior is reachable only through a new method whose defaults disable
it. Removing the two new modules and the method restores the post-Task-0 Phase 1C state exactly.

## 21. Phase boundaries

- Task 0 (complete in the working tree, pending independent review and commit): Phase 1C
  hotfix, §4.2.
- Phase 1D (this design): advisory VLM evidence for PDF embedded raster regions, local
  providers only in practice.
- Deferred: promotion (§11.5), vendor adapters, remote enablement (requires the D3 policy),
  vector-page rendering, standalone raster inputs, audit persistence.
- Separate specification: DXF/DWG annotations. Phase 2A: CAD↔drawing reconciliation.

## 22. Risks

- **P0:** none open. D1–D3 are approved and the four Task 0 defects are fixed in the working
  tree.
- **P1:**
  - Parent-process raster decoding in the OCR path (C5).
  - OCR rotation not applied (C7).
  - Tesseract version string asserted, not verified.
  - In-process providers cannot be hard-killed.
  - Providers cannot cross the Windows spawn boundary.
  - No network guard in the existing suites.
  - Encoding corruption risk in Windows tooling (C14; Task 0 added a source guard for
    `pdf_drawing.py` only).
  - `pyproject.toml` pins `Pillow>=10.4,<12` while `pdfplumber 0.11.10` requires
    `Pillow>=12.2.0`, so the declared constraint set does not resolve as written.
  - Pre-existing unrelated test failures in `test_population.py` (41, missing
    `ExchangeDocumentStatus.UNSUPPORTED`) and one stale `test_pdf_drawing.py` test that builds
    `DrawingRasterSource` without `parser_identity`.
  - `GDT_CANDIDATE_LIMIT` is FAILED (§4.2). Because the GD&T token count is per character for
    vector text, ordinary vector drawings above 5,000 non-space characters now fail closed.
    A later change should count frame candidates (or word tokens) instead of characters, or
    revisit the limit; this needs its own approval.
  - Vector GD&T recognition is effectively non-functional: vector text runs are single
    characters, so a characteristic word such as `FLATNESS` never forms one token. The
    existing `test_vector_gdt_e2e_produces_nonempty_gdt_references` passes vacuously (its
    assertions run only `if refs:`). Pre-existing; not changed by Task 0.
- **P2:**
  - Vector/OCR work runs twice when assistance is on.
  - `CanonicalDrawing` is unhashable (dict metadata).
  - `GdtTokenSource` and `DrawingEvidenceOrigin` overlap.
  - The provider contract may later move to `backend.ai`.
  - Duplicate Foundation copies.
  - Stale docstrings in `drawing.py`.
  - No metrics hook.
  - The OCR tolerance path keeps a dimension whose tolerance fails to parse (vector path
    drops it).
  - The identifier-line rule is conservative: text such as "SHEET METAL 2 mm" is rejected.

## 23. Acceptance criteria

1. With assistance disabled, a missing provider, or an ineligible base status: zero provider
   calls, zero network activity, and `advisory is None`.
2. `parse_with_assistance(...).result == parse(...)` for every fixture and provider behavior.
3. All existing drawing suites, including `TestPhase1CTask0Hotfix`, pass unchanged; the freeze
   tests are untouched; the full `tests/unit/interoperability` run shows no new failures against
   the recorded baseline.
4. Every AI item carries ADVISORY authority, provider/model/version, prompt contract, page,
   mapped box, image and region IDs, and a validation status.
5. No model-supplied value is used without grammar re-derivation; every §14 control has a test.
6. The §12 reconciliation matrix is implemented exactly; conflicts are never resolved by
   confidence.
7. Every §13 failure case has a test and a constant diagnostic.
8. Payloads contain only allowed fields; §16 limits are enforced; every REMOTE provider is
   rejected in Phase 1D.
9. Advisory reports are identical under replay and across `PYTHONHASHSEED` values.
10. No new dependency; Ruff, scoped `git diff --check` and the encoding gate pass.
