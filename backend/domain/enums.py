"""Canonical domain enumerations for Machinery AI.

All enums are :class:`enum.StrEnum` so they serialize directly to their
canonical string form (JSON-friendly, deterministic).
"""

from __future__ import annotations

from enum import StrEnum


class ProvenanceType(StrEnum):
    """Where a piece of engineering information came from.

    ``AI_SUGGESTION`` is intentionally explicit: AI-derived values must remain
    distinguishable from authoritative engineering values at all times.
    """

    USER_INPUT = "USER_INPUT"
    DRAWING = "DRAWING"
    CAD = "CAD"
    MANUFACTURER_DATA = "MANUFACTURER_DATA"
    MATERIAL_STANDARD = "MATERIAL_STANDARD"
    ENGINEERING_STANDARD = "ENGINEERING_STANDARD"
    LITERATURE = "LITERATURE"
    HISTORICAL_PROCESS_DATA = "HISTORICAL_PROCESS_DATA"
    DETERMINISTIC_CALCULATION = "DETERMINISTIC_CALCULATION"
    AI_SUGGESTION = "AI_SUGGESTION"
    UNKNOWN = "UNKNOWN"


class FeatureType(StrEnum):
    """Machinable / manufacturing feature kinds."""

    HOLE = "hole"
    POCKET = "pocket"
    SLOT = "slot"
    PLANAR_FACE = "planar_face"
    CYLINDRICAL_SURFACE = "cylindrical_surface"
    THREAD = "thread"
    CHAMFER = "chamfer"
    FILLET = "fillet"
    GROOVE = "groove"
    FREEFORM_SURFACE = "freeform_surface"
    UNKNOWN = "unknown"


class OperationType(StrEnum):
    """Manufacturing operation types supported by the domain model."""

    TURNING = "turning"
    FACING = "facing"
    MILLING = "milling"
    DRILLING = "drilling"
    BORING = "boring"
    REAMING = "reaming"
    TAPPING = "tapping"
    THREADING = "threading"
    HONING = "honing"      # Stage 3K — bore-wall honing
    LAPPING = "lapping"    # Stage 3L — flat/cylindrical lapping
    GRINDING = "grinding"
    DEBURRING = "deburring"
    INSPECTION = "inspection"
    HEAT_TREATMENT = "heat_treatment"
    OTHER = "other"


class OperationStatus(StrEnum):
    """Lifecycle status of a single planned/recorded operation."""

    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MaterialFamily(StrEnum):
    """Coarse material family classification."""

    STEEL = "steel"
    STAINLESS_STEEL = "stainless_steel"
    CAST_IRON = "cast_iron"
    ALUMINUM = "aluminum"
    COPPER_ALLOY = "copper_alloy"
    TITANIUM = "titanium"
    NICKEL_ALLOY = "nickel_alloy"
    PLASTIC = "plastic"
    COMPOSITE = "composite"
    GRAPHITE = "graphite"
    CERAMIC_MATERIAL = "ceramic_material"
    OTHER = "other"


class ToolType(StrEnum):
    """Cutting-tool classification."""

    DRILL = "drill"
    END_MILL = "end_mill"
    FACE_MILL = "face_mill"
    TURNING_INSERT = "turning_insert"
    BORING_BAR = "boring_bar"
    REAMER = "reamer"
    TAP = "tap"
    THREAD_MILL = "thread_mill"
    GRINDING_WHEEL = "grinding_wheel"
    DEBURRING_TOOL = "deburring_tool"
    PROBE = "probe"
    OTHER = "other"


class MachineType(StrEnum):
    """Machine-tool classification (axis detail is a separate field)."""

    MILL = "mill"
    LATHE = "lathe"
    MILL_TURN = "mill_turn"
    GRINDER = "grinder"
    EDM = "edm"
    OTHER = "other"


class CoolantMode(StrEnum):
    """Coolant delivery strategy for an operation."""

    NONE = "none"
    FLOOD = "flood"
    MIST = "mist"
    THROUGH_TOOL = "through_tool"
    AIR_BLAST = "air_blast"


class ResultStatus(StrEnum):
    """Deterministic engineering result status.

    ``INSUFFICIENT_DATA`` is fail-closed: missing inputs never become PASS.
    """

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class IsoMaterialGroup(StrEnum):
    """ISO 513 cutting material group classification."""

    P = "P"
    M = "M"
    K = "K"
    N = "N"
    S = "S"
    H = "H"


class IsoMaterialSubGroup(StrEnum):
    """Fine-grain ISO 513 sub-group — S must split Ti vs Ni-HRSA.

    ``UNSPECIFIED`` is used when sub-group is not applicable or unknown.
    """

    P_STEEL = "P_STEEL"
    M_STAINLESS = "M_STAINLESS"
    K_CAST_IRON = "K_CAST_IRON"
    N_ALUMINUM = "N_ALUMINUM"
    N_COPPER = "N_COPPER"
    # S must never be left undifferentiated — machinability differs dramatically.
    S_TITANIUM = "S_TITANIUM"
    S_NICKEL_HRSA = "S_NICKEL_HRSA"
    H_HARDENED = "H_HARDENED"
    UNSPECIFIED = "UNSPECIFIED"


class DataConfidence(StrEnum):
    """Data confidence tier for material property values.

    Values presented to users must carry explicit confidence levels.
    ``GENERAL_INDUSTRY`` and ``ESTIMATED`` mandate a REFERENCE_ONLY badge in UI.
    """

    VERIFIED_STANDARD = "VERIFIED_STANDARD"
    MANUFACTURER_REFERENCE = "MANUFACTURER_REFERENCE"
    MANUFACTURER_LEGACY = "MANUFACTURER_LEGACY"
    LITERATURE_REFERENCE = "LITERATURE_REFERENCE"
    INTERNAL_VALIDATED = "INTERNAL_VALIDATED"
    USER_PROVIDED = "USER_PROVIDED"
    ESTIMATED = "ESTIMATED"
    GENERAL_INDUSTRY = "GENERAL_INDUSTRY"
    UNKNOWN = "UNKNOWN"


class ToolCompatRating(StrEnum):
    """Tool-material compatibility rating (from Programlar matrix, REFERENCE_ONLY)."""

    RECOMMENDED = "RECOMMENDED"
    ACCEPTABLE = "ACCEPTABLE"
    CONDITIONAL = "CONDITIONAL"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ChipFormationClass(StrEnum):
    """Qualitative chip formation behaviour."""

    CONTINUOUS = "CONTINUOUS"
    SEGMENTED = "SEGMENTED"
    POWDER = "POWDER"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class MachinabilityLevel(StrEnum):
    """Qualitative machinability descriptor (work hardening, BUE, abrasiveness, thermal)."""

    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"
    EXTREME = "EXTREME"
    UNKNOWN = "UNKNOWN"


class ToolMaterial(StrEnum):
    """Cutting tool substrate / material classification."""

    HSS = "HSS"
    CARBIDE = "carbide"
    CERMET = "cermet"
    CERAMIC = "ceramic"
    CBN = "CBN"
    PCD = "PCD"
