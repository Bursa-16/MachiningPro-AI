"""Rule base: deterministic engineering-rule interface.

Every deterministic engineering rule:

* declares stable identity (``rule_id``), a version, a description, the
  engineering domain it applies to, and the exact inputs it requires;
* carries provenance/source reference metadata;
* evaluates deterministically and returns an
  :class:`~backend.domain.result.EngineeringResult`.

A rule never performs I/O, never calls a network, never calls a model, and
never silently repairs invalid input. Missing required inputs always produce
an ``INSUFFICIENT_DATA`` result (fail closed) — a rule must not guess.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from backend.domain.base import Provenance
from backend.domain.enums import ProvenanceType
from backend.domain.result import EngineeringResult, insufficient_data

__all__ = ["EngineeringRule", "missing_input_names"]


def missing_input_names(
    rule: EngineeringRule, inputs: Mapping[str, Any]
) -> tuple[str, ...]:
    """Names of required inputs that are absent (None counts as absent)."""
    return tuple(
        name for name in rule.required_inputs if inputs.get(name, None) is None
    )


class EngineeringRule(ABC):
    """Interface every deterministic engineering rule implements."""

    #: stable, unique identifier (e.g. \"R-1001\")
    rule_id: str
    #: version of this rule implementation ("1.0.0")
    rule_version: str
    #: human-readable description
    description: str
    #: engineering domain, e.g. "machining.parameters", "machine.capability"
    domain: str
    #: exact input names this rule needs
    required_inputs: tuple[str, ...] = ()
    #: source/document reference for the principle behind this rule
    source_reference: str | None = None

    # Abstract engine -------------------------------------------------- #
    @abstractmethod
    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        """Perform the actual deterministic evaluation."""

    # Public engine ------------------------------------------------------
    def evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        """Run the rule with fail-closed missing-input handling."""
        missing = missing_input_names(self, inputs)
        if missing:
            return insufficient_data(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                missing_inputs=missing,
            )
        return self._evaluate(inputs)

    @property
    def provenance(self) -> Provenance:
        """Deterministic-rule provenance carrying the source reference."""
        return Provenance(
            source_type=ProvenanceType.DETERMINISTIC_CALCULATION,
            source_reference=self.source_reference
            or f"{self.rule_id}@{self.rule_version}",
        )
