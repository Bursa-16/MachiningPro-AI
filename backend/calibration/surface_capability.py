"""Surface finish capability library and evaluator — EPIC_04F.

SURFACE_CAPABILITY_LIBRARY_IMPLEMENTED=YES
SURFACE_CAPABILITY_MARGIN_IMPLEMENTED=YES
FABRICATED_SURFACE_CAPABILITY=NO
UNKNOWN_CAPABILITY_TREATED_AS_SUPPORTED=NO
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.calibration.models import (
    CalibrationConfidence,
    CalibrationSource,
    CapabilityStatus,
    SurfaceCapabilityMargin,
)

__all__ = [
    "SurfaceOperationFamily",
    "SurfaceCapabilityRecord",
    "SURFACE_CAPABILITY_LIBRARY",
    "surface_capability_margin",
]


class SurfaceOperationFamily(StrEnum):
    ROUGH_TURNING = "ROUGH_TURNING"
    FINISH_TURNING = "FINISH_TURNING"
    ROUGH_MILLING = "ROUGH_MILLING"
    FINISH_MILLING = "FINISH_MILLING"
    REAMING = "REAMING"
    BORING = "BORING"
    GRINDING = "GRINDING"
    HONING = "HONING"
    LAPPING = "LAPPING"


@dataclass(frozen=True)
class SurfaceCapabilityRecord:
    """Reference surface finish capability for one operation family.

    ra_best_um: best (lowest) achievable Ra in µm
    ra_typical_um: typical 80th-percentile Ra in µm (production conditions)
    """

    operation: SurfaceOperationFamily
    ra_best_um: float
    ra_typical_um: float
    confidence: CalibrationConfidence
    source: CalibrationSource
    notes: str


_LIBRARY: list[SurfaceCapabilityRecord] = [
    SurfaceCapabilityRecord(
        operation=SurfaceOperationFamily.ROUGH_TURNING,
        ra_best_um=3.2,
        ra_typical_um=6.3,
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Rough turning: Ra 3.2–12.5 µm; best ~3.2 µm",
    ),
    SurfaceCapabilityRecord(
        operation=SurfaceOperationFamily.FINISH_TURNING,
        ra_best_um=0.4,
        ra_typical_um=1.6,
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Finish turning: Ra 0.4–1.6 µm; best ~0.4 µm with sharp tool",
    ),
    SurfaceCapabilityRecord(
        operation=SurfaceOperationFamily.ROUGH_MILLING,
        ra_best_um=3.2,
        ra_typical_um=6.3,
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Rough milling: Ra 3.2–12.5 µm",
    ),
    SurfaceCapabilityRecord(
        operation=SurfaceOperationFamily.FINISH_MILLING,
        ra_best_um=0.4,
        ra_typical_um=1.6,
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Finish milling: Ra 0.4–1.6 µm; depends on cutter geometry",
    ),
    SurfaceCapabilityRecord(
        operation=SurfaceOperationFamily.REAMING,
        ra_best_um=0.4,
        ra_typical_um=0.8,
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Reaming: Ra 0.4–0.8 µm typical",
    ),
    SurfaceCapabilityRecord(
        operation=SurfaceOperationFamily.BORING,
        ra_best_um=0.4,
        ra_typical_um=1.6,
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Finish boring: Ra 0.4–1.6 µm; fine boring to 0.4 µm",
    ),
    SurfaceCapabilityRecord(
        operation=SurfaceOperationFamily.GRINDING,
        ra_best_um=0.1,
        ra_typical_um=0.4,
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Grinding: Ra 0.1–0.4 µm",
    ),
    SurfaceCapabilityRecord(
        operation=SurfaceOperationFamily.HONING,
        ra_best_um=0.1,
        ra_typical_um=0.4,
        confidence=CalibrationConfidence.MEDIUM,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Honing: Ra 0.1–0.4 µm; bore finishing",
    ),
    SurfaceCapabilityRecord(
        operation=SurfaceOperationFamily.LAPPING,
        ra_best_um=0.05,
        ra_typical_um=0.2,
        confidence=CalibrationConfidence.LOW,
        source=CalibrationSource.LITERATURE_REFERENCE,
        notes="Lapping: Ra 0.05–0.2 µm; ultra-fine surfaces",
    ),
]

SURFACE_CAPABILITY_LIBRARY: dict[SurfaceOperationFamily, SurfaceCapabilityRecord] = {
    rec.operation: rec for rec in _LIBRARY
}


def _surface_status(margin_ratio: float) -> CapabilityStatus:
    """For Ra: margin_ratio = achievable_Ra / required_Ra.

    Lower Ra is better. ratio <= 1.0 means achievable <= required (capable).
      ratio <= 0.67: ROBUST (achievable Ra much better than required)
      ratio <= 0.80: ACCEPTABLE
      ratio <= 1.00: MARGINAL
      ratio >  1.00: NOT_CAPABLE
    """
    if margin_ratio <= 0.67:
        return CapabilityStatus.ROBUST
    if margin_ratio <= 0.80:
        return CapabilityStatus.ACCEPTABLE
    if margin_ratio <= 1.00:
        return CapabilityStatus.MARGINAL
    return CapabilityStatus.NOT_CAPABLE


def surface_capability_margin(
    operation: SurfaceOperationFamily | str,
    required_ra_um: float,
    use_typical: bool = False,
) -> SurfaceCapabilityMargin:
    """Evaluate surface finish capability margin.

    margin_ratio = achievable_ra_um / required_ra_um
    ratio <= 1.0 means capable.

    UNKNOWN_CAPABILITY_TREATED_AS_SUPPORTED=NO
    FABRICATED_SURFACE_CAPABILITY=NO
    """
    try:
        op = SurfaceOperationFamily(operation)
    except ValueError:
        return SurfaceCapabilityMargin(
            status=CapabilityStatus.INSUFFICIENT_DATA,
            required_ra_um=required_ra_um,
            achievable_ra_um_best=None,
            achievable_ra_um_typical=None,
            margin_ratio=None,
            confidence=CalibrationConfidence.UNKNOWN,
            source=CalibrationSource.INSUFFICIENT_DATA,
            operation=str(operation),
            reason=f"Operation '{operation}' not in surface capability library.",
        )

    rec = SURFACE_CAPABILITY_LIBRARY.get(op)
    if rec is None:
        return SurfaceCapabilityMargin(
            status=CapabilityStatus.INSUFFICIENT_DATA,
            required_ra_um=required_ra_um,
            achievable_ra_um_best=None,
            achievable_ra_um_typical=None,
            margin_ratio=None,
            confidence=CalibrationConfidence.UNKNOWN,
            source=CalibrationSource.INSUFFICIENT_DATA,
            operation=str(operation),
            reason="No surface capability record for this operation.",
        )

    if required_ra_um <= 0:
        return SurfaceCapabilityMargin(
            status=CapabilityStatus.INSUFFICIENT_DATA,
            required_ra_um=required_ra_um,
            achievable_ra_um_best=rec.ra_best_um,
            achievable_ra_um_typical=rec.ra_typical_um,
            margin_ratio=None,
            confidence=rec.confidence,
            source=rec.source,
            operation=str(operation),
            reason="required_ra_um must be > 0.",
        )

    reference_ra = rec.ra_typical_um if use_typical else rec.ra_best_um
    margin_ratio = round(reference_ra / required_ra_um, 4)
    status = _surface_status(margin_ratio)

    return SurfaceCapabilityMargin(
        status=status,
        required_ra_um=required_ra_um,
        achievable_ra_um_best=rec.ra_best_um,
        achievable_ra_um_typical=rec.ra_typical_um,
        margin_ratio=margin_ratio,
        confidence=rec.confidence,
        source=rec.source,
        operation=str(operation),
        reason=(
            f"{op.value}: achievable Ra {reference_ra} µm vs required {required_ra_um} µm "
            f"→ ratio {margin_ratio} → {status.value}"
        ),
        notes=rec.notes,
    )
