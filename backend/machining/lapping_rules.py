"""
MachiningPro AI — Lapping Engineering Rules (Stage 3L)

EngineeringRule wrappers for deterministic lapping calculations.

Calculation rules : R-3001 – R-3005
Validation rules  : R-3051 – R-3053

The Preston empirical evaluator is NOT wrapped as an EngineeringRule
because it is EMPIRICAL, not deterministic. It is exposed directly from
lapping.py and called by the AI advisory layer, not by the rule engine.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from backend.core.rules.base import EngineeringRule
from backend.domain.result import EngineeringResult, failure, success, warning
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.lapping import (
    lapping_contact_pressure,
    lapping_cycle_time,
    lapping_removed_thickness,
    lapping_removed_volume,
    lapping_volumetric_mrr,
)

_SOURCE = (
    "Preston, F.W. (1927). Theory and Design of Plate Glass Polishing Machines. "
    "Journal of the Society of Glass Technology, 11, 214-256. "
    "Deja, M. et al. (2020). Developing an Analytical Model and Computing Tool "
    "for Optimizing Lapping Operations. Materials, 13(6), 1343."
)

def _fail(rule_id: str, rule_version: str, msg: str) -> EngineeringResult:
    return failure(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=rule_version,
        violations=(msg,),
        summary=msg,
    )


def _ok(rule_id: str, rule_version: str, outputs: dict, summary: str) -> EngineeringResult:
    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=rule_version,
        outputs=outputs,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# R-3001  Lapping contact pressure
# ---------------------------------------------------------------------------

class LappingContactPressureRule(EngineeringRule):
    rule_id = "R-3001"
    rule_version = "1.0"
    description = "Lapping contact pressure: P = F / A  (1 N/mm² = 1 MPa)"
    domain = "lapping.kinematics"
    required_inputs = ("normal_force", "contact_area_mm2",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            area = Decimal(str(inputs["contact_area_mm2"]))
            p = lapping_contact_pressure(
                normal_force=inputs["normal_force"],
                contact_area_mm2=area,
            )
        except (MachiningMathError, Exception) as exc:
            return _fail(self.rule_id, self.rule_version, str(exc))
        return _ok(
            self.rule_id, self.rule_version,
            {"pressure": p},
            f"P = {p.value:.5f} MPa",
        )


# ---------------------------------------------------------------------------
# R-3002  Removed volume
# ---------------------------------------------------------------------------

class LappingRemovedVolumeRule(EngineeringRule):
    rule_id = "R-3002"
    rule_version = "1.0"
    description = "Lapping removed volume: V = A × Δh  (Δh in MM)"
    domain = "lapping.geometry"
    required_inputs = ("contact_area_mm2", "removed_thickness",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            area = Decimal(str(inputs["contact_area_mm2"]))
            v = lapping_removed_volume(
                contact_area_mm2=area,
                removed_thickness=inputs["removed_thickness"],
            )
        except (MachiningMathError, Exception) as exc:
            return _fail(self.rule_id, self.rule_version, str(exc))
        return _ok(
            self.rule_id, self.rule_version,
            {"removed_volume": v},
            f"V = {v.value:.4f} mm³",
        )


# ---------------------------------------------------------------------------
# R-3003  Volumetric MRR from measured data
# ---------------------------------------------------------------------------

class LappingVolumetricMRRRule(EngineeringRule):
    rule_id = "R-3003"
    rule_version = "1.0"
    description = (
        "Lapping volumetric MRR from MEASURED removal: MRR = V / t. "
        "DETERMINISTIC given measured inputs. Distinct from Preston estimate."
    )
    domain = "lapping.kinematics"
    required_inputs = ("removed_volume", "process_time",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            mrr = lapping_volumetric_mrr(
                removed_volume=inputs["removed_volume"],
                process_time=inputs["process_time"],
            )
        except MachiningMathError as exc:
            return _fail(self.rule_id, self.rule_version, str(exc))
        return _ok(
            self.rule_id, self.rule_version,
            {"volumetric_mrr": mrr},
            f"MRR = {mrr.value:.4f} mm³/min",
        )


# ---------------------------------------------------------------------------
# R-3004  Removed thickness from volume and area
# ---------------------------------------------------------------------------

class LappingRemovedThicknessRule(EngineeringRule):
    rule_id = "R-3004"
    rule_version = "1.0"
    description = "Lapping removed thickness: Δh = V / A"
    domain = "lapping.geometry"
    required_inputs = ("removed_volume", "contact_area_mm2",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            area = Decimal(str(inputs["contact_area_mm2"]))
            delta_h = lapping_removed_thickness(
                removed_volume=inputs["removed_volume"],
                contact_area_mm2=area,
            )
        except (MachiningMathError, Exception) as exc:
            return _fail(self.rule_id, self.rule_version, str(exc))
        return _ok(
            self.rule_id, self.rule_version,
            {"removed_thickness": delta_h},
            f"Δh = {delta_h.value:.6f} mm",
        )


# ---------------------------------------------------------------------------
# R-3005  Cycle time from target volume and MRR
# ---------------------------------------------------------------------------

class LappingCycleTimeRule(EngineeringRule):
    rule_id = "R-3005"
    rule_version = "1.0"
    description = "Lapping cycle time: t = V_target / MRR_vol"
    domain = "lapping.geometry"
    required_inputs = ("target_removed_volume", "volumetric_mrr",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            t = lapping_cycle_time(
                target_removed_volume=inputs["target_removed_volume"],
                volumetric_mrr=inputs["volumetric_mrr"],
            )
        except MachiningMathError as exc:
            return _fail(self.rule_id, self.rule_version, str(exc))
        return _ok(
            self.rule_id, self.rule_version,
            {"cycle_time": t},
            f"t = {t.value:.4f} min",
        )


# ---------------------------------------------------------------------------
# R-3051  Pressure range warning
# ---------------------------------------------------------------------------

class LappingPressureRangeRule(EngineeringRule):
    """
    Classification: VALIDATION

    Warns when pressure falls outside the typical empirical range for
    metal workpieces (0.005–0.200 MPa). Not a physical law — just a
    commonly cited guideline. Ceramics and optics may legitimately fall
    outside this range.

    EMPIRICAL — source: Lapmaster-Wolters application guide.
    """
    rule_id = "R-3051"
    rule_version = "1.0"
    description = (
        "Lapping pressure range warning: 0.005–0.200 MPa typical for metals. "
        "EMPIRICAL guideline — not a physical law."
    )
    domain = "lapping.validation"
    required_inputs = ("pressure",)
    source_reference = "Lapmaster-Wolters lapping application guide; precision-surface.com"

    _P_MIN = Decimal("0.005")
    _P_MAX = Decimal("0.200")

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        p: Quantity = inputs["pressure"]
        if p.unit is not Unit.MPA:
            return _fail(self.rule_id, self.rule_version,
                         "pressure must have unit MPa")
        pressure_warnings = []
        if p.value < self._P_MIN:
            pressure_warnings.append(
                f"P = {p.value:.4f} MPa is below empirical guideline "
                f"minimum {self._P_MIN} MPa — MRR may be negligible."
            )
        if p.value > self._P_MAX:
            pressure_warnings.append(
                f"P = {p.value:.4f} MPa exceeds empirical guideline "
                f"maximum {self._P_MAX} MPa — surface damage risk."
            )
        if pressure_warnings:
            return warning(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                outputs={"pressure": p},
                warnings=tuple(pressure_warnings),
                summary="Pressure outside empirical guideline range",
            )
        return _ok(
            self.rule_id, self.rule_version,
            {"pressure": p},
            f"P = {p.value:.4f} MPa within empirical guideline range",
        )


# ---------------------------------------------------------------------------
# R-3052  Stock removal tolerance guard
# ---------------------------------------------------------------------------

class LappingStockRemovalToleranceRule(EngineeringRule):
    """
    Fails when predicted or measured stock removal exceeds caller-supplied
    maximum allowance.  Over-lapping is irreversible.
    """
    rule_id = "R-3052"
    rule_version = "1.0"
    description = "Stock removal must not exceed maximum allowance (over-lapping prevention)"
    domain = "lapping.validation"
    required_inputs = ("removed_thickness", "max_allowance",)
    source_reference = "Dimensional constraint — over-lapping irreversible"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        actual: Quantity = inputs["removed_thickness"]
        allowed: Quantity = inputs["max_allowance"]
        if actual.unit is not Unit.MM or allowed.unit is not Unit.MM:
            return _fail(self.rule_id, self.rule_version,
                         "removed_thickness and max_allowance must both be in MM")
        if actual.value > allowed.value:
            return _fail(
                self.rule_id, self.rule_version,
                f"Removed thickness {actual.value:.6f} mm exceeds "
                f"allowance {allowed.value:.6f} mm. "
                "Reduce process time, pressure, or MRR.",
            )
        return _ok(
            self.rule_id, self.rule_version, {},
            f"Δh = {actual.value:.6f} mm ≤ allowance {allowed.value:.6f} mm",
        )


# ---------------------------------------------------------------------------
# R-3053  Preston K_p provenance guard (architectural)
# ---------------------------------------------------------------------------

class LappingPrestonKProvenanceRule(EngineeringRule):
    """
    Classification: VALIDATION / ARCHITECTURAL GUARD

    Verifies that K_p for the Preston model has a verified provenance
    record before any Preston-based estimate is used downstream.

    The Preston model is EMPIRICAL. K_p has no universal default.
    This rule must be evaluated before calling
    estimate_lapping_removal_rate_preston().

    Pass kp_provenance_verified=True only when a CuttingParameterRecord
    with evidence_status in {AUTHORITATIVE, EXPERIMENTAL} and a non-None
    source_reference has been retrieved from the Stage 3G registry.
    """
    rule_id = "R-3053"
    rule_version = "1.0"
    description = (
        "Preston K_p must come from a provenance-verified empirical record. "
        "No default. Missing or unverified → fail closed."
    )
    domain = "lapping.validation"
    required_inputs = ("kp_provenance_verified",)
    source_reference = "MachiningPro AI empirical data policy — Stage 3G"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        verified: bool = bool(inputs.get("kp_provenance_verified", False))
        if not verified:
            return _fail(
                self.rule_id, self.rule_version,
                "Preston coefficient K_p has no verified provenance. "
                "Retrieve an AUTHORITATIVE or EXPERIMENTAL CuttingParameterRecord "
                "with a non-None source_reference from the Stage 3G registry. "
                "Preston-based MRR estimation is blocked until K_p is verified.",
            )
        return _ok(
            self.rule_id, self.rule_version, {},
            "K_p provenance verified — Preston model may proceed",
        )


# ---------------------------------------------------------------------------
# Public rule registry for Stage 3L
# ---------------------------------------------------------------------------

LAPPING_RULES: tuple[type[EngineeringRule], ...] = (
    LappingContactPressureRule,
    LappingRemovedVolumeRule,
    LappingVolumetricMRRRule,
    LappingRemovedThicknessRule,
    LappingCycleTimeRule,
    LappingPressureRangeRule,
    LappingStockRemovalToleranceRule,
    LappingPrestonKProvenanceRule,
)

LAPPING_RULE_IDS: tuple[str, ...] = tuple(r.rule_id for r in LAPPING_RULES)
