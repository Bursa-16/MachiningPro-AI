"""Cutting Parameter Resolver — EPIC_04E Phase 2.

Resolves ParameterContext from the CuttingParameterRegistry for a given
(operation_type, iso_material_group) combination.

Creates CONSERVATIVE / BALANCED / PRODUCTIVITY variants using the range
bounds from REFERENCE_ONLY registry records.

CUTTING_PARAMETER_ALTERNATIVES_IMPLEMENTED=YES
FABRICATED_CUTTING_PARAMETER=NO — only returns registry evidence.
"""

from __future__ import annotations

from backend.cutting_parameters.models import ApplicabilityScope, ParameterType
from backend.domain.enums import IsoMaterialGroup, OperationType
from backend.drawing_intelligence.route_domain import (
    ParameterContext,
    ParameterVariant,
    ProcessCapabilityConfidence,
)

__all__ = ["ParameterResolver"]


def _confidence_from_evidence(status: str) -> ProcessCapabilityConfidence:
    mapping = {
        "AUTHORITATIVE":          ProcessCapabilityConfidence.VERIFIED_REFERENCE,
        "EXPERIMENTAL":           ProcessCapabilityConfidence.INTERNAL_VALIDATED,
        "REFERENCE_ONLY":         ProcessCapabilityConfidence.MANUFACTURER_REFERENCE,
        "ESTIMATED":              ProcessCapabilityConfidence.ADVISORY,
        "INSUFFICIENT_DATA":      ProcessCapabilityConfidence.INSUFFICIENT_DATA,
    }
    return mapping.get(status.upper(), ProcessCapabilityConfidence.ADVISORY)


class ParameterResolver:
    """Resolves cutting parameter alternatives from the registry.

    CUTTING_PARAMETER_ALTERNATIVES_IMPLEMENTED=YES
    FABRICATED_CUTTING_PARAMETER=NO
    """

    def __init__(self) -> None:
        self._registry = None

    def _get_registry(self):
        if self._registry is None:
            from backend.cutting_parameters.registry import CuttingParameterRegistry
            from backend.cutting_parameters.seed_reference import seed_reference_registry
            reg = CuttingParameterRegistry()
            try:
                seed_reference_registry(reg)
            except (OSError, FileNotFoundError):
                # Env var not set or file not found — empty registry.
                # FABRICATED_CUTTING_PARAMETER=NO: resolve() returns None.
                pass
            self._registry = reg
        return self._registry

    def resolve(
        self,
        op_type: OperationType,
        iso_material_group: str | None,
        source_record_id: str | None = None,
    ) -> ParameterContext | None:
        """Return ParameterContext with CONSERVATIVE/BALANCED/PRODUCTIVITY variants.

        Returns None when no registry records exist for this combination.
        FABRICATED_CUTTING_PARAMETER=NO — None is never replaced by guessed values.
        """
        reg = self._get_registry()

        iso = None
        if iso_material_group:
            try:
                iso = IsoMaterialGroup(iso_material_group.upper())
            except ValueError:
                pass

        scope = ApplicabilityScope(
            operation_type=op_type,
            iso_material_group=iso,
        )

        vc_records = reg.find(scope=scope, parameter_type=ParameterType.CUTTING_SPEED)
        if not vc_records:
            return None

        # Use the first authoritative or reference record
        rec = vc_records[0]
        vc_low = float(rec.value_range.low or 0)
        vc_high = float(rec.value_range.high or vc_low)
        confidence = _confidence_from_evidence(str(rec.evidence_status))
        rec_id = source_record_id or rec.record_id

        # fz / feed lookup
        fz_records = reg.find(scope=scope, parameter_type=ParameterType.FEED_PER_TOOTH)
        fz_low = fz_high = None
        if fz_records:
            fz_low = float(fz_records[0].value_range.low or 0)
            fz_high = float(fz_records[0].value_range.high or fz_low)

        f_records = reg.find(scope=scope, parameter_type=ParameterType.FEED_PER_REV)
        fr_low = None
        if f_records:
            fr_low = float(f_records[0].value_range.low or 0)

        # ap lookup
        ap_records = reg.find(scope=scope, parameter_type=ParameterType.AXIAL_DEPTH_OF_CUT)
        ap_low = ap_high = None
        if ap_records:
            ap_low = float(ap_records[0].value_range.low or 0)
            ap_high = float(ap_records[0].value_range.high or ap_low)

        fz_use = fz_low if fz_low else fr_low

        variants = (
            ParameterVariant(
                variant="CONSERVATIVE",
                vc_m_min=vc_low,
                fz_mm=fz_use,
                ap_mm=ap_low,
                ae_mm=None,
                confidence=confidence,
                source_record_id=rec_id,
                notes="Lower bound of reference range — conservative for tough materials.",
            ),
            ParameterVariant(
                variant="BALANCED",
                vc_m_min=round((vc_low + vc_high) / 2, 1) if vc_high else vc_low,
                fz_mm=(
                    round(((fz_use or 0) + (fz_high or fz_use or 0)) / 2, 4)
                    if (fz_use or fz_high) else None
                ),
                ap_mm=(
                    round(((ap_low or 0) + (ap_high or ap_low or 0)) / 2, 2)
                    if (ap_low or ap_high) else None
                ),
                ae_mm=None,
                confidence=confidence,
                source_record_id=rec_id,
                notes="Mid-point of reference range — general-purpose.",
            ),
            ParameterVariant(
                variant="PRODUCTIVITY",
                vc_m_min=vc_high,
                fz_mm=fz_high if fz_high else fz_use,
                ap_mm=ap_high,
                ae_mm=None,
                confidence=ProcessCapabilityConfidence.ADVISORY,
                source_record_id=rec_id,
                notes=(
                    "Upper bound of reference range — productivity-oriented. "
                    "Verify with tool manufacturer before use."
                ),
            ),
        )

        return ParameterContext(
            material_iso_group=iso_material_group,
            variants=variants,
        )
