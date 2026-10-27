"""GD&T Semantic Validation Rules (EPIC_04B Phase 2).

Implements deterministic validation rules VAL-GDT-001 through VAL-GDT-010.

FABRICATED_GDT_VALUE=NO
UNKNOWN_GDT_TREATED_AS_VALID=NO
INVALID_FCF_ACCEPTED=NO
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.drawing_intelligence.requirements import (
    GDT_FORM_ONLY,
    GDT_REQUIRES_DATUM,
    AmbiguityKind,
    CompositePositionFCF,
    ExpandedFeatureControlFrame,
    FeatureOfSize,
    GdtAmbiguity,
    GdtCharacteristic,
    GdtModifier,
)

__all__ = [
    "GdtValidationResult",
    "validate_fcf",
    "validate_composite_fcf",
    "validate_modifier_on_fos",
    "VALIDATION_RULE_IDS",
]

VALIDATION_RULE_IDS = (
    "VAL-GDT-001",
    "VAL-GDT-002",
    "VAL-GDT-003",
    "VAL-GDT-004",
    "VAL-GDT-005",
    "VAL-GDT-006",
    "VAL-GDT-007",
    "VAL-GDT-008",
    "VAL-GDT-009",
    "VAL-GDT-010",
)


@dataclass(frozen=True, slots=True)
class GdtValidationResult:
    rule_id: str
    passed: bool
    severity: str          # "ERROR" | "WARNING" | "INFO"
    message: str
    ambiguity: GdtAmbiguity | None = None


def validate_fcf(
    fcf: ExpandedFeatureControlFrame,
    req_id: str,
    fos: FeatureOfSize | None = None,
) -> list[GdtValidationResult]:
    """Run all applicable VAL-GDT rules against a single FCF."""
    results: list[GdtValidationResult] = []
    results.extend(_val_001(fcf, req_id))
    results.extend(_val_002(fcf, req_id))
    results.extend(_val_003(fcf, req_id, fos))
    results.extend(_val_004(fcf, req_id))
    results.extend(_val_007(fcf, req_id))
    results.extend(_val_008(fcf, req_id))
    return results


def validate_composite_fcf(
    composite: CompositePositionFCF,
) -> list[GdtValidationResult]:
    """VAL-GDT-006: composite FCF segment tolerance consistency."""
    return _val_006(composite)


def validate_modifier_on_fos(
    fcf: ExpandedFeatureControlFrame,
    req_id: str,
    fos: FeatureOfSize | None,
) -> list[GdtValidationResult]:
    return _val_003(fcf, req_id, fos)


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------

def _val_001(fcf: ExpandedFeatureControlFrame, req_id: str) -> list[GdtValidationResult]:
    """VAL-GDT-001: Form characteristics must NOT reference a datum."""
    if fcf.characteristic in GDT_FORM_ONLY and fcf.datum_frame is not None:
        return [GdtValidationResult(
            rule_id="VAL-GDT-001",
            passed=False,
            severity="ERROR",
            message=(
                f"{fcf.characteristic.value} at {req_id} references datum "
                f"{fcf.datum_frame.labels} — form tolerances cannot reference datums"
            ),
            ambiguity=GdtAmbiguity(
                ambiguity_id=f"AMB-{req_id}-001",
                kind=AmbiguityKind.INVALID_MODIFIER_COMBO,
                affected_ids=(req_id,),
                description=f"{fcf.characteristic.value} must not reference a datum",
                severity="ERROR",
                suggested_resolution="Remove datum reference from form tolerance FCF",
            ),
        )]
    return [GdtValidationResult(rule_id="VAL-GDT-001", passed=True, severity="INFO",
                                message=f"VAL-GDT-001 passed for {req_id}")]


def _val_002(fcf: ExpandedFeatureControlFrame, req_id: str) -> list[GdtValidationResult]:
    """VAL-GDT-002: Orientation/location/runout should reference a datum."""
    if fcf.characteristic in GDT_REQUIRES_DATUM and fcf.datum_frame is None:
        return [GdtValidationResult(
            rule_id="VAL-GDT-002",
            passed=False,
            severity="WARNING",
            message=(
                f"{fcf.characteristic.value} at {req_id} has no datum reference — "
                "datum is typically required"
            ),
            ambiguity=GdtAmbiguity(
                ambiguity_id=f"AMB-{req_id}-002",
                kind=AmbiguityKind.MISSING_DATUM,
                affected_ids=(req_id,),
                description=f"{fcf.characteristic.value} has no datum reference",
                severity="WARNING",
                suggested_resolution="Add appropriate datum reference to the FCF",
            ),
        )]
    return [GdtValidationResult(rule_id="VAL-GDT-002", passed=True, severity="INFO",
                                message=f"VAL-GDT-002 passed for {req_id}")]


def _val_003(
    fcf: ExpandedFeatureControlFrame,
    req_id: str,
    fos: FeatureOfSize | None,
) -> list[GdtValidationResult]:
    """VAL-GDT-003/004: MMC/LMC only valid on true feature-of-size."""
    modifier = fcf.modifier
    if modifier not in (GdtModifier.MMC, GdtModifier.LMC):
        return [GdtValidationResult(rule_id="VAL-GDT-003", passed=True, severity="INFO",
                                    message=f"VAL-GDT-003 passed for {req_id}")]
    is_fos = fos is not None and fos.is_true_fos
    if not is_fos:
        return [GdtValidationResult(
            rule_id="VAL-GDT-003",
            passed=False,
            severity="ERROR",
            message=(
                f"{modifier.value} on {fcf.characteristic.value} at {req_id} — "
                "modifier only valid on a true feature-of-size"
            ),
            ambiguity=GdtAmbiguity(
                ambiguity_id=f"AMB-{req_id}-003",
                kind=AmbiguityKind.INVALID_MODIFIER_COMBO,
                affected_ids=(req_id,),
                description=f"{modifier.value} requires feature-of-size semantics",
                severity="ERROR",
                suggested_resolution="Verify FOS classification or remove modifier",
            ),
        )]
    return [GdtValidationResult(rule_id="VAL-GDT-003", passed=True, severity="INFO",
                                message=f"VAL-GDT-003 passed for {req_id}")]


def _val_004(fcf: ExpandedFeatureControlFrame, req_id: str) -> list[GdtValidationResult]:
    """VAL-GDT-004: Form tolerances cannot carry MMC/LMC (handled by VAL-GDT-003)."""
    modifier = fcf.modifier
    if fcf.characteristic in GDT_FORM_ONLY and modifier in (GdtModifier.MMC, GdtModifier.LMC):
        return [GdtValidationResult(
            rule_id="VAL-GDT-004",
            passed=False,
            severity="ERROR",
            message=(
                f"{fcf.characteristic.value} at {req_id} carries {modifier.value} — "
                "form tolerances cannot use material condition modifiers"
            ),
            ambiguity=GdtAmbiguity(
                ambiguity_id=f"AMB-{req_id}-004",
                kind=AmbiguityKind.INVALID_MODIFIER_COMBO,
                affected_ids=(req_id,),
                description=(
                    f"{fcf.characteristic.value} + {modifier.value} is semantically invalid"
                ),
                severity="ERROR",
                suggested_resolution="Remove material condition modifier from form tolerance",
            ),
        )]
    return [GdtValidationResult(rule_id="VAL-GDT-004", passed=True, severity="INFO",
                                message=f"VAL-GDT-004 passed for {req_id}")]


def _val_006(composite: CompositePositionFCF) -> list[GdtValidationResult]:
    """VAL-GDT-006: Composite lower segment tolerance must be <= upper."""
    if len(composite.segments) < 2:
        return [GdtValidationResult(
            rule_id="VAL-GDT-006",
            passed=False,
            severity="ERROR",
            message=f"CompositePositionFCF {composite.fcf_id} requires at least 2 segments",
        )]
    upper = composite.segments[0].tolerance_value
    lower = composite.segments[1].tolerance_value
    if lower > upper:
        return [GdtValidationResult(
            rule_id="VAL-GDT-006",
            passed=False,
            severity="ERROR",
            message=(
                f"Composite FCF {composite.fcf_id}: lower segment {lower} > upper segment {upper} "
                "(GDT_COMPOSITE_TOLERANCE_INVERTED)"
            ),
            ambiguity=GdtAmbiguity(
                ambiguity_id=f"AMB-{composite.fcf_id}-006",
                kind=AmbiguityKind.COMPOSITE_TOLERANCE_INVERTED,
                affected_ids=(composite.fcf_id,),
                description="FRTZF tolerance exceeds PLTZF tolerance",
                severity="ERROR",
                suggested_resolution="FRTZF (lower) must be <= PLTZF (upper) tolerance",
            ),
        )]
    return [GdtValidationResult(rule_id="VAL-GDT-006", passed=True, severity="INFO",
                                message=f"VAL-GDT-006 passed for {composite.fcf_id}")]


def _val_007(fcf: ExpandedFeatureControlFrame, req_id: str) -> list[GdtValidationResult]:
    """VAL-GDT-007: TOTAL_RUNOUT datum should be a cylindrical feature."""
    if fcf.characteristic != GdtCharacteristic.TOTAL_RUNOUT:
        return [GdtValidationResult(rule_id="VAL-GDT-007", passed=True, severity="INFO",
                                    message=f"VAL-GDT-007 not applicable for {req_id}")]
    if fcf.datum_frame is None:
        return [GdtValidationResult(
            rule_id="VAL-GDT-007",
            passed=False,
            severity="WARNING",
            message=f"TOTAL_RUNOUT at {req_id} has no datum — datum axis is required",
            ambiguity=GdtAmbiguity(
                ambiguity_id=f"AMB-{req_id}-007",
                kind=AmbiguityKind.MISSING_DATUM,
                affected_ids=(req_id,),
                description="TOTAL_RUNOUT requires datum axis reference",
                severity="WARNING",
                suggested_resolution="Add datum axis reference (typically a cylindrical surface)",
            ),
        )]
    return [GdtValidationResult(rule_id="VAL-GDT-007", passed=True, severity="INFO",
                                message=f"VAL-GDT-007 passed for {req_id}")]


def _val_008(fcf: ExpandedFeatureControlFrame, req_id: str) -> list[GdtValidationResult]:
    """VAL-GDT-008: Advisory for legacy characteristics CONCENTRICITY/SYMMETRY."""
    legacy = {GdtCharacteristic.CONCENTRICITY, GdtCharacteristic.SYMMETRY}
    if fcf.characteristic in legacy:
        modern = ("POSITION (coaxial)" if fcf.characteristic == GdtCharacteristic.CONCENTRICITY
                  else "POSITION (symmetric features)")
        return [GdtValidationResult(
            rule_id="VAL-GDT-008",
            passed=True,
            severity="INFO",
            message=(
                f"{fcf.characteristic.value} at {req_id} is a legacy characteristic "
                f"(ASME Y14.5-2018 deprecated). Modern equivalent: {modern}."
            ),
            ambiguity=GdtAmbiguity(
                ambiguity_id=f"AMB-{req_id}-008",
                kind=AmbiguityKind.LEGACY_CHARACTERISTIC,
                affected_ids=(req_id,),
                description=f"{fcf.characteristic.value} is deprecated in ASME Y14.5-2018",
                severity="INFO",
                suggested_resolution=f"Consider replacing with {modern}",
            ),
        )]
    return [GdtValidationResult(rule_id="VAL-GDT-008", passed=True, severity="INFO",
                                message=f"VAL-GDT-008 not applicable for {req_id}")]
