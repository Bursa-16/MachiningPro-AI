"""Machine entity: machine-tool capability envelope.

Machine limits are **constraints**, never recommendations: exceeding them is
invalid, not merely suboptimal.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    require_non_empty_str,
    require_positive_int,
    require_positive_quantity,
)
from backend.domain.enums import MachineType, OperationType
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit

_SCHEMA_VERSION = "1"


def _rpm_quantity(quantity: Quantity, field_name: str) -> Quantity:
    require_positive_quantity(quantity, field_name)
    if quantity.unit is not Unit.RPM:
        raise ValidationError(
            f"{field_name} must use {Unit.RPM}, got {quantity.unit}"
        )
    return quantity


@dataclass(frozen=True, slots=True)
class Machine:
    """A physical machine tool with hard capability limits."""

    machine_id: str
    name: str
    machine_type: MachineType
    axis_count: int
    spindle_speed_min: Quantity  # rpm
    spindle_speed_max: Quantity  # rpm
    spindle_power: Quantity  # kW
    provenance: Provenance
    spindle_torque: Quantity | None = None  # Nm when known
    feed_rate_max: Quantity | None = None  # mm/min when known
    working_envelope: Mapping[str, Quantity] = field(default_factory=dict)
    supported_operations: tuple[OperationType, ...] = ()
    controller_metadata: Mapping[str, object] = field(default_factory=dict)
    schema_version: str = _SCHEMA_VERSION
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "machine_id",
            require_non_empty_str(self.machine_id, "machine_id"),
        )
        _set(self, "name", require_non_empty_str(self.name, "name"))
        if not isinstance(self.machine_type, MachineType):
            raise ValidationError("machine_type must be a MachineType")
        _set(
            self,
            "axis_count",
            require_positive_int(self.axis_count, "axis_count"),
        )
        _rpm_quantity(self.spindle_speed_min, "spindle_speed_min")
        _rpm_quantity(self.spindle_speed_max, "spindle_speed_max")
        if self.spindle_speed_min.value > self.spindle_speed_max.value:
            raise ValidationError(
                "spindle_speed_min must not exceed spindle_speed_max"
            )
        require_positive_quantity(self.spindle_power, "spindle_power")
        if self.spindle_power.unit is not Unit.KW:
            raise ValidationError(
                f"spindle_power must use {Unit.KW}, got {self.spindle_power.unit}"
            )
        if self.spindle_torque is not None:
            require_positive_quantity(self.spindle_torque, "spindle_torque")
            if self.spindle_torque.unit is not Unit.NM:
                raise ValidationError(
                    f"spindle_torque must use {Unit.NM}, got "
                    f"{self.spindle_torque.unit}"
                )
        if self.feed_rate_max is not None:
            require_positive_quantity(self.feed_rate_max, "feed_rate_max")
            if self.feed_rate_max.unit is not Unit.MM_MIN:
                raise ValidationError(
                    f"feed_rate_max must use {Unit.MM_MIN}, got "
                    f"{self.feed_rate_max.unit}"
                )
        object.__setattr__(
            self,
            "working_envelope",
            MappingProxyType(dict(self.working_envelope or {})),
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
        object.__setattr__(
            self,
            "controller_metadata",
            MappingProxyType(dict(self.controller_metadata or {})),
        )
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)
