"""EngineeringRule wrappers for DFM / process-feasibility checks (Stage 3I).

Rule ID range: R-2701 – R-2712.

Each rule wraps a pure function from :mod:`backend.dfm.validation` in the
:class:`~backend.core.rules.base.EngineeringRule` interface, consistent
with the pattern established in Stages 3A–3H.

Missing inputs produce INSUFFICIENT_DATA via the base ``evaluate()`` method.
Validation errors produce FAIL results.

Required inputs per rule
------------------------
R-2701  feature, tool
R-2702  feature, tool
R-2703  feature, tool
R-2704  feature, tool
R-2705  feature, operation_type
R-2706  feature  [, explicit_limit]
R-2710  machine_result
R-2712  results
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from backend.core.rules.base import EngineeringRule
from backend.dfm import validation as _v
from backend.domain.result import EngineeringResult, failure

__all__ = [
    "HoleToolDiameterRule",
    "CornerRadiusToolRule",
    "SlotWidthToolRule",
    "PocketAccessRule",
    "ProcessFeatureCompatRule",
    "DepthDiameterRatioRule",
    "MachineCapabilityCompositionRule",
    "AggregateFeasibilityRule",
    "foundational_dfm_rules",
]

_VERSION = "1.0.0"
_SOURCE = "MachineryPro AI Stage 3I DFM process feasibility"


def _err(rule_id: str, exc: Exception) -> EngineeringResult:
    return failure(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        violations=(str(exc),),
    )


class HoleToolDiameterRule(EngineeringRule):
    """R-2701: tool_diameter == hole_diameter for drilling."""

    rule_id = "R-2701"
    rule_version = _VERSION
    description = "Verify drilling tool diameter matches requested hole diameter."
    domain = "dfm.geometry.hole_tool"
    required_inputs = ("feature", "tool")
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.check_hole_tool_diameter(inputs["feature"], inputs["tool"])
        except Exception as exc:
            return _err(self.rule_id, exc)


class CornerRadiusToolRule(EngineeringRule):
    """R-2702: tool_radius <= internal_corner_radius."""

    rule_id = "R-2702"
    rule_version = _VERSION
    description = "Verify milling tool radius does not exceed internal corner radius."
    domain = "dfm.geometry.corner_radius"
    required_inputs = ("feature", "tool")
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.check_corner_radius_tool(inputs["feature"], inputs["tool"])
        except Exception as exc:
            return _err(self.rule_id, exc)


class SlotWidthToolRule(EngineeringRule):
    """R-2703: tool_diameter <= slot_width."""

    rule_id = "R-2703"
    rule_version = _VERSION
    description = "Verify milling tool fits within slot width."
    domain = "dfm.geometry.slot_width"
    required_inputs = ("feature", "tool")
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.check_slot_width_tool(inputs["feature"], inputs["tool"])
        except Exception as exc:
            return _err(self.rule_id, exc)


class PocketAccessRule(EngineeringRule):
    """R-2704: tool_diameter <= pocket_opening_width."""

    rule_id = "R-2704"
    rule_version = _VERSION
    description = "Verify milling tool fits through pocket opening."
    domain = "dfm.geometry.pocket_access"
    required_inputs = ("feature", "tool")
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.check_pocket_access(inputs["feature"], inputs["tool"])
        except Exception as exc:
            return _err(self.rule_id, exc)


class ProcessFeatureCompatRule(EngineeringRule):
    """R-2705: Operation type is compatible with feature type."""

    rule_id = "R-2705"
    rule_version = _VERSION
    description = "Check operation–feature type compatibility."
    domain = "dfm.compatibility.process_feature"
    required_inputs = ("feature", "operation_type")
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.check_process_feature_compatibility(
                inputs["feature"], inputs["operation_type"]
            )
        except Exception as exc:
            return _err(self.rule_id, exc)


class DepthDiameterRatioRule(EngineeringRule):
    """R-2706: Calculate depth/diameter ratio; validate against explicit limit.

    ``explicit_limit`` is an optional Decimal in the inputs mapping.
    If absent, ratio is reported as WARNING only (no arbitrary threshold).
    """

    rule_id = "R-2706"
    rule_version = _VERSION
    description = "Calculate depth/diameter ratio; validate against explicit limit."
    domain = "dfm.geometry.depth_diameter"
    required_inputs = ("feature",)  # explicit_limit is optional
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            limit = inputs.get("explicit_limit")
            if limit is not None and not isinstance(limit, Decimal):
                limit = Decimal(str(limit))
            return _v.check_depth_diameter_ratio(inputs["feature"], limit)
        except Exception as exc:
            return _err(self.rule_id, exc)


class MachineCapabilityCompositionRule(EngineeringRule):
    """R-2710: Compose a Stage 3H machine result into the DFM envelope."""

    rule_id = "R-2710"
    rule_version = _VERSION
    description = "Compose Stage 3H machine-capability result into DFM feasibility."
    domain = "dfm.composition.machine"
    required_inputs = ("machine_result",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.compose_machine_result(inputs["machine_result"])
        except Exception as exc:
            return _err(self.rule_id, exc)


class AggregateFeasibilityRule(EngineeringRule):
    """R-2712: Aggregate multiple check results into one feasibility status."""

    rule_id = "R-2712"
    rule_version = _VERSION
    description = "Aggregate all DFM check results into a single feasibility status."
    domain = "dfm.aggregate"
    required_inputs = ("results",)
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.aggregate_feasibility(tuple(inputs["results"]))
        except Exception as exc:
            return _err(self.rule_id, exc)


def foundational_dfm_rules() -> tuple[EngineeringRule, ...]:
    """Instantiate all Stage 3I DFM rules for registry registration."""
    return (
        HoleToolDiameterRule(),
        CornerRadiusToolRule(),
        SlotWidthToolRule(),
        PocketAccessRule(),
        ProcessFeatureCompatRule(),
        DepthDiameterRatioRule(),
        MachineCapabilityCompositionRule(),
        AggregateFeasibilityRule(),
    )
