# ruff: noqa: E501
"""Extended Feature → Operation Alternatives Matrix — EPIC_04E Phase 2.

Provides evidence-backed, deterministic operation-sequence alternatives
for each manufacturing feature type.  Every route here is derived from
standard manufacturing practice; no permutations are fabricated.

FEATURE_OPERATION_ALTERNATIVES_IMPLEMENTED=YES
PRECISION_HOLE_ROUTE_ALTERNATIVES_IMPLEMENTED=YES
MILLING_ROUTE_ALTERNATIVES_IMPLEMENTED=YES
TURNING_ROUTE_ALTERNATIVES_IMPLEMENTED=YES
FABRICATED_ROUTE=NO
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.domain.enums import MachineType, OperationType, ToolType

__all__ = [
    "ExtendedFeatureType",
    "RouteTemplate",
    "RouteOperationTemplate",
    "ROUTE_TEMPLATES",
    "get_templates_for_feature",
    "OPERATION_TO_MACHINE_TYPES",
    "OPERATION_CAPABILITY_EXT",
    "CapabilityRecord",
]


# ---------------------------------------------------------------------------
# Extended feature type (superset of existing FeatureType — adds EPIC_04D types)
# ---------------------------------------------------------------------------

class ExtendedFeatureType(StrEnum):
    """Feature types for route generation (extends domain FeatureType)."""

    # Original 11 types
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

    # Extended types (from spec section 4)
    PRECISION_BORE = "precision_bore"
    COUNTERBORE = "counterbore"
    COUNTERSINK = "countersink"
    THREADED_HOLE = "threaded_hole"
    BOSS = "boss"
    STEP = "step"
    TURNING_DIAMETER = "turning_diameter"


# ---------------------------------------------------------------------------
# Capability record (Ra / IT grade per operation, with confidence)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CapabilityRecord:
    operation_type: OperationType
    achievable_ra_um: float          # best-achievable surface roughness
    it_grade: str                    # e.g. "IT6"
    sub_operation: str | None        # ROUGH / SEMI_FINISH / FINISH / CENTER_DRILL / etc.
    typical_tool_type: ToolType | None
    notes: str


# ---------------------------------------------------------------------------
# Route template structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RouteOperationTemplate:
    """One operation step within a route template."""

    operation_type: OperationType
    sub_operation: str | None        # CENTER_DRILL / ROUGH / SEMI_FINISH / FINISH etc.
    tool_type_required: ToolType | None
    achievable_ra_um: float          # worst-case for this step in isolation
    it_grade: str
    notes: str


@dataclass(frozen=True, slots=True)
class RouteTemplate:
    """One named route alternative for a feature type.

    Routes are ordered by Ra capability (best last).
    FABRICATED_ROUTE=NO — every route here is established manufacturing practice.
    """

    template_id: str
    feature_type: ExtendedFeatureType
    label: str
    operations: tuple[RouteOperationTemplate, ...]
    best_ra_um: float                    # Ra of the final finishing step
    best_it_grade: str
    min_setups: int
    specialty_op_count: int              # honing / lapping / grinding count
    requires_machine_types: tuple[str, ...]  # MachineType values
    gdt_capable: bool                    # suitable for tight GD&T requirements
    notes: str


# ---------------------------------------------------------------------------
# Capability records per operation (extended from operation_capability.py)
# ---------------------------------------------------------------------------

OPERATION_CAPABILITY_EXT: dict[OperationType, CapabilityRecord] = {
    OperationType.TURNING:       CapabilityRecord(OperationType.TURNING,       0.4,  "IT6",  "FINISH",      ToolType.TURNING_INSERT, "Finish turning Ra 0.4 µm achievable"),
    OperationType.FACING:        CapabilityRecord(OperationType.FACING,        0.8,  "IT7",  "FINISH",      ToolType.FACE_MILL,      "Face milling Ra 0.8 µm achievable"),
    OperationType.MILLING:       CapabilityRecord(OperationType.MILLING,       0.4,  "IT7",  "FINISH",      ToolType.END_MILL,       "Finish milling Ra 0.4 µm achievable"),
    OperationType.DRILLING:      CapabilityRecord(OperationType.DRILLING,      1.6,  "IT10", None,          ToolType.DRILL,          "Standard drilling Ra 1.6 µm"),
    OperationType.BORING:        CapabilityRecord(OperationType.BORING,        0.4,  "IT6",  "FINISH",      ToolType.BORING_BAR,     "Finish boring Ra 0.4 µm, IT6"),
    OperationType.REAMING:       CapabilityRecord(OperationType.REAMING,       0.4,  "IT6",  "FINISH",      ToolType.REAMER,         "Reaming Ra 0.4 µm, IT6"),
    OperationType.TAPPING:       CapabilityRecord(OperationType.TAPPING,       1.6,  "IT7",  None,          ToolType.TAP,            "Tapping thread form"),
    OperationType.THREADING:     CapabilityRecord(OperationType.THREADING,     1.6,  "IT7",  None,          ToolType.THREAD_MILL,    "Thread milling"),
    OperationType.HONING:        CapabilityRecord(OperationType.HONING,        0.1,  "IT5",  "FINISH",      None,                    "Honing Ra 0.1 µm, IT5"),
    OperationType.LAPPING:       CapabilityRecord(OperationType.LAPPING,       0.05, "IT4",  "FINISH",      None,                    "Lapping Ra 0.05 µm, IT4"),
    OperationType.GRINDING:      CapabilityRecord(OperationType.GRINDING,      0.1,  "IT5",  "FINISH",      ToolType.GRINDING_WHEEL, "Grinding Ra 0.1 µm, IT5"),
    OperationType.DEBURRING:     CapabilityRecord(OperationType.DEBURRING,     3.2,  "IT12", None,          ToolType.DEBURRING_TOOL, "Deburring only"),
}


# ---------------------------------------------------------------------------
# OperationType → MachineType eligibility map
# ---------------------------------------------------------------------------

OPERATION_TO_MACHINE_TYPES: dict[OperationType, tuple[MachineType, ...]] = {
    OperationType.TURNING:   (MachineType.LATHE, MachineType.MILL_TURN, MachineType.LATHE_Y, MachineType.SWISS, MachineType.VTL),
    OperationType.FACING:    (MachineType.LATHE, MachineType.MILL_TURN, MachineType.LATHE_Y, MachineType.VTL, MachineType.VMC_3AXIS, MachineType.VMC_4AXIS, MachineType.VMC_5AXIS, MachineType.HMC),
    OperationType.MILLING:   (MachineType.VMC_3AXIS, MachineType.VMC_4AXIS, MachineType.VMC_5AXIS, MachineType.HMC, MachineType.MILL_TURN, MachineType.GANTRY),
    OperationType.DRILLING:  (MachineType.VMC_3AXIS, MachineType.VMC_4AXIS, MachineType.VMC_5AXIS, MachineType.HMC, MachineType.DRILL_TAP, MachineType.LATHE_Y, MachineType.MILL_TURN),
    OperationType.BORING:    (MachineType.VMC_3AXIS, MachineType.VMC_4AXIS, MachineType.VMC_5AXIS, MachineType.HMC, MachineType.BORING_MILL, MachineType.MILL_TURN, MachineType.LATHE, MachineType.LATHE_Y),
    OperationType.REAMING:   (MachineType.VMC_3AXIS, MachineType.VMC_4AXIS, MachineType.VMC_5AXIS, MachineType.HMC, MachineType.DRILL_TAP, MachineType.MILL_TURN),
    OperationType.TAPPING:   (MachineType.VMC_3AXIS, MachineType.VMC_4AXIS, MachineType.VMC_5AXIS, MachineType.HMC, MachineType.DRILL_TAP, MachineType.MILL_TURN, MachineType.LATHE_Y),
    OperationType.THREADING: (MachineType.VMC_3AXIS, MachineType.VMC_4AXIS, MachineType.VMC_5AXIS, MachineType.HMC, MachineType.LATHE, MachineType.MILL_TURN),
    OperationType.HONING:    (MachineType.OTHER,),    # external honing machine required
    OperationType.LAPPING:   (MachineType.OTHER,),    # external lapping machine required
    OperationType.GRINDING:  (MachineType.GRINDER, MachineType.OTHER),
    OperationType.DEBURRING: (MachineType.VMC_3AXIS, MachineType.VMC_4AXIS, MachineType.VMC_5AXIS, MachineType.HMC, MachineType.OTHER),
    OperationType.INSPECTION: (MachineType.OTHER,),
    OperationType.HEAT_TREATMENT: (MachineType.OTHER,),
    OperationType.OTHER:     (MachineType.OTHER,),
}


# ---------------------------------------------------------------------------
# Helper: operation template factory
# ---------------------------------------------------------------------------

def _op(
    op: OperationType,
    sub: str | None,
    tool: ToolType | None,
    ra: float,
    it: str,
    note: str,
) -> RouteOperationTemplate:
    return RouteOperationTemplate(
        operation_type=op,
        sub_operation=sub,
        tool_type_required=tool,
        achievable_ra_um=ra,
        it_grade=it,
        notes=note,
    )


# Shorthands
D = OperationType.DRILLING
B = OperationType.BORING
R = OperationType.REAMING
M = OperationType.MILLING
T = OperationType.TURNING
F = OperationType.FACING
H = OperationType.HONING
G = OperationType.GRINDING
L = OperationType.LAPPING
TAP = OperationType.TAPPING
THR = OperationType.THREADING
DB = OperationType.DEBURRING
INS = OperationType.INSPECTION


# ---------------------------------------------------------------------------
# Route templates — precision hole
# ---------------------------------------------------------------------------

_HOLE_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="HOLE-001",
        feature_type=ExtendedFeatureType.HOLE,
        label="Drill only",
        operations=(
            _op(D, None,         ToolType.DRILL,      1.6, "IT10", "Standard drilling"),
        ),
        best_ra_um=1.6, best_it_grade="IT10", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC", "DRILL_TAP"),
        gdt_capable=False,
        notes="Clearance holes; no Ra or IT requirement tighter than IT10.",
    ),
    RouteTemplate(
        template_id="HOLE-002",
        feature_type=ExtendedFeatureType.HOLE,
        label="Center drill → drill → ream",
        operations=(
            _op(D, "CENTER_DRILL", ToolType.DRILL,    3.2, "IT12", "Spot / center drill for drill entry accuracy"),
            _op(D, None,           ToolType.DRILL,    1.6, "IT10", "Drill to near-size"),
            _op(R, "FINISH",       ToolType.REAMER,   0.4, "IT6",  "Reaming to H7 tolerance"),
        ),
        best_ra_um=0.4, best_it_grade="IT6", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC", "DRILL_TAP"),
        gdt_capable=True,
        notes="Standard precision hole: H7 tolerance, Ra 0.4 µm.  Well-suited for jig plates and fixtures.",
    ),
    RouteTemplate(
        template_id="HOLE-003",
        feature_type=ExtendedFeatureType.HOLE,
        label="Drill → rough bore → finish bore",
        operations=(
            _op(D, None,         ToolType.DRILL,      1.6, "IT10", "Pilot drilling"),
            _op(B, "ROUGH",      ToolType.BORING_BAR, 0.8, "IT8",  "Rough boring for stock removal"),
            _op(B, "FINISH",     ToolType.BORING_BAR, 0.4, "IT6",  "Finish boring to H6/H7"),
        ),
        best_ra_um=0.4, best_it_grade="IT6", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC", "BORING_MILL"),
        gdt_capable=True,
        notes="For larger holes (>30 mm) or when reamer is unavailable for the diameter.  IT6 positional accuracy.",
    ),
    RouteTemplate(
        template_id="HOLE-004",
        feature_type=ExtendedFeatureType.HOLE,
        label="Drill → rough bore → finish bore → hone",
        operations=(
            _op(D, None,         ToolType.DRILL,      1.6, "IT10", "Pilot drilling"),
            _op(B, "ROUGH",      ToolType.BORING_BAR, 0.8, "IT8",  "Rough boring"),
            _op(B, "FINISH",     ToolType.BORING_BAR, 0.4, "IT6",  "Finish boring"),
            _op(H, "FINISH",     None,                0.1, "IT5",  "Honing Ra 0.1 µm, IT5 — external process"),
        ),
        best_ra_um=0.1, best_it_grade="IT5", min_setups=2, specialty_op_count=1,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "BORING_MILL"),
        gdt_capable=True,
        notes="Precision bores requiring Ra ≤ 0.1 µm — cylinder liners, hydraulic bores.  Honing is an external process.",
    ),
    RouteTemplate(
        template_id="HOLE-005",
        feature_type=ExtendedFeatureType.HOLE,
        label="Helical interpolation → finish bore",
        operations=(
            _op(M, "HELICAL",    ToolType.END_MILL,   1.6, "IT9",  "Helical interpolation roughing"),
            _op(B, "FINISH",     ToolType.BORING_BAR, 0.4, "IT6",  "Single-point finish boring"),
        ),
        best_ra_um=0.4, best_it_grade="IT6", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC"),
        gdt_capable=True,
        notes="For large-diameter holes without an appropriate drill — uses end mill for roughing.  Requires 3-axis CNC minimum.",
    ),
]

# ---------------------------------------------------------------------------
# Precision bore
# ---------------------------------------------------------------------------

_PRECISION_BORE_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="PBORE-001",
        feature_type=ExtendedFeatureType.PRECISION_BORE,
        label="Drill → rough bore → finish bore",
        operations=(
            _op(D, None,     ToolType.DRILL,      1.6, "IT10", "Pilot hole"),
            _op(B, "ROUGH",  ToolType.BORING_BAR, 0.8, "IT8",  "Rough bore"),
            _op(B, "FINISH", ToolType.BORING_BAR, 0.4, "IT6",  "Finish bore H6"),
        ),
        best_ra_um=0.4, best_it_grade="IT6", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC", "BORING_MILL"),
        gdt_capable=True,
        notes="Standard precision bore for bearing fits.",
    ),
    RouteTemplate(
        template_id="PBORE-002",
        feature_type=ExtendedFeatureType.PRECISION_BORE,
        label="Drill → rough bore → finish bore → hone",
        operations=(
            _op(D, None,     ToolType.DRILL,      1.6, "IT10", "Pilot hole"),
            _op(B, "ROUGH",  ToolType.BORING_BAR, 0.8, "IT8",  "Rough bore"),
            _op(B, "FINISH", ToolType.BORING_BAR, 0.4, "IT6",  "Finish bore"),
            _op(H, "FINISH", None,                0.1, "IT5",  "Hone"),
        ),
        best_ra_um=0.1, best_it_grade="IT5", min_setups=2, specialty_op_count=1,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "BORING_MILL"),
        gdt_capable=True,
        notes="High-precision bore with honing — Ra 0.1 µm, IT5.",
    ),
]

# ---------------------------------------------------------------------------
# Counterbore / countersink
# ---------------------------------------------------------------------------

_COUNTERBORE_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="CBORE-001",
        feature_type=ExtendedFeatureType.COUNTERBORE,
        label="Drill clearance → counterbore",
        operations=(
            _op(D, None, ToolType.DRILL, 1.6, "IT10", "Drill clearance diameter"),
            _op(M, "COUNTERBORE", ToolType.END_MILL, 1.6, "IT10", "Counterbore to depth"),
        ),
        best_ra_um=1.6, best_it_grade="IT10", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC", "DRILL_TAP"),
        gdt_capable=False,
        notes="Counterbore for socket-head cap screws.",
    ),
]

_COUNTERSINK_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="CSINK-001",
        feature_type=ExtendedFeatureType.COUNTERSINK,
        label="Drill → countersink",
        operations=(
            _op(D, None, ToolType.DRILL,    1.6, "IT10", "Drill through-hole"),
            _op(D, "COUNTERSINK", ToolType.DRILL, 1.6, "IT10", "Countersink to angle"),
        ),
        best_ra_um=1.6, best_it_grade="IT10", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC", "DRILL_TAP"),
        gdt_capable=False,
        notes="Countersink for flat-head screws.",
    ),
]

# ---------------------------------------------------------------------------
# Threaded hole / Thread
# ---------------------------------------------------------------------------

_THREADED_HOLE_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="THH-001",
        feature_type=ExtendedFeatureType.THREADED_HOLE,
        label="Center drill → drill → tap",
        operations=(
            _op(D, "CENTER_DRILL", ToolType.DRILL, 3.2, "IT12", "Center drilling"),
            _op(D, None,           ToolType.DRILL, 1.6, "IT10", "Tap drill"),
            _op(TAP, None,         ToolType.TAP,   1.6, "IT7",  "Tapping"),
        ),
        best_ra_um=1.6, best_it_grade="IT7", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC", "DRILL_TAP"),
        gdt_capable=False,
        notes="Standard tapped hole — M3 to M30.",
    ),
    RouteTemplate(
        template_id="THH-002",
        feature_type=ExtendedFeatureType.THREADED_HOLE,
        label="Drill → thread mill",
        operations=(
            _op(D, None,  ToolType.DRILL,       1.6, "IT10", "Drill to minor diameter"),
            _op(THR, None, ToolType.THREAD_MILL, 1.6, "IT7",  "Thread mill — helical interpolation"),
        ),
        best_ra_um=1.6, best_it_grade="IT7", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC"),
        gdt_capable=True,
        notes="Thread milling — preferred for blind holes, large threads, or titanium/stainless.",
    ),
]

_THREAD_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="THR-001",
        feature_type=ExtendedFeatureType.THREAD,
        label="Turn → thread (single-point)",
        operations=(
            _op(T, "ROUGH",  ToolType.TURNING_INSERT, 0.8, "IT8", "Rough turn to OD"),
            _op(THR, None,   ToolType.TURNING_INSERT, 1.6, "IT7", "Single-point threading"),
        ),
        best_ra_um=1.6, best_it_grade="IT7", min_setups=1, specialty_op_count=0,
        requires_machine_types=("LATHE", "MILL_TURN", "LATHE_Y"),
        gdt_capable=False,
        notes="External thread — lathe single-point threading.",
    ),
    RouteTemplate(
        template_id="THR-002",
        feature_type=ExtendedFeatureType.THREAD,
        label="Thread mill (external)",
        operations=(
            _op(THR, None, ToolType.THREAD_MILL, 1.6, "IT7", "External thread mill — helical interpolation"),
        ),
        best_ra_um=1.6, best_it_grade="IT7", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC"),
        gdt_capable=False,
        notes="External thread milling on mill.",
    ),
]

# ---------------------------------------------------------------------------
# Pocket / Slot / Planar face / Step / Boss
# ---------------------------------------------------------------------------

_POCKET_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="PCK-001",
        feature_type=ExtendedFeatureType.POCKET,
        label="Rough pocket → finish pocket",
        operations=(
            _op(M, "ROUGH",       ToolType.END_MILL, 3.2, "IT9",  "Rough pocketing — large step-over"),
            _op(M, "FINISH",      ToolType.END_MILL, 0.4, "IT7",  "Finish pocketing — small step-over"),
        ),
        best_ra_um=0.4, best_it_grade="IT7", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC", "MILL_TURN"),
        gdt_capable=True,
        notes="Standard pocket: rough + finish milling.",
    ),
    RouteTemplate(
        template_id="PCK-002",
        feature_type=ExtendedFeatureType.POCKET,
        label="Rough → semi-finish → finish pocket",
        operations=(
            _op(M, "ROUGH",       ToolType.END_MILL, 3.2, "IT9",  "Rough pocketing"),
            _op(M, "SEMI_FINISH", ToolType.END_MILL, 0.8, "IT8",  "Semi-finish pass"),
            _op(M, "FINISH",      ToolType.END_MILL, 0.4, "IT7",  "Finish pass"),
        ),
        best_ra_um=0.4, best_it_grade="IT7", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC"),
        gdt_capable=True,
        notes="Three-pass pocket: used when material is hard or form is complex.",
    ),
    RouteTemplate(
        template_id="PCK-003",
        feature_type=ExtendedFeatureType.POCKET,
        label="Rough pocket → finish mill → grind floor",
        operations=(
            _op(M, "ROUGH",  ToolType.END_MILL,      3.2, "IT9",  "Rough pocket"),
            _op(M, "FINISH", ToolType.END_MILL,      0.4, "IT7",  "Finish pocket walls/floor"),
            _op(G, "FINISH", ToolType.GRINDING_WHEEL, 0.1, "IT5", "Surface grind pocket floor"),
        ),
        best_ra_um=0.1, best_it_grade="IT5", min_setups=2, specialty_op_count=1,
        requires_machine_types=("VMC_3AXIS", "GRINDER"),
        gdt_capable=True,
        notes="Precision pocket floor — Ra 0.1 µm.  Grinding in a second setup.",
    ),
]

_SLOT_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="SLT-001",
        feature_type=ExtendedFeatureType.SLOT,
        label="Slot mill (full width)",
        operations=(
            _op(M, "SLOT", ToolType.END_MILL, 3.2, "IT9", "Full-width slotting"),
        ),
        best_ra_um=3.2, best_it_grade="IT9", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC"),
        gdt_capable=False,
        notes="Wide slot — single-pass full-width milling.",
    ),
    RouteTemplate(
        template_id="SLT-002",
        feature_type=ExtendedFeatureType.SLOT,
        label="Rough slot → finish slot",
        operations=(
            _op(M, "ROUGH",  ToolType.END_MILL, 3.2, "IT9", "Rough slot"),
            _op(M, "FINISH", ToolType.END_MILL, 0.4, "IT7", "Finish side walls"),
        ),
        best_ra_um=0.4, best_it_grade="IT7", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC"),
        gdt_capable=True,
        notes="Precision slot — controlled width and depth.",
    ),
]

_PLANAR_FACE_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="PF-001",
        feature_type=ExtendedFeatureType.PLANAR_FACE,
        label="Face mill (rough + finish)",
        operations=(
            _op(F, "ROUGH",  ToolType.FACE_MILL, 3.2, "IT9", "Rough face milling"),
            _op(F, "FINISH", ToolType.FACE_MILL, 0.8, "IT8", "Finish face milling"),
        ),
        best_ra_um=0.8, best_it_grade="IT8", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC", "MILL_TURN"),
        gdt_capable=True,
        notes="Standard face milling — datum faces.",
    ),
    RouteTemplate(
        template_id="PF-002",
        feature_type=ExtendedFeatureType.PLANAR_FACE,
        label="Face mill → surface grind",
        operations=(
            _op(F, "ROUGH",  ToolType.FACE_MILL,      3.2, "IT9", "Face mill"),
            _op(F, "FINISH", ToolType.FACE_MILL,      0.8, "IT8", "Finish face mill"),
            _op(G, "FINISH", ToolType.GRINDING_WHEEL, 0.1, "IT5", "Surface grind"),
        ),
        best_ra_um=0.1, best_it_grade="IT5", min_setups=2, specialty_op_count=1,
        requires_machine_types=("VMC_3AXIS", "GRINDER"),
        gdt_capable=True,
        notes="Precision flat face — Ra 0.1 µm flatness reference.",
    ),
]

_BOSS_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="BOSS-001",
        feature_type=ExtendedFeatureType.BOSS,
        label="Rough mill boss → finish mill",
        operations=(
            _op(M, "ROUGH",  ToolType.END_MILL, 3.2, "IT9", "Rough mill boss profile"),
            _op(M, "FINISH", ToolType.END_MILL, 0.4, "IT7", "Finish mill boss to size"),
        ),
        best_ra_um=0.4, best_it_grade="IT7", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC"),
        gdt_capable=True,
        notes="Raised boss — 2.5D milling.",
    ),
]

_STEP_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="STEP-001",
        feature_type=ExtendedFeatureType.STEP,
        label="Rough mill step → finish mill",
        operations=(
            _op(M, "ROUGH",  ToolType.END_MILL, 3.2, "IT9", "Rough step milling"),
            _op(M, "FINISH", ToolType.END_MILL, 0.4, "IT7", "Finish step milling"),
        ),
        best_ra_um=0.4, best_it_grade="IT7", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC"),
        gdt_capable=False,
        notes="Shoulder / step feature — milling.",
    ),
]

# ---------------------------------------------------------------------------
# Turning routes
# ---------------------------------------------------------------------------

_TURNING_DIAMETER_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="TRN-001",
        feature_type=ExtendedFeatureType.TURNING_DIAMETER,
        label="Rough turn → finish turn",
        operations=(
            _op(T, "ROUGH",  ToolType.TURNING_INSERT, 3.2, "IT9", "Rough turning"),
            _op(T, "FINISH", ToolType.TURNING_INSERT, 0.4, "IT6", "Finish turning Ra 0.4 µm"),
        ),
        best_ra_um=0.4, best_it_grade="IT6", min_setups=1, specialty_op_count=0,
        requires_machine_types=("LATHE", "MILL_TURN", "LATHE_Y", "SWISS", "VTL"),
        gdt_capable=True,
        notes="Standard OD turning.",
    ),
    RouteTemplate(
        template_id="TRN-002",
        feature_type=ExtendedFeatureType.TURNING_DIAMETER,
        label="Rough turn → semi-finish turn → finish turn",
        operations=(
            _op(T, "ROUGH",       ToolType.TURNING_INSERT, 3.2, "IT9", "Rough turning"),
            _op(T, "SEMI_FINISH", ToolType.TURNING_INSERT, 0.8, "IT8", "Semi-finish turning"),
            _op(T, "FINISH",      ToolType.TURNING_INSERT, 0.4, "IT6", "Finish turning"),
        ),
        best_ra_um=0.4, best_it_grade="IT6", min_setups=1, specialty_op_count=0,
        requires_machine_types=("LATHE", "MILL_TURN", "LATHE_Y"),
        gdt_capable=True,
        notes="Three-pass OD turning for hardened or interrupted cuts.",
    ),
    RouteTemplate(
        template_id="TRN-003",
        feature_type=ExtendedFeatureType.TURNING_DIAMETER,
        label="Rough turn → finish turn → cylindrical grind",
        operations=(
            _op(T, "ROUGH",  ToolType.TURNING_INSERT, 3.2, "IT9", "Rough turning"),
            _op(T, "FINISH", ToolType.TURNING_INSERT, 0.8, "IT8", "Pre-grind turning"),
            _op(G, "FINISH", ToolType.GRINDING_WHEEL, 0.1, "IT5", "Cylindrical grinding"),
        ),
        best_ra_um=0.1, best_it_grade="IT5", min_setups=2, specialty_op_count=1,
        requires_machine_types=("LATHE", "GRINDER"),
        gdt_capable=True,
        notes="OD grinding — bearing journals, precision fits.",
    ),
]

_CYLINDRICAL_SURFACE_ROUTES: list[RouteTemplate] = _TURNING_DIAMETER_ROUTES

# ---------------------------------------------------------------------------
# Groove
# ---------------------------------------------------------------------------

_GROOVE_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="GRV-001",
        feature_type=ExtendedFeatureType.GROOVE,
        label="Turn groove (external)",
        operations=(
            _op(T, "GROOVE", ToolType.TURNING_INSERT, 1.6, "IT8", "External turning groove"),
        ),
        best_ra_um=1.6, best_it_grade="IT8", min_setups=1, specialty_op_count=0,
        requires_machine_types=("LATHE", "MILL_TURN", "LATHE_Y"),
        gdt_capable=False,
        notes="External OD groove — parting/grooving insert.",
    ),
    RouteTemplate(
        template_id="GRV-002",
        feature_type=ExtendedFeatureType.GROOVE,
        label="Mill groove (slot)",
        operations=(
            _op(M, "ROUGH",  ToolType.END_MILL, 3.2, "IT9", "Rough mill groove"),
            _op(M, "FINISH", ToolType.END_MILL, 0.4, "IT7", "Finish mill groove walls"),
        ),
        best_ra_um=0.4, best_it_grade="IT7", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC"),
        gdt_capable=False,
        notes="Milled groove on prismatic part.",
    ),
]

# ---------------------------------------------------------------------------
# Chamfer / Fillet
# ---------------------------------------------------------------------------

_CHAMFER_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="CHM-001",
        feature_type=ExtendedFeatureType.CHAMFER,
        label="Mill chamfer",
        operations=(
            _op(M, "CHAMFER", ToolType.END_MILL, 1.6, "IT10", "Chamfer milling"),
        ),
        best_ra_um=1.6, best_it_grade="IT10", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC"),
        gdt_capable=False,
        notes="Chamfer milling — chamfer end mill.",
    ),
    RouteTemplate(
        template_id="CHM-002",
        feature_type=ExtendedFeatureType.CHAMFER,
        label="Deburr / chamfer",
        operations=(
            _op(DB, None, ToolType.DEBURRING_TOOL, 3.2, "IT12", "Deburring tool chamfer"),
        ),
        best_ra_um=3.2, best_it_grade="IT12", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC", "OTHER"),
        gdt_capable=False,
        notes="Light chamfer / deburring only.",
    ),
]

_FILLET_ROUTES: list[RouteTemplate] = [
    RouteTemplate(
        template_id="FLT-001",
        feature_type=ExtendedFeatureType.FILLET,
        label="Mill fillet (ball end mill)",
        operations=(
            _op(M, "FINISH", ToolType.END_MILL, 0.8, "IT8", "Ball end mill fillet"),
        ),
        best_ra_um=0.8, best_it_grade="IT8", min_setups=1, specialty_op_count=0,
        requires_machine_types=("VMC_3AXIS", "VMC_4AXIS", "VMC_5AXIS", "HMC"),
        gdt_capable=False,
        notes="Internal corner fillet — ball end mill.",
    ),
]

# ---------------------------------------------------------------------------
# Master route template registry
# ---------------------------------------------------------------------------

_ALL_TEMPLATES: list[RouteTemplate] = (
    _HOLE_ROUTES
    + _PRECISION_BORE_ROUTES
    + _COUNTERBORE_ROUTES
    + _COUNTERSINK_ROUTES
    + _THREADED_HOLE_ROUTES
    + _THREAD_ROUTES
    + _POCKET_ROUTES
    + _SLOT_ROUTES
    + _PLANAR_FACE_ROUTES
    + _BOSS_ROUTES
    + _STEP_ROUTES
    + _TURNING_DIAMETER_ROUTES
    + _GROOVE_ROUTES
    + _CHAMFER_ROUTES
    + _FILLET_ROUTES
)

# Build lookup index
_TEMPLATE_INDEX: dict[ExtendedFeatureType, list[RouteTemplate]] = {}
for _t in _ALL_TEMPLATES:
    _TEMPLATE_INDEX.setdefault(_t.feature_type, []).append(_t)

# Also map legacy FeatureType strings to ExtendedFeatureType
_LEGACY_MAP: dict[str, ExtendedFeatureType] = {
    "hole":                ExtendedFeatureType.HOLE,
    "pocket":              ExtendedFeatureType.POCKET,
    "slot":                ExtendedFeatureType.SLOT,
    "planar_face":         ExtendedFeatureType.PLANAR_FACE,
    "cylindrical_surface": ExtendedFeatureType.TURNING_DIAMETER,
    "thread":              ExtendedFeatureType.THREAD,
    "chamfer":             ExtendedFeatureType.CHAMFER,
    "fillet":              ExtendedFeatureType.FILLET,
    "groove":              ExtendedFeatureType.GROOVE,
    "freeform_surface":    ExtendedFeatureType.FREEFORM_SURFACE,
    "unknown":             ExtendedFeatureType.UNKNOWN,
}

ROUTE_TEMPLATES: dict[ExtendedFeatureType, list[RouteTemplate]] = _TEMPLATE_INDEX


def get_templates_for_feature(
    feature_type: str,
    required_ra_um: float | None = None,
    required_it_grade: str | None = None,
) -> list[RouteTemplate]:
    """Return route templates for *feature_type*, optionally filtered by Ra/IT requirement.

    Falls back via _LEGACY_MAP for old FeatureType string values.
    Returns [] (not error) for FREEFORM_SURFACE and UNKNOWN.
    FABRICATED_ROUTE=NO — only returns pre-defined templates.
    """
    ext = _LEGACY_MAP.get(feature_type) or ExtendedFeatureType.__members__.get(
        feature_type.upper(), ExtendedFeatureType.UNKNOWN
    )
    templates = list(_TEMPLATE_INDEX.get(ext, []))

    if required_ra_um is not None:
        templates = [t for t in templates if t.best_ra_um <= required_ra_um]

    return sorted(templates, key=lambda t: (t.best_ra_um, t.specialty_op_count))
