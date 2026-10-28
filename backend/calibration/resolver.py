"""Calibration precedence resolver — EPIC_04F.

CALIBRATION_PRECEDENCE_IMPLEMENTED=YES
CALIBRATION_RESOLVER_IMPLEMENTED=YES
CALIBRATION_AUDIT_TRACE_IMPLEMENTED=YES

Precedence (highest → lowest):
  USER_OVERRIDE > SHOP_VALIDATED > MACHINE_PROFILE > MANUFACTURER_REFERENCE
  > LITERATURE_REFERENCE > GLOBAL_REFERENCE > ESTIMATED > INSUFFICIENT_DATA
"""

from __future__ import annotations

from backend.calibration.models import (
    CalibrationAuditEntry,
    CalibrationConfidence,
    CalibrationSource,
    CalibrationValue,
)
from backend.calibration.shop_profile import ShopCalibrationProfile

__all__ = [
    "CalibrationContext",
    "resolve_calibration_value",
]

_PRECEDENCE: list[CalibrationSource] = [
    CalibrationSource.USER_OVERRIDE,
    CalibrationSource.SHOP_VALIDATED,
    CalibrationSource.MACHINE_PROFILE,
    CalibrationSource.MANUFACTURER_REFERENCE,
    CalibrationSource.LITERATURE_REFERENCE,
    CalibrationSource.GLOBAL_REFERENCE,
    CalibrationSource.ESTIMATED,
    CalibrationSource.INSUFFICIENT_DATA,
]

_PRECEDENCE_RANK: dict[CalibrationSource, int] = {
    src: i for i, src in enumerate(_PRECEDENCE)
}


class CalibrationContext:
    """Collects calibration inputs; resolver picks highest-priority non-None value."""

    def __init__(self) -> None:
        self._values: list[CalibrationValue] = []

    def add(self, value: CalibrationValue) -> CalibrationContext:
        if value.value is not None:
            self._values.append(value)
        return self

    def add_user_override(self, value: float, notes: str = "") -> CalibrationContext:
        return self.add(CalibrationValue(
            value=value,
            source=CalibrationSource.USER_OVERRIDE,
            confidence=CalibrationConfidence.HIGH,
            notes=notes,
        ))

    def add_shop_profile(
        self,
        profile: ShopCalibrationProfile,
        field: str,
    ) -> CalibrationContext:
        v = getattr(profile, field, None)
        if v is not None:
            self.add(CalibrationValue(
                value=float(v),
                source=CalibrationSource.SHOP_VALIDATED,
                confidence=profile.confidence,
                notes=f"Profile: {profile.label} (rev {profile.revision})",
            ))
        return self

    def add_reference(
        self,
        value: float,
        source: CalibrationSource = CalibrationSource.LITERATURE_REFERENCE,
        confidence: CalibrationConfidence = CalibrationConfidence.MEDIUM,
        notes: str = "",
    ) -> CalibrationContext:
        return self.add(CalibrationValue(
            value=value,
            source=source,
            confidence=confidence,
            notes=notes,
        ))

    @property
    def candidates(self) -> list[CalibrationValue]:
        return sorted(self._values, key=lambda v: _PRECEDENCE_RANK[v.source])


def resolve_calibration_value(
    context: CalibrationContext,
    field_name: str = "",
) -> CalibrationAuditEntry:
    """Resolve to the highest-priority available calibration value.

    CALIBRATION_AUDIT_TRACE_IMPLEMENTED=YES:
      Returns resolved_source, resolved_value, rejected_sources, confidence, notes.
    """
    candidates = context.candidates

    if not candidates:
        return CalibrationAuditEntry(
            resolved_source=CalibrationSource.INSUFFICIENT_DATA,
            resolved_value=None,
            rejected_sources=[],
            confidence=CalibrationConfidence.UNKNOWN,
            notes=f"No calibration value available for '{field_name}'.",
        )

    selected = candidates[0]
    rejected = [
        {
            "source": c.source.value,
            "value": c.value,
            "confidence": c.confidence.value,
            "notes": c.notes,
            "reason": "lower_precedence",
        }
        for c in candidates[1:]
    ]

    return CalibrationAuditEntry(
        resolved_source=selected.source,
        resolved_value=selected.value,
        rejected_sources=rejected,
        confidence=selected.confidence,
        notes=selected.notes,
    )
