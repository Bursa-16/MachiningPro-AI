"""EngineeringRule wrappers for deterministic milling calculations (Stage 3C).

Rule ID range: R-2201 onward.

Rule families:

  R-2201..R-2205  Milling-specific calculation rules (deterministic wrappers)
  R-2210..R-2214  Milling engineering validation rules (warn/reject checks)

Validation rules classify their thresholds as either PHYSICAL_CONSTRAINT
(derived from geometry/physics — e.g., ae cannot exceed D) or
ENGINEERING_POLICY_THRESHOLD (judgment-based limits that may be adjusted).
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from backend.core.rules.base import EngineeringRule
from backend.domain.result import EngineeringResult, failure, success, warning
from backend.domain.units import Quantity, Unit
from backend.machining import milling
from backend.machining.exceptions import MachiningMathError

__all__ = [
    # calculation rules
    "FeedPerRevFromToothFeedRule",
    "RadialEngagementRatioRule",
    "AxialEngagementRatioRule",
    "MillingMachiningTimeRule",
    "MillingMRRRule",
    # validation rules
    "RadialEngagementExceedsToolDiameterRule",
    "AxialEngagementSanityRule",
    "MillingFeedRateConsistencyRule",
    "MillingZeroEngagementRule",
    # collection
    "foundational_milling_rules",
]


def _fer(rule_id: str, version: str, exc: MachiningMathError) -> EngineeringResult:
    return failure(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=version,
        violations=(str(exc),),
    )


# ---------------------------------------------------------------------------
# Calculation rules (deterministic wrappers)
# ---------------------------------------------------------------------------

class FeedPerRevFromToothFeedRule(EngineeringRule):
    """R-2201: f_rev = z × fz."""
    rule_id = "R-2201"
    rule_version = "1.0.0"
    description = "Compute milling feed per revolution from tooth count and feed per tooth."
    domain = "milling.feed"
    required_inputs = ("tooth_count", "feed_per_tooth")
    source_reference = "machining-ai Stage 3C milling feed"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = milling.feed_per_rev_from_tooth_feed(
                inputs["tooth_count"], inputs["feed_per_tooth"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"feed_per_rev": result},
            summary=f"feed_per_rev {result}",
        )


class RadialEngagementRatioRule(EngineeringRule):
    """R-2202: ae_ratio = ae / D."""
    rule_id = "R-2202"
    rule_version = "1.0.0"
    description = "Compute radial engagement ratio for milling."
    domain = "milling.engagement"
    required_inputs = ("radial_width", "tool_diameter")
    source_reference = "machining-ai Stage 3C milling engagement"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = milling.radial_engagement_ratio(
                inputs["radial_width"], inputs["tool_diameter"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"radial_engagement_ratio": result},
            summary=f"ae/D {result}",
        )


class AxialEngagementRatioRule(EngineeringRule):
    """R-2203: ap_ratio = ap / D."""
    rule_id = "R-2203"
    rule_version = "1.0.0"
    description = "Compute axial engagement ratio for milling."
    domain = "milling.engagement"
    required_inputs = ("axial_depth", "tool_diameter")
    source_reference = "machining-ai Stage 3C milling engagement"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = milling.axial_engagement_ratio(
                inputs["axial_depth"], inputs["tool_diameter"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"axial_engagement_ratio": result},
            summary=f"ap/D {result}",
        )


class MillingMachiningTimeRule(EngineeringRule):
    """R-2204: t = L / (n × z × fz)."""
    rule_id = "R-2204"
    rule_version = "1.0.0"
    description = "Compute milling machining time from spindle speed, tooth feed and distance."
    domain = "milling.time"
    required_inputs = ("spindle_speed", "tooth_count", "feed_per_tooth", "cutting_distance")
    source_reference = "machining-ai Stage 3C milling time (composed from Stage 3A)"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = milling.milling_machining_time(
                inputs["spindle_speed"],
                inputs["tooth_count"],
                inputs["feed_per_tooth"],
                inputs["cutting_distance"],
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


class MillingMRRRule(EngineeringRule):
    """R-2205: MRR = ap × ae × (n × z × fz)."""
    rule_id = "R-2205"
    rule_version = "1.0.0"
    description = "Compute milling MRR from engagement and milling feed parameters."
    domain = "milling.removal"
    required_inputs = (
        "axial_depth", "radial_width",
        "spindle_speed", "tooth_count", "feed_per_tooth",
    )
    source_reference = "machining-ai Stage 3C milling MRR (composed from Stage 3A)"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = milling.milling_mrr(
                inputs["axial_depth"],
                inputs["radial_width"],
                inputs["spindle_speed"],
                inputs["tooth_count"],
                inputs["feed_per_tooth"],
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


# ---------------------------------------------------------------------------
# Validation rules (warn / reject)
# ---------------------------------------------------------------------------

class RadialEngagementExceedsToolDiameterRule(EngineeringRule):
    """R-2210: ae > D is physically impossible for a cylindrical end mill.

    Classification: PHYSICAL_CONSTRAINT.
    The radial width of cut cannot exceed the tool diameter.
    """
    rule_id = "R-2210"
    rule_version = "1.0.0"
    description = "Reject radial engagement exceeding tool diameter."
    domain = "milling.engagement.validation"
    required_inputs = ("radial_width", "tool_diameter")
    source_reference = "milling geometry: ae cannot exceed D for cylindrical tools"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        ae: Quantity = inputs["radial_width"]
        d: Quantity = inputs["tool_diameter"]
        try:
            ratio = milling.radial_engagement_ratio(ae, d)
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)

        if ratio.value > Decimal("1"):
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"radial_width ({ae.value} mm) exceeds tool_diameter "
                    f"({d.value} mm); ae/D = {ratio.value}",
                ),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"radial_engagement_ratio": ratio},
            summary=f"ae/D {ratio.value} within physical limit",
        )


class AxialEngagementSanityRule(EngineeringRule):
    """R-2211: warn when ap/D > 2.0.

    Classification: ENGINEERING_POLICY_THRESHOLD.
    An axial depth exceeding 2× the tool diameter is unusual for standard
    end mills and may indicate a data-entry error or a specialty operation
    (e.g. long-reach). Threshold is configurable engineering policy, not
    a physical impossibility.
    """
    rule_id = "R-2211"
    rule_version = "1.0.0"
    description = "Warn when axial engagement ratio exceeds 2.0× tool diameter."
    domain = "milling.engagement.validation"
    required_inputs = ("axial_depth", "tool_diameter")
    source_reference = (
        "ENGINEERING_POLICY_THRESHOLD: ap/D > 2.0 unusual for standard end mills"
    )

    _THRESHOLD = Decimal("2")

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        ap: Quantity = inputs["axial_depth"]
        d: Quantity = inputs["tool_diameter"]
        try:
            ratio = milling.axial_engagement_ratio(ap, d)
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)

        if ratio.value > self._THRESHOLD:
            return warning(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                warnings=(
                    f"axial engagement ratio ap/D = {ratio.value} exceeds "
                    f"policy threshold {self._THRESHOLD}; verify depth of cut",
                ),
                outputs={"axial_engagement_ratio": ratio},
                summary=f"ap/D {ratio.value} exceeds policy threshold",
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"axial_engagement_ratio": ratio},
            summary=f"ap/D {ratio.value} within policy threshold",
        )


class MillingFeedRateConsistencyRule(EngineeringRule):
    """R-2212: verify Vf = n × z × fz consistency when all four are provided.

    Classification: PHYSICAL_CONSTRAINT.
    If all four parameters are explicitly given, they must be
    mathematically consistent within a small tolerance.
    """
    rule_id = "R-2212"
    rule_version = "1.0.0"
    description = "Verify feed-rate / spindle-speed / tooth-count / fz consistency."
    domain = "milling.feed.validation"
    required_inputs = ("feed_rate", "spindle_speed", "tooth_count", "feed_per_tooth")
    source_reference = "milling kinematics: Vf = n × z × fz"

    _TOLERANCE = Decimal("0.001")  # 0.1% relative tolerance

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        vf: Quantity = inputs["feed_rate"]
        n: Quantity = inputs["spindle_speed"]
        z: int = inputs["tooth_count"]
        fz: Quantity = inputs["feed_per_tooth"]

        from backend.machining.formulas import feed_rate_from_rpm_tooth_feed

        try:
            expected_vf = feed_rate_from_rpm_tooth_feed(n, z, fz)
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
                    f"expected Vf = 0 from n×z×fz but got {vf.value} mm/min",
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
                    f"computed n×z×fz = {expected_vf.value} mm/min, "
                    f"relative error = {relative_error}",
                ),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary=f"Vf consistent within {self._TOLERANCE}",
        )


class MillingZeroEngagementRule(EngineeringRule):
    """R-2213: warn when both ap and ae are zero.

    Classification: PHYSICAL_CONSTRAINT.
    Zero engagement in both axes means no material is removed.
    This is likely a data-entry error.
    """
    rule_id = "R-2213"
    rule_version = "1.0.0"
    description = "Warn when both axial depth and radial width are zero."
    domain = "milling.engagement.validation"
    required_inputs = ("axial_depth", "radial_width")
    source_reference = "milling geometry: zero engagement removes no material"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        ap: Quantity = inputs["axial_depth"]
        aw: Quantity = inputs["radial_width"]

        # Validate units
        if ap.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(f"axial_depth must be in mm, got {ap.unit.value}"),
            )
        if aw.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(f"radial_width must be in mm, got {aw.unit.value}"),
            )

        if ap.value == Decimal("0") and aw.value == Decimal("0"):
            return warning(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                warnings=(
                    "both axial_depth and radial_width are zero; "
                    "no material will be removed",
                ),
                summary="zero engagement warning",
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary="engagement non-zero",
        )


def foundational_milling_rules() -> tuple[EngineeringRule, ...]:
    """Instantiate the Stage 3C milling rules for registration."""
    return (
        FeedPerRevFromToothFeedRule(),
        RadialEngagementRatioRule(),
        AxialEngagementRatioRule(),
        MillingMachiningTimeRule(),
        MillingMRRRule(),
        RadialEngagementExceedsToolDiameterRule(),
        AxialEngagementSanityRule(),
        MillingFeedRateConsistencyRule(),
        MillingZeroEngagementRule(),
    )
