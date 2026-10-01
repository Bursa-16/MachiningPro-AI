"""EngineeringRule wrappers for deterministic hole finishing (Stage 3F).

Rule ID range: R-2501 onward.

Rule families:
  R-2501..R-2505  Calculation rules
  R-2510..R-2514  Validation rules (all PHYSICAL_CONSTRAINT)

Zero arbitrary policy thresholds.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from backend.core.rules.base import EngineeringRule
from backend.domain.result import EngineeringResult, failure, success, warning
from backend.domain.units import Quantity, Unit
from backend.machining import hole_finishing
from backend.machining.exceptions import MachiningMathError

__all__ = [
    "DiametralStockRule",
    "RadialStockRule",
    "AnnularVolumeRule",
    "HoleFinishingMRRRule",
    "HoleFinishingMachiningTimeRule",
    "FinalDiameterNotLessThanInitialRule",
    "DiametralRadialConsistencyRule",
    "EffectiveTravelNotLessThanLengthRule",
    "ZeroStockRemovalRule",
    "MRRConsistencyRule",
    "foundational_hole_finishing_rules",
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

class DiametralStockRule(EngineeringRule):
    """R-2501: diametral_stock = D_final - D_initial."""
    rule_id = "R-2501"
    rule_version = "1.0.0"
    description = "Compute diametral stock removal for hole finishing."
    domain = "hole_finishing.stock"
    required_inputs = ("initial_diameter", "final_diameter")
    source_reference = "machining-ai Stage 3F hole finishing geometry"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = hole_finishing.diametral_stock(
                inputs["initial_diameter"], inputs["final_diameter"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"diametral_stock": result},
            summary=f"diametral_stock {result}",
        )


class RadialStockRule(EngineeringRule):
    """R-2502: radial_stock = (D_final - D_initial) / 2."""
    rule_id = "R-2502"
    rule_version = "1.0.0"
    description = "Compute radial stock removal for hole finishing."
    domain = "hole_finishing.stock"
    required_inputs = ("initial_diameter", "final_diameter")
    source_reference = "machining-ai Stage 3F hole finishing geometry"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = hole_finishing.radial_stock(
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


class AnnularVolumeRule(EngineeringRule):
    """R-2503: V = π/4 × (D_f² - D_i²) × L."""
    rule_id = "R-2503"
    rule_version = "1.0.0"
    description = "Compute annular volume removed in hole finishing."
    domain = "hole_finishing.volume"
    required_inputs = ("initial_diameter", "final_diameter", "length")
    source_reference = "machining-ai Stage 3F hole finishing volume"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = hole_finishing.annular_volume(
                inputs["initial_diameter"], inputs["final_diameter"],
                inputs["length"],
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


class HoleFinishingMRRRule(EngineeringRule):
    """R-2504: Q = π/4 × (D_f² - D_i²) × Vf."""
    rule_id = "R-2504"
    rule_version = "1.0.0"
    description = "Compute hole-finishing MRR."
    domain = "hole_finishing.removal"
    required_inputs = ("initial_diameter", "final_diameter", "feed_rate")
    source_reference = "machining-ai Stage 3F hole finishing MRR"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = hole_finishing.hole_finishing_mrr(
                inputs["initial_diameter"], inputs["final_diameter"],
                inputs["feed_rate"],
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"mrr": result},
            summary=f"MRR {result}",
        )


class HoleFinishingMachiningTimeRule(EngineeringRule):
    """R-2505: t = L_eff / (n × f)."""
    rule_id = "R-2505"
    rule_version = "1.0.0"
    description = "Compute hole-finishing machining time."
    domain = "hole_finishing.time"
    required_inputs = ("spindle_speed", "feed_per_rev", "operation_length")
    source_reference = "machining-ai Stage 3F hole finishing time (composed from 3A)"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = hole_finishing.hole_finishing_machining_time(
                inputs["spindle_speed"], inputs["feed_per_rev"],
                inputs["operation_length"],
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


# ---------------------------------------------------------------------------
# Validation rules (all PHYSICAL_CONSTRAINT)
# ---------------------------------------------------------------------------

class FinalDiameterNotLessThanInitialRule(EngineeringRule):
    """R-2510: D_final >= D_initial.

    Classification: PHYSICAL_CONSTRAINT.
    """
    rule_id = "R-2510"
    rule_version = "1.0.0"
    description = "Reject final diameter less than initial diameter."
    domain = "hole_finishing.stock.validation"
    required_inputs = ("initial_diameter", "final_diameter")
    source_reference = "hole finishing geometry: enlargement only"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        d_i: Quantity = inputs["initial_diameter"]
        d_f: Quantity = inputs["final_diameter"]
        if d_i.unit is not Unit.MM or d_f.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError("diameters must be in mm"),
            )
        if d_f.value < d_i.value:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"final_diameter ({d_f.value}) < initial_diameter ({d_i.value})",
                ),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary="D_final >= D_initial",
        )


class DiametralRadialConsistencyRule(EngineeringRule):
    """R-2511: diametral_stock == 2 × radial_stock.

    Classification: PHYSICAL_CONSTRAINT.
    """
    rule_id = "R-2511"
    rule_version = "1.0.0"
    description = "Verify diametral stock equals twice radial stock."
    domain = "hole_finishing.stock.validation"
    required_inputs = ("diametral_stock", "radial_stock")
    source_reference = "hole finishing geometry: diametral = 2 × radial"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        dia: Quantity = inputs["diametral_stock"]
        rad: Quantity = inputs["radial_stock"]
        if dia.unit is not Unit.MM or rad.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError("stock values must be in mm"),
            )
        expected = rad.value * Decimal("2")
        if dia.value != expected:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"diametral_stock ({dia.value}) != 2 × radial_stock "
                    f"({rad.value}); expected {expected}",
                ),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary="diametral == 2 × radial",
        )


class EffectiveTravelNotLessThanLengthRule(EngineeringRule):
    """R-2512: effective_travel >= operation_length.

    Classification: PHYSICAL_CONSTRAINT.
    """
    rule_id = "R-2512"
    rule_version = "1.0.0"
    description = "Verify effective travel is not less than operation length."
    domain = "hole_finishing.geometry.validation"
    required_inputs = ("operation_length", "effective_travel")
    source_reference = "hole finishing geometry: travel >= length"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        length: Quantity = inputs["operation_length"]
        travel: Quantity = inputs["effective_travel"]
        if length.unit is not Unit.MM or travel.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError("length and travel must be in mm"),
            )
        if travel.value < length.value:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"effective_travel ({travel.value}) < "
                    f"operation_length ({length.value})",
                ),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary="travel >= length",
        )


class ZeroStockRemovalRule(EngineeringRule):
    """R-2513: warn when D_initial == D_final (zero stock).

    Classification: PHYSICAL_CONSTRAINT.
    """
    rule_id = "R-2513"
    rule_version = "1.0.0"
    description = "Warn when initial and final diameters are equal."
    domain = "hole_finishing.stock.validation"
    required_inputs = ("initial_diameter", "final_diameter")
    source_reference = "hole finishing geometry: zero stock removes no material"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        d_i: Quantity = inputs["initial_diameter"]
        d_f: Quantity = inputs["final_diameter"]
        if d_i.unit is not Unit.MM or d_f.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError("diameters must be in mm"),
            )
        if d_i.value == d_f.value:
            return warning(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                warnings=(
                    f"initial_diameter == final_diameter ({d_i.value} mm); "
                    "no material will be removed",
                ),
                summary="zero stock warning",
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary="stock > 0",
        )


class MRRConsistencyRule(EngineeringRule):
    """R-2514: MRR should equal annular_area × Vf.

    Classification: PHYSICAL_CONSTRAINT.
    """
    rule_id = "R-2514"
    rule_version = "1.0.0"
    description = "Verify MRR consistency with annular geometry and feed rate."
    domain = "hole_finishing.removal.validation"
    required_inputs = ("initial_diameter", "final_diameter", "feed_rate", "mrr")
    source_reference = "hole finishing geometry: Q = A_annular × Vf"

    _TOLERANCE = Decimal("0.001")

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        mrr_given: Quantity = inputs["mrr"]
        try:
            mrr_expected = hole_finishing.hole_finishing_mrr(
                inputs["initial_diameter"], inputs["final_diameter"],
                inputs["feed_rate"],
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)

        if mrr_expected.value == Decimal("0") and mrr_given.value == Decimal("0"):
            return success(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                summary="both zero — consistent",
            )
        if mrr_expected.value == Decimal("0"):
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"expected MRR = 0 but got {mrr_given.value}",
                ),
            )
        rel = abs(mrr_given.value - mrr_expected.value) / mrr_expected.value
        if rel > self._TOLERANCE:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"MRR inconsistency: given {mrr_given.value}, "
                    f"expected {mrr_expected.value}, "
                    f"relative error {rel}",
                ),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary=f"MRR consistent within {self._TOLERANCE}",
        )


def foundational_hole_finishing_rules() -> tuple[EngineeringRule, ...]:
    """Instantiate the Stage 3F hole finishing rules for registration."""
    return (
        DiametralStockRule(),
        RadialStockRule(),
        AnnularVolumeRule(),
        HoleFinishingMRRRule(),
        HoleFinishingMachiningTimeRule(),
        FinalDiameterNotLessThanInitialRule(),
        DiametralRadialConsistencyRule(),
        EffectiveTravelNotLessThanLengthRule(),
        ZeroStockRemovalRule(),
        MRRConsistencyRule(),
    )
