# Technical Drawing Intelligence Phase 1C Design

Status: design-only proposal. This document does not authorize production-code or test changes.

## 1. Scope and governing evidence

Phase 1B is complete and remains the authoritative baseline for vector-PDF parsing, typed provenance, bounded diagnostics, security, and the statuses `VALID`, `PARTIAL`, `INSUFFICIENT_DATA`, `UNSUPPORTED`, and `FAILED`.

The foundation document assigns Phase 1C to OCR-based extraction from raster technical drawings and GD&T/PMI recognition. The same document also mentions DXF in both a Phase 1B exclusion table and a Phase 1C future-phase sequence. The Phase 1B governing specification resolves that conflict by requiring a dedicated DXF specification. Therefore this design keeps DXF out of Phase 1C.

Phase 1C is deterministic, local, and conservative. It adds:

- embedded-raster extraction and bounded OCR for PDF pages;
- typed OCR evidence and confidence-aware canonical text/metadata/dimension integration;
- a narrow, explicit GD&T subset covering feature-control-frame recognition and datum references;
- deterministic reconciliation of vector and OCR evidence.

It does not add AI/VLM behavior. AI/VLM remains Phase 1D+ per the foundation roadmap.

## 2. Decisions

| Decision | Phase 1C result |
| --- | --- |
| OCR | In scope for raster PDF evidence only |
| OCR engine | Offline Tesseract 5.x invoked through `pytesseract` |
| GD&T | In scope for the conservative subset in §5 |
| DXF | `DEFERRED_PENDING_DEDICATED_SPEC` |
| AI/VLM | `OUT_OF_SCOPE_PHASE_1C` |
| Rendering | No full-page rasterization; process embedded image objects only |
| Customer/OEM rules | Out of scope |

## 3. Raster and OCR contract

### 3.1 Detection and extraction boundary

Reuse the Phase 1B PDF preflight limits and parser-worker boundary. A page is raster-bearing when it contains one or more embedded image objects. A page is raster-only when it contains image objects but no accepted vector text or path evidence; it is mixed when both exist. Phase 1C does not render vector pages to pixels and does not OCR a page merely because vector extraction is sparse.

Only image bytes obtained from the already-open, validated PDF may be decoded. No external file, URL, attachment, embedded executable, JavaScript action, or remote resource is followed. Each image is assigned a deterministic source-object ID from the Phase 1B object-ID scheme and retains page identity and `DrawingBoundingBox`.

### 3.2 Supported image forms

The decoder accepts image encodings that Pillow can decode from the PDF image object after bounded extraction: grayscale, RGB/RGBA, indexed color, JPEG, JPEG2000 where the installed Pillow build supports it, and lossless Flate/PNG-like streams. CMYK, arbitrary device colorspaces, masks without a decodable base image, truncated streams, and codecs unavailable in the pinned build are rejected as unsupported rather than guessed.

Decoded images are converted to 8-bit grayscale. No color meaning is inferred.

### 3.3 Limits

The following values are the Phase 1C v1 contract and are checked before allocation or OCR:

| Resource | Limit |
| --- | ---: |
| input PDF bytes | 64 MiB (reuse Phase 1B) |
| pages | 200 |
| images per page | 16 |
| images per document | 512 |
| image width or height | 20,000 pixels |
| pixels per image | 25,000,000 |
| total decoded pixels | 100,000,000 |
| decoded raster budget | 512 MiB equivalent |
| OCR text characters | 1,000,000 |
| OCR evidence objects | 100,000 |
| GD&T candidates | 5,000 |
| worker timeout | 30 seconds |
| bounded IPC/result payload | 8 MiB |
| diagnostics | 50 entries |
| diagnostic message | 240 characters |

Exceeding a global limit is `FAILED` with no canonical document. A page-local unsupported image may yield `PARTIAL` when other accepted evidence exists; if no useful evidence remains, the result is `UNSUPPORTED` or `INSUFFICIENT_DATA` as described in §8.

### 3.4 Deterministic preprocessing

Preprocessing is versioned as `ocr-preprocess-v1` and consists of: grayscale conversion, page/image rotation using only the PDF rotation metadata (0/90/180/270), bounded downscaling to the configured maximum dimension, and a fixed OCR input mode. Content-based auto-rotation and automatic deskew are disabled in v1. Adaptive thresholding, denoising, sharpening, and other heuristic enhancement are disabled; an optional fixed global threshold may be enabled only as a versioned parser setting and must be covered by fixtures.

OCR is offline-only. The worker uses a pinned language/configuration, a fixed page-segmentation mode, and no user-provided command fragments. OCR output is normalized to Unicode NFC, whitespace is collapsed only for comparison, and original normalized token text is retained as evidence.

### 3.5 Confidence and canonical gates

Each word, line, and block has a typed `Decimal` confidence normalized to `[0, 1]`. Invalid or missing engine confidence is treated as zero. `0.80` is the minimum confidence for canonical ordinary text, title-block fields, dimensions, and tolerances derived from OCR. `0.90` is the minimum frame-level confidence for GD&T. Evidence below the applicable threshold may remain bounded diagnostic/evidence data but cannot create canonical semantics. No engineering unit is inferred from OCR context.

OCR may contribute to canonical content only after confidence, grammar, spatial, and false-positive checks. Unvalidated OCR text is never copied wholesale into the canonical document.

### 3.6 Provenance

Every OCR token/line/block carries:

- page number and page identity;
- `DrawingBoundingBox` in PDF coordinates;
- deterministic source-object ID of the image and an OCR child ID;
- parser identity and preprocessing version;
- confidence and evidence kind (`word`, `line`, or `block`).

Multi-token semantics retain all contributing source IDs and the union bounding box. Public results never expose raw image bytes, raw page text, paths, exceptions, or parser objects.

## 4. GD&T contract

### 4.1 Supported subset

Phase 1C v1 recognizes only explicit feature-control-frame evidence for these geometric characteristics: flatness, circularity, position, and symmetry. A frame may contain a finite Decimal tolerance value, an explicit diameter symbol, and an explicit sequence of single-letter datum references (`A`-`Z`). Datum identifiers are emitted only when directly present. No datum feature association is inferred.

The following are unsupported in v1 and remain unclassified: MMC/LMC/RFS modifiers, projected tolerance zones, composite frames, multi-segment frames, chained datum-reference-frame semantics, surface-finish/weld symbols, and any symbol not in the four-characteristic allowlist. Unsupported or ambiguous cells are omitted; they are never mapped to a different characteristic.

### 4.2 Typed representation

The model extension proposal is backward-compatible and immutable:

- `DrawingOcrTextEvidence`: normalized text, confidence, evidence kind, page/bounding box, source IDs, parser/preprocessing identity;
- `DrawingGdtCell`: cell index, normalized symbol/value/modifier text, confidence, source location, contributing source IDs;
- `DrawingFeatureControlFrame`: ordered tuple of cells, characteristic enum, optional finite tolerance value/unit, optional explicit diameter flag, ordered datum-reference tuple, frame confidence, source location, and parser identity;
- `DrawingDatumReference`: existing type retained and extended only with optional source evidence required for direct recognition;
- `DrawingGdtReference`: existing aggregate retained; its optional typed feature-control-frame payload carries the new frame without replacing existing callers.

No arbitrary dictionaries are used for semantic content. New fields are optional so Phase 1A/1B serialization and callers remain compatible. Absent evidence remains `None`/empty tuple.

### 4.3 Recognition and ambiguity

Frames are constructed only from bounded, spatially contiguous cells with deterministic left-to-right/top-to-bottom ordering. A missing cell, contradictory tolerance, unrecognized characteristic, or ambiguous cell boundary rejects the frame. Tolerance values are finite `Decimal` values; signs and explicit units are preserved. No datum, feature, or manufacturing intent is inferred.

## 5. Vector/OCR GD&T interaction

Vector evidence is authoritative only when it and OCR evidence describe the same normalized cell/value and have overlapping or directly adjacent bounding boxes. OCR may supplement a missing vector token, but it may not silently replace conflicting vector evidence. Duplicate suppression uses `(page, normalized cells, overlapping bounding-box cluster)` and deterministic source-ID ordering.

When vector and OCR values conflict, both candidates are retained only as bounded internal evidence, the semantic item is omitted, and a stable conflict diagnostic is emitted. Confidence is not used as a silent winner. When values agree, the merged semantic item retains all contributing source IDs and the union box, with vector parser identity and OCR confidence preserved. This same rule applies to ordinary raster dimensions/tolerances and title-block fields.

## 6. Status semantics

Existing statuses are reused:

| Condition | Status and document policy |
| --- | --- |
| valid vector only | Existing Phase 1B result unchanged (`VALID`, `PARTIAL`, or `INSUFFICIENT_DATA` according to its evidence) |
| accepted raster/OCR semantics | `VALID` when no required evidence failed; canonical document present |
| mixed accepted vector+raster | `VALID` when complete; otherwise `PARTIAL` with accepted content |
| raster confidence below gate | `INSUFFICIENT_DATA` if no accepted semantics; `PARTIAL` if other pages/evidence remain |
| unsupported codec/image | `UNSUPPORTED` if all useful evidence is unsupported; `PARTIAL` if accepted evidence remains |
| malformed image stream | `FAILED` for global structural corruption; page-local failure is `PARTIAL` only when other accepted content remains |
| OCR timeout or worker failure | `FAILED` for a global worker failure; isolated page failure is `PARTIAL` only with accepted content |
| valid GD&T subset | Included in the normal overall status; no new status is introduced |
| ambiguous/unsupported GD&T | Omit the frame; `PARTIAL` or `INSUFFICIENT_DATA` according to remaining evidence |
| resource limit exceeded | `FAILED`, no canonical document |

Fail-closed conditions never return a partial canonical document. Diagnostics remain bounded and code-only/message-safe.

## 7. Security requirements

The parser remains offline and worker-isolated. It executes no network call, remote OCR service, embedded file, JavaScript/action, or external resource. Raw PDF/image bytes are private to the worker and are never serialized into public results. Paths, filenames, environment values, exception text, tracebacks, parser objects, and arbitrary metadata dictionaries are excluded. OCR text and diagnostics are bounded by §3.3. Worker cleanup is deterministic on success, timeout, limit rejection, and failure.

## 8. Determinism requirements

Use pinned preprocessing and OCR configuration, stable Unicode normalization, stable confidence quantization, deterministic token grouping, and sort keys `(page, y0, x0, y1, x1, normalized_text, source_object_id)`. Frames sort by page, top-left box, characteristic, and source IDs. Duplicate suppression and vector/OCR merging are pure functions. Diagnostics sort by `(page, code, source IDs)` and serialization uses the existing canonical immutable ordering.

Tesseract can vary across engine builds/platforms. Phase 1C support is therefore pinned to a tested Tesseract 5.x build/configuration; unsupported engine drift is a compatibility concern, not a reason to introduce nondeterministic reconciliation. Identical bytes under the supported build must produce identical canonical output and diagnostics.

## 9. Dependency decisions

No dependency is added during planning.

| Dependency | Purpose | Version constraint | License/platform/offline | Security impact | Why needed |
| --- | --- | --- | --- | --- | --- |
| `pdfplumber` | Existing PDF object/page boundary and provenance | keep Phase 1B `>=0.11.10,<0.12` | MIT; Windows; offline | Reuse existing bounded worker | Already approved and sufficient for image-object discovery |
| `Pillow` | Bounded decode, grayscale, rotation, pixel accounting | proposed `>=10.4,<12` | MIT; Windows; offline wheels | Decode only after limits; reject unsupported codecs | Existing PDF dependencies do not safely expose normalized pixels |
| `pytesseract` + Tesseract engine | Local OCR | proposed `pytesseract>=0.3.13,<0.4`; Tesseract 5.x pinned in deployment | Apache-2.0; Windows; offline executable | No network; invoke fixed config; executable path is configuration, never public output | Existing dependencies provide no OCR engine; EasyOCR/torch would add larger, less deterministic model/runtime surface |

GD&T recognition requires no new dependency: it is a bounded grammar over normalized vector/OCR evidence. No EasyOCR, cloud OCR, VLM, CAD, or DXF dependency is approved by this plan.

## 10. Proposed module architecture

Production changes for a future implementation:

- `backend/interoperability/drawing.py` — typed OCR/GD&T model additions only;
- `backend/interoperability/raster_drawing.py` — image-object extraction, decode, limits, preprocessing;
- `backend/interoperability/ocr_drawing.py` — isolated OCR worker and confidence-normalized evidence;
- `backend/interoperability/gdt_drawing.py` — deterministic vector/OCR frame grammar and reconciliation;
- `backend/interoperability/pdf_drawing.py` — narrowly integrated raster/GD&T orchestration, preserving Phase 1B APIs.

Test additions:

- `tests/unit/interoperability/ocr_fixtures.py`;
- `tests/unit/interoperability/test_ocr_drawing.py`;
- `tests/unit/interoperability/test_gdt_drawing.py`;
- extensions to existing drawing/PDF tests only where integration is required.

These files are proposed only; they are not created by this design task.

## 11. Synthetic fixture strategy

Fixtures use generated, license-safe assets only: monochrome synthetic raster pages, deterministic text/line glyphs, rotated image objects, title-block-like labels, ordinary dimensions, four allowed GD&T characteristics, datum letters, ambiguous symbols, malformed/truncated image streams, and resource-limit documents. Mixed vector+raster PDFs are generated by the existing fixture builder. Fixtures must assert bytes, page boxes, source IDs, confidence gates, status, and serialization; no customer/OEM or copyrighted drawings are used.

## 12. Implementation sequence

1. Extend typed canonical OCR/GD&T/provenance models and publish limits/status contracts.
2. Add deterministic generated raster and mixed-PDF fixture builders.
3. Implement image-object detection, bounded decoding, pixel accounting, and worker cleanup.
4. Implement deterministic preprocessing and offline OCR worker output.
5. Integrate OCR text, title-block fields, ordinary dimensions, and tolerances through existing confidence/spatial gates.
6. Implement the four-characteristic GD&T frame grammar, datum letters, and conservative ambiguity rejection.
7. Integrate canonical frame mapping, vector/OCR reconciliation, diagnostics, and final status semantics.
8. Run final regression, security/leakage, determinism, dependency, and scope closeout.

## 13. Exact quality commands

Per-task focused commands (after the corresponding files exist):

```text
py -m pytest tests/unit/interoperability/test_drawing.py -q
py -m pytest tests/unit/interoperability/test_ocr_drawing.py -q
py -m pytest tests/unit/interoperability/test_gdt_drawing.py -q
```

Phase 1B regression plus Phase 1C focus:

```text
py -m pytest tests/unit/interoperability/test_drawing.py tests/unit/interoperability/test_pdf_drawing.py tests/unit/interoperability/test_ocr_drawing.py tests/unit/interoperability/test_gdt_drawing.py -q
```

Scoped Ruff:

```text
py -m ruff check backend/interoperability/drawing.py backend/interoperability/pdf_drawing.py backend/interoperability/raster_drawing.py backend/interoperability/ocr_drawing.py backend/interoperability/gdt_drawing.py tests/unit/interoperability/test_drawing.py tests/unit/interoperability/pdf_fixtures.py tests/unit/interoperability/test_pdf_drawing.py tests/unit/interoperability/ocr_fixtures.py tests/unit/interoperability/test_ocr_drawing.py tests/unit/interoperability/test_gdt_drawing.py
```

Scoped diff check:

```text
git diff --check -- pyproject.toml backend/interoperability/drawing.py backend/interoperability/pdf_drawing.py backend/interoperability/raster_drawing.py backend/interoperability/ocr_drawing.py backend/interoperability/gdt_drawing.py tests/unit/interoperability/test_drawing.py tests/unit/interoperability/pdf_fixtures.py tests/unit/interoperability/test_pdf_drawing.py tests/unit/interoperability/ocr_fixtures.py tests/unit/interoperability/test_ocr_drawing.py tests/unit/interoperability/test_gdt_drawing.py docs/superpowers/specs/2026-09-23-technical-drawing-phase-1c-design.md docs/superpowers/plans/2026-09-23-technical-drawing-phase-1c.md
```

## 14. Explicitly out of scope

AI/VLM and model-assisted extraction; DXF/DWG parsing pending a dedicated specification; frontend/UI, database, IGES, feature recognition, manufacturing recommendations, customer/OEM templates, cloud/remote OCR, automatic drawing redesign, CAM generation, surface-finish and weld recognition, unsupported GD&T modifiers/composites/projected zones, and any inference of units, datums, features, or engineering intent.

## 15. Resolved ambiguities

- The high-level project plan mentions VLM+OCR broadly, but the foundation phase sequence assigns VLM to 1D+; this design follows the phase-specific foundation contract.
- The foundation contains contradictory DXF phase labels; the governing Phase 1B spec requires a dedicated DXF specification, so DXF is deferred.
- Existing `DrawingGdtReference` is a container, not a recognizer; typed optional frame/cell structures are proposed without changing existing meanings.
- Raster pages are processed from embedded image objects only; vector pages are not rasterized for OCR in Phase 1C v1.
