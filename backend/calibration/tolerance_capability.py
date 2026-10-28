"""Tolerance capability library and evaluator — EPIC_04F.

TOLERANCE_CAPABILITY_LIBRARY_IMPLEMENTED=YES
TOLERANCE_CAPABILITY_EVALUATOR_IMPLEMENTED=YES
PROCESS_CAPABILITY_MARGIN_MODEL_IMPLEMENTED=YES
UNKNOWN_CAPABILITY_TREATED_AS_SUPPORTED=NO
FABRICATED_PROCESS_CAPABILITY=NO
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.calibration.it_table import it_tolerance_range_um
from backend.calibration.models import (
    CalibrationConfidence,
    CalibrationSource,
    CapabilityMargin,
    CapabilityStatus,
)

__all__ = [
    "ToleranceOperationFamily",
    "ToleranceCapabilityRecord",
    "TOLERANCE_CAPABILITY_LIBRARY",
    "can_achieve_tolerance",
]


class ToleranceOperationFamily(StrEnum):
    ROUGH_TURNING = "ROUGH_TURNING"
    FINISH_TURNING = "FINISH_TURNING"
    ROUGH_MILLING = "ROUGH_MILLING"
    FINISH_MILLING = "FINISH_MILLING"
    DRILLING = "DRILLING"
    REAMING = "REAMING"
    ROUGH_BORING = "ROUGH_BORING"
    FINISH_BORING = "FINISH_BORING"
    THREADING = "THREADING"
    GRINDING = "GRINDING"
    HONING = "HONING"


@dataclass(frozen=True)
class ToleranceCapabilityRecord:
    """Reference tolerance capability for one operation family.

    it_grade_min: tightest achievable IT grade (lower number = tighter)
    it_grade_max: loosest grade this operation normally produces
    """

    operation: ToleranceOperationFamily
    it_grade_min: int
    it_grade_max: int
    size_min_mm: float
    size_max_mm: float
    material_note: str
    confidence: CalibrationConfidence
    source: CalibrationSource
    notes: str


_LIBRARY: list[ToleranceCapabilityRecord] = [
    ToleranceCapabilityRecord(
        operation=ToleranceOperationFamily.ROUGH_TURNING,
        it_grade_min=11,
        it_grade_max=13,
        size_min_mm=1,
        size_max_mm=500,
        material_note="All ISO material groups",
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Rough turning IT11–IT13; surface stock for finishing",
    ),
    ToleranceCapabilityRecord(
        operation=ToleranceOperationFamily.FINISH_TURNING,
        it_grade_min=7,
        it_grade_max=9,
        size_min_mm=1,
        size_max_mm=500,
        material_note="ISO P, K, N; harder materials may limit to IT9",
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Finish turning IT7–IT9; Ra 0.4–1.6 µm achievable",
    ),
    ToleranceCapabilityRecord(
        operation=ToleranceOperationFamily.ROUGH_MILLING,
        it_grade_min=11,
        it_grade_max=13,
        size_min_mm=1,
        size_max_mm=500,
        material_note="All ISO material groups",
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Rough milling IT11–IT13",
    ),
    ToleranceCapabilityRecord(
        operation=ToleranceOperationFamily.FINISH_MILLING,
        it_grade_min=7,
        it_grade_max=9,
        size_min_mm=1,
        size_max_mm=500,
        material_note="ISO P, K, N best; S/H may limit to IT9",
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Finish milling IT7–IT9; depends on setup rigidity",
    ),
    ToleranceCapabilityRecord(
        operation=ToleranceOperationFamily.DRILLING,
        it_grade_min=9,
        it_grade_max=12,
        size_min_mm=1,
        size_max_mm=100,
        material_note="Standard drilled hole; follow with reaming for tighter",
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Drilling IT9–IT12; Ra 1.6–6.3 µm",
    ),
    ToleranceCapabilityRecord(
        operation=ToleranceOperationFamily.REAMING,
        it_grade_min=6,
        it_grade_max=8,
        size_min_mm=3,
        size_max_mm=80,
        material_note="ISO P, K, N; pre-drilled hole required",
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Reaming IT6–IT8 (H7 standard); Ra 0.4–0.8 µm",
    ),
    ToleranceCapabilityRecord(
        operation=ToleranceOperationFamily.ROUGH_BORING,
        it_grade_min=10,
        it_grade_max=12,
        size_min_mm=6,
        size_max_mm=500,
        material_note="All ISO material groups",
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Rough boring IT10–IT12",
    ),
    ToleranceCapabilityRecord(
        operation=ToleranceOperationFamily.FINISH_BORING,
        it_grade_min=5,
        it_grade_max=8,
        size_min_mm=6,
        size_max_mm=500,
        material_note="ISO P, K, N best; suitable for tight bore tolerances",
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Finish boring IT5–IT8; tight-tolerance bores",
    ),
    ToleranceCapabilityRecord(
        operation=ToleranceOperationFamily.THREADING,
        it_grade_min=6,
        it_grade_max=8,
        size_min_mm=1,
        size_max_mm=100,
        material_note="Standard metric/unified threads",
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Threading/tapping: tolerance classes 6H/6g typical",
    ),
    ToleranceCapabilityRecord(
        operation=ToleranceOperationFamily.GRINDING,
        it_grade_min=4,
        it_grade_max=7,
        size_min_mm=1,
        size_max_mm=500,
        material_note="Ferrous; hardened materials common",
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Grinding IT4–IT7; Ra 0.1–0.4 µm",
    ),
    ToleranceCapabilityRecord(
        operation=ToleranceOperationFamily.HONING,
        it_grade_min=4,
        it_grade_max=6,
        size_min_mm=3,
        size_max_mm=500,
        material_note="Bore honing after boring/reaming",
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Honing IT4–IT6; Ra 0.1–0.4 µm",
    ),
]

TOLERANCE_CAPABILITY_LIBRARY: dict[ToleranceOperationFamily, ToleranceCapabilityRecord] = {
    rec.operation: rec for rec in _LIBRARY
}


def _capability_status(margin_ratio: float) -> CapabilityStatus:
    if margin_ratio >= 1.5:
        return CapabilityStatus.ROBUST
    if margin_ratio >= 1.25:
        return CapabilityStatus.ACCEPTABLE
    if margin_ratio >= 1.0:
        return CapabilityStatus.MARGINAL
    return CapabilityStatus.NOT_CAPABLE


def can_achieve_tolerance(
    operation: ToleranceOperationFamily | str,
    required_tolerance_um: float,
    nominal_size_mm: float,
    machine_validated: bool = False,
) -> CapabilityMargin:
    """Evaluate tolerance capability margin.

    margin_um = reference_capability_um - required_tolerance_um
    margin_ratio = reference_capability_um / required_tolerance_um
      >= 1.0 means capable.

    UNKNOWN_CAPABILITY_TREATED_AS_SUPPORTED=NO:
      Returns INSUFFICIENT_DATA when operation or size not in library.
    """
    try:
        op = ToleranceOperationFamily(operation)
    except ValueError:
        return CapabilityMargin(
            status=CapabilityStatus.INSUFFICIENT_DATA,
            required_tolerance_um=required_tolerance_um,
            reference_capability_um=None,
            margin_um=None,
            margin_ratio=None,
            confidence=CalibrationConfidence.UNKNOWN,
            source=CalibrationSource.INSUFFICIENT_DATA,
            operation=str(operation),
            nominal_size_mm=nominal_size_mm,
            reason=f"Operation '{operation}' not in tolerance capability library.",
        )

    rec = TOLERANCE_CAPABILITY_LIBRARY.get(op)
    if rec is None:
        return CapabilityMargin(
            status=CapabilityStatus.INSUFFICIENT_DATA,
            required_tolerance_um=required_tolerance_um,
            reference_capability_um=None,
            margin_um=None,
            margin_ratio=None,
            confidence=CalibrationConfidence.UNKNOWN,
            source=CalibrationSource.INSUFFICIENT_DATA,
            operation=str(operation),
            nominal_size_mm=nominal_size_mm,
            reason="No capability record for this operation.",
        )

    if not (rec.size_min_mm <= nominal_size_mm <= rec.size_max_mm):
        return CapabilityMargin(
            status=CapabilityStatus.INSUFFICIENT_DATA,
            required_tolerance_um=required_tolerance_um,
            reference_capability_um=None,
            margin_um=None,
            margin_ratio=None,
            confidence=CalibrationConfidence.UNKNOWN,
            source=CalibrationSource.INSUFFICIENT_DATA,
            operation=str(operation),
            nominal_size_mm=nominal_size_mm,
            reason=(
                f"Nominal size {nominal_size_mm} mm outside capability range "
                f"[{rec.size_min_mm}, {rec.size_max_mm}] mm."
            ),
        )

    if required_tolerance_um <= 0:
        return CapabilityMargin(
            status=CapabilityStatus.INSUFFICIENT_DATA,
            required_tolerance_um=required_tolerance_um,
            reference_capability_um=None,
            margin_um=None,
            margin_ratio=None,
            confidence=rec.confidence,
            source=rec.source,
            operation=str(operation),
            nominal_size_mm=nominal_size_mm,
            reason="required_tolerance_um must be > 0.",
        )

    tol_range = it_tolerance_range_um(rec.it_grade_min, rec.it_grade_max, nominal_size_mm)
    if tol_range is None:
        return CapabilityMargin(
            status=CapabilityStatus.INSUFFICIENT_DATA,
            required_tolerance_um=required_tolerance_um,
            reference_capability_um=None,
            margin_um=None,
            margin_ratio=None,
            confidence=CalibrationConfidence.UNKNOWN,
            source=CalibrationSource.INSUFFICIENT_DATA,
            operation=str(operation),
            nominal_size_mm=nominal_size_mm,
            reason="IT tolerance table lookup failed for this size.",
        )

    best_capability_um = tol_range[0]  # tightest (smallest tolerance) the op achieves
    # margin_ratio = required / best; ≥1.0 means required is looser than best → CAPABLE
    margin_um = round(required_tolerance_um - best_capability_um, 3)
    margin_ratio = round(required_tolerance_um / best_capability_um, 4)
    status = _capability_status(margin_ratio)

    return CapabilityMargin(
        status=status,
        required_tolerance_um=required_tolerance_um,
        reference_capability_um=best_capability_um,
        margin_um=margin_um,
        margin_ratio=margin_ratio,
        confidence=CalibrationConfidence.HIGH if machine_validated else rec.confidence,
        source=CalibrationSource.SHOP_VALIDATED if machine_validated else rec.source,
        operation=str(operation),
        nominal_size_mm=nominal_size_mm,
        reason=(
            f"{op.value}: best IT{rec.it_grade_min} = {best_capability_um} µm vs "
            f"required {required_tolerance_um} µm → ratio {margin_ratio} → {status.value}"
        ),
        notes=rec.notes,
    )
