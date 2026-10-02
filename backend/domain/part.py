"""Part entity: a manufactured part under engineering control."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    optional_non_empty_str,
    require_non_empty_str,
    require_positive_int,
)
from backend.domain.exceptions import ValidationError

_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class Part:
    """A manufactured part identity with its primary references.

    ``quantity`` must be a positive integer — a part of quantity zero does
    not exist, and unknown quantity is not modeled at Stage 2.
    """

    part_id: str
    name: str
    revision: str
    material_id: str
    quantity: int
    provenance: Provenance
    description: str | None = None
    raw_stock_reference: str | None = None
    drawing_reference: str | None = None
    cad_reference: str | None = None
    unit_system: str = "METRIC"
    schema_version: str = _SCHEMA_VERSION
    notes: str | None = field(default=None)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "part_id", require_non_empty_str(self.part_id, "part_id"))
        _set(self, "name", require_non_empty_str(self.name, "name"))
        _set(self, "revision", require_non_empty_str(self.revision, "revision"))
        _set(
            self,
            "material_id",
            require_non_empty_str(self.material_id, "material_id"),
        )
        _set(self, "quantity", require_positive_int(self.quantity, "quantity"))
        _set(
            self,
            "unit_system",
            require_non_empty_str(self.unit_system, "unit_system"),
        )
        _set(
            self,
            "description",
            optional_non_empty_str(self.description, "description"),
        )
        _set(
            self,
            "raw_stock_reference",
            optional_non_empty_str(
                self.raw_stock_reference, "raw_stock_reference"
            ),
        )
        _set(
            self,
            "drawing_reference",
            optional_non_empty_str(
                self.drawing_reference, "drawing_reference"
            ),
        )
        _set(
            self,
            "cad_reference",
            optional_non_empty_str(self.cad_reference, "cad_reference"),
        )
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)
