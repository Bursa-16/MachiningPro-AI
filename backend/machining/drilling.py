"""Deterministic drilling calculations (Stage 3D).

Drilling-specific engineering geometry and derived process values
from EXPLICIT INPUTS.  No parameter recommendations, no empirical
constants, no automatic drill-point allowances.

Scope:
  - drilling feed rate (Vf = n × f)  — composed from Stage 3A
  - feed per revolution inverse       — composed from Stage 3A
  - effective drilling travel with explicit allowances
  - drilling machining time            — composed from Stage 3A
  - hole cross-sectional area (solid circular)
  - cylindrical volume removed
  - drilling MRR (solid circular)

Stage 3D REUSES the following Stage 3A shared formulas:
  - spindle_speed_from_cutting_speed
  - feed_rate_from_rpm_feed_per_rev
  - feed_per_rev_from_feed_rate
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
    "effective_drilling_travel",
    "drilling_machining_time",
    "hole_cross_sectional_area",
    "cylindrical_hole_volume",
    "drilling_mrr",
]

PI = Decimal("3.14159265358979323846264338327950288419716939937510")
FOUR = Decimal("4")


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


# ---------------------------------------------------------------------------
# Effective drilling travel
# ---------------------------------------------------------------------------

def effective_drilling_travel(
    hole_depth: Quantity,
    approach_allowance: Quantity | None = None,
    breakthrough_allowance: Quantity | None = None,
) -> Quantity:
    """L_eff = depth + approach + breakthrough.

    All allowances are explicit; no automatic drill-point calculation.

    Args:
        hole_depth: nominal hole depth in mm (>= 0).
        approach_allowance: explicit approach in mm (>= 0), optional.
        breakthrough_allowance: explicit breakthrough in mm (>= 0), optional.
    Returns:
        Effective feed travel in mm.
    """
    _require_unit(hole_depth, Unit.MM, "hole_depth")
    _require_non_negative(hole_depth.value, "hole_depth")

    total = hole_depth.value
    if approach_allowance is not None:
        _require_unit(approach_allowance, Unit.MM, "approach_allowance")
        _require_non_negative(approach_allowance.value, "approach_allowance")
        total += approach_allowance.value
    if breakthrough_allowance is not None:
        _require_unit(breakthrough_allowance, Unit.MM, "breakthrough_allowance")
        _require_non_negative(breakthrough_allowance.value, "breakthrough_allowance")
        total += breakthrough_allowance.value
    return Quantity(value=total, unit=Unit.MM)


# ---------------------------------------------------------------------------
# Drilling machining time
# ---------------------------------------------------------------------------

def drilling_machining_time(
    spindle_speed: Quantity,
    feed_per_rev: Quantity,
    hole_depth: Quantity,
    approach_allowance: Quantity | None = None,
    breakthrough_allowance: Quantity | None = None,
) -> Quantity:
    """Drilling time = effective_travel / Vf, where Vf = n × f.

    Composed from Stage 3A shared formulas.  No hidden allowances.

    Args:
        spindle_speed: n in rpm.
        feed_per_rev: f in mm/rev.
        hole_depth: nominal depth in mm (>= 0).
        approach_allowance: explicit in mm (>= 0), optional.
        breakthrough_allowance: explicit in mm (>= 0), optional.
    Returns:
        Machining time t in min.
    """
    travel = effective_drilling_travel(
        hole_depth, approach_allowance, breakthrough_allowance
    )
    feed_rate = feed_rate_from_rpm_feed_per_rev(spindle_speed, feed_per_rev)
    return machining_time_from_distance_feed_rate(travel, feed_rate)


# ---------------------------------------------------------------------------
# Hole cross-sectional area
# ---------------------------------------------------------------------------

def hole_cross_sectional_area(
    diameter: Quantity,
) -> Quantity:
    """A = π × D² / 4.

    Solid circular cross-section only.

    Args:
        diameter: D in mm (> 0).
    Returns:
        Area in mm² (as mm3 unit is unavailable; uses DIMENSIONLESS).

    Note:
        Returns a Quantity with Unit.MM for dimensional consistency
        in the repository.  The actual physical unit is mm².
        Since the domain model does not yet have MM2, this function
        stores the numeric value in mm² with Unit.DIMENSIONLESS and
        documents the semantic unit explicitly.
    """
    _require_unit(diameter, Unit.MM, "diameter")
    _require_positive(diameter.value, "diameter")

    area = PI * diameter.value * diameter.value / FOUR
    return Quantity(value=area, unit=Unit.DIMENSIONLESS)


# ---------------------------------------------------------------------------
# Volume removed (simple cylindrical hole)
# ---------------------------------------------------------------------------

def cylindrical_hole_volume(
    diameter: Quantity,
    depth: Quantity,
) -> Quantity:
    """V = (π × D² / 4) × depth.

    Simple cylindrical hole. Does NOT account for drill-point geometry.

    Args:
        diameter: D in mm (> 0).
        depth: hole depth in mm (>= 0).
    Returns:
        Volume in mm³.
    """
    _require_unit(diameter, Unit.MM, "diameter")
    _require_unit(depth, Unit.MM, "depth")
    _require_positive(diameter.value, "diameter")
    _require_non_negative(depth.value, "depth")

    volume = (PI * diameter.value * diameter.value / FOUR) * depth.value
    return Quantity(value=volume, unit=Unit.MM3)


# ---------------------------------------------------------------------------
# Drilling material removal rate
# ---------------------------------------------------------------------------

def drilling_mrr(
    diameter: Quantity,
    feed_rate: Quantity,
) -> Quantity:
    """Q = (π × D² / 4) × Vf.

    Solid circular drill only.  Not valid for annular cutters,
    trepanning, or boring.

    Args:
        diameter: D in mm (> 0).
        feed_rate: Vf in mm/min (>= 0).
    Returns:
        MRR in mm³/min.
    """
    _require_unit(diameter, Unit.MM, "diameter")
    _require_unit(feed_rate, Unit.MM_MIN, "feed_rate")
    _require_positive(diameter.value, "diameter")
    _require_non_negative(feed_rate.value, "feed_rate")

    mrr = (PI * diameter.value * diameter.value / FOUR) * feed_rate.value
    return Quantity(value=mrr, unit=Unit.MM3_MIN)
