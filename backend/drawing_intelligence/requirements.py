"""Drawing Requirement domain models (EPIC_04 Phase 2 / EPIC_04B).

Wraps extracted CanonicalDrawing data into engineering requirements:
dimensional, geometric (GD&T), surface finish, thread, and material.

Phase 2 (EPIC_04): 14 GD&T characteristics, 7 modifiers, DRF model.
Phase 04B: Feature-of-size, derived features, advanced DRF, datum targets,
compound datums, bonus tolerance, virtual condition, composite FCF,
profile/runout/orientation/form models, tolerance zones, basic dimensions,
feature patterns, ambiguity/confidence models, setup planning hints.

FABRICATED_DRAWING_REQUIREMENT=NO
FABRICATED_GDT_VALUE=NO
FABRICATED_DATUM=NO
FABRICATED_ACTUAL_SIZE=NO
MISSING_VALUE_AS_ZERO=NO
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

__all__ = [
    # GD&T enumerations
    "GdtCharacteristic",
    "GdtModifier",
    "FeatureModifier",
    "DatumBoundaryModifier",
    # Datum model
    "DatumReference",
    "DatumReferenceFrame",
    "DatumFeatureType",
    "DatumFeatureRecord",
    "DatumTargetKind",
    "DatumTargetRecord",
    "DatumCompositionKind",
    "CompoundDatumDefinition",
    "AdvancedDatumRef",
    "AdvancedDatumReferenceFrame",
    # Feature of size
    "FeatureOfSizeKind",
    "FeatureOfSize",
    "DerivedFeatureKind",
    "DerivedFeature",
    # Tolerance zone
    "ToleranceZoneGeometry",
    # Basic dimensions
    "BasicDimension",
    # Feature patterns
    "PatternKind",
    "FeaturePattern",
    # Composite FCF
    "SegmentIntent",
    "FCFSegment",
    "CompositePositionFCF",
    # Projected zone
    "ProjectedToleranceZone",
    # Bonus / virtual condition
    "BonusToleranceResult",
    "VirtualConditionResult",
    # Ambiguity / confidence
    "GdtConfidence",
    "AmbiguityKind",
    "GdtAmbiguity",
    # Setup planning
    "SetupPlanHint",
    # Tolerance precedence
    "TolerancePrecedence",
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
    # Convenience sets
    "GDT_REQUIRES_DATUM",
    "GDT_CYLINDRICAL_CONTEXT",
    "GDT_FORM_ONLY",
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

# Form-only characteristics: must NOT reference a datum
GDT_FORM_ONLY: frozenset[GdtCharacteristic] = frozenset({
    GdtCharacteristic.FLATNESS,
    GdtCharacteristic.CIRCULARITY,
    GdtCharacteristic.CYLINDRICITY,
    GdtCharacteristic.STRAIGHTNESS,
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
# Phase 04B: Feature-side modifier (separate from datum-side modifier)
# ---------------------------------------------------------------------------

class FeatureModifier(StrEnum):
    """Material condition modifier applied to the controlled feature (feature side)."""
    NONE = "NONE"
    MMC = "MMC"
    LMC = "LMC"
    RFS = "RFS"
    PROJECTED = "PROJECTED"
    FREE_STATE = "FREE_STATE"
    TANGENT_PLANE = "TANGENT_PLANE"


class DatumBoundaryModifier(StrEnum):
    """Material boundary modifier applied to a datum reference (datum side).

    Distinct from FeatureModifier. MMB/LMB permit datum shift; RMB does not.
    """
    RMB = "RMB"   # Regardless of Material Boundary (default, no shift)
    MMB = "MMB"   # Maximum Material Boundary — datum shift permitted
    LMB = "LMB"   # Least Material Boundary — datum shift permitted


# ---------------------------------------------------------------------------
# Phase 04B: Feature of Size
# ---------------------------------------------------------------------------

class FeatureOfSizeKind(StrEnum):
    INTERNAL_CYLINDRICAL = "INTERNAL_CYLINDRICAL"   # bore, hole
    EXTERNAL_CYLINDRICAL = "EXTERNAL_CYLINDRICAL"   # shaft, pin, boss
    WIDTH = "WIDTH"                                 # slot, tab, key
    SPHERICAL = "SPHERICAL"                         # sphere (when SR noted)
    NON_FEATURE_OF_SIZE = "NON_FEATURE_OF_SIZE"     # planar surface, profile surface
    PATTERN = "PATTERN"                             # repeated FOS group
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class FeatureOfSize:
    """Dimensional feature-of-size with size limits.

    FABRICATED_ACTUAL_SIZE=NO — actual_size_mm is never populated by inference.
    Bonus tolerance and virtual condition are gated on this field being non-None.
    """
    fos_id: str
    kind: FeatureOfSizeKind
    nominal_mm: Decimal | None
    upper_limit_mm: Decimal | None    # MMC limit for external; LMC limit for internal
    lower_limit_mm: Decimal | None    # LMC limit for external; MMC limit for internal
    actual_size_mm: Decimal | None    # NEVER fabricated — None unless explicitly provided
    source_req_id: str | None
    feature_id: str | None

    def __post_init__(self) -> None:
        if not self.fos_id.strip():
            raise ValueError("FeatureOfSize.fos_id must be non-empty")
        if (self.upper_limit_mm is not None and self.lower_limit_mm is not None
                and self.upper_limit_mm < self.lower_limit_mm):
            raise ValueError("FeatureOfSize.upper_limit_mm must be >= lower_limit_mm")

    @property
    def mmc_size_mm(self) -> Decimal | None:
        """Maximum material condition size."""
        if self.upper_limit_mm is None or self.lower_limit_mm is None:
            return None
        if self.kind == FeatureOfSizeKind.INTERNAL_CYLINDRICAL:
            return self.lower_limit_mm   # MMC hole = smallest hole
        if self.kind == FeatureOfSizeKind.EXTERNAL_CYLINDRICAL:
            return self.upper_limit_mm   # MMC shaft = largest shaft
        return self.upper_limit_mm

    @property
    def lmc_size_mm(self) -> Decimal | None:
        """Least material condition size."""
        if self.upper_limit_mm is None or self.lower_limit_mm is None:
            return None
        if self.kind == FeatureOfSizeKind.INTERNAL_CYLINDRICAL:
            return self.upper_limit_mm   # LMC hole = largest hole
        if self.kind == FeatureOfSizeKind.EXTERNAL_CYLINDRICAL:
            return self.lower_limit_mm   # LMC shaft = smallest shaft
        return self.lower_limit_mm

    @property
    def is_true_fos(self) -> bool:
        return self.kind not in (FeatureOfSizeKind.NON_FEATURE_OF_SIZE, FeatureOfSizeKind.UNKNOWN)


# ---------------------------------------------------------------------------
# Phase 04B: Derived features
# ---------------------------------------------------------------------------

class DerivedFeatureKind(StrEnum):
    AXIS = "AXIS"               # derived axis of cylindrical FOS
    MEDIAN_PLANE = "MEDIAN_PLANE"  # derived median plane of width FOS
    CENTER_POINT = "CENTER_POINT"  # center of spherical FOS
    MEDIAN_LINE = "MEDIAN_LINE"    # derived median line (non-ideal axis)


@dataclass(frozen=True, slots=True)
class DerivedFeature:
    derived_id: str
    kind: DerivedFeatureKind
    parent_fos_id: str
    description: str | None

    def __post_init__(self) -> None:
        if not self.derived_id.strip():
            raise ValueError("DerivedFeature.derived_id must be non-empty")
        if not self.parent_fos_id.strip():
            raise ValueError("DerivedFeature.parent_fos_id must be non-empty")


# ---------------------------------------------------------------------------
# Phase 04B: Datum models
# ---------------------------------------------------------------------------

class DatumFeatureType(StrEnum):
    PLANE = "PLANE"
    CYLINDER = "CYLINDER"
    CONE = "CONE"
    POINT = "POINT"
    LINE = "LINE"
    COMPLEX = "COMPLEX"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class DatumFeatureRecord:
    datum_id: str
    datum_label: str
    datum_feature_type: DatumFeatureType
    feature_id: str | None
    simulator_description: str | None
    is_target_based: bool = False
    targets: tuple[DatumTargetRecord, ...] = ()

    def __post_init__(self) -> None:
        if not self.datum_id.strip():
            raise ValueError("DatumFeatureRecord.datum_id must be non-empty")
        if not self.datum_label.strip():
            raise ValueError("DatumFeatureRecord.datum_label must be non-empty")


class DatumTargetKind(StrEnum):
    POINT = "POINT"
    LINE = "LINE"
    AREA = "AREA"


@dataclass(frozen=True, slots=True)
class DatumTargetRecord:
    target_id: str
    associated_datum: str
    kind: DatumTargetKind
    location_description: str | None
    extent_mm: Decimal | None
    area_shape: str | None      # "CIRCLE", "RECTANGLE"
    source_note: str | None

    def __post_init__(self) -> None:
        if not self.target_id.strip():
            raise ValueError("DatumTargetRecord.target_id must be non-empty")
        if not self.associated_datum.strip():
            raise ValueError("DatumTargetRecord.associated_datum must be non-empty")


class DatumCompositionKind(StrEnum):
    SINGLE = "SINGLE"       # one feature, one label
    COMMON = "COMMON"       # "A-B" — two coaxial/coplanar features as one datum
    COMPOUND = "COMPOUND"   # two separate features in same precedence slot


@dataclass(frozen=True, slots=True)
class CompoundDatumDefinition:
    composition: DatumCompositionKind
    members: tuple[str, ...]    # ("A",) or ("A","B")
    combined_label: str         # "A" or "A-B"

    def __post_init__(self) -> None:
        if not self.combined_label.strip():
            raise ValueError("CompoundDatumDefinition.combined_label must be non-empty")


@dataclass(frozen=True, slots=True)
class AdvancedDatumRef:
    """Datum reference with boundary modifier (Phase 04B)."""
    label: str
    precedence: int
    boundary_modifier: DatumBoundaryModifier = DatumBoundaryModifier.RMB
    allows_shift: bool = False
    compound_members: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("AdvancedDatumRef.label must be non-empty")
        if self.precedence not in (1, 2, 3):
            raise ValueError("AdvancedDatumRef.precedence must be 1, 2, or 3")


@dataclass(frozen=True, slots=True)
class AdvancedDatumReferenceFrame:
    """DRF with boundary modifiers and a deterministic fingerprint."""
    drf_id: str
    primary: AdvancedDatumRef
    secondary: AdvancedDatumRef | None = None
    tertiary: AdvancedDatumRef | None = None
    is_simultaneous: bool = False

    def __post_init__(self) -> None:
        if not self.drf_id.strip():
            raise ValueError("AdvancedDatumReferenceFrame.drf_id must be non-empty")
        if self.tertiary is not None and self.secondary is None:
            raise ValueError("AdvancedDatumReferenceFrame: tertiary requires secondary")

    @property
    def drf_fingerprint(self) -> str:
        parts = [self.primary.label, self.primary.boundary_modifier.value]
        if self.secondary:
            parts += [self.secondary.label, self.secondary.boundary_modifier.value]
        if self.tertiary:
            parts += [self.tertiary.label, self.tertiary.boundary_modifier.value]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]

    @property
    def labels(self) -> tuple[str, ...]:
        result = [self.primary.label]
        if self.secondary:
            result.append(self.secondary.label)
        if self.tertiary:
            result.append(self.tertiary.label)
        return tuple(result)


# ---------------------------------------------------------------------------
# Phase 04B: Tolerance zone geometry
# ---------------------------------------------------------------------------

class ToleranceZoneGeometry(StrEnum):
    TWO_PARALLEL_LINES = "TWO_PARALLEL_LINES"
    TWO_PARALLEL_PLANES = "TWO_PARALLEL_PLANES"
    CYLINDRICAL = "CYLINDRICAL"
    TWO_CONCENTRIC_CIRCLES = "TWO_CONCENTRIC_CIRCLES"
    TWO_COAXIAL_CYLINDERS = "TWO_COAXIAL_CYLINDERS"
    SPHERICAL = "SPHERICAL"
    PROFILE_ENVELOPE = "PROFILE_ENVELOPE"
    ANGULAR_SECTOR = "ANGULAR_SECTOR"
    UNKNOWN = "UNKNOWN"


def zone_geometry_for(
    characteristic: GdtCharacteristic,
    diameter_zone: bool = False,
) -> ToleranceZoneGeometry:
    """Deterministic zone geometry mapping per ASME Y14.5-2018 / ISO 1101:2017."""
    if characteristic == GdtCharacteristic.FLATNESS:
        return ToleranceZoneGeometry.TWO_PARALLEL_PLANES
    if characteristic == GdtCharacteristic.CIRCULARITY:
        return ToleranceZoneGeometry.TWO_CONCENTRIC_CIRCLES
    if characteristic == GdtCharacteristic.CYLINDRICITY:
        return ToleranceZoneGeometry.TWO_COAXIAL_CYLINDERS
    if characteristic == GdtCharacteristic.STRAIGHTNESS:
        if diameter_zone:
            return ToleranceZoneGeometry.CYLINDRICAL
        return ToleranceZoneGeometry.TWO_PARALLEL_LINES
    if characteristic == GdtCharacteristic.POSITION:
        if diameter_zone:
            return ToleranceZoneGeometry.CYLINDRICAL
        return ToleranceZoneGeometry.TWO_PARALLEL_PLANES
    if characteristic in (GdtCharacteristic.PERPENDICULARITY, GdtCharacteristic.PARALLELISM):
        if diameter_zone:
            return ToleranceZoneGeometry.CYLINDRICAL
        return ToleranceZoneGeometry.TWO_PARALLEL_PLANES
    if characteristic == GdtCharacteristic.ANGULARITY:
        return ToleranceZoneGeometry.ANGULAR_SECTOR
    if characteristic == GdtCharacteristic.CIRCULAR_RUNOUT:
        return ToleranceZoneGeometry.TWO_CONCENTRIC_CIRCLES
    if characteristic == GdtCharacteristic.TOTAL_RUNOUT:
        return ToleranceZoneGeometry.TWO_COAXIAL_CYLINDERS
    if characteristic == GdtCharacteristic.PROFILE_OF_A_LINE:
        return ToleranceZoneGeometry.TWO_PARALLEL_LINES
    if characteristic == GdtCharacteristic.PROFILE_OF_A_SURFACE:
        return ToleranceZoneGeometry.PROFILE_ENVELOPE
    return ToleranceZoneGeometry.UNKNOWN


# ---------------------------------------------------------------------------
# Phase 04B: Basic dimensions
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class BasicDimension:
    """Exact theoretical dimension linking to feature control frames."""
    basic_id: str
    value: Decimal
    unit: str
    direction: str | None           # "X", "Y", "Z", "ANGULAR", "RADIAL"
    source_dimension_id: str | None
    linked_fcf_ids: tuple[str, ...] = ()
    linked_feature_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.basic_id.strip():
            raise ValueError("BasicDimension.basic_id must be non-empty")
        if self.value <= Decimal(0):
            raise ValueError("BasicDimension.value must be > 0")

    @property
    def is_orphan(self) -> bool:
        return len(self.linked_fcf_ids) == 0


# ---------------------------------------------------------------------------
# Phase 04B: Feature patterns
# ---------------------------------------------------------------------------

class PatternKind(StrEnum):
    LINEAR = "LINEAR"
    CIRCULAR = "CIRCULAR"       # bolt circle / PCD pattern
    RECTANGULAR = "RECTANGULAR"
    IRREGULAR = "IRREGULAR"


@dataclass(frozen=True, slots=True)
class FeaturePattern:
    pattern_id: str
    kind: PatternKind
    member_feature_ids: tuple[str, ...]
    count: int
    pattern_fcf_id: str | None
    individual_fcf_ids: tuple[str, ...] = ()
    basic_spacing_mm: Decimal | None = None
    basic_pcd_mm: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.pattern_id.strip():
            raise ValueError("FeaturePattern.pattern_id must be non-empty")
        if self.count < 1:
            raise ValueError("FeaturePattern.count must be >= 1")


# ---------------------------------------------------------------------------
# Phase 04B: Projected tolerance zone
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProjectedToleranceZone:
    """Projected tolerance zone for threaded/press-fit holes."""
    projected_height_mm: Decimal
    direction: str = "ABOVE"    # "ABOVE" | "BELOW" | "BOTH"
    applicability_note: str | None = None

    def __post_init__(self) -> None:
        if self.projected_height_mm <= Decimal(0):
            raise ValueError("ProjectedToleranceZone.projected_height_mm must be > 0")
        if self.direction not in ("ABOVE", "BELOW", "BOTH"):
            raise ValueError("ProjectedToleranceZone.direction must be ABOVE, BELOW, or BOTH")


# ---------------------------------------------------------------------------
# Phase 04B: Composite FCF
# ---------------------------------------------------------------------------

class SegmentIntent(StrEnum):
    PATTERN_LOCATING_TOLERANCE_ZONE = "PLTZF"   # upper — locates pattern to datums
    FEATURE_RELATING_TOLERANCE_ZONE = "FRTZF"   # lower — inter-feature relationship


@dataclass(frozen=True, slots=True)
class FCFSegment:
    segment_index: int
    characteristic: GdtCharacteristic
    tolerance_value: Decimal
    tolerance_unit: str
    diameter_zone: bool
    modifier: FeatureModifier
    datum_frame: DatumReferenceFrame | None
    intent: SegmentIntent

    def __post_init__(self) -> None:
        if self.segment_index < 0:
            raise ValueError("FCFSegment.segment_index must be >= 0")
        if self.tolerance_value <= Decimal(0):
            raise ValueError("FCFSegment.tolerance_value must be > 0")


@dataclass(frozen=True, slots=True)
class CompositePositionFCF:
    """Two-segment composite position FCF (PLTZF + FRTZF)."""
    fcf_id: str
    segments: tuple[FCFSegment, ...]

    def __post_init__(self) -> None:
        if not self.fcf_id.strip():
            raise ValueError("CompositePositionFCF.fcf_id must be non-empty")
        if len(self.segments) < 2:
            raise ValueError("CompositePositionFCF requires at least 2 segments")
        if (self.segments[1].tolerance_value > self.segments[0].tolerance_value):
            raise ValueError(
                "CompositePositionFCF: lower segment tolerance must be <= upper segment "
                "(GDT_COMPOSITE_TOLERANCE_INVERTED)"
            )


# ---------------------------------------------------------------------------
# Phase 04B: Bonus tolerance and virtual condition
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class BonusToleranceResult:
    """Bonus tolerance calculation result.

    FABRICATED_ACTUAL_SIZE=NO — computed=False whenever actual_size_mm is None.
    """
    computed: bool
    stated_tolerance: Decimal
    bonus_amount: Decimal | None      # None when computed=False
    total_tolerance: Decimal | None   # None when computed=False
    actual_size_mm: Decimal | None
    mmc_or_lmc_size_mm: Decimal | None
    reason_not_computed: str | None

    @property
    def safe_total(self) -> Decimal:
        return self.total_tolerance if self.total_tolerance is not None else self.stated_tolerance


@dataclass(frozen=True, slots=True)
class VirtualConditionResult:
    """Virtual condition (worst-case boundary) calculation result."""
    computed: bool
    virtual_condition_mm: Decimal | None
    description: str


# ---------------------------------------------------------------------------
# Phase 04B: Ambiguity and confidence
# ---------------------------------------------------------------------------

class AmbiguityKind(StrEnum):
    MISSING_DATUM = "MISSING_DATUM"
    UNRESOLVED_FCF = "UNRESOLVED_FCF"
    MULTIPLE_CANDIDATE_FEATURES = "MULTIPLE_CANDIDATE_FEATURES"
    INVALID_MODIFIER_COMBO = "INVALID_MODIFIER_COMBO"
    AMBIGUOUS_FOS = "AMBIGUOUS_FOS"
    ORPHAN_BASIC_DIMENSION = "ORPHAN_BASIC_DIMENSION"
    COMPOUND_DATUM_UNRESOLVED = "COMPOUND_DATUM_UNRESOLVED"
    LEGACY_CHARACTERISTIC = "LEGACY_CHARACTERISTIC"
    COMPOSITE_TOLERANCE_INVERTED = "COMPOSITE_TOLERANCE_INVERTED"
    PATTERN_COUNT_MISMATCH = "PATTERN_COUNT_MISMATCH"


@dataclass(frozen=True, slots=True)
class GdtAmbiguity:
    ambiguity_id: str
    kind: AmbiguityKind
    affected_ids: tuple[str, ...]
    description: str
    severity: str               # "ERROR" | "WARNING" | "INFO"
    suggested_resolution: str | None

    def __post_init__(self) -> None:
        if not self.ambiguity_id.strip():
            raise ValueError("GdtAmbiguity.ambiguity_id must be non-empty")
        if self.severity not in ("ERROR", "WARNING", "INFO"):
            raise ValueError("GdtAmbiguity.severity must be ERROR, WARNING, or INFO")


class GdtConfidence(StrEnum):
    EXACT_STRUCTURED = "EXACT_STRUCTURED"   # parsed from well-formed vector FCF
    RULE_PARSED = "RULE_PARSED"             # structured OCR, high confidence
    GEOMETRY_MATCHED = "GEOMETRY_MATCHED"   # spatial/geometry association
    PATTERN_MATCHED = "PATTERN_MATCHED"     # inferred via pattern rule
    INFERRED = "INFERRED"                   # heuristic — low confidence
    USER_CONFIRMED = "USER_CONFIRMED"       # user resolved in review UI
    AMBIGUOUS = "AMBIGUOUS"                 # multiple interpretations, not resolved


# ---------------------------------------------------------------------------
# Phase 04B: Setup planning hints
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SetupPlanHint:
    """Datum-driven setup planning hints derived from the DRF."""
    source_id: str
    primary_datum_label: str
    primary_setup_note: str
    secondary_datum_label: str | None
    secondary_setup_note: str | None
    tertiary_datum_label: str | None
    tertiary_setup_note: str | None
    same_setup_requirements: tuple[str, ...] = ()   # FCF IDs that must share same setup
    access_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("SetupPlanHint.source_id must be non-empty")


# ---------------------------------------------------------------------------
# Phase 04B: Tolerance precedence
# ---------------------------------------------------------------------------

class TolerancePrecedence(StrEnum):
    SPECIFIC_GDT = "SPECIFIC_GDT"
    SPECIFIC_DIMENSION = "SPECIFIC_DIMENSION"
    SPECIFIC_NOTE = "SPECIFIC_NOTE"
    TITLE_BLOCK_TOLERANCE = "TITLE_BLOCK_TOLERANCE"
    GENERAL_STANDARD = "GENERAL_STANDARD"
    DEFAULT_UNKNOWN = "DEFAULT_UNKNOWN"


# ---------------------------------------------------------------------------
# Datum / DRF model (Phase 04 original — kept for backward compatibility)
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
        """Stable hex digest for traceability (includes GD&T modifiers and DRF labels)."""
        modifier_hash = hashlib.sha256(
            "|".join(
                f"{g.req_id}:{g.fcf.modifier.value}:{g.fcf.characteristic.value}"
                for g in self.geometric
            ).encode()
        ).hexdigest()[:8]
        drf_hash = hashlib.sha256(
            "|".join(
                ":".join(g.fcf.datum_frame.labels) if g.fcf.datum_frame else "NONE"
                for g in self.geometric
            ).encode()
        ).hexdigest()[:8]
        payload = (
            f"{self.source_id}|{self.drawing_number}|{self.revision}"
            f"|D{len(self.dimensional)}|G{len(self.geometric)}"
            f"|S{len(self.surface_finish)}|T{len(self.threads)}"
            f"|GDT_MODIFIERS:{modifier_hash}|DRF_SEQUENCE:{drf_hash}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _req_id(prefix: str, index: int) -> str:
    """Generate deterministic requirement ID."""
    return f"{prefix}-{index:04d}"
