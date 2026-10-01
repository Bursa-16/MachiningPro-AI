"""EngineeringRule wrappers for deterministic turning calculations (Stage 3B).

Rule ID range: R-2101 onward.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.core.rules.base import EngineeringRule
from backend.domain.result import EngineeringResult, failure, success
from backend.domain.units import Quantity, Unit
from backend.machining import turning
from backend.machining.exceptions import MachiningMathError
from backend.machining.formulas import (
    feed_rate_from_rpm_feed_per_rev,
    machining_time_from_distance_feed_rate,
)

__all__ = [
    "ExternalRadialStockRule",
    "ExternalFinalDiameterRule",
    "BoringRadialStockRule",
    "BoringFinalDiameterRule",
    "PassCountRule",
    "EqualPassDepthRule",
    "ExternalRemovedVolumeRule",
    "BoringRemovedVolumeRule",
    "LongitudinalTurningTimeRule",
    "TurningMRRFromVolumeTimeRule",
    "TurningDirectMRRRule",
    "FacingTravelRule",
    "FacingTimeRule",
    "FacingRemovedVolumeRule",
    "foundational_turning_rules",
]


def _fer(rule_id: str, version: str, exc: MachiningMathError) -> EngineeringResult:
    return failure(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=version,
        violations=(str(exc),),
    )


class ExternalRadialStockRule(EngineeringRule):
    """R-2101: radial_stock = (D0 - D1) / 2."""
    rule_id = "R-2101"
    rule_version = "1.0.0"
    description = "Compute radial stock removed in external turning."
    domain = "turning.external.geometry"
    required_inputs = ("initial_diameter", "final_diameter")
    source_reference = "machining-ai Stage 3B turning geometry"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.radial_stock_external(
                inputs["initial_diameter"], inputs["final_diameter"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"radial_stock": result},
            summary=f"radial_stock {result}",
        )


class ExternalFinalDiameterRule(EngineeringRule):
    """R-2102: D1 = D0 - 2 * ap."""
    rule_id = "R-2102"
    rule_version = "1.0.0"
    description = "Compute final diameter after external turning."
    domain = "turning.external.geometry"
    required_inputs = ("initial_diameter", "radial_depth")
    source_reference = "machining-ai Stage 3B turning geometry"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.final_diameter_external(
                inputs["initial_diameter"], inputs["radial_depth"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"final_diameter": result},
            summary=f"final_diameter {result}",
        )


class BoringRadialStockRule(EngineeringRule):
    """R-2103: radial_stock = (D1 - D0) / 2."""
    rule_id = "R-2103"
    rule_version = "1.0.0"
    description = "Compute radial stock removed in boring."
    domain = "turning.boring.geometry"
    required_inputs = ("initial_diameter", "final_diameter")
    source_reference = "machining-ai Stage 3B turning geometry"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.radial_stock_boring(
                inputs["initial_diameter"], inputs["final_diameter"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"radial_stock": result},
            summary=f"radial_stock {result}",
        )


class BoringFinalDiameterRule(EngineeringRule):
    """R-2104: D1 = D0 + 2 * ap."""
    rule_id = "R-2104"
    rule_version = "1.0.0"
    description = "Compute final bore diameter after boring."
    domain = "turning.boring.geometry"
    required_inputs = ("initial_diameter", "radial_depth")
    source_reference = "machining-ai Stage 3B turning geometry"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.final_diameter_boring(
                inputs["initial_diameter"], inputs["radial_depth"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"final_diameter": result},
            summary=f"final_diameter {result}",
        )


class PassCountRule(EngineeringRule):
    """R-2105: pass_count = ceil(stock / max_depth)."""
    rule_id = "R-2105"
    rule_version = "1.0.0"
    description = "Compute number of turning passes from stock and max depth."
    domain = "turning.external.passes"
    required_inputs = ("total_radial_stock", "max_radial_depth_per_pass")
    source_reference = "machining-ai Stage 3B turning passes"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.pass_count(
                inputs["total_radial_stock"],
                inputs["max_radial_depth_per_pass"],
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"pass_count": Quantity.of(result, Unit.DIMENSIONLESS)},
            summary=f"pass_count {result}",
        )


class EqualPassDepthRule(EngineeringRule):
    """R-2106: equal_pass_depth = stock / pass_count."""
    rule_id = "R-2106"
    rule_version = "1.0.0"
    description = "Compute actual depth per pass when stock is divided evenly."
    domain = "turning.external.passes"
    required_inputs = ("total_radial_stock", "pass_count")
    source_reference = "machining-ai Stage 3B turning passes"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.equal_pass_depth(
                inputs["total_radial_stock"], inputs["pass_count"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"pass_depth": result},
            summary=f"pass_depth {result}",
        )


class ExternalRemovedVolumeRule(EngineeringRule):
    """R-2107: V = (pi/4)*(D0^2 - D1^2)*L."""
    rule_id = "R-2107"
    rule_version = "1.0.0"
    description = "Compute removed volume in external turning."
    domain = "turning.external.volume"
    required_inputs = ("initial_diameter", "final_diameter", "axial_length")
    source_reference = "machining-ai Stage 3B turning volume"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.removed_volume_external(
                inputs["initial_diameter"],
                inputs["final_diameter"],
                inputs["axial_length"],
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"removed_volume": result},
            summary=f"removed_volume {result}",
        )


class BoringRemovedVolumeRule(EngineeringRule):
    """R-2108: V = (pi/4)*(D1^2 - D0^2)*L."""
    rule_id = "R-2108"
    rule_version = "1.0.0"
    description = "Compute removed volume in boring."
    domain = "turning.boring.volume"
    required_inputs = ("initial_diameter", "final_diameter", "axial_length")
    source_reference = "machining-ai Stage 3B turning volume"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.removed_volume_boring(
                inputs["initial_diameter"],
                inputs["final_diameter"],
                inputs["axial_length"],
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"removed_volume": result},
            summary=f"removed_volume {result}",
        )


class LongitudinalTurningTimeRule(EngineeringRule):
    """R-2109: time = effective_travel / feed_rate."""
    rule_id = "R-2109"
    rule_version = "1.0.0"
    description = "Compute longitudinal turning time."
    domain = "turning.external.time"
    required_inputs = ("spindle_speed", "feed_per_rev", "machining_length")
    source_reference = "machining-ai Stage 3B turning time"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.longitudinal_turning_time(
                inputs["spindle_speed"],
                inputs["feed_per_rev"],
                inputs["machining_length"],
                inputs.get("approach_allowance"),
                inputs.get("overtravel_allowance"),
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


class TurningMRRFromVolumeTimeRule(EngineeringRule):
    """R-2110: MRR = removed_volume / time."""
    rule_id = "R-2110"
    rule_version = "1.0.0"
    description = "Compute average turning MRR from volume and time."
    domain = "turning.external.mrr"
    required_inputs = ("removed_volume", "machining_time")
    source_reference = "machining-ai Stage 3B turning MRR"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.turning_mrr_from_volume_time(
                inputs["removed_volume"], inputs["machining_time"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"mrr": result},
            summary=f"mrr {result}",
        )


class TurningDirectMRRRule(EngineeringRule):
    """R-2111: MRR = (pi/4)*(D0^2-D1^2) * feed_rate."""
    rule_id = "R-2111"
    rule_version = "1.0.0"
    description = "Compute direct geometric average turning MRR."
    domain = "turning.external.mrr"
    required_inputs = ("initial_diameter", "final_diameter", "feed_rate")
    source_reference = "machining-ai Stage 3B turning MRR"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.turning_mrr_direct(
                inputs["initial_diameter"],
                inputs["final_diameter"],
                inputs["feed_rate"],
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"mrr": result},
            summary=f"mrr {result}",
        )


class FacingTravelRule(EngineeringRule):
    """R-2112: effective radial facing travel with explicit allowances."""
    rule_id = "R-2112"
    rule_version = "1.0.0"
    description = "Compute effective radial facing travel."
    domain = "turning.facing.geometry"
    required_inputs = ("outer_diameter", "inner_diameter")
    source_reference = "machining-ai Stage 3B facing geometry"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.facing_travel(
                inputs["outer_diameter"],
                inputs["inner_diameter"],
                inputs.get("approach_allowance"),
                inputs.get("overtravel_allowance"),
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"facing_travel": result},
            summary=f"facing_travel {result}",
        )


class FacingTimeRule(EngineeringRule):
    """R-2113: facing_time = radial_travel / feed_rate."""
    rule_id = "R-2113"
    rule_version = "1.0.0"
    description = "Compute facing time from rpm, feed/rev and radial travel."
    domain = "turning.facing.time"
    required_inputs = ("spindle_speed", "feed_per_rev", "radial_travel")
    source_reference = "machining-ai Stage 3B facing time"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            fr = feed_rate_from_rpm_feed_per_rev(
                inputs["spindle_speed"], inputs["feed_per_rev"]
            )
            result = machining_time_from_distance_feed_rate(
                inputs["radial_travel"], fr
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


class FacingRemovedVolumeRule(EngineeringRule):
    """R-2114: V = (pi/4)*(D_outer^2 - D_inner^2)*face_depth."""
    rule_id = "R-2114"
    rule_version = "1.0.0"
    description = "Compute removed volume in facing."
    domain = "turning.facing.volume"
    required_inputs = ("outer_diameter", "inner_diameter", "face_depth")
    source_reference = "machining-ai Stage 3B facing volume"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = turning.facing_removed_volume(
                inputs["outer_diameter"],
                inputs["inner_diameter"],
                inputs["face_depth"],
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"removed_volume": result},
            summary=f"removed_volume {result}",
        )


def foundational_turning_rules() -> tuple[EngineeringRule, ...]:
    """Instantiate the Stage 3B turning rules for registration."""
    return (
        ExternalRadialStockRule(),
        ExternalFinalDiameterRule(),
        BoringRadialStockRule(),
        BoringFinalDiameterRule(),
        PassCountRule(),
        EqualPassDepthRule(),
        ExternalRemovedVolumeRule(),
        BoringRemovedVolumeRule(),
        LongitudinalTurningTimeRule(),
        TurningMRRFromVolumeTimeRule(),
        TurningDirectMRRRule(),
        FacingTravelRule(),
        FacingTimeRule(),
        FacingRemovedVolumeRule(),
    )
