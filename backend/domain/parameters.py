"""Machining parameters: explicit engineering inputs with explicit units.

Doctrine: **unknown stays ``None``**. Zero is a valid engineering value in
some contexts and is therefore *rejected* here as an unknown-substitute — a
provided quantity must be strictly positive so nothing downstream can mistake
a placeholder for real data.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    require_positive_quantity_or_none,
)
from backend.domain.enums import CoolantMode
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity

_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class MachiningParameters:
    """Explicit cutting-parameter inputs; every member may be unknown."""

    provenance: Provenance | None = None
    cutting_speed: Quantity | None = None  # m/min
    spindle_speed: Quantity | None = None  # rpm
    feed_per_tooth: Quantity | None = None  # mm/tooth
    feed_per_rev: Quantity | None = None  # mm/rev
    feed_rate: Quantity | None = None  # mm/min
    axial_depth_of_cut: Quantity | None = None  # mm
    radial_depth_of_cut: Quantity | None = None  # mm
    coolant_mode: CoolantMode | None = None  # None == not specified
    schema_version: str = _SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.provenance is not None and not isinstance(
            self.provenance, Provenance
        ):
            raise ValidationError("provenance must be a Provenance or None")
        for name in (
            "cutting_speed",
            "spindle_speed",
            "feed_per_tooth",
            "feed_per_rev",
            "feed_rate",
            "axial_depth_of_cut",
            "radial_depth_of_cut",
        ):
            require_positive_quantity_or_none(getattr(self, name), name)
        if self.coolant_mode is not None and not isinstance(
            self.coolant_mode, CoolantMode
        ):
            raise ValidationError("coolant_mode must be a CoolantMode or None")

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)
