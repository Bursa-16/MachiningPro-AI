"""Deterministic engineering-rule framework.

Registry-backed, deterministic, fail-closed. No AI calls, no network, no
dynamic YAML execution — rules are code and registry is in-memory at Stage 2.
"""

from backend.core.rules.base import EngineeringRule, missing_input_names
from backend.core.rules.foundational import (
    PositiveDimensionalValueRule,
    RequiredInputCompletenessRule,
    SpindleRpmRangeRule,
    ToolDiameterRangeRule,
    foundational_rules,
)
from backend.core.rules.models import RuleMetadata
from backend.core.rules.registry import RuleRegistry

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
