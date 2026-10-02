"""Operation entity: one manufacturing step on a part.

Stage 2 records explicit operations only — automatic sequencing is a later
stage.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    optional_non_empty_str,
    require_non_empty_str,
    require_positive_int,
)
from backend.domain.enums import OperationStatus, OperationType
from backend.domain.exceptions import ValidationError

_SCHEMA_VERSION = "1"


def _id_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    cleaned: list[str] = []
    for value in values:
        cleaned.append(require_non_empty_str(value, f"{field_name} entry"))
    return tuple(cleaned)


@dataclass(frozen=True, slots=True)
class Operation:
    """A single manufacturing operation applied to (part of) a part."""

    operation_id: str
    part_id: str
    operation_type: OperationType
    sequence_index: int
    provenance: Provenance
    feature_ids: tuple[str, ...] = ()
    machine_id: str | None = None
    tool_ids: tuple[str, ...] = ()
    parameter_set_id: str | None = None
    status: OperationStatus = OperationStatus.PLANNED
    schema_version: str = _SCHEMA_VERSION
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "operation_id",
            require_non_empty_str(self.operation_id, "operation_id"),
        )
        _set(self, "part_id", require_non_empty_str(self.part_id, "part_id"))
        if not isinstance(self.operation_type, OperationType):
            raise ValidationError("operation_type must be an OperationType")
        _set(
            self,
            "sequence_index",
            require_positive_int(self.sequence_index, "sequence_index"),
        )
        object.__setattr__(self, "feature_ids", _id_tuple(self.feature_ids, "feature_ids"))
        object.__setattr__(self, "tool_ids", _id_tuple(self.tool_ids, "tool_ids"))
        _set(
            self,
            "machine_id",
            optional_non_empty_str(self.machine_id, "machine_id"),
        )
        _set(
            self,
            "parameter_set_id",
            optional_non_empty_str(self.parameter_set_id, "parameter_set_id"),
        )
        if not isinstance(self.status, OperationStatus):
            raise ValidationError("status must be an OperationStatus")
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)
