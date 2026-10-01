"""Deterministic milling calculations (Stage 3C).

Milling-specific engineering geometry and derived process values computed
from EXPLICIT INPUTS.  No parameter recommendations, no empirical constants.

Scope:
  - feed per revolution from tooth count and feed per tooth
  - radial engagement ratio (ae / D)
  - axial engagement ratio (ap / D)
  - milling machining time (composed from Stage 3A shared formulas)
  - milling MRR convenience (composed from Stage 3A shared formula)

Stage 3C REUSES the following Stage 3A shared formulas rather than
duplicating them:

  - spindle_speed_from_cutting_speed  (n = 1000·Vc / π·D)
  - feed_rate_from_rpm_tooth_feed     (Vf = n·z·fz)
  - feed_per_tooth_from_feed_rate     (fz = Vf / (n·z))
  - milling_material_removal_rate     (Q = ap·ae·Vf)
  - machining_time_from_distance_feed_rate  (t = L / Vf)
  - torque_from_power_rpm / power_from_torque_rpm

Every function is deterministic, unit-explicit and fail-closed.
"""

from __future__ import annotations

from decimal import Decimal

from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.formulas import (
    feed_rate_from_rpm_tooth_feed,
    machining_time_from_distance_feed_rate,
    milling_material_removal_rate,
)

__all__ = [
    "feed_per_rev_from_tooth_feed",
    "radial_engagement_ratio",
    "axial_engagement_ratio",
    "milling_machining_time",
    "milling_mrr",
]


def _require_unit(quantity: Quantity, expected: Unit, name: str) -> None:
    """Fail closed when ``quantity`` does not carry ``expected`` unit."""
    if quantity.unit is not expected:
        raise MachiningMathError(
            f"{name} must be in {expected.value}, got {quantity.unit.value}"
        )


def _require_positive(value: Decimal, name: str) -> None:
    """Fail closed when ``value`` is not strictly greater than zero."""
    if value <= 0:
        raise MachiningMathError(
            f"{name} must be strictly positive, got {value}"
        )


def _require_non_negative(value: Decimal, name: str) -> None:
    """Fail closed when ``value`` is negative."""
    if value < 0:
        raise MachiningMathError(
            f"{name} must be non-negative, got {value}"
        )


def _require_positive_int(value: int, name: str) -> None:
    """Validate a positive integer tooth/flute count."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise MachiningMathError(
            f"{name} must be an integer, got {type(value).__name__}"
        )
    if value <= 0:
        raise MachiningMathError(
            f"{name} must be strictly positive, got {value}"
        )


# ---------------------------------------------------------------------------
# Feed per revolution (milling context)
# ---------------------------------------------------------------------------

def feed_per_rev_from_tooth_feed(
    tooth_count: int,
    feed_per_tooth: Quantity,
) -> Quantity:
    """f_rev = z × fz

    Feed per revolution in a milling context: the total feed advance
    per one spindle revolution, computed from tooth count and feed per tooth.

    Args:
        tooth_count: z, positive integer number of flutes/teeth.
        feed_per_tooth: fz in mm/tooth (>= 0).
    Returns:
        Feed per revolution f_rev in mm/rev (>= 0).
    """
    _require_positive_int(tooth_count, "tooth_count")
    _require_unit(feed_per_tooth, Unit.MM_TOOTH, "feed_per_tooth")
    _require_non_negative(feed_per_tooth.value, "feed_per_tooth")

    f_rev = Decimal(tooth_count) * feed_per_tooth.value
    return Quantity(value=f_rev, unit=Unit.MM_REV)


# ---------------------------------------------------------------------------
# Engagement ratios
# ---------------------------------------------------------------------------

def radial_engagement_ratio(
    radial_width: Quantity,
    tool_diameter: Quantity,
) -> Quantity:
    """ae_ratio = ae / D

    Normalized radial engagement as a dimensionless fraction.

    Args:
        radial_width: ae in mm (>= 0).
        tool_diameter: D in mm (> 0).
    Returns:
        Dimensionless ratio (>= 0).
    """
    _require_unit(radial_width, Unit.MM, "radial_width")
    _require_unit(tool_diameter, Unit.MM, "tool_diameter")
    _require_non_negative(radial_width.value, "radial_width")
    _require_positive(tool_diameter.value, "tool_diameter")

    ratio = radial_width.value / tool_diameter.value
    return Quantity(value=ratio, unit=Unit.DIMENSIONLESS)


def axial_engagement_ratio(
    axial_depth: Quantity,
    tool_diameter: Quantity,
) -> Quantity:
    """ap_ratio = ap / D

    Normalized axial engagement as a dimensionless fraction.

    Args:
        axial_depth: ap in mm (>= 0).
        tool_diameter: D in mm (> 0).
    Returns:
        Dimensionless ratio (>= 0).
    """
    _require_unit(axial_depth, Unit.MM, "axial_depth")
    _require_unit(tool_diameter, Unit.MM, "tool_diameter")
    _require_non_negative(axial_depth.value, "axial_depth")
    _require_positive(tool_diameter.value, "tool_diameter")

    ratio = axial_depth.value / tool_diameter.value
    return Quantity(value=ratio, unit=Unit.DIMENSIONLESS)


# ---------------------------------------------------------------------------
# Milling machining time (composition of Stage 3A formulas)
# ---------------------------------------------------------------------------

def milling_machining_time(
    spindle_speed: Quantity,
    tooth_count: int,
    feed_per_tooth: Quantity,
    cutting_distance: Quantity,
) -> Quantity:
    """Milling machining time = L / Vf, where Vf = n × z × fz.

    Composed from Stage 3A shared formulas.  Does NOT include
    approach, retract, rapid, or tool-change time.

    Args:
        spindle_speed: n in rpm (> 0 required for meaningful time).
        tooth_count: z, positive integer.
        feed_per_tooth: fz in mm/tooth (> 0 required for meaningful time).
        cutting_distance: L in mm (>= 0).
    Returns:
        Machining time t in min (>= 0).
    """
    feed_rate = feed_rate_from_rpm_tooth_feed(
        spindle_speed, tooth_count, feed_per_tooth
    )
    return machining_time_from_distance_feed_rate(cutting_distance, feed_rate)


# ---------------------------------------------------------------------------
# Milling MRR convenience (composition of Stage 3A formula)
# ---------------------------------------------------------------------------

def milling_mrr(
    axial_depth: Quantity,
    radial_width: Quantity,
    spindle_speed: Quantity,
    tooth_count: int,
    feed_per_tooth: Quantity,
) -> Quantity:
    """MRR = ap × ae × Vf, where Vf = n × z × fz.

    Convenience function that computes feed rate from milling parameters
    and delegates to the Stage 3A MRR formula.  Result in mm³/min.

    Args:
        axial_depth: ap in mm (>= 0).
        radial_width: ae in mm (>= 0).
        spindle_speed: n in rpm (>= 0).
        tooth_count: z, positive integer.
        feed_per_tooth: fz in mm/tooth (>= 0).
    Returns:
        Material removal rate in mm³/min (>= 0).
    """
    feed_rate = feed_rate_from_rpm_tooth_feed(
        spindle_speed, tooth_count, feed_per_tooth
    )
    return milling_material_removal_rate(axial_depth, radial_width, feed_rate)
