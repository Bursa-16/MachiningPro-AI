"""Material entity: engineering material identity and *known* properties.

Core doctrine: **unknown is different from zero.** A property that has not
been measured/sourced stays ``None``; a fabricated or zero-filled value would
poison every downstream deterministic calculation.
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
    require_positive_quantity_or_none,
)
from backend.domain.enums import MaterialFamily
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit

_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class Material:
    """Material identity plus only the properties that are actually known."""

    material_id: str
    designation: str
    material_family: MaterialFamily
    provenance: Provenance
    standard: str | None = None
    condition: str | None = None
    hardness: Quantity | None = None  # caller selects HB/HRC/etc. unit explicitly
    density: Quantity | None = None  # must use kg/m3 when provided
    tensile_strength: Quantity | None = None  # must use MPa when provided
    yield_strength: Quantity | None = None  # must use MPa when provided
    machinability_metadata: Mapping[str, object] = field(default_factory=dict)
    schema_version: str = _SCHEMA_VERSION
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "material_id",
            require_non_empty_str(self.material_id, "material_id"),
        )
        _set(
            self,
            "designation",
            require_non_empty_str(self.designation, "designation"),
        )
        _set(
            self,
            "standard",
            optional_non_empty_str(self.standard, "standard"),
        )
        _set(
            self,
            "condition",
            optional_non_empty_str(self.condition, "condition"),
        )
        if not isinstance(self.material_family, MaterialFamily):
            raise ValidationError("material_family must be a MaterialFamily")
        if self.hardness is not None:
            require_positive_quantity_or_none(self.hardness, "hardness")
        if self.density is not None:
            require_positive_quantity_or_none(self.density, "density")
            if self.density.unit is not Unit.KG_M3:
                raise ValidationError(
                    f"density must use {Unit.KG_M3}, got {self.density.unit}"
                )
        for name in ("tensile_strength", "yield_strength"):
            quantity: Quantity | None = getattr(self, name)
            if quantity is not None:
                require_positive_quantity_or_none(quantity, name)
                if quantity.unit is not Unit.MPA:
                    raise ValidationError(
                        f"{name} must use {Unit.MPA}, got {quantity.unit}"
                    )
        object.__setattr__(
            self,
            "machinability_metadata",
            MappingProxyType(dict(self.machinability_metadata or {})),
        )
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)
