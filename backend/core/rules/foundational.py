"""Foundational engineering rules proving the Stage 2 framework.

Only minimal, framework-proving rules live here — no machining
recommendations, no literature-derived cutting data, no speculative limits.
Each value used in evaluation is supplied by the caller; tests use synthetic
values only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.core.rules.base import EngineeringRule
from backend.domain.result import (
    EngineeringResult,
    failure,
    success,
)
from backend.domain.units import Quantity

_RULE_VERSIONS = {
    "R-1001": "1.0.0",
    "R-1002": "1.0.0",
    "R-1003": "1.0.0",
    "R-1004": "1.0.0",
}


class PositiveDimensionalValueRule(EngineeringRule):
    """R-1001: a provided dimensional value must be strictly positive.

    Zero is a *value the caller intentionally supplied*; unknown is ``None``
    and is handled by the base-class fail-closed completeness gate before
    this rule runs.
    """

    rule_id = "R-1001"
    rule_version = _RULE_VERSIONS["R-1001"]
    description = "A dimensional Quantity must be strictly positive."
    domain = "validation.dimensional"
    required_inputs = ("value",)
    source_reference = "machinery-ai engineering rule framework (Stage 2)"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        value = inputs["value"]
        if not isinstance(value, Quantity):
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"value must be a Quantity, got {type(value).__name__}",
                ),
            )
        if value.is_positive():
            return success(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                outputs={"value": value},
                summary=f"value {value} is strictly positive",
            )
        return failure(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            violations=(
                f"value must be strictly positive, got {value}",
            ),
        )


class SpindleRpmRangeRule(EngineeringRule):
    """R-1002: a spindle-speed quantity lies within a machine rpm envelope.

    Both envelope endpoints and the spindle speed must be ``Quantity`` in
    ``rpm``; units are compared exactly (no implicit conversion).
    """

    rule_id = "R-1002"
    rule_version = _RULE_VERSIONS["R-1002"]
    description = "Spindle speed must be within the machine rpm range."
    domain = "machine.capability"
    required_inputs = ("spindle_speed", "speed_min", "speed_max")
    source_reference = "machinery-ai engineering rule (Stage 2)"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        speed = inputs["spindle_speed"]
        min_value = inputs["speed_min"]
        max_value = inputs["speed_max"]
        for name, value in (
            ("spindle_speed", speed),
            ("speed_min", min_value),
            ("speed_max", max_value),
        ):
            if not isinstance(value, Quantity):
                return failure(
                    result_id=f"{self.rule_id}.result",
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    violations=(
                        f"{name} must be a Quantity, got {type(value).__name__}",
                    ),
                )
        if speed.unit != min_value.unit or speed.unit != max_value.unit:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    "all inputs must share the same unit; explicit "
                    "conversion is required otherwise",
                ),
            )
        if min_value.value > max_value.value:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=("speed_min must not exceed speed_max",),
            )
        if min_value.value <= speed.value <= max_value.value:
            return success(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                outputs={"spindle_speed": speed},
            )
        return failure(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            violations=(
                f"spindle speed {speed} outside machine range "
                f"[{min_value}, {max_value}]",
            ),
        )


class ToolDiameterRangeRule(EngineeringRule):
    """R-1003: a tool diameter lies within a declared allowable mm range.

    A range is only evaluated when the caller supplies both endpoints; the
    range itself is caller-declared (the registry does not invent tool limits).
    """

    rule_id = "R-1003"
    rule_version = _RULE_VERSIONS["R-1003"]
    description = "Tool diameter must lie within the declared allowable range."
    domain = "tooling.constraint"
    required_inputs = ("tool_diameter", "diameter_min", "diameter_max")
    source_reference = "machinery-ai engineering rule (Stage 2)"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        diameter = inputs["tool_diameter"]
        min_value = inputs["diameter_min"]
        max_value = inputs["diameter_max"]
        for name, value in (
            ("tool_diameter", diameter),
            ("diameter_min", min_value),
            ("diameter_max", max_value),
        ):
            if not isinstance(value, Quantity):
                return failure(
                    result_id=f"{self.rule_id}.result",
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    violations=(
                        f"{name} must be a Quantity, got {type(value).__name__}",
                    ),
                )
            if value.unit.value != "mm":
                return failure(
                    result_id=f"{self.rule_id}.result",
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    violations=(
                        f"{name} must use mm, got {value.unit.value}",
                    ),
                )
        if min_value.value > max_value.value:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=("diameter_min must not exceed diameter_max",),
            )
        if min_value.value <= diameter.value <= max_value.value:
            return success(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                outputs={"tool_diameter": diameter},
            )
        return failure(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            violations=(
                f"tool diameter {diameter} outside allowable range "
                f"[{min_value}, {max_value}]",
            ),
        )


class RequiredInputCompletenessRule(EngineeringRule):
    """R-1004: every expected parameter is present and non-None.

    Unknown-equals-missing: a key absent from the input mapping or mapped to
    ``None`` is reported as a missing-input violation.
    """

    rule_id = "R-1004"
    rule_version = _RULE_VERSIONS["R-1004"]
    description = "Required machining inputs must all be present."
    domain = "validation.completeness"
    required_inputs = ("expected",)
    source_reference = "machinery-ai engineering rule (Stage 2)"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        expected = inputs["expected"]
        if not isinstance(expected, (tuple, list, set)):
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    "expected must be a tuple/list/set of input names, got "
                    f"{type(expected).__name__}",
                ),
            )
        missing = tuple(
            name for name in expected if inputs.get(name, None) is None
        )
        if missing:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(f"missing required inputs: {missing}",),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary="all required inputs are present",
        )


def foundational_rules() -> tuple[EngineeringRule, ...]:
    """Instantiate the Stage 2 foundational rules for registration."""
    return (
        PositiveDimensionalValueRule(),
        SpindleRpmRangeRule(),
        ToolDiameterRangeRule(),
        RequiredInputCompletenessRule(),
    )
