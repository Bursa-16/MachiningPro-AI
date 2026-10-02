"""Explicit unit model: canonical symbolic units and immutable quantities.

The domain model deliberately refuses ambiguous bare numbers. An engineering
value is always a :class:`Quantity` pairing a finite numeric ``value``
(:class:`decimal.Decimal`) with one canonical :class:`~backend.domain.enums.Unit`.

There is **no** implicit unit conversion (no mm↔inch, no m↔mm). Two
quantities are equal only when both value and unit are identical; helper
``require_same_unit`` makes unit mismatches explicit at comparison sites.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from backend.domain.exceptions import UnitError, UnknownUnitError, ValidationError

Numeric = int | float | str | Decimal


def _to_decimal(value: Numeric, field: str) -> Decimal:
    if isinstance(value, bool):
        raise UnitError(f"{field}: bool is not a valid numeric value")
    try:
        converted = Decimal(value if isinstance(value, Decimal) else str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise UnitError(f"{field}: not a valid number: {value!r}") from exc
    if not converted.is_finite():
        raise UnitError(f"{field}: value must be finite, got {converted}")
    return converted


class Unit(StrEnum):
    """Canonical symbolic units (extensible; symbols are the values)."""

    MM = "mm"
    M = "m"
    MM_MIN = "mm/min"
    MM_REV = "mm/rev"
    MM_TOOTH = "mm/tooth"
    M_MIN = "m/min"
    RPM = "rpm"
    KW = "kW"
    NM = "Nm"
    N = "N"
    MPA = "MPa"
    GPA = "GPa"
    KG_M3 = "kg/m3"
    RA_UM = "Ra_um"
    DIMENSIONLESS = "1"
    MM3 = "mm3"
    MM3_MIN = "mm3/min"
    MIN = "min"


@dataclass(frozen=True, slots=True)
class Quantity:
    """An immutable engineering value with an explicit canonical unit."""

    value: Decimal
    unit: Unit

    def __post_init__(self) -> None:
        if not isinstance(self.unit, Unit):
            raise ValidationError(
                f"unit must be a Unit enum member, got {self.unit!r}"
            )
        object.__setattr__(self, "value", _to_decimal(self.value, "value"))

    # ------------------------------------------------------------------ #
    # Factories
    # ------------------------------------------------------------------ #
    @classmethod
    def of(cls, value: Numeric, unit: Unit | str) -> Quantity:
        """Build a quantity from any numeric-like value and unit symbol."""
        if isinstance(unit, Unit):
            unit_value = unit
        else:
            try:
                unit_value = Unit(unit)
            except ValueError as exc:
                raise UnknownUnitError(
                    f"unknown unit symbol: {unit!r}"
                ) from exc
        return cls(value=_to_decimal(value, "value"), unit=unit_value)

    # ------------------------------------------------------------------ #
    # Predicates / helpers
    # ------------------------------------------------------------------ #
    def is_positive(self) -> bool:
        """True when the value is strictly greater than zero."""
        return self.value > 0

    def require_same_unit(self, other: Quantity, *, context: str = "") -> None:
        """Raise unless ``other`` carries exactly the same unit.

        There is no implicit conversion: comparing mm against m is a caller
        error and fails closed here.
        """
        if self.unit != other.unit:
            prefix = f"{context}: " if context else ""
            raise ValidationError(
                f"{prefix}unit mismatch ({self.unit} vs {other.unit}); "
                "explicit conversion is required before comparison"
            )

    def __str__(self) -> str:
        return f"{self.value} {self.unit.value}"
