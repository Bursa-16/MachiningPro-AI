"""
MachiningPro AI — Honing Engineering Rules (Stage 3K)

EngineeringRule wrappers for deterministic honing calculations.

Calculation rules : R-2901 – R-2906
Validation rules  : R-2951 – R-2953

Each rule converts a MachiningMathError into a failure EngineeringResult,
following the same pattern as turning_rules.py.

[ASSUMPTION A4] EngineeringRule / EngineeringResult pattern matches
turning_rules.py exactly — rule_id, rule_version, description, domain,
required_inputs, source_reference, _evaluate(inputs).
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from backend.core.rules.base import EngineeringRule
from backend.domain.result import EngineeringResult, failure, success, warning
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.honing import (
    honing_crosshatch_included_angle,
    honing_peripheral_speed,
    honing_radial_stock,
    honing_removed_volume,
    honing_required_stroke_speed,
    honing_resultant_speed,
)

# ---------------------------------------------------------------------------
# Shared citation for kinematic / geometric rules (used as source_reference)
# ---------------------------------------------------------------------------

_SOURCE = (
    "Honing process kinematics: Schwarz, E. (Ed.), Handbook of Machining "
    "and Metalworking Calculations, McGraw-Hill, 2001. "
    "ISO 74344 surface texture; engine manufacturer specifications. "
    "Barnes Honing stroke geometry guide."
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
# R-2901  Peripheral speed
# ---------------------------------------------------------------------------

class HoningPeripheralSpeedRule(EngineeringRule):
    rule_id = "R-2901"
    rule_version = "1.0"
    description = "Honing peripheral speed: v_p = (π × D × n) / 1000"
    domain = "honing.kinematics"
    required_inputs = ("bore_diameter", "spindle_speed",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            v_p = honing_peripheral_speed(
                bore_diameter=inputs["bore_diameter"],
                spindle_speed=inputs["spindle_speed"],
            )
        except MachiningMathError as exc:
            return _fail(self.rule_id, self.rule_version, str(exc))
        return _ok(
            self.rule_id, self.rule_version,
            {"peripheral_speed": v_p},
            f"v_p = {v_p.value:.4f} m/min",
        )


# ---------------------------------------------------------------------------
# R-2902  Crosshatch included angle
# ---------------------------------------------------------------------------

class HoningCrosshatchIncludedAngleRule(EngineeringRule):
    """
    Computes the INCLUDED angle between crossing groove families.
    α_included = 2 × arctan(v_h / v_p).
    See honing.py module docstring for convention details.
    """
    rule_id = "R-2902"
    rule_version = "1.0"
    description = (
        "Honing crosshatch INCLUDED angle: α = 2 × arctan(v_h / v_p). "
        "Reports included angle between crossing groove families (not single-groove angle)."
    )
    domain = "honing.kinematics"
    required_inputs = ("stroke_speed", "peripheral_speed",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            alpha = honing_crosshatch_included_angle(
                stroke_speed=inputs["stroke_speed"],
                peripheral_speed=inputs["peripheral_speed"],
            )
        except MachiningMathError as exc:
            return _fail(self.rule_id, self.rule_version, str(exc))
        return _ok(
            self.rule_id, self.rule_version,
            {"crosshatch_included_angle_deg": alpha},
            f"α_included = {alpha.value:.2f}° (included angle between groove families)",
        )


# ---------------------------------------------------------------------------
# R-2903  Required stroke speed for target crosshatch angle
# ---------------------------------------------------------------------------

class HoningRequiredStrokeSpeedRule(EngineeringRule):
    rule_id = "R-2903"
    rule_version = "1.0"
    description = (
        "Required stroke speed for target crosshatch included angle: "
        "v_h = v_p × tan(α_included / 2)"
    )
    domain = "honing.kinematics"
    required_inputs = ("crosshatch_included_angle_deg", "peripheral_speed",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            v_h = honing_required_stroke_speed(
                crosshatch_included_angle_deg=inputs["crosshatch_included_angle_deg"],
                peripheral_speed=inputs["peripheral_speed"],
            )
        except MachiningMathError as exc:
            return _fail(self.rule_id, self.rule_version, str(exc))
        return _ok(
            self.rule_id, self.rule_version,
            {"stroke_speed": v_h},
            f"v_h = {v_h.value:.4f} m/min",
        )


# ---------------------------------------------------------------------------
# R-2904  Resultant cutting speed
# ---------------------------------------------------------------------------

class HoningResultantSpeedRule(EngineeringRule):
    rule_id = "R-2904"
    rule_version = "1.0"
    description = "Honing resultant cutting speed: v_c = √(v_p² + v_h²)"
    domain = "honing.kinematics"
    required_inputs = ("stroke_speed", "peripheral_speed",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            v_c = honing_resultant_speed(
                stroke_speed=inputs["stroke_speed"],
                peripheral_speed=inputs["peripheral_speed"],
            )
        except MachiningMathError as exc:
            return _fail(self.rule_id, self.rule_version, str(exc))
        return _ok(
            self.rule_id, self.rule_version,
            {"resultant_speed": v_c},
            f"v_c = {v_c.value:.4f} m/min",
        )


# ---------------------------------------------------------------------------
# R-2905  Radial stock removal
# ---------------------------------------------------------------------------

class HoningRadialStockRule(EngineeringRule):
    rule_id = "R-2905"
    rule_version = "1.0"
    description = "Honing radial stock: s = (D_final − D_initial) / 2"
    domain = "honing.geometry"
    required_inputs = ("diameter_initial", "diameter_final",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            s = honing_radial_stock(
                diameter_initial=inputs["diameter_initial"],
                diameter_final=inputs["diameter_final"],
            )
        except MachiningMathError as exc:
            return _fail(self.rule_id, self.rule_version, str(exc))
        return _ok(
            self.rule_id, self.rule_version,
            {"radial_stock": s},
            f"s_radial = {s.value:.4f} mm",
        )


# ---------------------------------------------------------------------------
# R-2906  Removed volume
# ---------------------------------------------------------------------------

class HoningRemovedVolumeRule(EngineeringRule):
    rule_id = "R-2906"
    rule_version = "1.0"
    description = "Honing removed volume: V = (π/4) × (D_final² − D_initial²) × L"
    domain = "honing.geometry"
    required_inputs = ("diameter_initial", "diameter_final", "bore_length",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            v = honing_removed_volume(
                diameter_initial=inputs["diameter_initial"],
                diameter_final=inputs["diameter_final"],
                bore_length=inputs["bore_length"],
            )
        except MachiningMathError as exc:
            return _fail(self.rule_id, self.rule_version, str(exc))
        return _ok(
            self.rule_id, self.rule_version,
            {"volume_removed": v},
            f"V = {v.value:.2f} mm³",
        )


# ---------------------------------------------------------------------------
# R-2951  Peripheral speed upper-bound validation
# ---------------------------------------------------------------------------

class HoningPeripheralSpeedBoundRule(EngineeringRule):
    """
    Classification: VALIDATION

    Warns when peripheral speed exceeds 60 m/min, the typical upper bound
    for long-stroke internal honing. Some short-bore or superfinishing
    operations legitimately exceed this — rule warns rather than fails.

    Source: Honing handbook practice; ScienceDirect honing overview.
    This limit is EMPIRICAL / MANUFACTURER_DERIVED, not derived from
    first principles. It is a warning threshold, not a physical law.
    """
    rule_id = "R-2951"
    rule_version = "1.0"
    description = (
        "Peripheral speed warning: v_p > 60 m/min exceeds typical long-stroke bound. "
        "EMPIRICAL threshold — source: honing handbook practice."
    )
    domain = "honing.validation"
    required_inputs = ("peripheral_speed",)
    source_reference = (
        "Sunnen Products Company honing handbook; "
        "ScienceDirect Azar 2021 honing overview"
    )

    _V_P_WARN = Decimal("60")

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        v_p: Quantity = inputs["peripheral_speed"]
        if v_p.unit is not Unit.M_MIN:
            return _fail(self.rule_id, self.rule_version,
                         "peripheral_speed must have unit m/min")
        if v_p.value > self._V_P_WARN:
            return warning(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                outputs={"peripheral_speed": v_p},
                warnings=(
                    f"v_p = {v_p.value:.1f} m/min exceeds 60 m/min empirical "
                    "upper bound for long-stroke internal honing. "
                    "Risk of stone loading or thermal effects.",
                ),
                summary="Peripheral speed above empirical warning threshold",
            )
        return _ok(
            self.rule_id, self.rule_version,
            {"peripheral_speed": v_p},
            f"v_p = {v_p.value:.1f} m/min within empirical guideline",
        )


# ---------------------------------------------------------------------------
# R-2952  Crosshatch angle practical bounds validation
# ---------------------------------------------------------------------------

class HoningCrosshatchAngleBoundsRule(EngineeringRule):
    """
    Classification: VALIDATION

    Fails when the included crosshatch angle falls outside 20°–60°.
    Below 20°: groove angle almost axial, crosshatch oil-retention function lost.
    Above 60°: groove angle almost circumferential, poor oil retention.

    Range [20°, 60°] is EMPIRICAL, drawn from engine-manufacturer specs
    and honing handbooks — not a universal physical law.
    """
    rule_id = "R-2952"
    rule_version = "1.0"
    description = (
        "Crosshatch included angle must be in [20°, 60°]. "
        "EMPIRICAL bounds — source: engine manufacturer specifications."
    )
    domain = "honing.validation"
    required_inputs = ("crosshatch_included_angle_deg",)
    source_reference = (
        "Engine manufacturer cylinder bore specifications; "
        "ISO 74344; Gehring/Kadia plateau honing documentation"
    )

    _ALPHA_MIN = Decimal("20")
    _ALPHA_MAX = Decimal("60")

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        alpha: Quantity = inputs["crosshatch_included_angle_deg"]
        if alpha.unit is not Unit.DIMENSIONLESS:
            return _fail(self.rule_id, self.rule_version,
                         "crosshatch_included_angle_deg must be DIMENSIONLESS "
                         "(degrees stored as Decimal)")
        if not (self._ALPHA_MIN <= alpha.value <= self._ALPHA_MAX):
            return _fail(
                self.rule_id, self.rule_version,
                f"Included crosshatch angle {alpha.value:.2f}° is outside "
                f"empirical bounds [{self._ALPHA_MIN}°, {self._ALPHA_MAX}°]. "
                "Adjust stroke speed or spindle speed.",
            )
        return _ok(
            self.rule_id, self.rule_version,
            {"crosshatch_included_angle_deg": alpha},
            f"α_included = {alpha.value:.2f}° within empirical bounds",
        )


# ---------------------------------------------------------------------------
# R-2953  Radial stock positive validation
# ---------------------------------------------------------------------------

class HoningStockPositiveRule(EngineeringRule):
    """
    Classification: VALIDATION (physical constraint)

    Ensures the target diameter exceeds the initial diameter.
    Honing can only enlarge a bore — it cannot reduce diameter.
    """
    rule_id = "R-2953"
    rule_version = "1.0"
    description = "Honing radial stock must be positive: D_final > D_initial"
    domain = "honing.validation"
    required_inputs = ("diameter_initial", "diameter_final",)
    source_reference = "Physical constraint — honing enlarges bore"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        d_i: Quantity = inputs["diameter_initial"]
        d_f: Quantity = inputs["diameter_final"]
        if d_f.value <= d_i.value:
            return _fail(
                self.rule_id, self.rule_version,
                f"diameter_final ({d_f.value} mm) must exceed "
                f"diameter_initial ({d_i.value} mm). "
                "Honing only enlarges the bore.",
            )
        return _ok(
            self.rule_id, self.rule_version, {},
            "Radial stock is positive",
        )


# ---------------------------------------------------------------------------
# Public rule registry for Stage 3K
# ---------------------------------------------------------------------------

HONING_RULES: tuple[type[EngineeringRule], ...] = (
    HoningPeripheralSpeedRule,
    HoningCrosshatchIncludedAngleRule,
    HoningRequiredStrokeSpeedRule,
    HoningResultantSpeedRule,
    HoningRadialStockRule,
    HoningRemovedVolumeRule,
    HoningPeripheralSpeedBoundRule,
    HoningCrosshatchAngleBoundsRule,
    HoningStockPositiveRule,
)

HONING_RULE_IDS: tuple[str, ...] = tuple(r.rule_id for r in HONING_RULES)
