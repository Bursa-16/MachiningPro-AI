"""Deterministic reaming & boring calculations (Stage 3F).

Shared hole-finishing geometry (diametral/radial stock, annular volume,
annular MRR) plus effective travel and machining time for reaming and
boring operations.  All from EXPLICIT INPUTS.

Scope:
  - diametral stock
  - radial stock (= diametral / 2)
  - annular cross-sectional area
  - annular volume removed (concentric cylindrical)
  - hole-finishing MRR (annular × feed rate)
  - effective travel with explicit allowances
  - machining time (composed from Stage 3A)

Stage 3F REUSES Stage 3A shared formulas:
  - feed_rate_from_rpm_feed_per_rev
  - machining_time_from_distance_feed_rate

Every function is deterministic, unit-explicit and fail-closed.
"""

from __future__ import annotations

from decimal import Decimal

from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.formulas import (
    feed_rate_from_rpm_feed_per_rev,
    machining_time_from_distance_feed_rate,
)

__all__ = [
    "diametral_stock",
    "radial_stock",
    "annular_cross_sectional_area",
    "annular_volume",
    "hole_finishing_mrr",
    "effective_hole_finishing_travel",
    "hole_finishing_machining_time",
]

PI = Decimal("3.14159265358979323846264338327950288419716939937510")
FOUR = Decimal("4")
TWO = Decimal("2")


def _require_unit(quantity: Quantity, expected: Unit, name: str) -> None:
    if quantity.unit is not expected:
        raise MachiningMathError(
            f"{name} must be in {expected.value}, got {quantity.unit.value}"
        )


def _require_positive(value: Decimal, name: str) -> None:
    if value <= 0:
        raise MachiningMathError(
            f"{name} must be strictly positive, got {value}"
        )


def _require_non_negative(value: Decimal, name: str) -> None:
    if value < 0:
        raise MachiningMathError(
            f"{name} must be non-negative, got {value}"
        )


def _validate_diameter_pair(
    initial: Quantity, final: Quantity,
) -> tuple[Decimal, Decimal]:
    """Validate and return (d_initial, d_final) for hole enlargement."""
    _require_unit(initial, Unit.MM, "initial_diameter")
    _require_unit(final, Unit.MM, "final_diameter")
    _require_positive(initial.value, "initial_diameter")
    _require_positive(final.value, "final_diameter")
    if final.value < initial.value:
        raise MachiningMathError(
            f"final_diameter ({final.value}) must be >= "
            f"initial_diameter ({initial.value})"
        )
    return initial.value, final.value


# ---------------------------------------------------------------------------
# Stock removal
# ---------------------------------------------------------------------------

def diametral_stock(
    initial_diameter: Quantity,
    final_diameter: Quantity,
) -> Quantity:
    """diametral_stock = D_final - D_initial.

    Args:
        initial_diameter: pre-hole diameter in mm (> 0).
        final_diameter: finished diameter in mm (>= initial).
    Returns:
        Diametral stock in mm (>= 0).
    """
    d_i, d_f = _validate_diameter_pair(initial_diameter, final_diameter)
    return Quantity(value=d_f - d_i, unit=Unit.MM)


def radial_stock(
    initial_diameter: Quantity,
    final_diameter: Quantity,
) -> Quantity:
    """radial_stock = (D_final - D_initial) / 2.

    Args:
        initial_diameter: pre-hole diameter in mm (> 0).
        final_diameter: finished diameter in mm (>= initial).
    Returns:
        Radial stock in mm (>= 0).
    """
    d_i, d_f = _validate_diameter_pair(initial_diameter, final_diameter)
    return Quantity(value=(d_f - d_i) / TWO, unit=Unit.MM)


# ---------------------------------------------------------------------------
# Annular geometry
# ---------------------------------------------------------------------------

def annular_cross_sectional_area(
    initial_diameter: Quantity,
    final_diameter: Quantity,
) -> Quantity:
    """A = π/4 × (D_final² - D_initial²).

    Annular ring cross-section.  Result is dimensionless (mm² semantically)
    because the domain model lacks an MM2 unit.

    Args:
        initial_diameter: in mm (> 0).
        final_diameter: in mm (>= initial).
    Returns:
        Dimensionless value representing mm².
    """
    d_i, d_f = _validate_diameter_pair(initial_diameter, final_diameter)
    area = (PI / FOUR) * (d_f * d_f - d_i * d_i)
    return Quantity(value=area, unit=Unit.DIMENSIONLESS)


def annular_volume(
    initial_diameter: Quantity,
    final_diameter: Quantity,
    length: Quantity,
) -> Quantity:
    """V = π/4 × (D_final² - D_initial²) × length.

    Concentric cylindrical annulus.

    Args:
        initial_diameter: in mm (> 0).
        final_diameter: in mm (>= initial).
        length: axial length in mm (>= 0).
    Returns:
        Volume in mm³.
    """
    d_i, d_f = _validate_diameter_pair(initial_diameter, final_diameter)
    _require_unit(length, Unit.MM, "length")
    _require_non_negative(length.value, "length")

    vol = (PI / FOUR) * (d_f * d_f - d_i * d_i) * length.value
    return Quantity(value=vol, unit=Unit.MM3)


# ---------------------------------------------------------------------------
# MRR
# ---------------------------------------------------------------------------

def hole_finishing_mrr(
    initial_diameter: Quantity,
    final_diameter: Quantity,
    feed_rate: Quantity,
) -> Quantity:
    """Q = π/4 × (D_final² - D_initial²) × Vf.

    Annular MRR for simple axial full-length reaming or boring.

    Args:
        initial_diameter: in mm (> 0).
        final_diameter: in mm (>= initial).
        feed_rate: Vf in mm/min (>= 0).
    Returns:
        MRR in mm³/min.
    """
    d_i, d_f = _validate_diameter_pair(initial_diameter, final_diameter)
    _require_unit(feed_rate, Unit.MM_MIN, "feed_rate")
    _require_non_negative(feed_rate.value, "feed_rate")

    mrr = (PI / FOUR) * (d_f * d_f - d_i * d_i) * feed_rate.value
    return Quantity(value=mrr, unit=Unit.MM3_MIN)


# ---------------------------------------------------------------------------
# Effective travel
# ---------------------------------------------------------------------------

def effective_hole_finishing_travel(
    operation_length: Quantity,
    approach_allowance: Quantity | None = None,
    overtravel_allowance: Quantity | None = None,
) -> Quantity:
    """L_eff = operation_length + approach + overtravel.

    All allowances are explicit.

    Args:
        operation_length: nominal ream/bore length in mm (>= 0).
        approach_allowance: in mm (>= 0), optional.
        overtravel_allowance: in mm (>= 0), optional.
    Returns:
        Effective travel in mm.
    """
    _require_unit(operation_length, Unit.MM, "operation_length")
    _require_non_negative(operation_length.value, "operation_length")

    total = operation_length.value
    if approach_allowance is not None:
        _require_unit(approach_allowance, Unit.MM, "approach_allowance")
        _require_non_negative(approach_allowance.value, "approach_allowance")
        total += approach_allowance.value
    if overtravel_allowance is not None:
        _require_unit(overtravel_allowance, Unit.MM, "overtravel_allowance")
        _require_non_negative(overtravel_allowance.value, "overtravel_allowance")
        total += overtravel_allowance.value
    return Quantity(value=total, unit=Unit.MM)


# ---------------------------------------------------------------------------
# Machining time
# ---------------------------------------------------------------------------

def hole_finishing_machining_time(
    spindle_speed: Quantity,
    feed_per_rev: Quantity,
    operation_length: Quantity,
    approach_allowance: Quantity | None = None,
    overtravel_allowance: Quantity | None = None,
) -> Quantity:
    """Hole-finishing time = L_eff / Vf, where Vf = n × f.

    Composed from Stage 3A.

    Args:
        spindle_speed: n in rpm.
        feed_per_rev: f in mm/rev.
        operation_length: in mm (>= 0).
        approach_allowance: in mm (>= 0), optional.
        overtravel_allowance: in mm (>= 0), optional.
    Returns:
        Machining time in min.
    """
    travel = effective_hole_finishing_travel(
        operation_length, approach_allowance, overtravel_allowance
    )
    vf = feed_rate_from_rpm_feed_per_rev(spindle_speed, feed_per_rev)
    return machining_time_from_distance_feed_rate(travel, vf)
