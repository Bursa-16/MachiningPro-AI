"""Shared domain base: validation helpers, provenance, serialization.

Principles (Stage 2):

* fail closed — invalid engineering input raises :class:`ValidationError`;
* unknown is ``None`` — zero is a *value*, never a substitute for unknown;
* provenance is first-class and AI-derived values stay identifiable;
* entities serialize deterministically (sorted keys, Decimal→str,
  datetime→ISO-8601) via :func:`entity_as_dict`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from backend.domain.enums import ProvenanceType
from backend.domain.exceptions import ValidationError
from backend.domain.units import Numeric, Quantity, _to_decimal

__all__ = [
    "Provenance",
    "entity_as_dict",
    "json_safe",
    "optional_non_empty_str",
    "require_non_empty_str",
    "require_positive_decimal",
    "require_positive_int",
    "require_positive_quantity",
    "require_positive_quantity_or_none",
]


# --------------------------------------------------------------------- #
# Validation helpers (shared by every entity)
# --------------------------------------------------------------------- #
def require_non_empty_str(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string")
    return value.strip()


def optional_non_empty_str(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(
            f"{field_name} must be None or a non-empty string"
        )
    return cleaned


def require_positive_int(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValidationError(
            f"{field_name} must be a positive integer, got {value}"
        )
    return value


def require_positive_quantity(quantity: Quantity, field_name: str) -> Quantity:
    if not isinstance(quantity, Quantity):
        raise ValidationError(f"{field_name} must be a Quantity")
    if not quantity.is_positive():
        raise ValidationError(
            f"{field_name} must be strictly positive, got {quantity}"
        )
    return quantity


def require_positive_quantity_or_none(
    quantity: Quantity | None, field_name: str
) -> Quantity | None:
    """Unknown is ``None``; a provided value must still be positive.

    Zero is rejected explicitly so callers cannot use it to mean "unknown".
    """
    if quantity is None:
        return None
    return require_positive_quantity(quantity, field_name)


def require_positive_decimal(
    value: Numeric | None, field_name: str
) -> Decimal | None:
    """Unknown is ``None``; a provided value must be finite and > 0."""
    if value is None:
        return None
    converted = _to_decimal(value, field_name)
    if converted <= 0:
        raise ValidationError(
            f"{field_name} must be strictly positive when known "
            f"(use null for unknown), got {converted}"
        )
    return converted


# --------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Provenance:
    """Reusable source/provenance record attached to domain entities.

    ``AI_SUGGESTION`` provenance keeps AI-derived data permanently
    distinguishable from authoritative engineering sources. Confidence is
    optional and only meaningful where the producing step defines it.
    """

    source_type: ProvenanceType
    source_reference: str | None = None
    source_document: str | None = None
    page_section: str | None = None
    timestamp: datetime | None = None
    confidence: float | None = field(default=None)
    notes: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_type, ProvenanceType):
            raise ValidationError(
                f"source_type must be a ProvenanceType, got {self.source_type!r}"
            )
        for name in ("source_reference", "source_document", "page_section", "notes"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValidationError(
                    f"provenance.{name} must be a string or None"
                )
            if isinstance(value, str) and not value.strip():
                raise ValidationError(
                    f"provenance.{name} must be None or a non-empty string"
                )
        if self.timestamp is not None and not isinstance(self.timestamp, datetime):
            raise ValidationError("provenance.timestamp must be a datetime or None")
        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(
                self.confidence, (int, float)
            ):
                raise ValidationError(
                    "provenance.confidence must be a number between 0 and 1"
                )
            if not 0.0 <= float(self.confidence) <= 1.0:
                raise ValidationError(
                    f"provenance.confidence must lie within [0, 1], got {self.confidence}"
                )

    @property
    def is_ai_suggestion(self) -> bool:
        """True only for AI-derived information."""
        return self.source_type is ProvenanceType.AI_SUGGESTION


# --------------------------------------------------------------------- #
# Deterministic, serialization-friendly representation
# --------------------------------------------------------------------- #
def json_safe(value: Any) -> Any:
    """Convert a dataclass tree into JSON-serializable primitives.

    Quantity -> its exact decimal value as a string, Decimal -> string
    (exact), Enum -> value, datetime -> ISO-8601; mappings/tuples/lists are
    recursed preserving order. Fields are read via ``dataclasses.fields``
    instead of ``dataclasses.asdict`` so frozen mappings (MappingProxyType)
    never require deepcopy.
    """
    if isinstance(value, Quantity):
        return str(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: json_safe(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def entity_as_dict(entity: Any) -> dict[str, Any]:
    """Deterministic serialization-friendly representation of an entity."""
    return json_safe(entity)
