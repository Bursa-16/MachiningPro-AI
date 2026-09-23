"""
backend/interoperability/drawing.py
====================================
Phase 1A — Canonical Technical Drawing Model & Ingestion Contract
MachiningPro AI

Provides the canonical domain representation for technical drawings and
the parser/adapter interface contract.

SCOPE OF THIS MODULE
--------------------
- Canonical drawing model (CanonicalDrawing and all sub-models)
- Drawing parser/adapter interface (DrawingParser)
- Drawing ingestion result contract (DrawingIngestionResult)
- Fail-closed validation for model integrity
- Provenance and authority semantics for drawing information

OUT OF SCOPE (Phase 1B/1C)
--------------------------
- OCR / Tesseract integration
- PyMuPDF / pdfplumber / pypdf parsing logic
- AI / VLM extraction
- GD&T symbol recognition
- Actual title block extraction
- Actual dimension detection
- CAD ↔ drawing reconciliation
- Manufacturing feature recognition changes

ARCHITECTURAL RULES
-------------------
- Reuses existing EngineeringSource, Provenance from the live repository.
- Numeric values use Decimal (never float) following existing conventions.
- All models are frozen dataclasses (immutable).
- Fail-closed: unknown/malformed content never silently becomes authoritative.
- No AI result may become authoritative in Phase 1A.
- Authority and result-status enums reference existing enums.py where possible;
  new drawing-specific variants are introduced only where no equivalent exists.

INTEGRATION POINTS
------------------
    from backend.interoperability.drawing import (
        CanonicalDrawing,
        DrawingIngestionResult,
        DrawingParser,
    )
    from backend.interoperability.models import EngineeringSource
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum, unique

# ---------------------------------------------------------------------------
# Drawing-specific enums
#
# NOTE: Before introducing these, inspect backend/interoperability/enums.py.
# If equivalent authority/status concepts already exist there, import them
# instead of the local definitions below.
# The names below follow the spec's authority semantics; rename to match
# whatever equivalents exist in the live enums.py.
# ---------------------------------------------------------------------------


@unique
class DrawingExtractionAuthority(StrEnum):
    """
    Authority level of a piece of information extracted from a drawing.

    Inspect backend/interoperability/enums.py — if an equivalent enum
    (e.g. Authority, ProvenanceLevel, SourceAuthority) already exists,
    remove this class and import that one instead.
    """
    DECLARED = "DECLARED"           # Explicitly stated in the source document
    EXTRACTED = "EXTRACTED"         # Extracted by a parser from source content
    INFERRED = "INFERRED"           # Inferred from context / heuristic
    ADVISORY = "ADVISORY"           # AI-suggested; never authoritative in 1A


@unique
class DrawingIngestionStatus(StrEnum):
    """
    Outcome of a drawing ingestion attempt.

    Inspect backend/interoperability/exchange.py and result.py — if an
    equivalent result/status enum already exists, remove this class and
    import that one instead.
    """
    VALID = "VALID"                         # All mandatory content parsed
    PARTIAL = "PARTIAL"                     # Some content parsed; gaps present
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA" # Too little data to be useful
    UNSUPPORTED = "UNSUPPORTED"             # Format/content not supported
    FAILED = "FAILED"                       # Adapter raised an error


@unique
class DrawingViewType(StrEnum):
    """Standard engineering view types."""
    FRONT = "FRONT"
    TOP = "TOP"
    RIGHT = "RIGHT"
    LEFT = "LEFT"
    BOTTOM = "BOTTOM"
    BACK = "BACK"
    ISOMETRIC = "ISOMETRIC"
    SECTION = "SECTION"
    DETAIL = "DETAIL"
    AUXILIARY = "AUXILIARY"
    UNKNOWN = "UNKNOWN"


@unique
class DrawingDimensionType(StrEnum):
    """Type of a dimension annotation."""
    LINEAR = "LINEAR"
    RADIAL = "RADIAL"
    DIAMETRAL = "DIAMETRAL"
    ANGULAR = "ANGULAR"
    ARC_LENGTH = "ARC_LENGTH"
    ORDINATE = "ORDINATE"
    UNKNOWN = "UNKNOWN"


@unique
class DrawingToleranceType(StrEnum):
    """How a tolerance is expressed."""
    SYMMETRIC = "SYMMETRIC"         # ±value
    ASYMMETRIC = "ASYMMETRIC"       # +upper / -lower
    LIMIT = "LIMIT"                 # max / min stated
    UNILATERAL_PLUS = "UNILATERAL_PLUS"   # +value / 0
    UNILATERAL_MINUS = "UNILATERAL_MINUS" # 0 / -value
    UNKNOWN = "UNKNOWN"


@unique
class DrawingNoteCategory(StrEnum):
    """Semantic category of a drawing note."""
    GENERAL = "GENERAL"
    MATERIAL = "MATERIAL"
    HEAT_TREATMENT = "HEAT_TREATMENT"
    SURFACE_FINISH = "SURFACE_FINISH"
    TOLERANCE = "TOLERANCE"
    WELD = "WELD"
    COATING = "COATING"
    INSPECTION = "INSPECTION"
    PROCESS = "PROCESS"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Source location — provenance within the drawing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingBoundingBox:
    """A deterministic page-local bounding box measured in PDF points.

    Coordinates use a top-left origin and the ordering ``(x0, top, x1,
    bottom)``. One PDF point is 1/72 inch. The canonical model stores only
    these typed values; parser-library objects are never retained.
    """

    x0: Decimal
    top: Decimal
    x1: Decimal
    bottom: Decimal
    unit: str = "pt"

    def __post_init__(self) -> None:
        coordinates = (
            ("x0", self.x0),
            ("top", self.top),
            ("x1", self.x1),
            ("bottom", self.bottom),
        )
        for name, value in coordinates:
            if not isinstance(value, Decimal):
                raise TypeError(
                    f"DrawingBoundingBox.{name} must be Decimal, got {type(value)}"
                )
            if not value.is_finite():
                raise ValueError(f"DrawingBoundingBox.{name} must be finite")
        if self.x0 > self.x1:
            raise ValueError("DrawingBoundingBox.x0 must be <= x1")
        if self.top > self.bottom:
            raise ValueError("DrawingBoundingBox.top must be <= bottom")
        if self.unit != "pt":
            raise ValueError("DrawingBoundingBox.unit must be 'pt'")


@dataclass(frozen=True)
class DrawingSourceLocation:
    """
    Identifies where a piece of information originates within a drawing.

    All fields are optional because not all parsers can provide all
    granularity. At minimum, source_id must be populated when a
    CanonicalDrawing is constructed.

    Attributes
    ----------
    source_id:
        The EngineeringSource.source_id of the parent ingestion.
    sheet_number:
        1-based sheet index, or None if unknown.
    page_number:
        1-based page index (may differ from sheet in multi-page PDFs).
    view_id:
        Identifier of the DrawingView where this item was found.
    original_text:
        Raw string token from which this item was extracted.
    adapter_id:
        Identifier of the parser/adapter that produced this location.
    adapter_version:
        Version string of that adapter.
    confidence:
        Extraction confidence in [0.0, 1.0]; None if not applicable.
    authority:
        DrawingExtractionAuthority of this item.
    bounding_box:
        Optional typed page-local spatial bounds in PDF points.
    source_object_ids:
        Ordered identifiers of source objects contributing to this item.
    """
    source_id: str
    sheet_number: int | None = None
    page_number: int | None = None
    view_id: str | None = None
    original_text: str | None = None
    adapter_id: str | None = None
    adapter_version: str | None = None
    confidence: Decimal | None = None
    authority: DrawingExtractionAuthority = DrawingExtractionAuthority.EXTRACTED
    bounding_box: DrawingBoundingBox | None = None
    source_object_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_id.strip():
            raise ValueError("DrawingSourceLocation.source_id must not be blank")
        if self.sheet_number is not None and self.sheet_number < 1:
            raise ValueError(
                f"DrawingSourceLocation.sheet_number must be >= 1, got {self.sheet_number}"
            )
        if self.page_number is not None and self.page_number < 1:
            raise ValueError(
                f"DrawingSourceLocation.page_number must be >= 1, got {self.page_number}"
            )
        if self.confidence is not None:
            if not (Decimal("0") <= self.confidence <= Decimal("1")):
                raise ValueError(
                    f"DrawingSourceLocation.confidence must be in [0, 1], got {self.confidence}"
                )
        if self.bounding_box is not None and not isinstance(
            self.bounding_box, DrawingBoundingBox
        ):
            raise TypeError(
                "DrawingSourceLocation.bounding_box must be DrawingBoundingBox or None"
            )
        if not isinstance(self.source_object_ids, tuple):
            raise TypeError("DrawingSourceLocation.source_object_ids must be tuple[str, ...]")
        seen_object_ids: set[str] = set()
        for object_id in self.source_object_ids:
            if not isinstance(object_id, str):
                raise TypeError(
                    "DrawingSourceLocation.source_object_ids must contain only strings"
                )
            if not object_id.strip():
                raise ValueError(
                    "DrawingSourceLocation.source_object_ids must not contain blank IDs"
                )
            if object_id in seen_object_ids:
                raise ValueError(
                    "DrawingSourceLocation.source_object_ids must contain unique IDs"
                )
            seen_object_ids.add(object_id)


# ---------------------------------------------------------------------------
# Tolerance representation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingTolerance:
    """
    A dimensional tolerance extracted from a drawing.

    Numeric values use Decimal. The unit string must match the repository's
    existing unit conventions (inspect normalization.py).

    Attributes
    ----------
    tolerance_id:
        Unique identifier within the drawing.
    tolerance_type:
        How the tolerance is expressed.
    unit:
        Engineering unit string (e.g. "mm", "inch").
    upper_value:
        Upper tolerance bound. For SYMMETRIC, equals lower_value in magnitude.
    lower_value:
        Lower tolerance bound (negative for minus-direction, positive for plus).
    source_location:
        Provenance within the source drawing.
    """
    tolerance_id: str
    tolerance_type: DrawingToleranceType
    unit: str
    upper_value: Decimal | None = None
    lower_value: Decimal | None = None
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.tolerance_id or not self.tolerance_id.strip():
            raise ValueError("DrawingTolerance.tolerance_id must not be blank")
        if not self.unit or not self.unit.strip():
            raise ValueError("DrawingTolerance.unit must not be blank")
        if self.upper_value is not None and not isinstance(self.upper_value, Decimal):
            raise TypeError(
                f"DrawingTolerance.upper_value must be Decimal, got {type(self.upper_value)}"
            )
        if self.lower_value is not None and not isinstance(self.lower_value, Decimal):
            raise TypeError(
                f"DrawingTolerance.lower_value must be Decimal, got {type(self.lower_value)}"
            )
        # Symmetric: upper and lower should have equal magnitude
        if (
            self.tolerance_type == DrawingToleranceType.SYMMETRIC
            and self.upper_value is not None
            and self.lower_value is not None
        ):
            if abs(self.upper_value) != abs(self.lower_value):
                raise ValueError(
                    "SYMMETRIC tolerance requires |upper_value| == |lower_value|"
                )


# ---------------------------------------------------------------------------
# Datum reference
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingDatumReference:
    """
    A datum reference letter/label as declared in the drawing.

    No GD&T parsing logic is performed here — this is a pure representation
    of the declared datum identifier and its location in the source.

    Attributes
    ----------
    datum_label:
        The datum identifier (e.g. "A", "B", "C").
    referenced_entity_id:
        Optional reference to a geometry entity or feature in the canonical
        model (matches CanonicalGeometry entity_id conventions).
    source_location:
        Provenance within the source drawing.
    """
    datum_label: str
    referenced_entity_id: str | None = None
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.datum_label or not self.datum_label.strip():
            raise ValueError("DrawingDatumReference.datum_label must not be blank")


# ---------------------------------------------------------------------------
# GD&T / PMI reference (semantic foundation only — no symbol recognition)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingGdtReference:
    """
    A GD&T / PMI callout reference extracted from a drawing.

    Phase 1A provides the semantic container only. The symbol_type is a
    free string at this stage — GD&T symbol recognition is Phase 1B/1C.

    Attributes
    ----------
    gdt_id:
        Unique identifier within the drawing.
    symbol_type:
        Raw symbol or type string as extracted (e.g. "⌀", "◎", "flatness").
    tolerance_value:
        Tolerance Quantity value if explicitly stated in numeric form.
    tolerance_unit:
        Engineering unit of tolerance_value.
    datum_references:
        Ordered sequence of datum reference letters.
    source_location:
        Provenance within the source drawing.
    """
    gdt_id: str
    symbol_type: str | None = None
    tolerance_value: Decimal | None = None
    tolerance_unit: str | None = None
    datum_references: tuple[DrawingDatumReference, ...] = field(default_factory=tuple)
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.gdt_id or not self.gdt_id.strip():
            raise ValueError("DrawingGdtReference.gdt_id must not be blank")
        if self.tolerance_value is not None and not isinstance(self.tolerance_value, Decimal):
            raise TypeError(
                f"DrawingGdtReference.tolerance_value must be Decimal, "
                f"got {type(self.tolerance_value)}"
            )
        if self.tolerance_value is not None and self.tolerance_unit is None:
            raise ValueError(
                "DrawingGdtReference.tolerance_unit is required when tolerance_value is set"
            )


# ---------------------------------------------------------------------------
# Dimension annotation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingDimension:
    """
    A dimension annotation extracted from a drawing.

    Attributes
    ----------
    dimension_id:
        Unique identifier within the drawing.
    nominal_value:
        Nominal (basic) dimension value as Decimal.
    unit:
        Engineering unit string.
    dimension_type:
        LINEAR, RADIAL, DIAMETRAL, ANGULAR, etc.
    tolerance:
        Optional tolerance associated with this dimension.
    referenced_entity_ids:
        Geometry/feature entities this dimension refers to.
    source_location:
        Provenance within the source drawing.
    """
    dimension_id: str
    nominal_value: Decimal
    unit: str
    dimension_type: DrawingDimensionType = DrawingDimensionType.UNKNOWN
    tolerance: DrawingTolerance | None = None
    referenced_entity_ids: tuple[str, ...] = field(default_factory=tuple)
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.dimension_id or not self.dimension_id.strip():
            raise ValueError("DrawingDimension.dimension_id must not be blank")
        if not isinstance(self.nominal_value, Decimal):
            raise TypeError(
                f"DrawingDimension.nominal_value must be Decimal, got {type(self.nominal_value)}"
            )
        if not self.unit or not self.unit.strip():
            raise ValueError("DrawingDimension.unit must not be blank")


# ---------------------------------------------------------------------------
# Surface finish annotation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingSurfaceFinish:
    """
    A surface finish requirement extracted from a drawing.

    Supports Ra, Rz, and generic finish type strings.
    Numeric values use Decimal.

    Attributes
    ----------
    finish_id:
        Unique identifier within the drawing.
    parameter:
        Surface roughness parameter name (e.g. "Ra", "Rz").
    value:
        Numeric roughness value as Decimal.
    unit:
        Engineering unit string (typically "µm" or "µin").
    referenced_entity_ids:
        Geometry/feature entities this annotation applies to.
    raw_text:
        Original text token from the source drawing.
    source_location:
        Provenance within the source drawing.
    """
    finish_id: str
    parameter: str | None = None
    value: Decimal | None = None
    unit: str | None = None
    referenced_entity_ids: tuple[str, ...] = field(default_factory=tuple)
    raw_text: str | None = None
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.finish_id or not self.finish_id.strip():
            raise ValueError("DrawingSurfaceFinish.finish_id must not be blank")
        if self.value is not None and not isinstance(self.value, Decimal):
            raise TypeError(
                f"DrawingSurfaceFinish.value must be Decimal, got {type(self.value)}"
            )
        if self.value is not None and self.unit is None:
            raise ValueError(
                "DrawingSurfaceFinish.unit is required when value is set"
            )


# ---------------------------------------------------------------------------
# Drawing notes (general, material, heat treatment)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingNote:
    """
    A text note extracted from a drawing.

    Raw text is preserved without modification. Semantic interpretation
    (material lookup, heat treatment normalization) is Phase 1B/1C.

    Attributes
    ----------
    note_id:
        Unique identifier within the drawing.
    raw_text:
        Original note text exactly as extracted.
    category:
        Semantic category of this note.
    source_location:
        Provenance within the source drawing.
    """
    note_id: str
    raw_text: str
    category: DrawingNoteCategory = DrawingNoteCategory.UNKNOWN
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.note_id or not self.note_id.strip():
            raise ValueError("DrawingNote.note_id must not be blank")
        if not self.raw_text or not self.raw_text.strip():
            raise ValueError("DrawingNote.raw_text must not be blank")


@dataclass(frozen=True)
class DrawingMaterialNote:
    """
    A material specification note extracted from a drawing.

    Retains original source text. Normalized/reference fields are optional
    and must not be populated by inference without an explicit rule.

    Attributes
    ----------
    note_id:
        Unique identifier within the drawing.
    raw_text:
        Original material specification exactly as written.
    normalized_identifier:
        Optional: normalized material ID (e.g. "EN 10083-2 42CrMo4").
        Only populated when extracted directly, never inferred.
    source_location:
        Provenance within the source drawing.
    """
    note_id: str
    raw_text: str
    normalized_identifier: str | None = None
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.note_id or not self.note_id.strip():
            raise ValueError("DrawingMaterialNote.note_id must not be blank")
        if not self.raw_text or not self.raw_text.strip():
            raise ValueError("DrawingMaterialNote.raw_text must not be blank")


@dataclass(frozen=True)
class DrawingHeatTreatmentNote:
    """
    A heat treatment specification extracted from a drawing.

    Retains original source text without normalization in Phase 1A.

    Attributes
    ----------
    note_id:
        Unique identifier within the drawing.
    raw_text:
        Original heat treatment specification exactly as written.
    source_location:
        Provenance within the source drawing.
    """
    note_id: str
    raw_text: str
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.note_id or not self.note_id.strip():
            raise ValueError("DrawingHeatTreatmentNote.note_id must not be blank")
        if not self.raw_text or not self.raw_text.strip():
            raise ValueError("DrawingHeatTreatmentNote.raw_text must not be blank")


# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingRevision:
    """
    Drawing revision metadata as declared in the title block or revision table.

    Attributes
    ----------
    revision_code:
        Revision identifier (e.g. "A", "B", "01", "REV3").
    description:
        Optional free-text description of the revision.
    date_text:
        Revision date as raw text (not parsed to datetime — parsing is Phase 1C).
    author:
        Author/drafter as extracted.
    approver:
        Approver as extracted.
    source_location:
        Provenance within the source drawing.
    """
    revision_code: str
    description: str | None = None
    date_text: str | None = None
    author: str | None = None
    approver: str | None = None
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.revision_code or not self.revision_code.strip():
            raise ValueError("DrawingRevision.revision_code must not be blank")


# ---------------------------------------------------------------------------
# Title block
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingTitleBlock:
    """
    Content extracted from the drawing title block.

    All fields are optional because partial extraction is valid (PARTIAL
    ingestion status). Mandatory provenance is enforced at CanonicalDrawing
    level, not here.

    Attributes
    ----------
    drawing_number:
        Drawing/part number.
    part_number:
        Part number if distinct from drawing_number.
    part_name:
        Part name or description.
    material_raw:
        Raw material specification text.
    scale:
        Drawing scale as a raw string (e.g. "1:1", "1:2", "2:1").
    sheet_number:
        Sheet number extracted from title block.
    sheet_count:
        Total sheet count extracted from title block.
    revision:
        Revision metadata extracted from title block.
    author:
        Author / drafter name.
    checker:
        Checker name.
    approver:
        Approver name.
    date_text:
        Creation/issue date as raw text.
    source_location:
        Provenance within the source drawing.
    """
    drawing_number: str | None = None
    part_number: str | None = None
    part_name: str | None = None
    material_raw: str | None = None
    scale: str | None = None
    sheet_number: int | None = None
    sheet_count: int | None = None
    revision: DrawingRevision | None = None
    author: str | None = None
    checker: str | None = None
    approver: str | None = None
    date_text: str | None = None
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if (
            self.sheet_number is not None
            and self.sheet_count is not None
            and self.sheet_number > self.sheet_count
        ):
            raise ValueError(
                f"DrawingTitleBlock.sheet_number ({self.sheet_number}) "
                f"exceeds sheet_count ({self.sheet_count})"
            )
        if self.sheet_number is not None and self.sheet_number < 1:
            raise ValueError(
                f"DrawingTitleBlock.sheet_number must be >= 1, got {self.sheet_number}"
            )
        if self.sheet_count is not None and self.sheet_count < 1:
            raise ValueError(
                f"DrawingTitleBlock.sheet_count must be >= 1, got {self.sheet_count}"
            )


# ---------------------------------------------------------------------------
# View model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingView:
    """
    A single engineering view on a drawing sheet.

    Attributes
    ----------
    view_id:
        Unique identifier within the drawing.
    view_type:
        Standard view type (FRONT, TOP, SECTION, DETAIL, etc.).
    name:
        Optional view name or label as extracted.
    scale:
        View-specific scale string (overrides sheet scale if present).
    dimensions:
        Dimension annotations located within this view.
    gdt_references:
        GD&T/PMI references located within this view.
    surface_finish_annotations:
        Surface finish annotations within this view.
    referenced_geometry_ids:
        Geometry/feature entity IDs visible in this view.
    source_location:
        Provenance within the source drawing.
    """
    view_id: str
    view_type: DrawingViewType = DrawingViewType.UNKNOWN
    name: str | None = None
    scale: str | None = None
    dimensions: tuple[DrawingDimension, ...] = field(default_factory=tuple)
    gdt_references: tuple[DrawingGdtReference, ...] = field(default_factory=tuple)
    surface_finish_annotations: tuple[DrawingSurfaceFinish, ...] = field(default_factory=tuple)
    referenced_geometry_ids: tuple[str, ...] = field(default_factory=tuple)
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.view_id or not self.view_id.strip():
            raise ValueError("DrawingView.view_id must not be blank")


# ---------------------------------------------------------------------------
# Sheet model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingSheet:
    """
    A single sheet within a multi-sheet drawing.

    Attributes
    ----------
    sheet_number:
        1-based sheet index.
    sheet_count:
        Total number of sheets declared or inferred for this drawing.
    size:
        Sheet size designation (e.g. "A4", "A3", "A0", "ANSI B").
    scale:
        Sheet-level scale string.
    views:
        Engineering views on this sheet.
    notes:
        Notes located on this sheet.
    datum_references:
        Datum references declared on this sheet.
    source_location:
        Provenance within the source drawing.
    """
    sheet_number: int
    sheet_count: int | None = None
    size: str | None = None
    scale: str | None = None
    views: tuple[DrawingView, ...] = field(default_factory=tuple)
    notes: tuple[DrawingNote, ...] = field(default_factory=tuple)
    datum_references: tuple[DrawingDatumReference, ...] = field(default_factory=tuple)
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if self.sheet_number < 1:
            raise ValueError(
                f"DrawingSheet.sheet_number must be >= 1, got {self.sheet_number}"
            )
        if self.sheet_count is not None:
            if self.sheet_count < 1:
                raise ValueError(
                    f"DrawingSheet.sheet_count must be >= 1, got {self.sheet_count}"
                )
            if self.sheet_number > self.sheet_count:
                raise ValueError(
                    f"DrawingSheet.sheet_number ({self.sheet_number}) "
                    f"exceeds sheet_count ({self.sheet_count})"
                )


# ---------------------------------------------------------------------------
# Canonical drawing — top-level model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CanonicalDrawing:
    """
    The canonical representation of a technical drawing.

    Produced by a DrawingParser and consumed by downstream engineering
    modules. All fields follow the repository's provenance-mandatory,
    fail-closed, immutable conventions.

    Attributes
    ----------
    drawing_id:
        Unique drawing identifier. Mandatory.
    source_id:
        EngineeringSource.source_id of the originating source. Mandatory.
    sheets:
        Ordered sequence of drawing sheets (at least one).
    title_block:
        Extracted title block data. May be None for unsupported sources.
    revision:
        Drawing revision from title block or revision table.
    material_notes:
        Material specification notes extracted from the drawing.
    heat_treatment_notes:
        Heat treatment notes extracted from the drawing.
    all_dimensions:
        All dimensions across all sheets/views (flat collection for queries).
    all_tolerances:
        All tolerances across all sheets/views.
    all_datum_references:
        All datum references across all sheets/views.
    all_gdt_references:
        All GD&T/PMI references across all sheets/views.
    all_surface_finish:
        All surface finish annotations across all sheets/views.
    metadata:
        Arbitrary key→string metadata from the source (page count, PDF version, etc.).
    source_location:
        Top-level provenance for the drawing as a whole.
    """
    drawing_id: str
    source_id: str
    sheets: tuple[DrawingSheet, ...] = field(default_factory=tuple)
    title_block: DrawingTitleBlock | None = None
    revision: DrawingRevision | None = None
    material_notes: tuple[DrawingMaterialNote, ...] = field(default_factory=tuple)
    heat_treatment_notes: tuple[DrawingHeatTreatmentNote, ...] = field(default_factory=tuple)
    all_dimensions: tuple[DrawingDimension, ...] = field(default_factory=tuple)
    all_tolerances: tuple[DrawingTolerance, ...] = field(default_factory=tuple)
    all_datum_references: tuple[DrawingDatumReference, ...] = field(default_factory=tuple)
    all_gdt_references: tuple[DrawingGdtReference, ...] = field(default_factory=tuple)
    all_surface_finish: tuple[DrawingSurfaceFinish, ...] = field(default_factory=tuple)
    metadata: dict[str, str] = field(default_factory=dict)
    source_location: DrawingSourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.drawing_id or not self.drawing_id.strip():
            raise ValueError("CanonicalDrawing.drawing_id must not be blank")
        if not self.source_id or not self.source_id.strip():
            raise ValueError("CanonicalDrawing.source_id must not be blank")
        # Validate datum labels are unique across all sheets
        all_labels = [
            d.datum_label
            for d in self.all_datum_references
        ]
        seen: set[str] = set()
        for label in all_labels:
            if label in seen:
                raise ValueError(
                    f"CanonicalDrawing contains duplicate datum label: {label!r}"
                )
            seen.add(label)

    @property
    def sheet_count(self) -> int:
        """Number of sheets in this drawing."""
        return len(self.sheets)

    @property
    def has_title_block(self) -> bool:
        """True if a title block was extracted."""
        return self.title_block is not None

    @property
    def has_revision(self) -> bool:
        """True if revision metadata is available."""
        return self.revision is not None


# ---------------------------------------------------------------------------
# Drawing ingestion result contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrawingIngestionDiagnostics:
    """
    Diagnostic information from a drawing ingestion attempt.

    Attributes
    ----------
    status:
        Overall ingestion outcome.
    format_detected:
        Format string detected by the adapter (e.g. "PDF", "DXF").
    parser_id:
        Identifier of the DrawingParser implementation.
    parser_version:
        Version string of that parser.
    warnings:
        Non-fatal issues encountered during ingestion.
    errors:
        Fatal issues that caused FAILED or INSUFFICIENT_DATA status.
    sheet_count_expected:
        Sheet count declared by the source (e.g. PDF page count).
    sheet_count_parsed:
        Number of sheets successfully parsed.
    """
    status: DrawingIngestionStatus
    format_detected: str | None = None
    parser_id: str | None = None
    parser_version: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    sheet_count_expected: int | None = None
    sheet_count_parsed: int = 0


@dataclass(frozen=True)
class DrawingIngestionResult:
    """
    The result contract for a drawing ingestion operation.

    Mirrors the ImportResult pattern in backend/interoperability/orchestrator.py.
    Fail-closed: a FAILED or INSUFFICIENT_DATA result always has document=None.

    Attributes
    ----------
    source_id:
        EngineeringSource.source_id that produced this result.
    diagnostics:
        Ingestion outcome, format info, warnings and errors.
    document:
        The CanonicalDrawing if ingestion succeeded (VALID or PARTIAL).
        None for FAILED, UNSUPPORTED, or INSUFFICIENT_DATA.
    """
    source_id: str
    diagnostics: DrawingIngestionDiagnostics
    document: CanonicalDrawing | None = None

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_id.strip():
            raise ValueError("DrawingIngestionResult.source_id must not be blank")
        # Fail-closed: FAILED/UNSUPPORTED/INSUFFICIENT_DATA must not carry a document
        if self.diagnostics.status in (
            DrawingIngestionStatus.FAILED,
            DrawingIngestionStatus.UNSUPPORTED,
            DrawingIngestionStatus.INSUFFICIENT_DATA,
        ) and self.document is not None:
            raise ValueError(
                f"DrawingIngestionResult with status "
                f"{self.diagnostics.status!r} must not carry a document"
            )
        # VALID must carry a document
        if (
            self.diagnostics.status == DrawingIngestionStatus.VALID
            and self.document is None
        ):
            raise ValueError(
                "DrawingIngestionResult with status VALID must carry a document"
            )

    @property
    def succeeded(self) -> bool:
        """True if the ingestion produced usable output (VALID or PARTIAL)."""
        return self.diagnostics.status in (
            DrawingIngestionStatus.VALID,
            DrawingIngestionStatus.PARTIAL,
        )

    @property
    def failed(self) -> bool:
        """True if the ingestion produced no usable output."""
        return not self.succeeded


# ---------------------------------------------------------------------------
# Drawing parser / adapter interface contract
#
# Extends the FormatAdapter pattern from backend/interoperability/adapter.py.
# If FormatAdapter is a concrete ABC in that module, DrawingParser should
# either extend it or parallel its interface. The implementation below
# parallels the interface (using an independent ABC) so it compiles without
# importing adapter.py, which is not available in this container.
#
# On the live machine: inspect adapter.py and decide whether to:
#   (a) class DrawingParser(FormatAdapter): ...  — preferred if safe
#   (b) keep this independent ABC              — if FormatAdapter has
#       geometry-specific methods that don't apply to drawings
# ---------------------------------------------------------------------------

class DrawingParser(abc.ABC):
    """
    Interface contract for technical drawing parsers.

    Concrete implementations (Phase 1B/1C):
        PdfDrawingParser       — PyMuPDF / pdfplumber
        VectorPdfDrawingParser — vector-only PDF extraction
        OcrDrawingParser       — OCR-based raster drawing extraction
        DxfDrawingParser       — ezdxf-based DXF annotation extraction

    None of these are implemented here. This ABC defines the contract only.

    NOTE: On the live machine, check whether FormatAdapter in adapter.py
    defines can_read / read methods with compatible signatures. If so,
    subclass FormatAdapter instead:

        class DrawingParser(FormatAdapter, abc.ABC):
            ...
    """

    @abc.abstractmethod
    def parser_id(self) -> str:
        """
        Return a stable identifier for this parser implementation.
        Used in DrawingSourceLocation.adapter_id.
        """

    @abc.abstractmethod
    def parser_version(self) -> str:
        """
        Return the version string of this parser implementation.
        Used in DrawingSourceLocation.adapter_version.
        """

    @abc.abstractmethod
    def supports(self, source_id: str, file_name: str, notes: str | None = None) -> bool:
        """
        Return True if this parser can attempt to parse the given source.

        Parameters
        ----------
        source_id:
            EngineeringSource.source_id.
        file_name:
            Original file name including extension.
        notes:
            Optional header bytes or hints (mirrors EngineeringSource.notes usage).

        Notes
        -----
        This method must not raise. Unknown or unsupported input returns False.
        """

    @abc.abstractmethod
    def parse(
        self,
        source_id: str,
        file_name: str,
        content: bytes,
        notes: str | None = None,
    ) -> DrawingIngestionResult:
        """
        Parse a drawing source and return an ingestion result.

        Parameters
        ----------
        source_id:
            EngineeringSource.source_id for provenance.
        file_name:
            Original file name.
        content:
            Raw file bytes.
        notes:
            Optional header/hint text (first 512 bytes, following existing
            CadImportOrchestrator convention).

        Returns
        -------
        DrawingIngestionResult
            Always returns a result. Never raises for recoverable failures —
            those produce FAILED or UNSUPPORTED status. Only truly unexpected
            implementation errors may propagate as exceptions.
        """


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------

__all__ = [
    # Enums
    "DrawingExtractionAuthority",
    "DrawingIngestionStatus",
    "DrawingViewType",
    "DrawingDimensionType",
    "DrawingToleranceType",
    "DrawingNoteCategory",
    # Source location / provenance
    "DrawingBoundingBox",
    "DrawingSourceLocation",
    # Sub-models
    "DrawingTolerance",
    "DrawingDatumReference",
    "DrawingGdtReference",
    "DrawingDimension",
    "DrawingSurfaceFinish",
    "DrawingNote",
    "DrawingMaterialNote",
    "DrawingHeatTreatmentNote",
    "DrawingRevision",
    "DrawingTitleBlock",
    "DrawingView",
    "DrawingSheet",
    # Top-level model
    "CanonicalDrawing",
    # Ingestion result
    "DrawingIngestionDiagnostics",
    "DrawingIngestionResult",
    # Parser contract
    "DrawingParser",
]
