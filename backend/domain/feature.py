"""Feature entity: a machinable / manufacturing feature of a part.

Stage 2 carries explicit feature *descriptions* only — CAD feature
recognition is explicitly out of scope.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    require_non_empty_str,
    require_positive_quantity_or_none,
)
from backend.domain.enums import FeatureType
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit

_SCHEMA_VERSION = "1"


def _frozen_str_mapping(
    mapping: Mapping[str, Quantity] | None, field_name: str
) -> Mapping[str, Quantity]:
    source = mapping or {}
    cleaned: dict[str, Quantity] = {}
    for key, value in source.items():
        clean_key = require_non_empty_str(key, f"{field_name} key")
        if not isinstance(value, Quantity):
            raise ValidationError(
                f"{field_name}[{clean_key}] must be a Quantity"
            )
        cleaned[clean_key] = value
    return MappingProxyType(cleaned)


@dataclass(frozen=True, slots=True)
class Feature:
    """A named feature on a part, with known dimensions when available."""

    feature_id: str
    part_id: str
    feature_type: FeatureType
    provenance: Provenance
    dimensions: Mapping[str, Quantity] = field(default_factory=dict)
    tolerance_refs: tuple[str, ...] = ()
    surface_finish: Quantity | None = None
    accessibility_metadata: Mapping[str, object] = field(default_factory=dict)
    schema_version: str = _SCHEMA_VERSION
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "feature_id",
            require_non_empty_str(self.feature_id, "feature_id"),
        )
        _set(
            self,
            "part_id",
            require_non_empty_str(self.part_id, "part_id"),
        )
        if not isinstance(self.feature_type, FeatureType):
            raise ValidationError("feature_type must be a FeatureType")
        _set(
            self,
            "dimensions",
            _frozen_str_mapping(self.dimensions, "dimensions"),
        )
        object.__setattr__(
            self,
            "accessibility_metadata",
            MappingProxyType(dict(self.accessibility_metadata or {})),
        )
        cleaned_refs: list[str] = []
        for ref in self.tolerance_refs:
            cleaned_refs.append(require_non_empty_str(ref, "tolerance_refs entry"))
        object.__setattr__(self, "tolerance_refs", tuple(cleaned_refs))
        if self.surface_finish is not None:
            require_positive_quantity_or_none(
                self.surface_finish, "surface_finish"
            )
            if self.surface_finish.unit is not Unit.RA_UM:
                raise ValidationError(
                    "surface_finish must use the Ra_um unit, got "
                    f"{self.surface_finish.unit}"
                )
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)
