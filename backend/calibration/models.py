"""Calibration domain models for EPIC_04F.

FABRICATED_PROCESS_CAPABILITY=NO
FABRICATED_CYCLE_TIME=NO
FABRICATED_MACHINE_ACCURACY=NO
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "CalibrationSource",
    "CalibrationConfidence",
    "CapabilityStatus",
    "CycleComponentStatus",
    "CycleTimeCompleteness",
    "CalibrationValue",
    "CalibrationAuditEntry",
    "CapabilityMargin",
    "SurfaceCapabilityMargin",
    "CycleTimeComponent",
    "CycleTimeEstimate",
    "BatchModel",
]


class CalibrationSource(StrEnum):
    USER_OVERRIDE = "USER_OVERRIDE"
    SHOP_VALIDATED = "SHOP_VALIDATED"
    MACHINE_PROFILE = "MACHINE_PROFILE"
    MANUFACTURER_REFERENCE = "MANUFACTURER_REFERENCE"
    LITERATURE_REFERENCE = "LITERATURE_REFERENCE"
    GLOBAL_REFERENCE = "GLOBAL_REFERENCE"
    ESTIMATED = "ESTIMATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class CalibrationConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class CapabilityStatus(StrEnum):
    ROBUST = "ROBUST"
    ACCEPTABLE = "ACCEPTABLE"
    MARGINAL = "MARGINAL"
    NOT_CAPABLE = "NOT_CAPABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class CycleComponentStatus(StrEnum):
    CALCULATED = "CALCULATED"
    REFERENCE = "REFERENCE"
    USER_SUPPLIED = "USER_SUPPLIED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


class CycleTimeCompleteness(StrEnum):
    FULLY_CALCULATED = "FULLY_CALCULATED"
    PARTIALLY_CALCULATED = "PARTIALLY_CALCULATED"
    ESTIMATED = "ESTIMATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class CalibrationValue(BaseModel):
    value: float | None
    source: CalibrationSource
    confidence: CalibrationConfidence
    notes: str = ""


class CalibrationAuditEntry(BaseModel):
    resolved_source: CalibrationSource
    resolved_value: float | None
    rejected_sources: list[dict[str, Any]] = Field(default_factory=list)
    confidence: CalibrationConfidence
    notes: str = ""


class CapabilityMargin(BaseModel):
    """Tolerance capability margin result.

    reference_capability_um = tightest (best) IT grade tolerance the operation achieves.
    margin_um = required_tolerance_um - reference_capability_um
    margin_ratio = required_tolerance_um / reference_capability_um
    margin_ratio >= 1.0 means CAPABLE (required is looser than or equal to the operation's best).

    Sign semantics:
      positive margin_um: required is looser than best → capable
      negative margin_um: required is tighter than best → NOT_CAPABLE
    """

    status: CapabilityStatus
    required_tolerance_um: float
    reference_capability_um: float | None
    margin_um: float | None
    margin_ratio: float | None
    confidence: CalibrationConfidence
    source: CalibrationSource
    operation: str
    nominal_size_mm: float | None
    reason: str
    notes: str = ""


class SurfaceCapabilityMargin(BaseModel):
    """Surface finish capability margin result.

    margin_ratio = achievable_ra_um / required_ra_um
    ratio <= 1.0 means capable (achievable Ra <= required Ra).
    """

    status: CapabilityStatus
    required_ra_um: float
    achievable_ra_um_best: float | None
    achievable_ra_um_typical: float | None
    margin_ratio: float | None
    confidence: CalibrationConfidence
    source: CalibrationSource
    operation: str
    reason: str
    notes: str = ""


class CycleTimeComponent(BaseModel):
    """One component of a cycle time estimate.

    value_sec_min/max=None means UNKNOWN — never treated as zero.
    UNKNOWN_TIME_COMPONENT_TREATED_AS_ZERO=NO
    """

    component_id: str
    component_type: str
    status: CycleComponentStatus
    value_sec_min: float | None = None
    value_sec_max: float | None = None
    source: CalibrationSource = CalibrationSource.INSUFFICIENT_DATA
    confidence: CalibrationConfidence = CalibrationConfidence.UNKNOWN
    method: str = ""
    missing_inputs: list[str] = Field(default_factory=list)
    notes: str = ""


class CycleTimeEstimate(BaseModel):
    """Cycle time estimate for a step or route.

    PARTIAL_TIME_PRESENTED_AS_TOTAL=NO:
      known_total = sum of known components only.
      total_cycle_time = set only when ALL required components are known.
    """

    components: list[CycleTimeComponent]
    completeness: CycleTimeCompleteness
    known_total_sec_min: float | None = None
    known_total_sec_max: float | None = None
    total_cycle_time_sec_min: float | None = None
    total_cycle_time_sec_max: float | None = None
    unknown_components: list[str] = Field(default_factory=list)
    uncertainty_note: str = ""
    limitations: list[str] = Field(default_factory=list)


class BatchModel(BaseModel):
    """Batch quantity amortization.

    per_part_setup_sec = setup_sec / batch_quantity
    per_part_total_sec = per_part_cutting_sec + per_part_setup_sec + other
    """

    batch_quantity: int
    setup_sec: float | None = None
    per_part_cutting_sec_min: float | None = None
    per_part_cutting_sec_max: float | None = None
    per_part_setup_sec: float | None = None
    per_part_total_sec_min: float | None = None
    per_part_total_sec_max: float | None = None
    completeness: CycleTimeCompleteness = CycleTimeCompleteness.INSUFFICIENT_DATA
    notes: str = ""
