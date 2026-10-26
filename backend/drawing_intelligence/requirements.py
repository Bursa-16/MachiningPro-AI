"""Drawing Requirement domain models (EPIC_04 Phase 2).

Wraps extracted CanonicalDrawing data into engineering requirements:
dimensional, geometric (GD&T), surface finish, thread, and material.

Expands the existing 4-characteristic GD&T model with the 10 additional
characteristics required for machining process planning.

FABRICATED_DRAWING_REQUIREMENT=NO
FABRICATED_GDT_VALUE=NO
FABRICATED_DATUM=NO
MISSING_VALUE_AS_ZERO=NO
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

__all__ = [
    # GD&T enumerations
    "GdtCharacteristic",
    "GdtModifier",
    # Datum model
    "DatumReference",
    "DatumReferenceFrame",
    # GD&T requirement
    "ExpandedFeatureControlFrame",
    # Drawing requirement types
    "DimensionalRequirement",
    "GeometricRequirement",
    "SurfaceFinishRequirement",
    "ThreadRequirement",
    "MaterialRequirement",
    "HeatTreatmentRequirement",
    "DrawingRequirementSet",
    "RequirementExtractionStatus",
]

# ---------------------------------------------------------------------------
# GD&T characteristic enumeration (expanded from Phase 1C's 4 types)
# ---------------------------------------------------------------------------

class GdtCharacteristic(StrEnum):
    """ISO 1101 / ASME Y14.5 GD&T characteristic symbols."""

    # Form (no datum reference)
    STRAIGHTNESS = "STRAIGHTNESS"
    FLATNESS = "FLATNESS"             # Phase 1C supported
    CIRCULARITY = "CIRCULARITY"       # Phase 1C supported
    CYLINDRICITY = "CYLINDRICITY"

    # Profile
    PROFILE_OF_A_LINE = "PROFILE_OF_A_LINE"
    PROFILE_OF_A_SURFACE = "PROFILE_OF_A_SURFACE"

    # Orientation (require datum)
    PERPENDICULARITY = "PERPENDICULARITY"
    ANGULARITY = "ANGULARITY"
    PARALLELISM = "PARALLELISM"

    # Location (require datum)
    POSITION = "POSITION"             # Phase 1C supported
    CONCENTRICITY = "CONCENTRICITY"
    SYMMETRY = "SYMMETRY"             # Phase 1C supported

    # Runout (require datum)
    CIRCULAR_RUNOUT = "CIRCULAR_RUNOUT"
    TOTAL_RUNOUT = "TOTAL_RUNOUT"

    UNKNOWN = "UNKNOWN"


# Characteristics that require a datum reference frame
GDT_REQUIRES_DATUM: frozenset[GdtCharacteristic] = frozenset({
    GdtCharacteristic.PERPENDICULARITY,
    GdtCharacteristic.ANGULARITY,
    GdtCharacteristic.PARALLELISM,
    GdtCharacteristic.POSITION,
    GdtCharacteristic.CONCENTRICITY,
    GdtCharacteristic.SYMMETRY,
    GdtCharacteristic.CIRCULAR_RUNOUT,
    GdtCharacteristic.TOTAL_RUNOUT,
})

# Characteristics that imply bore/cylindrical feature context
GDT_CYLINDRICAL_CONTEXT: frozenset[GdtCharacteristic] = frozenset({
    GdtCharacteristic.CIRCULARITY,
    GdtCharacteristic.CYLINDRICITY,
    GdtCharacteristic.CIRCULAR_RUNOUT,
    GdtCharacteristic.TOTAL_RUNOUT,
    GdtCharacteristic.CONCENTRICITY,
})


class GdtModifier(StrEnum):
    """GD&T material condition and other modifiers."""

    NONE = "NONE"
    MMC = "MMC"          # Maximum Material Condition
    LMC = "LMC"          # Least Material Condition
    RFS = "RFS"          # Regardless of Feature Size (default for most)
    PROJECTED = "PROJECTED"
    FREE_STATE = "FREE_STATE"
    TANGENT_PLANE = "TANGENT_PLANE"
    UNEQUAL = "UNEQUAL"


# ---------------------------------------------------------------------------
# Datum / DRF model
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DatumReference:
    """Single datum entry in a feature control frame."""

    label: str              # "A", "B", "C", or compound like "A-B"
    precedence: int         # 1=primary, 2=secondary, 3=tertiary
    modifier: GdtModifier = GdtModifier.NONE

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("DatumReference.label must be non-empty")
        if self.precedence not in (1, 2, 3):
            raise ValueError("DatumReference.precedence must be 1, 2, or 3")


@dataclass(frozen=True, slots=True)
class DatumReferenceFrame:
    """Compound datum reference frame — up to primary/secondary/tertiary."""

    primary: DatumReference
    secondary: DatumReference | None = None
    tertiary: DatumReference | None = None

    def __post_init__(self) -> None:
        if self.tertiary is not None and self.secondary is None:
            raise ValueError(
                "DatumReferenceFrame: tertiary requires secondary datum"
            )

    @property
    def labels(self) -> tuple[str, ...]:
        parts = [self.primary.label]
        if self.secondary:
            parts.append(self.secondary.label)
        if self.tertiary:
            parts.append(self.tertiary.label)
        return tuple(parts)


# ---------------------------------------------------------------------------
# Expanded Feature Control Frame
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ExpandedFeatureControlFrame:
    """Fully parsed feature control frame with expanded GD&T model.

    Extends Phase 1C's DrawingFeatureControlFrame with:
    - 14 characteristics (up from 4)
    - 7 modifiers (up from 1)
    - Compound DatumReferenceFrame (up from flat datum labels)
    """

    characteristic: GdtCharacteristic
    tolerance_value: Decimal
    tolerance_unit: str              # "mm" | "°" | "in"
    diameter_zone: bool = False      # ⌀ prefix on tolerance zone
    modifier: GdtModifier = GdtModifier.NONE
    datum_frame: DatumReferenceFrame | None = None
    source_fcf_id: str | None = None  # provenance: DrawingFeatureControlFrame.frame_id

    def __post_init__(self) -> None:
        if self.tolerance_value <= Decimal(0):
            raise ValueError(
                "ExpandedFeatureControlFrame.tolerance_value must be > 0"
            )
        if self.datum_frame is None and self.characteristic in GDT_REQUIRES_DATUM:
            # Soft warning — not a hard failure; datum may be extractable separately
            pass


# ---------------------------------------------------------------------------
# Status of requirement extraction
# ---------------------------------------------------------------------------

class RequirementExtractionStatus(StrEnum):
    COMPLETE = "COMPLETE"               # All required fields extracted
    PARTIAL = "PARTIAL"                 # Some fields missing but usable
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Cannot generate useful requirements
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"  # Format not supported for extraction


# ---------------------------------------------------------------------------
# Individual requirement types
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DimensionalRequirement:
    """A single extracted dimensional requirement from a drawing."""

    req_id: str
    dimension_type: str          # from DrawingDimensionType value
    nominal_value: Decimal
    unit: str                    # "mm" | "in"
    tolerance_upper: Decimal | None = None
    tolerance_lower: Decimal | None = None
    tolerance_type: str | None = None
    authority: str = "EXTRACTED"
    source_dimension_id: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.req_id.strip():
            raise ValueError("DimensionalRequirement.req_id must be non-empty")
        if not self.unit.strip():
            raise ValueError("DimensionalRequirement.unit must be non-empty")

    @property
    def has_tolerance(self) -> bool:
        return self.tolerance_upper is not None or self.tolerance_lower is not None

    @property
    def bilateral_tolerance(self) -> Decimal | None:
        """Returns total tolerance band when symmetric, else None."""
        if (self.tolerance_upper is not None and self.tolerance_lower is not None
                and self.tolerance_upper == -self.tolerance_lower):
            return self.tolerance_upper * Decimal(2)
        return None


@dataclass(frozen=True, slots=True)
class GeometricRequirement:
    """A GD&T feature control frame requirement extracted from a drawing."""

    req_id: str
    fcf: ExpandedFeatureControlFrame
    feature_ref: str | None = None    # links to feature on drawing
    authority: str = "EXTRACTED"
    source_fcf_id: str | None = None

    def __post_init__(self) -> None:
        if not self.req_id.strip():
            raise ValueError("GeometricRequirement.req_id must be non-empty")
        if not isinstance(self.fcf, ExpandedFeatureControlFrame):
            raise ValueError("GeometricRequirement.fcf must be ExpandedFeatureControlFrame")


@dataclass(frozen=True, slots=True)
class SurfaceFinishRequirement:
    """Surface finish (roughness) requirement from a drawing."""

    req_id: str
    ra_um: Decimal | None = None     # Ra in micrometers
    rz_um: Decimal | None = None     # Rz in micrometers
    feature_ref: str | None = None
    authority: str = "EXTRACTED"
    source_id: str | None = None

    def __post_init__(self) -> None:
        if self.ra_um is None and self.rz_um is None:
            raise ValueError(
                "SurfaceFinishRequirement: at least ra_um or rz_um must be provided"
            )
        if self.ra_um is not None and self.ra_um <= Decimal(0):
            raise ValueError("SurfaceFinishRequirement.ra_um must be > 0")
        if self.rz_um is not None and self.rz_um <= Decimal(0):
            raise ValueError("SurfaceFinishRequirement.rz_um must be > 0")

    @property
    def requires_grinding(self) -> bool:
        """Ra ≤ 0.8 µm typically requires grinding or honing."""
        return self.ra_um is not None and self.ra_um <= Decimal("0.8")

    @property
    def requires_finishing(self) -> bool:
        """Ra ≤ 3.2 µm requires a finishing pass."""
        return self.ra_um is not None and self.ra_um <= Decimal("3.2")


@dataclass(frozen=True, slots=True)
class ThreadRequirement:
    """Thread specification extracted from a drawing note or dimension."""

    req_id: str
    designation: str | None = None   # "M12x1.75", "1/2-13 UNC", "G1/4"
    standard: str | None = None      # "ISO", "ASME", "BSP"
    hand: str = "RH"                 # "RH" | "LH"
    nominal_diameter_mm: Decimal | None = None
    pitch_mm: Decimal | None = None
    thread_class: str | None = None  # "6H/6g", "2A/2B"
    note_text: str | None = None
    authority: str = "EXTRACTED"

    def __post_init__(self) -> None:
        if self.hand not in ("RH", "LH"):
            raise ValueError("ThreadRequirement.hand must be 'RH' or 'LH'")

    @property
    def is_metric(self) -> bool:
        return self.designation is not None and self.designation.upper().startswith("M")

    @property
    def requires_tapping(self) -> bool:
        """Thread in a hole → tapping operation required."""
        return True  # All thread requirements need a thread operation


@dataclass(frozen=True, slots=True)
class MaterialRequirement:
    """Material specification extracted from drawing title block or notes."""

    req_id: str
    raw_designation: str              # as-found text, verbatim
    standard: str | None = None      # "EN 10083", "AISI", "DIN"
    matched_material_id: str | None = None  # MaterialRecord.material_id if found
    match_confidence: str = "NONE"   # "EXACT" | "PARTIAL" | "NONE"
    iso_group: str | None = None     # inferred ISO 513 group
    authority: str = "EXTRACTED"

    def __post_init__(self) -> None:
        if not self.raw_designation.strip():
            raise ValueError("MaterialRequirement.raw_designation must be non-empty")
        if self.match_confidence not in ("EXACT", "PARTIAL", "NONE"):
            raise ValueError(
                "MaterialRequirement.match_confidence must be EXACT, PARTIAL, or NONE"
            )


@dataclass(frozen=True, slots=True)
class HeatTreatmentRequirement:
    """Heat treatment note extracted from drawing."""

    req_id: str
    raw_note: str
    condition_code: str | None = None  # "QT", "ANNEALED", "NORMALIZED", "CASE_HARDEN"
    hardness_target_hb: int | None = None
    hardness_target_hrc: int | None = None
    authority: str = "EXTRACTED"

    def __post_init__(self) -> None:
        if not self.raw_note.strip():
            raise ValueError("HeatTreatmentRequirement.raw_note must be non-empty")


# ---------------------------------------------------------------------------
# DrawingRequirementSet — aggregate container
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DrawingRequirementSet:
    """Complete set of engineering requirements extracted from a drawing.

    This is the primary input to the Feature Recognition Engine.
    All requirements carry provenance; none are fabricated.

    FABRICATED_DRAWING_REQUIREMENT=NO
    """

    source_id: str
    drawing_number: str | None
    revision: str | None
    extraction_status: RequirementExtractionStatus
    dimensional: tuple[DimensionalRequirement, ...]
    geometric: tuple[GeometricRequirement, ...]
    surface_finish: tuple[SurfaceFinishRequirement, ...]
    threads: tuple[ThreadRequirement, ...]
    material: MaterialRequirement | None
    heat_treatment: tuple[HeatTreatmentRequirement, ...]
    extraction_warnings: tuple[str, ...] = ()
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("DrawingRequirementSet.source_id must be non-empty")

    @property
    def has_gdt(self) -> bool:
        return len(self.geometric) > 0

    @property
    def has_threads(self) -> bool:
        return len(self.threads) > 0

    @property
    def has_material(self) -> bool:
        return self.material is not None

    @property
    def requirement_count(self) -> int:
        return (len(self.dimensional) + len(self.geometric)
                + len(self.surface_finish) + len(self.threads))

    @property
    def fingerprint(self) -> str:
        """Stable hex digest for traceability."""
        payload = (
            f"{self.source_id}|{self.drawing_number}|{self.revision}"
            f"|D{len(self.dimensional)}|G{len(self.geometric)}"
            f"|S{len(self.surface_finish)}|T{len(self.threads)}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _req_id(prefix: str, index: int) -> str:
    """Generate deterministic requirement ID."""
    return f"{prefix}-{index:04d}"
