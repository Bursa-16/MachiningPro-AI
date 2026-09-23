# Vector PDF Technical Drawing Parsing Design

**Phase:** Technical Drawing Intelligence Phase 1B

**Status:** Design proposed; implementation requires explicit approval

**Date:** 2026-09-22

**Phase 1A baseline:** `backend/interoperability/drawing.py` at
`0c29d891609d1b029f570ec8ab71be83ff53a358`

## 1. Goal

Implement a deterministic, fail-closed parser for machine-generated vector PDF
technical drawings. The parser extracts explicitly represented title-block
fields, drawing metadata, dimensions, and numeric tolerances into the existing
Phase 1A `CanonicalDrawing` model while retaining source page, bounding-box,
and PDF-object provenance.

Phase 1B does not render PDFs, run OCR, recognize GD&T symbols, infer missing
engineering facts, use an AI/VLM, expose a new route, change the UI, or persist
anything to a database.

## 2. Repository Basis and Scope Resolution

The governing Phase 1A foundation assigns these capabilities to Phase 1B:

- a real vector PDF parser;
- vector text extraction;
- title-block extraction;
- dimension annotation detection;
- tolerance extraction from dimension strings.

`docs/TECHNICAL_DRAWING_INTELLIGENCE_FOUNDATION.md` contains a DXF conflict.
Its exclusions table assigns the DXF annotation parser to Phase 1B, while its
explicit future-phase sequence assigns `DxfDrawingParser` to Phase 1C. The
named Phase 1B heading and bullets are PDF-only. Therefore Phase 1B is PDF-only;
DXF remains out of scope until a dedicated specification resolves that conflict.

The existing CAD import route is also out of scope. It handles STEP, IGES, and
DXF geometry through `CadImportOrchestrator`; a drawing-PDF upload route has not
been specified. Phase 1B supplies a backend parser implementing the Phase 1A
`DrawingParser` contract, not frontend or route integration.

## 3. PDF Library and Dependency Decision

Use **pdfplumber 0.11.x**, declared as:

```toml
"pdfplumber>=0.11.10,<0.12"
```

in `[project].dependencies` in `pyproject.toml`.

Reasons:

- pdfplumber is MIT-licensed, compatible with this proprietary repository;
- it exposes positioned characters, words, lines, rectangles, curves, images,
  and annotations, which are the exact vector primitives required here;
- it operates on byte streams and builds on pdfminer.six without requiring an
  external executable;
- its extraction API exposes stable bounding-box coordinates suitable for
  provenance and deterministic spatial rules;
- its supported Python versions include the repository's Python 3.11 baseline.

Do not use PyMuPDF in Phase 1B. Its AGPL/commercial licensing introduces an
avoidable distribution obligation or commercial-license decision. Do not use
pypdf as the primary extractor because it does not provide the same convenient
positioned vector object surface. Do not add MarkItDown, OCR packages, rendering
engines, or image-analysis dependencies.

The dependency is required at runtime, not a development extra, because
`PdfDrawingParser` is product functionality. Transitive dependencies remain
managed by pdfplumber. No other dependency is approved by this design.

## 4. Modules and Public API

### 4.1 Exact production paths

- Existing canonical contract, minimally extended for spatial provenance:
  `backend/interoperability/drawing.py`
- New parser implementation:
  `backend/interoperability/pdf_drawing.py`
- Dependency declaration: `pyproject.toml`

Do not modify `backend/interoperability/__init__.py`. Phase 1A's public objects
are currently imported from their defining module, and Phase 1B follows that
pattern to avoid broadening the package-root API.

### 4.2 Provenance model extension

Add this immutable public model to `drawing.py`:

```python
@dataclass(frozen=True)
class DrawingBoundingBox:
    x0: Decimal
    top: Decimal
    x1: Decimal
    bottom: Decimal
    unit: str = "pt"
```

Validation is exact:

- all four coordinates must be `Decimal`;
- `x0 <= x1` and `top <= bottom`;
- `unit` must equal `"pt"`;
- coordinates use a page-local, top-left origin;
- one PDF point is 1/72 inch.

Extend `DrawingSourceLocation` with backward-compatible defaulted fields:

```python
bounding_box: DrawingBoundingBox | None = None
source_object_ids: tuple[str, ...] = field(default_factory=tuple)
```

Every object ID must be non-blank and unique within the tuple. Existing
constructors remain valid. Add `DrawingBoundingBox` to `drawing.py.__all__`.

### 4.3 Parser public interface

`backend/interoperability/pdf_drawing.py` exposes exactly:

```python
@dataclass(frozen=True)
class PdfDrawingLimits:
    max_file_bytes: int = 67_108_864
    max_pages: int = 200
    parse_timeout_seconds: float = 10.0
    max_objects_total: int = 200_000
    max_objects_per_page: int = 20_000
    max_text_characters: int = 2_000_000
    max_text_characters_per_object: int = 4_096
    max_vector_points_total: int = 1_000_000
    max_vector_points_per_object: int = 10_000
    max_dimension_candidates: int = 20_000
    max_title_block_candidates: int = 1_000
    max_page_dimension_points: int = 20_000
    max_diagnostics_per_kind: int = 50
    max_diagnostic_characters: int = 240

class PdfDrawingParser(DrawingParser):
    def __init__(self, *, limits: PdfDrawingLimits | None = None) -> None: ...
    def parser_id(self) -> str: ...
    def parser_version(self) -> str: ...
    def supports(
        self, source_id: str, file_name: str, notes: str | None = None
    ) -> bool: ...
    def parse(
        self,
        source_id: str,
        file_name: str,
        content: bytes,
        notes: str | None = None,
    ) -> DrawingIngestionResult: ...
```

`parser_id()` returns `"machiningpro.vector-pdf"` and `parser_version()` returns
`"1.0.0"`. The module's `__all__` contains only `PdfDrawingLimits` and
`PdfDrawingParser`. There is no second convenience parsing function and no
global mutable parser instance.

`PdfDrawingLimits.__post_init__` rejects booleans, non-positive values, and a
per-page object or point limit greater than its corresponding total.

`supports()` never raises. It returns true only when the case-insensitive file
suffix is `.pdf` or a supplied sniff string begins with `%PDF-`. It is a routing
hint, not validation. `parse()` independently validates the bytes.

## 5. Internal Extraction Representation

The parser uses private, frozen dataclasses; they are not canonical entities or
part of the public API:

```python
_PdfObjectRef(object_id, page_number, kind, bounding_box)
_PdfTextRun(ref, text)
_PdfVectorPath(ref, segments)
_PdfTextBlock(ref, text_run_ids, text)
_PdfPageSnapshot(
    page_number,
    width_pt,
    height_pt,
    text_runs,
    vector_paths,
    text_blocks,
    image_count,
)
_PdfDocumentSnapshot(pdf_version, pages)
```

Representation rules:

- Page numbers are one-based.
- All coordinates are converted at the library boundary with
  `Decimal(str(value))`; downstream recognition never uses binary floats.
- Coordinates are `(x0, top, x1, bottom)` PDF points with a top-left origin.
- Text runs come from positioned vector characters/words, not rendered pixels.
- Lines, rectangles, and curves are normalized to `_PdfVectorPath` segments.
- A text block is a deterministic grouping of adjacent text runs using fixed
  point-distance thresholds: baselines within 2 points and horizontal gaps no
  greater than 6 points join one line; vertically adjacent lines with left
  edges within 3 points and a vertical gap no greater than 3 points join one
  block. It is not a pdfplumber layout guess and cannot cross a page boundary.
- Images are counted only. Their bytes are never decoded, rendered, OCRed, or
  copied into a result.
- Rotated pages are normalized to the displayed page coordinate system before
  object ordering and provenance are assigned.
- PDF coordinate distance is used only for spatial association. It is never
  treated as a manufactured-part measurement.

Object IDs are stable content IDs:

```text
pdf-p{page:04d}-{kind}-{sha256(kind|bbox|normalized-content)[:16]}-{ordinal:04d}
```

The ordinal resolves exact duplicates after deterministic sorting. The digest
is of bounded normalized text or numeric geometry, never of the whole source.

## 6. Safe Parsing Boundary and Resource Limits

Before invoking pdfplumber, `parse()` performs these parent-process checks:

1. `source_id` and `file_name` are non-blank;
2. `content` is bytes-like and non-empty;
3. byte length is at most 67,108,864 bytes (64 MiB);
4. `%PDF-` occurs within the first 1,024 bytes;
5. the suffix/sniff combination does not positively identify another format.

The actual pdfplumber operation runs in a fresh process created with
`multiprocessing.get_context("spawn")`. The worker receives only immutable
bytes and limits and returns a bounded snapshot or a private error code. The
parent waits 10.0 seconds for the whole document. On timeout it calls
`terminate()`, waits one second, and calls `kill()` if the worker remains alive.
The result is `FAILED`; partial worker output is discarded.

The worker stops and reports a limit error as soon as any exact cap in
`PdfDrawingLimits` is crossed. The caps apply before objects or text are placed
in the inter-process payload. A declared page count over 200 is rejected before
page extraction. A page width or height over 20,000 points is rejected. Global
resource-limit breaches fail the whole document rather than returning a
misleading partial document.

The child-process boundary provides a hard wall-clock termination mechanism and
keeps parser faults out of the request process. Phase 1B does not claim a
portable hard RSS cap; compressed-stream expansion before pdfplumber exposes an
object remains a residual risk mitigated by the 64 MiB input cap, 10-second
process lifetime, page/object/text/point caps, and no rendering. A future
sandbox service may add an OS-enforced memory quota without changing the public
interface.

## 7. Vector, Raster, and Unsupported Detection

After structural PDF parsing:

- A page has vector evidence when it contains at least one positioned text run,
  line, rectangle, or curve.
- A PDF is vector-capable when at least one page has vector evidence.
- A valid PDF whose pages contain images but no vector evidence is raster-only
  and returns `UNSUPPORTED` with no document.
- A valid PDF with neither images nor vector evidence is `INSUFFICIENT_DATA`.
- An encrypted/password-protected PDF is `UNSUPPORTED`; Phase 1B never accepts
  or attempts passwords.
- Embedded files, multimedia, JavaScript, actions, external references,
  annotations, and form execution are ignored. Their presence never triggers
  execution or network/file access.

A vector-capable PDF that contains no unambiguous title-block field and no
unambiguous dimension is `INSUFFICIENT_DATA`; vector lines alone do not justify
fabricating a canonical drawing.

## 8. Title-Block and Drawing-Metadata Extraction

Title-block recognition is generic and layout-independent:

1. Build candidate regions from closed rectangles and connected orthogonal
   line grids on every page.
2. Attach text blocks whose centers are inside each candidate region.
3. Treat segments as horizontal/vertical when the opposite-axis delta is at
   most 0.5 point, and connect endpoints within 1 point. A candidate must have
   a closed perimeter, at least one internal horizontal separator, at least one
   internal vertical separator, and at least four contained text blocks.
4. Score each candidate exactly: 4 points for the closed perimeter, 2 points
   for having both separator directions, 3 points per distinct recognized
   label capped at 18, and 2 points per label with one unique adjacent nonblank
   value capped at 12.
5. Accept a candidate only when its score is at least 15 and it has at least
   two distinct recognized label/value pairs. Position contributes no score. A
   title block may occur at any page edge or interior location.
6. If two candidates share the highest score, omit the title block as
   ambiguous. If a field has two equally plausible values, omit that field and
   warn. Candidate coordinates are used only to produce deterministic warning
   order, never to break a semantic tie.

The vocabulary is repository-owned, case-insensitive, Unicode-normalized, and
contains generic concepts and common abbreviations only: drawing number, part
number, title/description, material, scale, sheet, revision, drawn by, checked
by, approved by, date, and units. It contains no customer name, logo, template
coordinate, or customer-specific drawing-number pattern.

Values are accepted only from the same grid cell or the immediately adjacent
cell to the right or below the label. Label text is never used as its own value.
The parser does not guess missing fields. Exact field mapping is:

| Recognized field | Canonical target |
|---|---|
| drawing number | `DrawingTitleBlock.drawing_number` |
| part number | `DrawingTitleBlock.part_number` |
| title/description | `DrawingTitleBlock.part_name` |
| material | `DrawingTitleBlock.material_raw` and one `DrawingMaterialNote` |
| scale | `DrawingTitleBlock.scale`, corresponding `DrawingSheet.scale` |
| sheet N of M | `DrawingTitleBlock.sheet_number/sheet_count` |
| revision | `DrawingRevision.revision_code` and both revision fields |
| drawn by | `DrawingTitleBlock.author` |
| checked by | `DrawingTitleBlock.checker` |
| approved by | `DrawingTitleBlock.approver` |
| date | `DrawingTitleBlock.date_text`; it remains unparsed text |
| explicitly declared unit | `CanonicalDrawing.metadata["drawing.unit"]` |

Material is retained as raw declared text; Phase 1B does not normalize it.
Revision tables outside the accepted title-block region are not parsed.

Technical PDF metadata is allowlisted into `CanonicalDrawing.metadata`:
`pdf.version`, `pdf.page_count`, `pdf.vector_object_count`,
`pdf.text_character_count`, and per-page `width_pt`, `height_pt`, and `rotation`.
Free-form PDF Info/XMP fields such as author, title, subject, keywords, creator,
and producer are not copied. They are not reliable drawing metadata and may
leak arbitrary source content.

### 8.1 Task 5 contract addendum (normative)

This subsection resolves the Task 5 vocabulary, pairing, provenance, and
ambiguity rules. It narrows Section 8; it does not add a new canonical field or
expand Phase 1B scope. If a shorter statement elsewhere in this document or in
the implementation plan is open to multiple interpretations, this subsection
controls for Task 5.

#### 8.1.1 Canonical metadata allowlist

Task 5 may populate only these existing canonical fields:

| Field key used internally | Canonical target |
|---|---|
| `drawing_number` | `DrawingTitleBlock.drawing_number` |
| `part_number` | `DrawingTitleBlock.part_number` |
| `part_name` | `DrawingTitleBlock.part_name` |
| `material` | `DrawingTitleBlock.material_raw` and one `DrawingMaterialNote.raw_text` |
| `scale` | `DrawingTitleBlock.scale` and the accepted candidate page's `DrawingSheet.scale` |
| `sheet` | `DrawingTitleBlock.sheet_number` and optional `sheet_count` |
| `revision` | one `DrawingRevision.revision_code`, shared by `DrawingTitleBlock.revision` and `CanonicalDrawing.revision` |
| `author` | `DrawingTitleBlock.author` |
| `checker` | `DrawingTitleBlock.checker` |
| `approver` | `DrawingTitleBlock.approver` |
| `date` | `DrawingTitleBlock.date_text` |
| `unit` | `CanonicalDrawing.metadata["drawing.unit"]` |

Task 5 does not populate `DrawingRevision.description`, `date_text`, `author`,
or `approver`; those values require revision-table semantics that are outside
the accepted title-block contract. Organization, project, customer, company,
logo, document-type, and approval-status fields are not canonical Task 5
fields. They must not be added to `CanonicalDrawing.metadata` as a workaround.

The complete technical metadata allowlist and exact key spelling is:

- `drawing.unit`, only when an explicit accepted `unit` field exists;
- `pdf.version`;
- `pdf.page_count`;
- `pdf.vector_object_count`;
- `pdf.text_character_count`;
- `pdf.page.{page_number:04d}.width_pt`;
- `pdf.page.{page_number:04d}.height_pt`;
- `pdf.page.{page_number:04d}.rotation`.

All metadata values are strings because the existing model is
`dict[str, str]`. Decimal values use the Task 4 plain-decimal form, integer
counts and rotations use base-10 digits without padding, and keys are inserted
in lexicographic order. No other PDF Info, XMP, filename, path, or parser
metadata key is allowed.

#### 8.1.2 Exact generic label aliases

The label dictionary contains exactly these 27 normalized aliases. An alias
maps to one internal field key and no alias is inferred or generated at
runtime.

| Canonical field key | Exact normalized aliases |
|---|---|
| `drawing_number` | `DRAWING NO`, `DRAWING NUMBER`, `DWG NO`, `DWG NUMBER` |
| `part_number` | `PART NO`, `PART NUMBER` |
| `part_name` | `TITLE`, `DESCRIPTION`, `PART NAME` |
| `material` | `MATERIAL`, `MATL` |
| `scale` | `SCALE` |
| `sheet` | `SHEET`, `SHEET NO`, `SHEET NUMBER` |
| `revision` | `REV`, `REVISION` |
| `author` | `DRAWN`, `DRAWN BY` |
| `checker` | `CHECKED`, `CHECKED BY` |
| `approver` | `APPROVED`, `APPROVED BY` |
| `date` | `DATE`, `DRAWING DATE` |
| `unit` | `UNIT`, `UNITS` |

These aliases are generic English engineering labels. Task 5 does not perform
translation, fuzzy matching, stemming, edit-distance matching, logo matching,
or customer-specific abbreviation expansion. Additional languages and aliases
require a separately reviewed specification change.

#### 8.1.3 Label and value matching

Label matching uses this exact normalization pipeline:

1. Apply Unicode NFKC.
2. Reject a candidate label containing a control character.
3. Convert letters to uppercase.
4. Replace each period, underscore, or hyphen with one ASCII space.
5. Collapse all Unicode whitespace runs to one ASCII space and trim both ends.
6. Remove one trailing colon and surrounding whitespace from a label-only
   fragment, then repeat whitespace collapse.
7. Compare the whole normalized fragment to the alias table.

Other punctuation remains significant and therefore prevents a match.
Abbreviations match only because they appear literally in the table. There is
no prefix or substring match for a label-only block.

Pairing is evaluated in this fixed precedence order:

1. **Inline colon:** one text line has an exact alias before its first colon
   and a nonblank value after it. Later colons belong to the value, so
   `SCALE: 1:2` remains valid.
2. **Adjacent runs on one line:** a leading contiguous sequence of Task 4 text
   runs normalizes to one exact alias; one or more remaining runs to its right
   form the value. A run boundary, not a string-prefix guess, separates them.
3. **Same grid cell:** an exact label-only text block and exactly one nonlabel
   value block occupy the same derived cell.
4. **Immediately adjacent right cell.**
5. **Immediately adjacent below cell.**

For ranks 2 through 5, the label and value bounding boxes must be no more than
72 points apart. Distance is the maximum of their horizontal and vertical
axis-aligned gaps, with overlap contributing a zero gap. Right-cell pairing
also requires vertical cell overlap; below-cell pairing requires horizontal
cell overlap. A cell is adjacent only when it shares a separator boundary with
the label cell. Diagonal, second-cell, nearest-text, and unrestricted spatial
searches are forbidden. The label text can never serve as its own value, and a
value fragment that itself matches any label alias is rejected.

Value validation uses an NFKC comparison copy, but the canonical value is not
uppercased. Values are stripped at both ends, free of control characters other
than an allowed multiline newline, and at most 256 Unicode code points.
Single-line internal whitespace is collapsed to one ASCII space except for
`material` and `date`, whose accepted source spelling is retained after outer
trimming. Additional field caps are: 128 characters for drawing number, part
number, author, checker, and approver; 64 for date; and 32 for scale, sheet,
revision, and unit. `part_name` and `material` use the 256 character global
cap.

Field validation is conservative:

- `sheet` accepts an anchored positive integer `N`, `N OF M`, or `N/M`, where
  `N` and `M` are at most 10,000 and `N <= M`. `N` alone leaves
  `DrawingTitleBlock.sheet_count` as `None`.
- `scale` accepts an anchored positive decimal ratio `A:B`, `NTS`, or
  `NOT TO SCALE`. Whitespace around the ratio colon is removed in the
  canonical value; no scale is calculated.
- `unit` accepts only `MM`, `MILLIMETER`, `MILLIMETERS`, `IN`, `INCH`, or
  `INCHES`. The canonical value is respectively `mm` or `inch`.
- Other fields require a nonblank value within their cap. Dates remain
  unparsed text, material remains declared text, and identifiers retain case.

#### 8.1.4 Page and title-block representation

Every structurally extracted PDF page is represented by one `DrawingSheet`.
`DrawingSheet.sheet_number` is the one-based PDF page number and
`DrawingSheet.sheet_count` is the PDF page count. These describe the PDF
container and are not overwritten by a declared title-block `sheet` value.
The declared `N` and optional `M` are stored only in
`DrawingTitleBlock.sheet_number` and `sheet_count`. A mismatch is retained as
declared data with one bounded constant warning; it is not silently reconciled.

Each `DrawingSheet.source_location` has the caller's `source_id`, its one-based
page and sheet number, the parser ID/version, `EXTRACTED` authority, and a
bounding box of `(0, 0, page_width, page_height)` in points. It has no
`original_text`, `view_id`, or invented source-object ID.

The accepted title-block region is represented by
`DrawingTitleBlock.source_location`. Its bounding box is the candidate
perimeter. Its `source_object_ids` contain the vector paths forming the
perimeter/separators followed by the label/value text-run IDs that support
accepted fields. Each group is de-duplicated and sorted by the Task 4 object
ordering.
`original_text` is `None`: an aggregate title block is not a license to expose
all contained text. `DrawingRevision` and `DrawingMaterialNote` each receive a
separate location containing only their exact label/value evidence and exact
accepted value in `original_text`.

No new canonical page-metadata or provenance model is introduced. In
particular, title-block coordinates are not duplicated into arbitrary metadata
keys.

#### 8.1.5 Multiline values

Only `part_name` and `material` may be multiline. A multiline value must
already be one Task 4 `_PdfTextBlock`, contain exactly two nonblank lines, and
remain in one derived grid cell. Task 5 never joins separate text blocks to
manufacture a multiline value. Blank intervening lines, more than two lines,
a line that matches a label alias, or a second value block in the same target
cell makes the field ambiguous and therefore omitted.

For `part_name`, trim each line, collapse its internal whitespace, and join the
two lines with one ASCII space. For `material`, remove only outer whitespace
from each line and join the lines with `\n`, preserving declared line content.
The provenance bounding box is the union of the exact contributing text-run
boxes and its source-object IDs follow Task 4 order. The joined value remains
subject to the 256-character cap.

#### 8.1.6 Candidate construction, scoring, and ordering

Candidate construction consumes only the immutable Task 4 page snapshots:

- Curves are not title-block evidence. A line or rectangle segment is
  horizontal or vertical only under the existing 0.5-point opposite-axis
  tolerance.
- Two orthogonal segments are connected when endpoints are within 1 point, or
  when an endpoint meets the other segment within 1 point. Processing is
  page-local.
- Candidate perimeters come from an explicit closed rectangle path or a
  closed rectangle formed by connected orthogonal segments. Perimeter sides
  must be continuously covered with no uncovered gap greater than 1 point.
- A candidate includes connected segments inside or touching its perimeter.
  It must have at least one internal horizontal and one internal vertical
  separator connected to the perimeter or another separator, positive area,
  and at least four contained nonblank text blocks. Text-block center points
  on the perimeter count as inside.
- Grid cells are the bounded regions formed by the perimeter and connected
  separators. Before scoring, structurally identical candidates are
  de-duplicated by `(page, bounding_box, sorted_geometry_object_ids)`.
  Candidate enumeration then sorts page, top, left, bottom, right, and
  contributing object IDs before applying the existing
  `max_title_block_candidates` limit. Exceeding that limit is the existing
  resource-limit failure for the whole document; candidates are not silently
  truncated.
- Label density is the number of contained text blocks that contain a label
  recognized by Section 8.1.3 divided by the number of contained nonblank text
  blocks. It must be at least `0.20` in addition to the existing score and
  pair-count thresholds.

Scoring remains exactly Section 8's integer formula. Distinct labels are
distinct internal field keys, not alias spellings. A field contributes to the
pair score only when one value survives the matching and conflict rules.
Candidate position is never a score component. Candidate order is exactly
`(-score, page, top, x0, bottom, x1, source_object_ids)`.

Task 5 uses private frozen evidence records, never dictionaries or parser
objects:

```python
@dataclass(frozen=True)
class _TitleFieldEvidence:
    field_key: str
    value: str
    pairing_rank: int
    page_number: int
    bounding_box: DrawingBoundingBox
    source_object_ids: tuple[str, ...]
    original_text: str

@dataclass(frozen=True)
class _TitleBlockCandidate:
    page_number: int
    bounding_box: DrawingBoundingBox
    source_object_ids: tuple[str, ...]
    score: int
    recognized_field_keys: tuple[str, ...]
    field_evidence: tuple[_TitleFieldEvidence, ...]
```

The records remain private to `pdf_drawing.py` and do not cross the public
parser boundary.

#### 8.1.7 Duplicate and conflict resolution

Resolve evidence in this order:

1. Reject candidates below any structural, density, score, or pair threshold.
2. Select the unique highest-scoring accepted candidate across the document.
   If two or more candidates share that score, omit the entire title block and
   emit one bounded ambiguity warning. Coordinates and page order do not break
   the semantic tie.
3. Within the selected candidate and one canonical field, retain evidence at
   the best available pairing rank from Section 8.1.3.
4. If all best-rank evidence normalizes to the same canonical value, merge its
   boxes and object IDs deterministically and emit one value.
5. If best-rank evidence contains different canonical values, omit that field
   and emit one bounded field-conflict warning. Lower-ranked evidence and
   source order never choose between conflicting best-rank values.

An explicit inline pair may therefore outrank loose cell evidence, but source
order never resolves a semantic conflict. Missing optional fields do not by
themselves make a successful title block partial. Omitted conflicting fields
produce `PARTIAL` when other usable canonical content remains. A tied title
candidate with no dimension content produces `INSUFFICIENT_DATA`, consistently
with Sections 7 and 12. The only Task 5 warning codes are
`PDF_TITLE_BLOCK_AMBIGUOUS`, `PDF_TITLE_FIELD_CONFLICT`, and
`PDF_TITLE_SHEET_MISMATCH`; they use constant messages and never include field
names or source values.

#### 8.1.8 Security and boundedness

The alias table is the fixed 27-entry table above. Candidate count is bounded
by `PdfDrawingLimits.max_title_block_candidates`; input objects, text, and
diagnostics retain the Task 3/4 limits; every accepted field is bounded by the
limits in Section 8.1.3. Diagnostics use constant templates, never accepted or
rejected values, full-page text, filenames, filesystem paths, exception text,
or tracebacks.

Canonical output may contain only accepted allowlisted field values and their
exact bounded provenance tokens. It contains no full-page text dump, raw PDF
bytes, image payload, pdfplumber object, arbitrary source dictionary, PDF
Info/XMP content, or candidate-debug payload. Task 5 performs no file, network,
embedded-file, action, JavaScript, OCR, or raster processing.

#### 8.1.9 Required focused tests

Task 5 must add these focused cases to
`tests/unit/interoperability/test_pdf_drawing.py` under the exact class
`TestPdfDrawingTask5`:

- `test_detects_same_title_block_in_all_approved_locations`;
- `test_builds_candidates_from_rectangles_and_connected_lines`;
- `test_rejects_structurally_insufficient_and_low_density_regions`;
- `test_scores_orders_deduplicates_and_rejects_tied_candidates`;
- `test_title_candidate_limit_fails_closed_without_truncation`;
- `test_every_approved_alias_maps_to_one_canonical_field`, parameterized over
  all 27 aliases;
- `test_label_normalization_is_exact_and_bounded`;
- `test_unapproved_fuzzy_prefix_translated_and_customer_labels_do_not_match`;
- `test_pairing_precedence_and_72_point_boundary_are_exact`;
- `test_maps_only_approved_title_revision_material_sheet_and_unit_fields`;
- `test_metadata_uses_exact_allowlisted_keys_and_string_values`;
- `test_pdf_info_xmp_and_unapproved_fields_never_surface`;
- `test_multiline_policy_accepts_only_two_line_title_and_material`;
- `test_duplicate_and_conflicting_evidence_follow_exact_resolution`;
- `test_page_and_field_provenance_is_typed_minimal_and_deterministic`;
- `test_task5_repeated_parse_and_serialization_are_deterministic`;
- `test_task5_output_contains_no_task6_or_unapproved_semantics`;
- `test_task5_diagnostics_and_repr_are_bounded_and_redacted`; and
- `test_malformed_normalized_title_evidence_fails_closed`.

These named tests include the boundary/negative cases described by their
surrounding subsections. The full existing Task 1-4 drawing/PDF suites are the
regression gate.

The exact Task 5 focused command remains:

```powershell
py -m pytest tests/unit/interoperability/test_pdf_drawing.py -q
```

## 9. Conservative Dimension and Tolerance Recognition

Recognition operates on bounded text blocks after accepted title-block regions
have been excluded. Matching uses fully anchored patterns after Unicode NFKC
normalization for matching only. Original matched text is retained, bounded to
256 characters, in provenance.

Phase 1B accepts:

- explicit linear values with units: `25 mm`, `1.250 in`;
- diameter values: `DIA 25 mm`, `Ø25 mm`, `⌀25 mm`;
- radius values: `R5 mm`, `RAD 5 mm`;
- angular values: `45°`, `45 deg`;
- symmetric tolerances: `25 ±0.10 mm`;
- asymmetric/unilateral tolerances: `25 +0.20/-0.10 mm`,
  `25 +0.20/0 mm`, and `25 +0/-0.10 mm`.

Whitespace and decimal-comma variants are normalized only when the token has a
single unambiguous numeric convention. Thousands separators, mixed separators,
fractions, dual dimensions, reference dimensions, basic dimensions, ordinate
sets, fit classes, stacked limit dimensions, and general-tolerance tables are
not extracted in Phase 1B.

A bare number without a prefix, unit, angle symbol, or tolerance is accepted
only if all of these deterministic geometry cues exist:

- one nearby dimension-line segment;
- the dimension line is horizontal or vertical within a 0.5-point axis delta
  and is at least 6 points long;
- two terminating extension or witness segments, each perpendicular within the
  same 0.5-point axis delta and meeting a dimension-line endpoint within 2
  points;
- the text block lies within a fixed 12-point band around that dimension line;
- the candidate is outside title and revision regions;
- it does not match a date, scale, sheet count, revision, or identifier context;
- an explicit sheet/title-block units declaration exists.

When those cues are absent, the number is ignored. The parser never assumes
millimetres or inches. Unit precedence is: explicit token unit, then explicit
sheet/title-block unit; otherwise the candidate is omitted with a bounded safe
warning. Supported canonical units are `mm`, `inch`, and `degree`.

Numeric values are constructed directly as `Decimal`. The mapping is:

- plain value -> `DrawingDimension`, no tolerance;
- `±x` -> `DrawingToleranceType.SYMMETRIC`, upper `x`, lower `-x`;
- `+x/-y` -> `ASYMMETRIC`, upper `x`, lower `-y`;
- `+x/0` -> `UNILATERAL_PLUS`, upper `x`, lower `0`;
- `+0/-y` -> `UNILATERAL_MINUS`, upper `0`, lower `-y`.

Limit dimensions are deliberately omitted despite the Phase 1A enum because
deriving a nominal value would invent data. Every tolerance is attached to its
dimension and repeated in `CanonicalDrawing.all_tolerances` by object identity.
No referenced geometry IDs are populated; CAD/drawing reconciliation is Phase
2A. No GD&T, datum, surface-finish, weld, or feature semantics are created.

## 10. Canonical Population and Provenance

For each successfully extracted PDF page, create one `DrawingSheet` with the
PDF page number as `sheet_number`. Create one `DrawingView` of type `UNKNOWN`
per page only when that page has accepted dimensions; it is a page extraction
container, not an inferred engineering view. Its deterministic ID is
`pdf-view-p{page:04d}`.

Top-level IDs are deterministic:

- drawing: `pdf-drawing-{sha256(content)[:24]}`;
- dimension: `pdf-dim-p{page:04d}-{ordinal:06d}`;
- tolerance: `pdf-tol-p{page:04d}-{ordinal:06d}`;
- material note: `pdf-material-p{page:04d}-{ordinal:06d}`.

Every `DrawingSheet`, `DrawingView`, title block, revision, material note,
dimension, and tolerance gets a `DrawingSourceLocation` containing:

- the caller-provided `source_id`;
- one-based page and sheet numbers;
- view ID where applicable;
- the union bounding box of the exact contributing source objects;
- deterministically ordered contributing object IDs;
- parser ID and version;
- `DrawingExtractionAuthority.EXTRACTED`;
- original text only for the exact accepted token/field, never an entire page.

Confidence is not populated. Rule-based acceptance is binary, and a fabricated
confidence score would be misleading. The top-level location has no bounding
box or original text.

`CanonicalDrawing.all_dimensions` is the page/view dimensions flattened in
the same order. `all_tolerances` follows dimension order. Title block revision
is the same immutable `DrawingRevision` instance as `CanonicalDrawing.revision`.
Empty GD&T, datum, heat-treatment, and surface-finish collections remain empty.

## 11. Determinism

Given identical bytes, limits, and parser version, the result must compare
equal across repeated runs on the same supported pdfplumber minor series.

Rules:

- normalize rotations and convert every coordinate to `Decimal` immediately;
- sort pages by one-based page number;
- sort text and path objects by
  `(top, x0, bottom, x1, kind, normalized_content, source_index)`;
- group lines/blocks with fixed point thresholds, never adaptive randomness;
- sort title candidates by
  `(-score, page, top, x0, bottom, x1, object_ids)`;
- sort accepted dimensions by
  `(page, top, x0, bottom, x1, normalized_text, object_ids)`;
- use stable hashes and deterministic duplicate ordinals for IDs;
- preserve tuple ordering; never expose set/dict iteration order;
- format metadata decimals with fixed plain decimal formatting;
- cap and sort diagnostics by `(code, page, object_id)` before rendering their
  fixed safe message templates;
- never include wall-clock time, process ID, random UUID, temporary path, or
  library exception text in the result.

## 12. Status and Error Semantics

The existing `DrawingIngestionStatus` contract is authoritative:

| Condition | Status | Document |
|---|---|---|
| All pages parse; at least one unambiguous title field or dimension; no required extraction was dropped | `VALID` | present |
| Usable canonical content exists, but a page or otherwise valid candidate is skipped for a recoverable ambiguity/page-local defect | `PARTIAL` | present |
| Structurally valid vector PDF but no unambiguous canonical field/dimension | `INSUFFICIENT_DATA` | `None` |
| Non-PDF, encrypted PDF, raster-only PDF, or unsupported PDF feature required for extraction | `UNSUPPORTED` | `None` |
| Malformed/truncated/corrupt PDF, timeout, worker crash, or any resource-limit breach | `FAILED` | `None` |

The parser catches library and worker exceptions at its boundary. Diagnostics
use fixed codes/messages such as `PDF_MALFORMED`, `PDF_TIMEOUT`,
`PDF_RESOURCE_LIMIT`, `PDF_RASTER_ONLY`, `PDF_ENCRYPTED`, and
`PDF_INSUFFICIENT_VECTOR_DATA`. They do not contain exception messages,
tracebacks, filenames, paths, raw bytes, arbitrary page text, or PDF metadata.

`format_detected` is `"PDF"` after a PDF header is confirmed and `None` before
confirmation. Expected and parsed page counts are populated only from bounded
integers. `PARTIAL` is never used for a global security/resource failure.

## 13. Security and Leakage Rules

- Parse from `BytesIO` inside the worker; create no temporary files.
- Do not render pages or decode image streams.
- Do not execute JavaScript, actions, launch directives, forms, multimedia, or
  embedded files.
- Do not follow URLs, file specifications, external streams, or network links.
- Do not accept passwords or attempt decryption.
- Do not log or emit raw PDF bytes, content streams, arbitrary page text,
  document Info/XMP values, exception messages, or tracebacks.
- Canonical output may contain only accepted bounded engineering fields and
  their exact bounded source tokens. This is required provenance, not a general
  text dump.
- Diagnostics are selected from constant templates and bounded in count/length.
- Unsupported and failed results carry no `CanonicalDrawing` and therefore no
  extracted content.
- Never create fake geometry, topology, drawing views, dimensions, tolerances,
  or metadata to make a result appear more complete.

## 14. Synthetic Fixture Strategy

Create `tests/unit/interoperability/pdf_fixtures.py`, a test-only deterministic
PDF byte builder using only the standard library. It writes minimal PDF 1.4
objects, xref offsets, page trees, built-in Type 1 Helvetica text, vector
line/rectangle operators, and optional image XObjects. It must not depend on
pdfplumber or copy any third-party/customer drawing.

Fixtures are generated in memory and have fixed object ordering and bytes:

- title blocks in lower-right, lower-left, upper-left, and interior positions;
- a grid with generic labels and adjacent values;
- linear, radius, diameter, angular, symmetric, asymmetric, and unilateral
  dimension strings;
- bare-number dimension with and without valid line cues;
- explicit sheet unit and missing-unit cases;
- multi-page and rotated-page vector drawings;
- duplicate/ambiguous title candidates;
- vector-only, mixed vector/image, raster-only, and empty PDFs;
- malformed header, truncated xref/trailer, corrupt page, and encrypted marker;
- page/object/text/vector-point/count-limit boundary cases;
- strings resembling dates, scales, revisions, and drawing numbers;
- malicious-looking JavaScript/action/link/attachment tokens proving they are
  ignored and never surfaced;
- sentinel source text and exception text proving diagnostics do not leak it.

No binary fixture is checked in unless the test builder cannot represent the
case; any exception requires a separate license/source note and approval.

## 15. Test and Verification Contract

Focused implementation commands, in order:

```powershell
py -m pytest tests/unit/interoperability/test_drawing.py -q
py -m pytest tests/unit/interoperability/test_pdf_drawing.py -q
py -m pytest tests/unit/interoperability/test_drawing.py tests/unit/interoperability/test_pdf_drawing.py -q
py -m ruff check backend/interoperability/drawing.py backend/interoperability/pdf_drawing.py tests/unit/interoperability/pdf_fixtures.py tests/unit/interoperability/test_drawing.py tests/unit/interoperability/test_pdf_drawing.py
git diff --check -- pyproject.toml backend/interoperability/drawing.py backend/interoperability/pdf_drawing.py tests/unit/interoperability/pdf_fixtures.py tests/unit/interoperability/test_drawing.py tests/unit/interoperability/test_pdf_drawing.py docs/superpowers/specs/2026-09-22-vector-pdf-drawing-parse-design.md docs/superpowers/plans/2026-09-22-vector-pdf-drawing-parse.md
```

Do not run the full repository suite unless a focused failure proves broader
impact. Tests must cover public behavior, canonical equality on repeated parses,
the spawned timeout path, exact limit boundaries, safe statuses, provenance,
and absence of raw sentinels/tracebacks from diagnostics.

## 16. Files Expected During Implementation

Create:

- `backend/interoperability/pdf_drawing.py`
- `tests/unit/interoperability/pdf_fixtures.py`
- `tests/unit/interoperability/test_pdf_drawing.py`

Modify:

- `pyproject.toml`
- `backend/interoperability/drawing.py`
- `tests/unit/interoperability/test_drawing.py`

Planning documents created before implementation:

- `docs/superpowers/specs/2026-09-22-vector-pdf-drawing-parse-design.md`
- `docs/superpowers/plans/2026-09-22-vector-pdf-drawing-parse.md`

No frontend, template, route, orchestrator, database, migration, CAD geometry,
CAD topology, DXF, OCR, GD&T, or AI/VLM file belongs to Phase 1B.

## 17. Acceptance Criteria

Phase 1B is complete only when:

1. pdfplumber is the only new runtime PDF dependency and its version range is
   the one specified here.
2. `PdfDrawingParser` implements the Phase 1A contract without changing its
   signature or status invariants.
3. Vector, raster-only, encrypted, unsupported, malformed, empty, and
   insufficient PDFs receive the exact safe semantics above.
4. Generic title-block detection is independent of customer layouts.
5. Only conservative supported dimension/tolerance forms are emitted.
6. No unit, value, title field, geometry reference, or view type is inferred
   when source evidence is absent.
7. Every emitted drawing object has deterministic source page, bounding box,
   and object provenance where applicable.
8. Repeated parsing produces equal canonical results and diagnostics.
9. All exact resource limits are enforced fail-closed through the spawned
   worker boundary.
10. Raw bytes, arbitrary content, PDF metadata, exceptions, and tracebacks do
    not leak into diagnostics or failed/unsupported results.
11. All synthetic fixture and focused regression tests pass.
12. Targeted Ruff and the scoped `git diff --check` pass.
13. No frontend, database, DXF, OCR, GD&T, AI/VLM, or unrelated dirty-tree file
    is changed.

## 18. Known Risks

- pdfplumber/pdfminer behavior can change across minor releases; the dependency
  is constrained to 0.11.x and deterministic fixtures guard the API contract.
- PDF internals are adversarially complex. The worker timeout and caps reduce
  exposure but are not an OS-level memory sandbox.
- Font encodings may yield missing or substituted Unicode. Ambiguous tokens are
  omitted rather than repaired or guessed.
- Generic title-block and dimension heuristics intentionally trade recall for
  precision; real drawings may return `PARTIAL` or `INSUFFICIENT_DATA`.
- The existing canonical title block has one aggregate source location rather
  than per-scalar-field provenance. Its bounding box and contributing object-ID
  tuple retain auditable evidence without redesigning the Phase 1A model.
- Spawned-process behavior is platform-sensitive. Tests must run on Windows and
  remain compatible with POSIX spawn semantics; worker entry points must be
  module-level and pickleable.

## 19. Source References

Repository:

- `docs/TECHNICAL_DRAWING_INTELLIGENCE_FOUNDATION.md`, especially sections 2,
  3, 5, and 6
- `backend/interoperability/drawing.py`
- `tests/unit/interoperability/test_drawing.py`
- `Programlar/MachiningPro_AI_Proje_Plani_16.9.2026.md`, Phase 1 technical
  drawing/CAD reading
- `MachineryPro_AI_Universal_Interoperability_Architecture_Roadmap.md`, drawing
  intelligence and PDF/DXF pipeline sections
- Git history: Phase 1A commit `05c4ff3`; current baseline `0c29d89`

Primary dependency sources:

- pdfplumber package metadata: https://pypi.org/project/pdfplumber/
- pdfplumber extraction API: https://github.com/jsvine/pdfplumber/blob/stable/README.md
- pdfplumber MIT license: https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt
- PyMuPDF license documentation: https://pymupdf.readthedocs.io/_/downloads/en/latest/pdf/
