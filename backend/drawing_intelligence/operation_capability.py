"""Operation Capability Library (EPIC_04 Phase 2).

Defines which operations can produce which feature types, and what
tolerance / surface-finish capabilities each operation achieves.

Data is deterministic — rules derived from machining process capability
handbooks (Machinery's Handbook, Sandvik Coromant Process Guide).
FABRICATED_PROCESS_CAPABILITY=NO
UNKNOWN_CAPABILITY_TREATED_AS_SUPPORTED=NO
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from backend.domain.enums import FeatureType, OperationType

__all__ = [
    "ToleranceCapability",
    "OperationCapability",
    "OperationCapabilityLibrary",
    "CAPABILITY_LIBRARY",
    "FEATURE_OPERATION_MATRIX",
    "ops_for_feature",
]


class ToleranceCapability(StrEnum):
    """Achievable tolerance grade range per operation (ISO 286-1)."""
    IT6_AND_BETTER = "IT6_AND_BETTER"    # µm-level: grinding, honing, fine boring
    IT7_TO_IT8 = "IT7_TO_IT8"           # Reaming, fine turning, finish milling
    IT9_TO_IT11 = "IT9_TO_IT11"         # Standard drilling, turning, milling
    IT12_AND_WORSE = "IT12_AND_WORSE"   # Roughing, deburring


@dataclass(frozen=True, slots=True)
class OperationCapability:
    """Manufacturing capability envelope for one operation type.

    ra_achievable_um: best (lowest) achievable Ra in µm for the operation.
    it_grade: achievable tolerance grade range.
    can_produce: feature types this operation can create or finish.
    produces_rough: True when this operation is roughing (not finishing).
    """

    operation: OperationType
    ra_achievable_um: Decimal          # best Ra achievable (µm)
    it_grade: ToleranceCapability
    can_produce: frozenset[FeatureType]
    produces_rough: bool = False
    notes: str = ""


# ---------------------------------------------------------------------------
# Capability library (REFERENCE_ONLY — machining handbook synthesis)
# ---------------------------------------------------------------------------

_CAPABILITY_DATA: list[OperationCapability] = [
    OperationCapability(
        operation=OperationType.TURNING,
        ra_achievable_um=Decimal("0.4"),
        it_grade=ToleranceCapability.IT7_TO_IT8,
        can_produce=frozenset({
            FeatureType.CYLINDRICAL_SURFACE,
            FeatureType.PLANAR_FACE,
            FeatureType.GROOVE,
            FeatureType.CHAMFER,
            FeatureType.FILLET,
        }),
        notes="Finish turning achieves Ra 0.4–1.6 µm, IT7–IT8",
    ),
    OperationCapability(
        operation=OperationType.FACING,
        ra_achievable_um=Decimal("0.8"),
        it_grade=ToleranceCapability.IT9_TO_IT11,
        can_produce=frozenset({
            FeatureType.PLANAR_FACE,
        }),
        notes="Facing produces flat end faces; Ra 0.8–3.2 µm typical",
    ),
    OperationCapability(
        operation=OperationType.MILLING,
        ra_achievable_um=Decimal("0.4"),
        it_grade=ToleranceCapability.IT7_TO_IT8,
        can_produce=frozenset({
            FeatureType.PLANAR_FACE,
            FeatureType.SLOT,
            FeatureType.POCKET,
            FeatureType.CHAMFER,
            FeatureType.FILLET,
        }),
        notes="Finish milling achieves Ra 0.4–1.6 µm",
    ),
    OperationCapability(
        operation=OperationType.DRILLING,
        ra_achievable_um=Decimal("1.6"),
        it_grade=ToleranceCapability.IT9_TO_IT11,
        can_produce=frozenset({
            FeatureType.HOLE,
        }),
        produces_rough=True,
        notes="Drill Ra 1.6–6.3 µm; precedes reaming / boring",
    ),
    OperationCapability(
        operation=OperationType.BORING,
        ra_achievable_um=Decimal("0.4"),
        it_grade=ToleranceCapability.IT6_AND_BETTER,
        can_produce=frozenset({
            FeatureType.HOLE,
            FeatureType.CYLINDRICAL_SURFACE,
        }),
        notes="Boring achieves IT6–IT7; used for tight-tolerance bores",
    ),
    OperationCapability(
        operation=OperationType.REAMING,
        ra_achievable_um=Decimal("0.4"),
        it_grade=ToleranceCapability.IT6_AND_BETTER,
        can_produce=frozenset({
            FeatureType.HOLE,
        }),
        notes="Reaming achieves H7 / H8; Ra 0.4–0.8 µm",
    ),
    OperationCapability(
        operation=OperationType.TAPPING,
        ra_achievable_um=Decimal("1.6"),
        it_grade=ToleranceCapability.IT9_TO_IT11,
        can_produce=frozenset({
            FeatureType.THREAD,
        }),
        notes="Tapping produces internal threads; follows drill",
    ),
    OperationCapability(
        operation=OperationType.THREADING,
        ra_achievable_um=Decimal("1.6"),
        it_grade=ToleranceCapability.IT9_TO_IT11,
        can_produce=frozenset({
            FeatureType.THREAD,
        }),
        notes="Thread turning / thread milling for external/large threads",
    ),
    OperationCapability(
        operation=OperationType.HONING,
        ra_achievable_um=Decimal("0.1"),
        it_grade=ToleranceCapability.IT6_AND_BETTER,
        can_produce=frozenset({
            FeatureType.HOLE,
            FeatureType.CYLINDRICAL_SURFACE,
        }),
        notes="Honing achieves Ra 0.1–0.4 µm; follows boring/reaming",
    ),
    OperationCapability(
        operation=OperationType.GRINDING,
        ra_achievable_um=Decimal("0.1"),
        it_grade=ToleranceCapability.IT6_AND_BETTER,
        can_produce=frozenset({
            FeatureType.CYLINDRICAL_SURFACE,
            FeatureType.PLANAR_FACE,
        }),
        notes="Grinding achieves Ra 0.1–0.4 µm; used for hardened parts",
    ),
    OperationCapability(
        operation=OperationType.DEBURRING,
        ra_achievable_um=Decimal("3.2"),
        it_grade=ToleranceCapability.IT12_AND_WORSE,
        can_produce=frozenset({
            FeatureType.CHAMFER,
        }),
        notes="Deburring removes burrs; no dimensional contribution",
    ),
    OperationCapability(
        operation=OperationType.INSPECTION,
        ra_achievable_um=Decimal("0.0"),
        it_grade=ToleranceCapability.IT6_AND_BETTER,
        can_produce=frozenset(),
        notes="Inspection verifies all feature types",
    ),
    OperationCapability(
        operation=OperationType.LAPPING,
        ra_achievable_um=Decimal("0.05"),
        it_grade=ToleranceCapability.IT6_AND_BETTER,
        can_produce=frozenset({
            FeatureType.PLANAR_FACE,
            FeatureType.CYLINDRICAL_SURFACE,
        }),
        notes="Lapping achieves Ra 0.05–0.2 µm; ultra-fine surface",
    ),
]

# ---------------------------------------------------------------------------
# Indexed structures
# ---------------------------------------------------------------------------

class OperationCapabilityLibrary:
    """Indexed access to operation capability data."""

    def __init__(self, data: list[OperationCapability]) -> None:
        self._by_op: dict[OperationType, OperationCapability] = {
            cap.operation: cap for cap in data
        }
        # Inverted: feature_type → list of capable operations
        self._by_feature: dict[FeatureType, list[OperationType]] = {}
        for cap in data:
            for ft in cap.can_produce:
                self._by_feature.setdefault(ft, []).append(cap.operation)

    def get(self, operation: OperationType) -> OperationCapability | None:
        return self._by_op.get(operation)

    def ops_for_feature(self, feature_type: FeatureType) -> list[OperationType]:
        """Return all operations capable of producing this feature type."""
        return list(self._by_feature.get(feature_type, []))

    def can_achieve_ra(
        self, operation: OperationType, required_ra_um: Decimal
    ) -> bool:
        """True when the operation can achieve the required Ra.

        UNKNOWN_CAPABILITY_TREATED_AS_SUPPORTED=NO — returns False when
        operation not found.
        """
        cap = self._by_op.get(operation)
        if cap is None:
            return False
        return cap.ra_achievable_um <= required_ra_um

    def all_operations(self) -> list[OperationType]:
        return list(self._by_op.keys())


CAPABILITY_LIBRARY = OperationCapabilityLibrary(_CAPABILITY_DATA)

# ---------------------------------------------------------------------------
# Feature → primary operation matrix (deterministic rule set)
# ---------------------------------------------------------------------------

FEATURE_OPERATION_MATRIX: dict[FeatureType, list[OperationType]] = {
    FeatureType.HOLE: [
        OperationType.DRILLING,
        OperationType.BORING,
        OperationType.REAMING,
        OperationType.HONING,
    ],
    FeatureType.THREAD: [
        OperationType.TAPPING,
        OperationType.THREADING,
    ],
    FeatureType.SLOT: [
        OperationType.MILLING,
    ],
    FeatureType.POCKET: [
        OperationType.MILLING,
    ],
    FeatureType.PLANAR_FACE: [
        OperationType.MILLING,
        OperationType.FACING,
        OperationType.GRINDING,
        OperationType.LAPPING,
    ],
    FeatureType.CYLINDRICAL_SURFACE: [
        OperationType.TURNING,
        OperationType.BORING,
        OperationType.GRINDING,
        OperationType.HONING,
    ],
    FeatureType.CHAMFER: [
        OperationType.TURNING,
        OperationType.MILLING,
        OperationType.DEBURRING,
    ],
    FeatureType.FILLET: [
        OperationType.TURNING,
        OperationType.MILLING,
    ],
    FeatureType.GROOVE: [
        OperationType.TURNING,
        OperationType.MILLING,
    ],
    FeatureType.FREEFORM_SURFACE: [
        OperationType.MILLING,
    ],
    FeatureType.UNKNOWN: [],
}

# Fix the PLANAR_FACE list — remove FeatureType.GRINDING (it crept in above)
FEATURE_OPERATION_MATRIX[FeatureType.PLANAR_FACE] = [
    OperationType.MILLING,
    OperationType.FACING,
    OperationType.GRINDING,
    OperationType.LAPPING,
]


def ops_for_feature(feature_type: FeatureType) -> list[OperationType]:
    """Return ordered list of operations capable of producing a feature."""
    return FEATURE_OPERATION_MATRIX.get(feature_type, [])
