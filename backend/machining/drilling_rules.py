"""EngineeringRule wrappers for deterministic drilling calculations (Stage 3D).

Rule ID range: R-2301 onward.

Rule families:

  R-2301..R-2305  Drilling-specific calculation rules (deterministic wrappers)
  R-2310..R-2313  Drilling engineering validation rules (warn/reject checks)

Validation rules classify their thresholds as either PHYSICAL_CONSTRAINT
or ENGINEERING_POLICY_THRESHOLD.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from backend.core.rules.base import EngineeringRule
from backend.domain.result import EngineeringResult, failure, success, warning
from backend.domain.units import Quantity, Unit
from backend.machining import drilling
from backend.machining.exceptions import MachiningMathError
from backend.machining.formulas import feed_rate_from_rpm_feed_per_rev

__all__ = [
    # calculation rules
    "EffectiveDrillingTravelRule",
    "DrillingMachiningTimeRule",
    "HoleCrossSectionalAreaRule",
    "CylindricalHoleVolumeRule",
    "DrillingMRRRule",
    # validation rules
    "DrillingFeedConsistencyRule",
    "EffectiveTravelNotLessThanDepthRule",
    "DrillingZeroDepthRule",
    "DrillingDepthToDiameterRatioRule",
    # collection
    "foundational_drilling_rules",
]


def _fer(rule_id: str, version: str, exc: MachiningMathError) -> EngineeringResult:
    return failure(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=version,
        violations=(str(exc),),
    )


# ---------------------------------------------------------------------------
# Calculation rules
# ---------------------------------------------------------------------------

class EffectiveDrillingTravelRule(EngineeringRule):
    """R-2301: L_eff = depth + approach + breakthrough."""
    rule_id = "R-2301"
    rule_version = "1.0.0"
    description = "Compute effective drilling feed travel with explicit allowances."
    domain = "drilling.geometry"
    required_inputs = ("hole_depth",)
    source_reference = "machining-ai Stage 3D drilling geometry"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = drilling.effective_drilling_travel(
                inputs["hole_depth"],
                inputs.get("approach_allowance"),
                inputs.get("breakthrough_allowance"),
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"effective_travel": result},
            summary=f"effective_travel {result}",
        )


class DrillingMachiningTimeRule(EngineeringRule):
    """R-2302: t = effective_travel / (n × f)."""
    rule_id = "R-2302"
    rule_version = "1.0.0"
    description = "Compute drilling machining time from rpm, feed/rev and depth."
    domain = "drilling.time"
    required_inputs = ("spindle_speed", "feed_per_rev", "hole_depth")
    source_reference = "machining-ai Stage 3D drilling time (composed from Stage 3A)"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = drilling.drilling_machining_time(
                inputs["spindle_speed"],
                inputs["feed_per_rev"],
                inputs["hole_depth"],
                inputs.get("approach_allowance"),
                inputs.get("breakthrough_allowance"),
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"time": result},
            summary=f"time {result}",
        )


class HoleCrossSectionalAreaRule(EngineeringRule):
    """R-2303: A = π × D² / 4."""
    rule_id = "R-2303"
    rule_version = "1.0.0"
    description = "Compute hole cross-sectional area for solid circular drilling."
    domain = "drilling.geometry"
    required_inputs = ("diameter",)
    source_reference = "machining-ai Stage 3D drilling geometry"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = drilling.hole_cross_sectional_area(inputs["diameter"])
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"area": result},
            summary=f"area {result}",
        )


class CylindricalHoleVolumeRule(EngineeringRule):
    """R-2304: V = (π × D² / 4) × depth."""
    rule_id = "R-2304"
    rule_version = "1.0.0"
    description = "Compute volume removed for a simple cylindrical hole."
    domain = "drilling.volume"
    required_inputs = ("diameter", "depth")
    source_reference = "machining-ai Stage 3D drilling volume"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = drilling.cylindrical_hole_volume(
                inputs["diameter"], inputs["depth"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"volume": result},
            summary=f"volume {result}",
        )


class DrillingMRRRule(EngineeringRule):
    """R-2305: Q = (π × D² / 4) × Vf."""
    rule_id = "R-2305"
    rule_version = "1.0.0"
    description = "Compute drilling MRR for solid circular drill."
    domain = "drilling.removal"
    required_inputs = ("diameter", "feed_rate")
    source_reference = "machining-ai Stage 3D drilling MRR"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = drilling.drilling_mrr(inputs["diameter"], inputs["feed_rate"])
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"mrr": result},
            summary=f"MRR {result}",
        )


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------

class DrillingFeedConsistencyRule(EngineeringRule):
    """R-2310: verify Vf = n × f consistency when all three are provided.

    Classification: PHYSICAL_CONSTRAINT.
    """
    rule_id = "R-2310"
    rule_version = "1.0.0"
    description = "Verify drilling feed-rate / spindle-speed / feed-per-rev consistency."
    domain = "drilling.feed.validation"
    required_inputs = ("feed_rate", "spindle_speed", "feed_per_rev")
    source_reference = "drilling kinematics: Vf = n × f"

    _TOLERANCE = Decimal("0.001")

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        vf: Quantity = inputs["feed_rate"]
        n: Quantity = inputs["spindle_speed"]
        f: Quantity = inputs["feed_per_rev"]

        try:
            expected_vf = feed_rate_from_rpm_feed_per_rev(n, f)
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)

        if expected_vf.value == Decimal("0") and vf.value == Decimal("0"):
            return success(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                summary="all zero — consistent",
            )

        if expected_vf.value == Decimal("0"):
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"expected Vf = 0 from n×f but got {vf.value} mm/min",
                ),
            )

        relative_error = abs(vf.value - expected_vf.value) / expected_vf.value
        if relative_error > self._TOLERANCE:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"feed rate inconsistency: given Vf = {vf.value} mm/min, "
                    f"computed n×f = {expected_vf.value} mm/min, "
                    f"relative error = {relative_error}",
                ),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary=f"Vf consistent within {self._TOLERANCE}",
        )


class EffectiveTravelNotLessThanDepthRule(EngineeringRule):
    """R-2311: effective travel must be >= hole depth.

    Classification: PHYSICAL_CONSTRAINT.
    If explicit allowances are provided, effective travel should
    never be less than hole depth.
    """
    rule_id = "R-2311"
    rule_version = "1.0.0"
    description = "Verify effective drilling travel is not less than hole depth."
    domain = "drilling.geometry.validation"
    required_inputs = ("hole_depth", "effective_travel")
    source_reference = "drilling geometry: travel >= depth"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        depth: Quantity = inputs["hole_depth"]
        travel: Quantity = inputs["effective_travel"]

        if depth.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(f"hole_depth must be in mm, got {depth.unit.value}"),
            )
        if travel.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(
                    f"effective_travel must be in mm, got {travel.unit.value}"
                ),
            )

        if travel.value < depth.value:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"effective_travel ({travel.value} mm) < hole_depth "
                    f"({depth.value} mm)",
                ),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary="effective_travel >= hole_depth",
        )


class DrillingZeroDepthRule(EngineeringRule):
    """R-2312: warn when hole depth is zero.

    Classification: PHYSICAL_CONSTRAINT.
    Zero depth means no material is removed.
    """
    rule_id = "R-2312"
    rule_version = "1.0.0"
    description = "Warn when hole depth is zero."
    domain = "drilling.geometry.validation"
    required_inputs = ("hole_depth",)
    source_reference = "drilling geometry: zero depth removes no material"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        depth: Quantity = inputs["hole_depth"]
        if depth.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(f"hole_depth must be in mm, got {depth.unit.value}"),
            )
        if depth.value == Decimal("0"):
            return warning(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                warnings=("hole_depth is zero; no material will be removed",),
                summary="zero depth warning",
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary="hole_depth > 0",
        )


class DrillingDepthToDiameterRatioRule(EngineeringRule):
    """R-2313: warn when depth/D > 10.

    Classification: ENGINEERING_POLICY_THRESHOLD.
    Deep-hole drilling (L/D > 10) typically requires special tooling,
    peck cycles, or through-spindle coolant.  This threshold is
    engineering policy, not a physical impossibility.
    """
    rule_id = "R-2313"
    rule_version = "1.0.0"
    description = "Warn when drilling depth-to-diameter ratio exceeds 10."
    domain = "drilling.geometry.validation"
    required_inputs = ("hole_depth", "diameter")
    source_reference = (
        "ENGINEERING_POLICY_THRESHOLD: L/D > 10 indicates deep-hole drilling"
    )

    _THRESHOLD = Decimal("10")

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        depth: Quantity = inputs["hole_depth"]
        dia: Quantity = inputs["diameter"]

        if depth.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(f"hole_depth must be in mm, got {depth.unit.value}"),
            )
        if dia.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(f"diameter must be in mm, got {dia.unit.value}"),
            )
        if dia.value <= 0:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(f"diameter must be positive, got {dia.value}"),
            )

        ratio = depth.value / dia.value
        if ratio > self._THRESHOLD:
            return warning(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                warnings=(
                    f"depth/diameter ratio = {ratio} exceeds policy "
                    f"threshold {self._THRESHOLD}; deep-hole drilling "
                    f"may require special tooling or peck cycles",
                ),
                outputs={"depth_diameter_ratio": Quantity.of(ratio, Unit.DIMENSIONLESS)},
                summary=f"L/D {ratio} exceeds policy threshold",
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"depth_diameter_ratio": Quantity.of(ratio, Unit.DIMENSIONLESS)},
            summary=f"L/D {ratio} within policy threshold",
        )


def foundational_drilling_rules() -> tuple[EngineeringRule, ...]:
    """Instantiate the Stage 3D drilling rules for registration."""
    return (
        EffectiveDrillingTravelRule(),
        DrillingMachiningTimeRule(),
        HoleCrossSectionalAreaRule(),
        CylindricalHoleVolumeRule(),
        DrillingMRRRule(),
        DrillingFeedConsistencyRule(),
        EffectiveTravelNotLessThanDepthRule(),
        DrillingZeroDepthRule(),
        DrillingDepthToDiameterRatioRule(),
    )
