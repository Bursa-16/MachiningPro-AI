"""EngineeringRule wrappers for deterministic machining formulas (Stage 3A).

Each rule wraps a pure function from :mod:`backend.machining.formulas` in the
:class:`~backend.core.rules.base.EngineeringRule` interface so calculations
can participate in the rule registry, carry provenance, and return
:class:`~backend.domain.result.EngineeringResult` envelopes.

Formula-level exceptions (:class:`~backend.machining.exceptions.MachiningMathError`)
are caught and converted to ``FAIL`` results so the rule contract is honored.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.core.rules.base import EngineeringRule
from backend.domain.result import EngineeringResult, failure, success
from backend.domain.units import Quantity, Unit
from backend.machining import formulas
from backend.machining.exceptions import MachiningMathError

__all__ = [
    "SpindleSpeedFromCuttingSpeedRule",
    "CuttingSpeedFromSpindleSpeedRule",
    "FeedRateFromRpmFeedPerRevRule",
    "FeedPerRevFromFeedRateRule",
    "SpindleSpeedFromFeedRateFeedPerRevRule",
    "FeedRateFromRpmToothFeedRule",
    "FeedPerToothFromFeedRateRule",
    "SpindleSpeedFromFeedRateToothFeedRule",
    "ToothCountFromFeedRateRule",
    "MillingMaterialRemovalRateRule",
    "MachiningTimeRule",
    "TorqueFromPowerRule",
    "PowerFromTorqueRule",
    "foundational_machining_rules",
]


def _formula_error_result(rule_id: str, version: str, exc: MachiningMathError) -> EngineeringResult:
    return failure(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=version,
        violations=(str(exc),),
    )


class SpindleSpeedFromCuttingSpeedRule(EngineeringRule):
    """R-2001: n = (1000 * Vc) / (pi * D)."""
    rule_id = "R-2001"
    rule_version = "1.0.0"
    description = "Compute spindle speed from cutting speed and diameter."
    domain = "machining.speed"
    required_inputs = ("cutting_speed", "diameter")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.spindle_speed_from_cutting_speed(
                inputs["cutting_speed"], inputs["diameter"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"spindle_speed": result},
            summary=f"spindle speed {result}",
        )


class CuttingSpeedFromSpindleSpeedRule(EngineeringRule):
    """R-2002: Vc = (pi * D * n) / 1000."""
    rule_id = "R-2002"
    rule_version = "1.0.0"
    description = "Compute cutting speed from spindle speed and diameter."
    domain = "machining.speed"
    required_inputs = ("spindle_speed", "diameter")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.cutting_speed_from_spindle_speed(
                inputs["spindle_speed"], inputs["diameter"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"cutting_speed": result},
            summary=f"cutting speed {result}",
        )


class FeedRateFromRpmFeedPerRevRule(EngineeringRule):
    """R-2003: fr = n * f."""
    rule_id = "R-2003"
    rule_version = "1.0.0"
    description = "Compute feed rate from spindle speed and feed per revolution."
    domain = "machining.feed"
    required_inputs = ("spindle_speed", "feed_per_rev")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.feed_rate_from_rpm_feed_per_rev(
                inputs["spindle_speed"], inputs["feed_per_rev"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"feed_rate": result},
            summary=f"feed rate {result}",
        )


class FeedPerRevFromFeedRateRule(EngineeringRule):
    """R-2004: f = fr / n."""
    rule_id = "R-2004"
    rule_version = "1.0.0"
    description = "Compute feed per revolution from feed rate and spindle speed."
    domain = "machining.feed"
    required_inputs = ("feed_rate", "spindle_speed")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.feed_per_rev_from_feed_rate(
                inputs["feed_rate"], inputs["spindle_speed"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"feed_per_rev": result},
            summary=f"feed per revolution {result}",
        )


class SpindleSpeedFromFeedRateFeedPerRevRule(EngineeringRule):
    """R-2005: n = fr / f."""
    rule_id = "R-2005"
    rule_version = "1.0.0"
    description = "Compute spindle speed from feed rate and feed per revolution."
    domain = "machining.feed"
    required_inputs = ("feed_rate", "feed_per_rev")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.spindle_speed_from_feed_rate_feed_per_rev(
                inputs["feed_rate"], inputs["feed_per_rev"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"spindle_speed": result},
            summary=f"spindle speed {result}",
        )


class FeedRateFromRpmToothFeedRule(EngineeringRule):
    """R-2006: fr = n * z * fz."""
    rule_id = "R-2006"
    rule_version = "1.0.0"
    description = "Compute milling feed rate from spindle speed, tooth count and feed per tooth."
    domain = "machining.feed.milling"
    required_inputs = ("spindle_speed", "tooth_count", "feed_per_tooth")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.feed_rate_from_rpm_tooth_feed(
                inputs["spindle_speed"], inputs["tooth_count"], inputs["feed_per_tooth"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"feed_rate": result},
            summary=f"feed rate {result}",
        )


class FeedPerToothFromFeedRateRule(EngineeringRule):
    """R-2007: fz = fr / (n * z)."""
    rule_id = "R-2007"
    rule_version = "1.0.0"
    description = "Compute feed per tooth from feed rate, spindle speed and tooth count."
    domain = "machining.feed.milling"
    required_inputs = ("feed_rate", "spindle_speed", "tooth_count")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.feed_per_tooth_from_feed_rate(
                inputs["feed_rate"], inputs["spindle_speed"], inputs["tooth_count"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"feed_per_tooth": result},
            summary=f"feed per tooth {result}",
        )


class SpindleSpeedFromFeedRateToothFeedRule(EngineeringRule):
    """R-2008: n = fr / (z * fz)."""
    rule_id = "R-2008"
    rule_version = "1.0.0"
    description = "Compute spindle speed from feed rate, tooth count and feed per tooth."
    domain = "machining.feed.milling"
    required_inputs = ("feed_rate", "tooth_count", "feed_per_tooth")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.spindle_speed_from_feed_rate_tooth_feed(
                inputs["feed_rate"], inputs["tooth_count"], inputs["feed_per_tooth"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"spindle_speed": result},
            summary=f"spindle speed {result}",
        )


class ToothCountFromFeedRateRule(EngineeringRule):
    """R-2009: z = fr / (n * fz)."""
    rule_id = "R-2009"
    rule_version = "1.0.0"
    description = "Compute tooth count from feed rate, spindle speed and feed per tooth."
    domain = "machining.feed.milling"
    required_inputs = ("feed_rate", "spindle_speed", "feed_per_tooth")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.tooth_count_from_feed_rate(
                inputs["feed_rate"], inputs["spindle_speed"], inputs["feed_per_tooth"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"tooth_count": Quantity.of(result, Unit.DIMENSIONLESS)},
            summary=f"tooth_count {result}",
        )


class MillingMaterialRemovalRateRule(EngineeringRule):
    """R-2010: MRR = ap * ae * fr."""
    rule_id = "R-2010"
    rule_version = "1.0.0"
    description = "Compute milling material removal rate."
    domain = "machining.removal"
    required_inputs = ("axial_depth", "radial_width", "feed_rate")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.milling_material_removal_rate(
                inputs["axial_depth"], inputs["radial_width"], inputs["feed_rate"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"mrr": result},
            summary=f"MRR {result}",
        )


class MachiningTimeRule(EngineeringRule):
    """R-2011: t = L / fr."""
    rule_id = "R-2011"
    rule_version = "1.0.0"
    description = "Compute machining time from travel distance and feed rate."
    domain = "machining.time"
    required_inputs = ("distance", "feed_rate")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.machining_time_from_distance_feed_rate(
                inputs["distance"], inputs["feed_rate"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"time": result},
            summary=f"time {result}",
        )


class TorqueFromPowerRule(EngineeringRule):
    """R-2012: T = (P * 60000) / (2 * pi * n)."""
    rule_id = "R-2012"
    rule_version = "1.0.0"
    description = "Compute torque from power and spindle speed."
    domain = "machining.power"
    required_inputs = ("power", "spindle_speed")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.torque_from_power_rpm(
                inputs["power"], inputs["spindle_speed"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"torque": result},
            summary=f"torque {result}",
        )


class PowerFromTorqueRule(EngineeringRule):
    """R-2013: P = (2 * pi * n * T) / 60000."""
    rule_id = "R-2013"
    rule_version = "1.0.0"
    description = "Compute power from torque and spindle speed."
    domain = "machining.power"
    required_inputs = ("torque", "spindle_speed")
    source_reference = "machining-ai Stage 3A deterministic formula"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = formulas.power_from_torque_rpm(
                inputs["torque"], inputs["spindle_speed"]
            )
        except MachiningMathError as exc:
            return _formula_error_result(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"power": result},
            summary=f"power {result}",
        )


def foundational_machining_rules() -> tuple[EngineeringRule, ...]:
    """Instantiate the Stage 3A machining-math rules for registration."""
    return (
        SpindleSpeedFromCuttingSpeedRule(),
        CuttingSpeedFromSpindleSpeedRule(),
        FeedRateFromRpmFeedPerRevRule(),
        FeedPerRevFromFeedRateRule(),
        SpindleSpeedFromFeedRateFeedPerRevRule(),
        FeedRateFromRpmToothFeedRule(),
        FeedPerToothFromFeedRateRule(),
        SpindleSpeedFromFeedRateToothFeedRule(),
        ToothCountFromFeedRateRule(),
        MillingMaterialRemovalRateRule(),
        MachiningTimeRule(),
        TorqueFromPowerRule(),
        PowerFromTorqueRule(),
    )
