# Technical Drawing Intelligence Phase 1C Implementation Plan

This plan is execution-ready after approval. It is planning-only and creates no production or test changes by itself.

## Scope gate

Implement only offline raster-PDF OCR and the four-characteristic GD&T subset defined in the Phase 1C design. Preserve every Phase 1B API, status, provenance, security, and deterministic-ordering contract. DXF is `DEFERRED_PENDING_DEDICATED_SPEC`; AI/VLM is Phase 1D+.

## Task 1 — typed model and contract extensions

Add immutable, serializable OCR evidence, GD&T cell/frame, confidence, parser identity, and source-provenance types to `backend/interoperability/drawing.py`. Extend existing GDT containers only with optional typed fields. Publish the v1 limits and status table from the design. Do not add dictionaries or infer semantics.

Focused verification:

```text
py -m pytest tests/unit/interoperability/test_drawing.py -q
```

## Task 2 — deterministic synthetic fixtures

Add `tests/unit/interoperability/ocr_fixtures.py` using generated image/PDF bytes only. Cover raster-only, rotated, mixed vector+raster, title-block text, ordinary dimensions, four GD&T characteristics, datum letters, ambiguity, malformed streams, and each limit. Assert deterministic bytes and source-object IDs.

Focused verification:

```text
py -m pytest tests/unit/interoperability/test_ocr_drawing.py -q
```

## Task 3 — raster detection, decoding, and limits

Implement `backend/interoperability/raster_drawing.py`. Detect embedded image objects without page rendering, enforce page/image/pixel/memory limits before allocation, decode only approved Pillow formats, convert to grayscale, apply `ocr-preprocess-v1`, and return typed evidence or bounded stable diagnostics. Preserve worker cleanup and fail-closed behavior.

Focused verification:

```text
py -m pytest tests/unit/interoperability/test_ocr_drawing.py -q -k "raster or limit or decode or preprocess"
```

## Task 4 — offline OCR worker

Implement `backend/interoperability/ocr_drawing.py` around pinned Tesseract 5.x and `pytesseract` configuration. Enforce offline execution, fixed language/segmentation settings, confidence normalization, text/object limits, deterministic ordering, timeout, and safe worker error mapping. Never expose raw OCR dumps or exceptions.

Focused verification:

```text
py -m pytest tests/unit/interoperability/test_ocr_drawing.py -q -k "ocr or confidence or timeout or worker or leakage"
```

## Task 5 — OCR canonical integration

Integrate accepted OCR evidence through `backend/interoperability/pdf_drawing.py` without changing Phase 1B vector behavior. Apply confidence and grammar gates before title-block, metadata, ordinary dimension, or tolerance emission. Implement vector/OCR duplicate and conflict rules; preserve all source IDs and boxes.

Focused verification:

```text
py -m pytest tests/unit/interoperability/test_pdf_drawing.py tests/unit/interoperability/test_ocr_drawing.py -q
```

## Task 6 — conservative GD&T recognition

Implement `backend/interoperability/gdt_drawing.py` for flatness, circularity, position, and symmetry only. Recognize explicit finite tolerances, explicit diameter symbols, and single-letter datum references. Reject unsupported modifiers, composite/multi-segment/projected frames, malformed values, and ambiguous spatial grouping. Support both normalized vector evidence and typed OCR evidence.

Focused verification:

```text
py -m pytest tests/unit/interoperability/test_gdt_drawing.py -q
```

## Task 7 — canonical mapping and evidence reconciliation

Map only accepted frames into the optional typed `DrawingGdtReference` payload. Merge agreeing vector/OCR evidence deterministically, retain union provenance, and omit conflicts without silently selecting by confidence. Integrate status/diagnostic semantics for mixed, sparse, unsupported, malformed, timeout, and resource-limit cases.

Focused verification:

```text
py -m pytest tests/unit/interoperability/test_drawing.py tests/unit/interoperability/test_pdf_drawing.py tests/unit/interoperability/test_ocr_drawing.py tests/unit/interoperability/test_gdt_drawing.py -q
```

## Task 8 — final verification and closeout

Run the combined suite, security/leakage assertions, deterministic repeat-parse assertions, false-positive cases, dependency audit, scope audit, Ruff, and scoped diff check. Do not repair unrelated repository failures. Close Phase 1C only when all eight tasks pass and no prohibited capability has been added.

Final command:

```text
py -m pytest tests/unit/interoperability/test_drawing.py tests/unit/interoperability/test_pdf_drawing.py tests/unit/interoperability/test_ocr_drawing.py tests/unit/interoperability/test_gdt_drawing.py -q
```

## Quality gates

Use the exact Ruff and `git diff --check` commands in the design document. The closeout audit must enumerate changed/untracked files, confirm no frontend/database/IGES/DXF/VLM files were touched, confirm no raw-content/path/traceback leakage, and verify repeated parsing is byte-for-byte equivalent under the supported OCR engine build.

## Deliverables by completion

Expected implementation files are `backend/interoperability/raster_drawing.py`, `ocr_drawing.py`, `gdt_drawing.py`, narrow edits to `drawing.py` and `pdf_drawing.py`, and the three proposed test modules/fixture extensions. Dependency changes, if approved after implementation review, are limited to the Pillow and pytesseract/Tesseract decisions in the design; no dependency is added by this planning task.
