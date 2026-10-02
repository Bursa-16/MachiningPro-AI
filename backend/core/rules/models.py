"""Rule models: declarative metadata for registered engineering rules.

Stage 2 carries *metadata declarations only* — no YAML execution, no eval,
no dynamic expression evaluation. The executable engine that backs a rule
lives in code (an :class:`~backend.core.rules.base.EngineeringRule`).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.base import require_non_empty_str


@dataclass(frozen=True, slots=True)
class RuleMetadata:
    """Declarative, immutable metadata describing one engineering rule."""

    rule_id: str
    rule_version: str
    description: str
    domain: str
    required_inputs: tuple[str, ...]
    source_reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rule_id",
            require_non_empty_str(self.rule_id, "rule_id"),
        )
        object.__setattr__(
            self,
            "rule_version",
            require_non_empty_str(self.rule_version, "rule_version"),
        )
        object.__setattr__(
            self,
            "description",
            require_non_empty_str(self.description, "description"),
        )
        object.__setattr__(
            self,
            "domain",
            require_non_empty_str(self.domain, "domain"),
        )
        cleaned_inputs: list[str] = []
        for name in self.required_inputs:
            cleaned_inputs.append(
                require_non_empty_str(name, "required_inputs entry")
            )
        cleaned = tuple(dict.fromkeys(cleaned_inputs))
        object.__setattr__(self, "required_inputs", cleaned)
        if self.source_reference is not None:
            cleaned_ref = self.source_reference.strip()
            if not cleaned_ref:
                raise ValueError(
                    "source_reference must be None or a non-empty string"
                )
            object.__setattr__(self, "source_reference", cleaned_ref)
