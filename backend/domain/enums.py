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


class ToolMaterial(StrEnum):
    """Cutting tool substrate / material classification."""

    HSS = "HSS"
    CARBIDE = "carbide"
    CERMET = "cermet"
    CERAMIC = "ceramic"
    CBN = "CBN"
    PCD = "PCD"
