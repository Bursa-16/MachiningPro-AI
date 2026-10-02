"""Core engineering primitives: unit handling, validation and the fail-closed
policy engine.

Every deterministic result must be reproducible from registered rules and
inputs; on missing/invalid data the system must fail closed (refuse to answer)
rather than guess.
"""

from backend.core.rules import (
    EngineeringRule,
    PositiveDimensionalValueRule,
    RequiredInputCompletenessRule,
    RuleMetadata,
    RuleRegistry,
    SpindleRpmRangeRule,
    ToolDiameterRangeRule,
    foundational_rules,
    missing_input_names,
)

__all__ = [
    "EngineeringRule",
    "PositiveDimensionalValueRule",
    "RequiredInputCompletenessRule",
    "RuleMetadata",
    "RuleRegistry",
    "SpindleRpmRangeRule",
    "ToolDiameterRangeRule",
    "foundational_rules",
    "missing_input_names",
]
