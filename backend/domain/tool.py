"""Tool entity: cutting-tool identity and capability.

Stage 2 models identity/capability only — tool *selection* algorithms are a
later stage.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    optional_non_empty_str,
    require_non_empty_str,
    require_positive_int,
    require_positive_quantity,
    require_positive_quantity_or_none,
)
from backend.domain.enums import OperationType, ToolType
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity

_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class Tool:
    """A physical cutting tool with its measurable capability envelope."""

    tool_id: str
    tool_type: ToolType
    diameter: Quantity  # canonical expectation: mm (unit kept explicit)
    cutting_edge_count: int
    provenance: Provenance
    manufacturer: str | None = None
    reference: str | None = None
    usable_length: Quantity | None = None
    material_metadata: Mapping[str, object] = field(default_factory=dict)
    coating_metadata: Mapping[str, object] = field(default_factory=dict)
    supported_operations: tuple[OperationType, ...] = ()
    schema_version: str = _SCHEMA_VERSION
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "tool_id", require_non_empty_str(self.tool_id, "tool_id"))
        if not isinstance(self.tool_type, ToolType):
            raise ValidationError("tool_type must be a ToolType")
        require_positive_quantity(self.diameter, "diameter")
        _set(
            self,
            "cutting_edge_count",
            require_positive_int(self.cutting_edge_count, "cutting_edge_count"),
        )
        require_positive_quantity_or_none(self.usable_length, "usable_length")
        _set(
            self,
            "manufacturer",
            optional_non_empty_str(self.manufacturer, "manufacturer"),
        )
        _set(
            self,
            "reference",
            optional_non_empty_str(self.reference, "reference"),
        )
        for name in ("material_metadata", "coating_metadata"):
            object.__setattr__(
                self,
                name,
                MappingProxyType(dict(getattr(self, name) or {})),
            )
        cleaned_ops: list[OperationType] = []
        for operation in self.supported_operations:
            if not isinstance(operation, OperationType):
                raise ValidationError(
                    "supported_operations entries must be OperationType"
                )
            cleaned_ops.append(operation)
        object.__setattr__(self, "supported_operations", tuple(cleaned_ops))
        if not cleaned_ops:
            raise ValidationError(
                "supported_operations must contain at least one operation type"
            )
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)
