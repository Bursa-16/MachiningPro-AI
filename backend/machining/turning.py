"""Deterministic turning calculations (Stage 3B).

Turning-specific engineering geometry and derived process values computed
from EXPLICIT INPUTS. No parameter recommendations.

Scope:
  - external longitudinal turning geometry
  - internal boring geometry
  - pass count from explicit maximum depth-per-pass
  - cutting/travel distance
  - turning machining time (via Stage 3A feed/time functions)
  - removed volume (exact cylindrical annulus geometry)
  - turning material removal rate (exact geometric)
  - facing geometry, time and removed volume

Every function is deterministic, unit-explicit and fail-closed.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal

from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.formulas import (
    feed_rate_from_rpm_feed_per_rev,
    machining_time_from_distance_feed_rate,
)

__all__ = [
    # external turning
    "radial_stock_external",
    "final_diameter_external",
    # boring
    "radial_stock_boring",
    "final_diameter_boring",
    # pass count
    "pass_count",
    "equal_pass_depth",
    # removed volume
    "removed_volume_external",
    "removed_volume_boring",
    # mrr
    "turning_mrr_from_volume_time",
    "turning_mrr_direct",
    # facing
    "facing_travel",
    "facing_removed_volume",
    # longitudinal turning time
    "longitudinal_turning_time",
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


def _dec_ceil(value: Decimal) -> int:
    """Ceiling of a Decimal, always exact (no float)."""
    return int(value.to_integral_value(rounding=ROUND_CEILING))


# ---------------------------------------------------------------------------
# External longitudinal turning
# ---------------------------------------------------------------------------

def radial_stock_external(
    initial_diameter: Quantity,
    final_diameter: Quantity,
) -> Quantity:
    """Radial stock removed in external turning: (D0 - D1) / 2.

    Requires initial_diameter >= final_diameter.
    """
    _require_unit(initial_diameter, Unit.MM, "initial_diameter")
    _require_unit(final_diameter, Unit.MM, "final_diameter")
    _require_positive(initial_diameter.value, "initial_diameter")
    _require_positive(final_diameter.value, "final_diameter")
    if final_diameter.value > initial_diameter.value:
        raise MachiningMathError(
            "external turning: final_diameter cannot exceed initial_diameter "
            f"({final_diameter.value} > {initial_diameter.value})"
        )
    stock = (initial_diameter.value - final_diameter.value) / TWO
    return Quantity(value=stock, unit=Unit.MM)


def final_diameter_external(
    initial_diameter: Quantity,
    radial_depth: Quantity,
) -> Quantity:
    """Final diameter after external turning: D1 = D0 - 2 * ap."""
    _require_unit(initial_diameter, Unit.MM, "initial_diameter")
    _require_unit(radial_depth, Unit.MM, "radial_depth")
    _require_positive(initial_diameter.value, "initial_diameter")
    _require_non_negative(radial_depth.value, "radial_depth")
    final = initial_diameter.value - TWO * radial_depth.value
    if final < 0:
        raise MachiningMathError(
            f"radial_depth {radial_depth.value} removes more than the full "
            f"diameter {initial_diameter.value}"
        )
    return Quantity(value=final, unit=Unit.MM)


# ---------------------------------------------------------------------------
# Internal boring
# ---------------------------------------------------------------------------

def radial_stock_boring(
    initial_diameter: Quantity,
    final_diameter: Quantity,
) -> Quantity:
    """Radial stock removed in boring: (D1 - D0) / 2.

    Requires final_diameter >= initial_diameter.
    """
    _require_unit(initial_diameter, Unit.MM, "initial_diameter")
    _require_unit(final_diameter, Unit.MM, "final_diameter")
    _require_positive(initial_diameter.value, "initial_diameter")
    _require_positive(final_diameter.value, "final_diameter")
    if final_diameter.value < initial_diameter.value:
        raise MachiningMathError(
            "boring: final_diameter cannot be smaller than initial_diameter "
            f"({final_diameter.value} < {initial_diameter.value})"
        )
    stock = (final_diameter.value - initial_diameter.value) / TWO
    return Quantity(value=stock, unit=Unit.MM)


def final_diameter_boring(
    initial_diameter: Quantity,
    radial_depth: Quantity,
) -> Quantity:
    """Final bore diameter after boring: D1 = D0 + 2 * ap."""
    _require_unit(initial_diameter, Unit.MM, "initial_diameter")
    _require_unit(radial_depth, Unit.MM, "radial_depth")
    _require_positive(initial_diameter.value, "initial_diameter")
    _require_non_negative(radial_depth.value, "radial_depth")
    final = initial_diameter.value + TWO * radial_depth.value
    return Quantity(value=final, unit=Unit.MM)


# ---------------------------------------------------------------------------
# Pass count
# ---------------------------------------------------------------------------

def pass_count(
    total_radial_stock: Quantity,
    max_radial_depth_per_pass: Quantity,
) -> int:
    """ceil(total_radial_stock / max_radial_depth_per_pass).

    Zero stock -> zero passes. max_radial_depth_per_pass must be > 0.
    """
    _require_unit(total_radial_stock, Unit.MM, "total_radial_stock")
    _require_unit(max_radial_depth_per_pass, Unit.MM, "max_radial_depth_per_pass")
    _require_non_negative(total_radial_stock.value, "total_radial_stock")
    _require_positive(max_radial_depth_per_pass.value, "max_radial_depth_per_pass")
    if total_radial_stock.value == 0:
        return 0
    return _dec_ceil(
        total_radial_stock.value / max_radial_depth_per_pass.value
    )


def equal_pass_depth(
    total_radial_stock: Quantity,
    pass_count: int,
) -> Quantity:
    """Actual depth per pass when stock is divided evenly: stock / pass_count."""
    _require_unit(total_radial_stock, Unit.MM, "total_radial_stock")
    _require_non_negative(total_radial_stock.value, "total_radial_stock")
    if not isinstance(pass_count, int) or isinstance(pass_count, bool):
        raise MachiningMathError(
            f"pass_count must be an integer, got {type(pass_count).__name__}"
        )
    if pass_count <= 0:
        raise MachiningMathError(
            f"pass_count must be strictly positive, got {pass_count}"
        )
    depth = total_radial_stock.value / Decimal(pass_count)
    return Quantity(value=depth, unit=Unit.MM)


# ---------------------------------------------------------------------------
# Removed volume (exact cylindrical annulus geometry)
# ---------------------------------------------------------------------------

def removed_volume_external(
    initial_diameter: Quantity,
    final_diameter: Quantity,
    axial_length: Quantity,
) -> Quantity:
    """V = (pi/4) * (D0^2 - D1^2) * L."""
    _require_unit(initial_diameter, Unit.MM, "initial_diameter")
    _require_unit(final_diameter, Unit.MM, "final_diameter")
    _require_unit(axial_length, Unit.MM, "axial_length")
    _require_positive(initial_diameter.value, "initial_diameter")
    _require_positive(final_diameter.value, "final_diameter")
    _require_non_negative(axial_length.value, "axial_length")
    if final_diameter.value > initial_diameter.value:
        raise MachiningMathError(
            "external turning: final_diameter cannot exceed initial_diameter"
        )
    d0 = initial_diameter.value
    d1 = final_diameter.value
    volume = (PI / FOUR) * (d0 * d0 - d1 * d1) * axial_length.value
    return Quantity(value=volume, unit=Unit.MM3)


def removed_volume_boring(
    initial_diameter: Quantity,
    final_diameter: Quantity,
    axial_length: Quantity,
) -> Quantity:
    """V = (pi/4) * (D1^2 - D0^2) * L."""
    _require_unit(initial_diameter, Unit.MM, "initial_diameter")
    _require_unit(final_diameter, Unit.MM, "final_diameter")
    _require_unit(axial_length, Unit.MM, "axial_length")
    _require_positive(initial_diameter.value, "initial_diameter")
    _require_positive(final_diameter.value, "final_diameter")
    _require_non_negative(axial_length.value, "axial_length")
    if final_diameter.value < initial_diameter.value:
        raise MachiningMathError(
            "boring: final_diameter cannot be smaller than initial_diameter"
        )
    d0 = initial_diameter.value
    d1 = final_diameter.value
    volume = (PI / FOUR) * (d1 * d1 - d0 * d0) * axial_length.value
    return Quantity(value=volume, unit=Unit.MM3)


# ---------------------------------------------------------------------------
# Turning material removal rate
# ---------------------------------------------------------------------------

def turning_mrr_from_volume_time(
    removed_volume: Quantity,
    machining_time: Quantity,
) -> Quantity:
    """Average MRR = removed_volume / machining_time."""
    _require_unit(removed_volume, Unit.MM3, "removed_volume")
    _require_unit(machining_time, Unit.MIN, "machining_time")
    _require_non_negative(removed_volume.value, "removed_volume")
    _require_positive(machining_time.value, "machining_time")
    mrr = removed_volume.value / machining_time.value
    return Quantity(value=mrr, unit=Unit.MM3_MIN)


def turning_mrr_direct(
    initial_diameter: Quantity,
    final_diameter: Quantity,
    feed_rate: Quantity,
) -> Quantity:
    """Direct geometric average MRR = (pi/4)*(D0^2 - D1^2) * feed_rate."""
    _require_unit(initial_diameter, Unit.MM, "initial_diameter")
    _require_unit(final_diameter, Unit.MM, "final_diameter")
    _require_unit(feed_rate, Unit.MM_MIN, "feed_rate")
    _require_positive(initial_diameter.value, "initial_diameter")
    _require_positive(final_diameter.value, "final_diameter")
    _require_non_negative(feed_rate.value, "feed_rate")
    if final_diameter.value > initial_diameter.value:
        raise MachiningMathError(
            "external turning: final_diameter cannot exceed initial_diameter"
        )
    d0 = initial_diameter.value
    d1 = final_diameter.value
    mrr = (PI / FOUR) * (d0 * d0 - d1 * d1) * feed_rate.value
    return Quantity(value=mrr, unit=Unit.MM3_MIN)


# ---------------------------------------------------------------------------
# Facing
# ---------------------------------------------------------------------------

def facing_travel(
    outer_diameter: Quantity,
    inner_diameter: Quantity,
    approach_allowance: Quantity | None = None,
    overtravel_allowance: Quantity | None = None,
) -> Quantity:
    """Effective radial facing travel including explicit allowances."""
    _require_unit(outer_diameter, Unit.MM, "outer_diameter")
    _require_unit(inner_diameter, Unit.MM, "inner_diameter")
    _require_positive(outer_diameter.value, "outer_diameter")
    _require_non_negative(inner_diameter.value, "inner_diameter")
    if inner_diameter.value > outer_diameter.value:
        raise MachiningMathError(
            "inner_diameter cannot exceed outer_diameter"
        )
    radial = (outer_diameter.value - inner_diameter.value) / TWO
    extra = Decimal("0")
    if approach_allowance is not None:
        _require_unit(approach_allowance, Unit.MM, "approach_allowance")
        _require_non_negative(approach_allowance.value, "approach_allowance")
        extra += approach_allowance.value
    if overtravel_allowance is not None:
        _require_unit(overtravel_allowance, Unit.MM, "overtravel_allowance")
        _require_non_negative(overtravel_allowance.value, "overtravel_allowance")
        extra += overtravel_allowance.value
    return Quantity(value=radial + extra, unit=Unit.MM)


def facing_removed_volume(
    outer_diameter: Quantity,
    inner_diameter: Quantity,
    face_depth: Quantity,
) -> Quantity:
    """V = (pi/4) * (D_outer^2 - D_inner^2) * face_depth."""
    _require_unit(outer_diameter, Unit.MM, "outer_diameter")
    _require_unit(inner_diameter, Unit.MM, "inner_diameter")
    _require_unit(face_depth, Unit.MM, "face_depth")
    _require_positive(outer_diameter.value, "outer_diameter")
    _require_non_negative(inner_diameter.value, "inner_diameter")
    _require_positive(face_depth.value, "face_depth")
    if inner_diameter.value > outer_diameter.value:
        raise MachiningMathError(
            "inner_diameter cannot exceed outer_diameter"
        )
    d_outer = outer_diameter.value
    d_inner = inner_diameter.value
    volume = (PI / FOUR) * (d_outer * d_outer - d_inner * d_inner) * face_depth.value
    return Quantity(value=volume, unit=Unit.MM3)


# ---------------------------------------------------------------------------
# Longitudinal turning time
# ---------------------------------------------------------------------------

def longitudinal_turning_time(
    spindle_speed: Quantity,
    feed_per_rev: Quantity,
    machining_length: Quantity,
    approach_allowance: Quantity | None = None,
    overtravel_allowance: Quantity | None = None,
) -> Quantity:
    """Turning time = effective_travel / feed_rate.

    effective_travel = machining_length + explicit approach + explicit overtravel.
    No hidden defaults.
    """
    _require_unit(spindle_speed, Unit.RPM, "spindle_speed")
    _require_unit(feed_per_rev, Unit.MM_REV, "feed_per_rev")
    _require_unit(machining_length, Unit.MM, "machining_length")
    _require_non_negative(spindle_speed.value, "spindle_speed")
    _require_non_negative(feed_per_rev.value, "feed_per_rev")
    _require_non_negative(machining_length.value, "machining_length")
    effective = machining_length.value
    if approach_allowance is not None:
        _require_unit(approach_allowance, Unit.MM, "approach_allowance")
        _require_non_negative(approach_allowance.value, "approach_allowance")
        effective += approach_allowance.value
    if overtravel_allowance is not None:
        _require_unit(overtravel_allowance, Unit.MM, "overtravel_allowance")
        _require_non_negative(overtravel_allowance.value, "overtravel_allowance")
        effective += overtravel_allowance.value
    feed_rate = feed_rate_from_rpm_feed_per_rev(spindle_speed, feed_per_rev)
    distance = Quantity(value=effective, unit=Unit.MM)
    return machining_time_from_distance_feed_rate(distance, feed_rate)
