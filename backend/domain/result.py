"""EngineeringResult: deterministic result envelope for rules/calculations.

Every deterministic rule or calculation returns this envelope so consumers
always see status, outputs-with-units, warnings, violations, assumptions and
provenance in one immutable, serializable structure.

Status semantics (locked):

* ``PASS``              — evaluated; no violations (warnings belong to
                          ``WARNING``).
* ``WARNING``           — evaluated successfully but with at least one warning
                          and no violations.
* ``FAIL``              — evaluated; at least one engineering violation.
* ``INSUFFICIENT_DATA`` — fail-closed: required inputs were missing/unknown;
                          never converted into PASS by any later layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    require_non_empty_str,
)
from backend.domain.enums import ResultStatus
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity

_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class EngineeringResult:
    """Immutable envelope describing one deterministic evaluation."""

    result_id: str
    rule_id: str
    rule_version: str
    status: ResultStatus
    provenance: Provenance
    outputs: Mapping[str, Quantity] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    summary: str | None = None
    schema_version: str = _SCHEMA_VERSION

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "result_id",
            require_non_empty_str(self.result_id, "result_id"),
        )
        _set(self, "rule_id", require_non_empty_str(self.rule_id, "rule_id"))
        _set(
            self,
            "rule_version",
            require_non_empty_str(self.rule_version, "rule_version"),
        )
        if not isinstance(self.status, ResultStatus):
            raise ValidationError("status must be a ResultStatus")
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")
        object.__setattr__(
            self, "outputs", MappingProxyType(dict(self.outputs or {}))
        )
        for name in ("warnings", "violations", "assumptions", "missing_inputs"):
            cleaned: list[str] = []
            for entry in getattr(self, name):
                if not isinstance(entry, str) or not entry.strip():
                    raise ValidationError(
                        f"{name} entries must be non-empty strings"
                    )
                cleaned.append(entry.strip())
            object.__setattr__(self, name, tuple(cleaned))

        if self.status is ResultStatus.PASS and (
            self.violations or self.missing_inputs
        ):
            raise ValidationError("PASS results must not carry violations")
        if self.status is ResultStatus.WARNING:
            if self.violations or self.missing_inputs:
                raise ValidationError("WARNING results must not carry violations")
            if not self.warnings:
                raise ValidationError(
                    "WARNING results must carry at least one warning"
                )
        if self.status is ResultStatus.FAIL and not self.violations:
            raise ValidationError("FAIL results must carry at least one violation")
        if self.status is ResultStatus.INSUFFICIENT_DATA and not (
            self.missing_inputs
        ):
            raise ValidationError(
                "INSUFFICIENT_DATA results must list the missing inputs"
            )

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


def _provenance_for(rule_id: str, version: str) -> Provenance:
    from backend.domain.enums import ProvenanceType

    return Provenance(
        source_type=ProvenanceType.DETERMINISTIC_CALCULATION,
        source_reference=f"{rule_id}@{version}",
    )


def success(
    *,
    result_id: str,
    rule_id: str,
    rule_version: str,
    outputs: Mapping[str, Quantity] | None = None,
    assumptions: tuple[str, ...] = (),
    summary: str | None = None,
) -> EngineeringResult:
    """Build a coherent ``PASS`` result."""
    return EngineeringResult(
        result_id=result_id,
        rule_id=rule_id,
        rule_version=rule_version,
        status=ResultStatus.PASS,
        provenance=_provenance_for(rule_id, rule_version),
        outputs=outputs or {},
        assumptions=assumptions,
        summary=summary,
    )


def warning(
    *,
    result_id: str,
    rule_id: str,
    rule_version: str,
    warnings: tuple[str, ...],
    outputs: Mapping[str, Quantity] | None = None,
    assumptions: tuple[str, ...] = (),
    summary: str | None = None,
) -> EngineeringResult:
    """Build a coherent ``WARNING`` result (at least one warning)."""
    return EngineeringResult(
        result_id=result_id,
        rule_id=rule_id,
        rule_version=rule_version,
        status=ResultStatus.WARNING,
        provenance=_provenance_for(rule_id, rule_version),
        outputs=outputs or {},
        warnings=warnings,
        assumptions=assumptions,
        summary=summary,
    )


def failure(
    *,
    result_id: str,
    rule_id: str,
    rule_version: str,
    violations: tuple[str, ...],
    outputs: Mapping[str, Quantity] | None = None,
    assumptions: tuple[str, ...] = (),
    summary: str | None = None,
) -> EngineeringResult:
    """Build a coherent ``FAIL`` result (at least one violation)."""
    return EngineeringResult(
        result_id=result_id,
        rule_id=rule_id,
        rule_version=rule_version,
        status=ResultStatus.FAIL,
        provenance=_provenance_for(rule_id, rule_version),
        outputs=outputs or {},
        violations=violations,
        assumptions=assumptions,
        summary=summary,
    )


def insufficient_data(
    *,
    result_id: str,
    rule_id: str,
    rule_version: str,
    missing_inputs: tuple[str, ...],
    summary: str | None = None,
) -> EngineeringResult:
    """Build a fail-closed ``INSUFFICIENT_DATA`` result."""
    return EngineeringResult(
        result_id=result_id,
        rule_id=rule_id,
        rule_version=rule_version,
        status=ResultStatus.INSUFFICIENT_DATA,
        provenance=_provenance_for(rule_id, rule_version),
        missing_inputs=missing_inputs,
        summary=summary or "required inputs are missing; evaluation refused",
    )
