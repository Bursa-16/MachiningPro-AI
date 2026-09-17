# MachiningPro AI â€” Technical Drawing Intelligence Foundation
## Phase 1A â€” Canonical Drawing Model & Ingestion Contract

**Stage:** Phase 1A
**Status:** Implemented
**Baseline:** v0.1.0-alpha.5 / HEAD 2b681fb7ca04bf419ad9b8fd81feb3ea791c9347
**Module:** `backend/interoperability/drawing.py`
**Tests:** `tests/unit/interoperability/test_drawing.py`

---

## 1. What Phase 1A Implements

Phase 1A creates the canonical domain representation for technical drawings
and the parser/adapter interface contract. It does **not** implement any parser
logic â€” that is Phase 1B and 1C.

### 1.1 Canonical Drawing Model

The complete canonical model hierarchy:

```
CanonicalDrawing
â”œâ”€â”€ source_id               â†’ EngineeringSource.source_id (provenance anchor)
â”œâ”€â”€ drawing_id              â†’ unique drawing identifier
â”œâ”€â”€ sheets: [DrawingSheet]
â”‚   â”œâ”€â”€ sheet_number / sheet_count / size / scale
â”‚   â”œâ”€â”€ views: [DrawingView]
â”‚   â”‚   â”œâ”€â”€ view_id / view_type / name / scale
â”‚   â”‚   â”œâ”€â”€ dimensions: [DrawingDimension]
â”‚   â”‚   â”œâ”€â”€ gdt_references: [DrawingGdtReference]
â”‚   â”‚   â””â”€â”€ surface_finish_annotations: [DrawingSurfaceFinish]
â”‚   â”œâ”€â”€ notes: [DrawingNote]
â”‚   â””â”€â”€ datum_references: [DrawingDatumReference]
â”œâ”€â”€ title_block: DrawingTitleBlock
â”‚   â”œâ”€â”€ drawing_number / part_number / part_name
â”‚   â”œâ”€â”€ material_raw / scale / sheet_number / sheet_count
â”‚   â”œâ”€â”€ revision: DrawingRevision
â”‚   â””â”€â”€ author / checker / approver / date_text
â”œâ”€â”€ revision: DrawingRevision
â”œâ”€â”€ material_notes: [DrawingMaterialNote]
â”œâ”€â”€ heat_treatment_notes: [DrawingHeatTreatmentNote]
â”œâ”€â”€ all_dimensions: [DrawingDimension]     â† flat collection across all sheets
â”œâ”€â”€ all_tolerances: [DrawingTolerance]
â”œâ”€â”€ all_datum_references: [DrawingDatumReference]
â”œâ”€â”€ all_gdt_references: [DrawingGdtReference]
â”œâ”€â”€ all_surface_finish: [DrawingSurfaceFinish]
â”œâ”€â”€ metadata: dict[str, str]
â””â”€â”€ source_location: DrawingSourceLocation
```

### 1.2 Parser/Adapter Contract

```python
class DrawingParser(abc.ABC):
    def parser_id(self) -> str: ...
    def parser_version(self) -> str: ...
    def supports(self, source_id, file_name, notes=None) -> bool: ...
    def parse(self, source_id, file_name, content, notes=None) -> DrawingIngestionResult: ...
```

### 1.3 Ingestion Result Contract

```python
DrawingIngestionResult(
    source_id: str,
    diagnostics: DrawingIngestionDiagnostics,
    document: CanonicalDrawing | None,
)
```

---

## 2. What Phase 1A Does NOT Implement

The following are explicitly **out of scope** for Phase 1A:

| Capability | Phase |
|---|---|
| OCR / Tesseract integration | 1C |
| PyMuPDF / pdfplumber parsing logic | 1B |
| AI / VLM extraction | 1D+ |
| GD&T symbol recognition | 1C |
| Actual title block extraction | 1B |
| Actual dimension detection | 1B |
| Actual tolerance extraction | 1B |
| Actual PMI parsing | 1C |
| Real PDF parser | 1B |
| DXF annotation parser | 1B |
| CAD â†” drawing reconciliation | 2A |
| Manufacturing feature recognition changes | 2B |
| Frontend UI changes | separate |
| New routes | separate |
| Database changes | separate |

---

## 3. Architectural Rules

### 3.1 Reuses Existing Interoperability Architecture

This module integrates with the existing `backend/interoperability/` package:

- `EngineeringSource` (from `models.py`) â€” provides `source_id` as the provenance anchor
- `ImportResult` pattern (from `orchestrator.py`) â€” `DrawingIngestionResult` mirrors this
- `enums.py` â€” capability and drawing-type enums already defined there should be
  inspected and reused where equivalents exist
- `adapter.py` â€” `FormatAdapter` ABC should be evaluated for extension by `DrawingParser`

**On the live machine:** Inspect `adapter.py` and decide whether
`DrawingParser` should extend `FormatAdapter`. Prefer extension if the
FormatAdapter interface is format-generic (not geometry-specific).

### 3.2 Fail-Closed

Unknown, malformed, or incomplete drawing content never silently becomes
authoritative engineering data.

| Status | Meaning | document field |
|---|---|---|
| `VALID` | All mandatory content parsed | Required â€” must be present |
| `PARTIAL` | Some content parsed; gaps exist | Optional â€” may be present |
| `INSUFFICIENT_DATA` | Too little data to be useful | None â€” must be absent |
| `UNSUPPORTED` | Format/content not supported | None â€” must be absent |
| `FAILED` | Adapter raised an error | None â€” must be absent |

### 3.3 Authority Semantics

Every piece of extracted drawing information carries a `DrawingExtractionAuthority`:

| Authority | Meaning |
|---|---|
| `DECLARED` | Explicitly stated in source â€” highest trust |
| `EXTRACTED` | Extracted by a parser from source content |
| `INFERRED` | Inferred from context / heuristic â€” lower trust |
| `ADVISORY` | AI-suggested â€” never authoritative in Phase 1A |

**On the live machine:** Check `enums.py` for existing authority/provenance
enums. If an equivalent exists, import it instead of the local
`DrawingExtractionAuthority`.

### 3.4 Decimal / Unit Safety

All engineering numeric values use `Decimal`, never `float`.

```python
# Correct
DrawingDimension(nominal_value=Decimal("25.0"), unit="mm")

# Rejected at construction time
DrawingDimension(nominal_value=25.0, unit="mm")  # TypeError
```

### 3.5 Immutability

All models are frozen dataclasses. No field can be mutated after construction.

### 3.6 Provenance

Every extracted item is traceable via `DrawingSourceLocation`:

```python
DrawingSourceLocation(
    source_id="upload::part4711.pdf",   # EngineeringSource.source_id
    sheet_number=1,
    page_number=1,
    view_id="v-front",
    original_text="Ã˜50 Â±0.05",          # raw token from source
    adapter_id="pdf-adapter",
    adapter_version="1.0.0",
    confidence=Decimal("0.95"),
    authority=DrawingExtractionAuthority.EXTRACTED,
)
```

### 3.7 No AI Authority

`DrawingExtractionAuthority.ADVISORY` is defined and can be stored for
completeness, but no ADVISORY result may be treated as authoritative in
Phase 1A. Consumers must check `.authority` before using extracted data.

---

## 4. Validation Rules

Phase 1A enforces deterministic model-integrity validation at construction time:

| Rule | Effect |
|---|---|
| `drawing_id` blank | `ValueError` |
| `source_id` blank | `ValueError` |
| `sheet_number < 1` | `ValueError` |
| `sheet_number > sheet_count` | `ValueError` |
| `page_number < 1` | `ValueError` |
| `confidence` outside [0, 1] | `ValueError` |
| `nominal_value` is float (not Decimal) | `TypeError` |
| `tolerance_value` is float | `TypeError` |
| `upper_value` is float | `TypeError` |
| SYMMETRIC tolerance with unequal magnitudes | `ValueError` |
| `tolerance_value` set without `tolerance_unit` | `ValueError` |
| `surface_finish.value` set without `unit` | `ValueError` |
| Duplicate datum labels in `CanonicalDrawing` | `ValueError` |
| VALID result without document | `ValueError` |
| FAILED/UNSUPPORTED/INSUFFICIENT_DATA with document | `ValueError` |
| Blank `revision_code` | `ValueError` |
| Blank `note_id` or `raw_text` | `ValueError` |
| Blank `datum_label` | `ValueError` |
| Blank `gdt_id`, `dimension_id`, `tolerance_id`, `finish_id` | `ValueError` |

---

## 5. Integration with Existing Pipeline

Phase 1A connects to the existing CAD import pipeline:

```
EngineeringSource (models.py)
    â†“
CadImportOrchestrator (orchestrator.py)        â† existing
    â†“
ImportResult / CanonicalDocument               â† existing

  [separately, for drawing-type sources:]

EngineeringSource (models.py)
    â†“
DrawingParser.parse(source_id, file_name, content, notes)   â† Phase 1A contract
    â†“
DrawingIngestionResult
    â”œâ”€â”€ diagnostics (status, format, warnings, errors)
    â””â”€â”€ document: CanonicalDrawing                          â† Phase 1A model
```

The `notes` parameter of `DrawingParser.parse()` follows the existing convention
established in `frontend/routers/ui.py` line 255â€“256, where the first 512 bytes
of content are passed as `notes` for format sniffing.

---

## 6. Future Phases

### Phase 1B â€” PDF Vector Extraction

- `PdfDrawingParser` â€” PyMuPDF/pdfplumber, vector text extraction
- Actual title block extraction
- Dimension annotation detection from vector layer
- Tolerance extraction from dimension strings

### Phase 1C â€” OCR-Based Extraction

- `OcrDrawingParser` â€” Tesseract / easyocr for raster drawings
- GD&T symbol recognition
- DXF annotation extraction (`DxfDrawingParser` via ezdxf)

### Phase 1D â€” AI-Assisted Extraction

- VLM-based drawing interpretation
- Results always labelled `ADVISORY`
- Never override `DECLARED` or `EXTRACTED` results

### Phase 2A â€” CAD â†” Drawing Reconciliation

- Cross-reference `CanonicalDrawing` dimensions against `CanonicalGeometry`
- Conflict detection: drawing vs. CAD dimension mismatch
- Gap detection: features in CAD with no drawing annotation

---

## 7. File Locations

```
backend/interoperability/drawing.py                 â† canonical model + contract
tests/unit/interoperability/test_drawing.py         â† full test suite
docs/TECHNICAL_DRAWING_INTELLIGENCE_FOUNDATION.md  â† this document
```

---

## 8. Quick Usage Reference

```python
from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingDimension,
    DrawingIngestionResult,
    DrawingIngestionStatus,
    DrawingParser,
    DrawingSourceLocation,
    DrawingTitleBlock,
)
from decimal import Decimal

# Create a source location for provenance
loc = DrawingSourceLocation(
    source_id="upload::flange-4711.pdf",
    sheet_number=1,
    adapter_id="pdf-adapter",
    adapter_version="1.0.0",
)

# Create a dimension (Decimal, not float)
dim = DrawingDimension(
    dimension_id="d-flange-od",
    nominal_value=Decimal("120"),
    unit="mm",
    source_location=loc,
)

# Create a drawing
drawing = CanonicalDrawing(
    drawing_id="DWG-4711",
    source_id="upload::flange-4711.pdf",
    all_dimensions=(dim,),
    source_location=loc,
)

# Wrap in ingestion result
result = DrawingIngestionResult(
    source_id="upload::flange-4711.pdf",
    diagnostics=DrawingIngestionDiagnostics(
        status=DrawingIngestionStatus.VALID,
        parser_id="pdf-adapter",
        parser_version="1.0.0",
    ),
    document=drawing,
)

assert result.succeeded
assert result.document.sheet_count == 0   # no sheets declared yet
```

---

*Phase 1A â€” Model & Contract only. No OCR, no PDF parser, no AI extraction.*
