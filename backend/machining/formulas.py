"""Deterministic machining formulas (Stage 3A).

Pure mathematical relationships between explicit engineering inputs.
No empirical constants, no material data, no manufacturer recommendations.

Every function:
  * requires explicit :class:`~backend.domain.units.Quantity` inputs with
    canonical units (no implicit conversion);
  * validates units and physical bounds, failing closed on any contract
    violation;
  * returns a :class:`~backend.domain.units.Quantity` with the correct
    canonical unit;
  * uses :class:`decimal.Decimal` throughout for deterministic precision.

Precision policy
-----------------
Pi is taken as a 50-significant-digit Decimal literal, far exceeding any
engineering requirement. All intermediate arithmetic stays in Decimal
(binary float is never introduced inside a formula). Division uses
exact Decimal arithmetic; callers needing rounded display values can
quantize the result.
"""

from __future__ import annotations

from decimal import Decimal

from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError

__all__ = [
    # speed
    "spindle_speed_from_cutting_speed",
    "cutting_speed_from_spindle_speed",
    # turning / drilling feed
    "feed_rate_from_rpm_feed_per_rev",
    "feed_per_rev_from_feed_rate",
    "spindle_speed_from_feed_rate_feed_per_rev",
    # milling feed
    "feed_rate_from_rpm_tooth_feed",
    "feed_per_tooth_from_feed_rate",
    "spindle_speed_from_feed_rate_tooth_feed",
    "tooth_count_from_feed_rate",
    # material removal rate
    "milling_material_removal_rate",
    # machining time
    "machining_time_from_distance_feed_rate",
    # power / torque
    "torque_from_power_rpm",
    "power_from_torque_rpm",
]

# 50-significant-digit pi (Decimal). Far exceeds any engineering need.
PI = Decimal("3.14159265358979323846264338327950288419716939937510")

# Factor 60000 = 60 (s/min) * 1000 (W/kW), used in the kW/Nm/rpm relation.
_KW_NM_RPM_FACTOR = Decimal("60000")


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


def _to_positive_int(value: Decimal, name: str) -> int:
    """Return ``value`` as int after validating it is a positive integer."""
    if value <= 0:
        raise MachiningMathError(f"{name} must be positive, got {value}")
    if value != value.to_integral_value():
        raise MachiningMathError(f"{name} must be an integer, got {value}")
    return int(value)


# ---------------------------------------------------------------------------
# Cutting speed <-> spindle speed
# ---------------------------------------------------------------------------
def spindle_speed_from_cutting_speed(
    cutting_speed: Quantity,
    diameter: Quantity,
) -> Quantity:
    """n = (1000 * Vc) / (pi * D)

    Args:
        cutting_speed: Vc in m/min (>= 0).
        diameter: D in mm (> 0).
    Returns:
        Spindle speed n in rpm (>= 0).
    """
    _require_unit(cutting_speed, Unit.M_MIN, "cutting_speed")
    _require_unit(diameter, Unit.MM, "diameter")
    _require_non_negative(cutting_speed.value, "cutting_speed")
    _require_positive(diameter.value, "diameter")

    rpm = (Decimal("1000") * cutting_speed.value) / (PI * diameter.value)
    return Quantity(value=rpm, unit=Unit.RPM)


def cutting_speed_from_spindle_speed(
    spindle_speed: Quantity,
    diameter: Quantity,
) -> Quantity:
    """Vc = (pi * D * n) / 1000

    Args:
        spindle_speed: n in rpm (>= 0).
        diameter: D in mm (> 0).
    Returns:
        Cutting speed Vc in m/min (>= 0).
    """
    _require_unit(spindle_speed, Unit.RPM, "spindle_speed")
    _require_unit(diameter, Unit.MM, "diameter")
    _require_non_negative(spindle_speed.value, "spindle_speed")
    _require_positive(diameter.value, "diameter")

    vc = (PI * diameter.value * spindle_speed.value) / Decimal("1000")
    return Quantity(value=vc, unit=Unit.M_MIN)


# ---------------------------------------------------------------------------
# Turning / drilling feed relations
# ---------------------------------------------------------------------------
def feed_rate_from_rpm_feed_per_rev(
    spindle_speed: Quantity,
    feed_per_rev: Quantity,
) -> Quantity:
    """fr = n * f

    Args:
        spindle_speed: n in rpm (>= 0).
        feed_per_rev: f in mm/rev (>= 0).
    Returns:
        Feed rate fr in mm/min (>= 0).
    """
    _require_unit(spindle_speed, Unit.RPM, "spindle_speed")
    _require_unit(feed_per_rev, Unit.MM_REV, "feed_per_rev")
    _require_non_negative(spindle_speed.value, "spindle_speed")
    _require_non_negative(feed_per_rev.value, "feed_per_rev")

    fr = spindle_speed.value * feed_per_rev.value
    return Quantity(value=fr, unit=Unit.MM_MIN)


def feed_per_rev_from_feed_rate(
    feed_rate: Quantity,
    spindle_speed: Quantity,
) -> Quantity:
    """f = fr / n

    Args:
        feed_rate: fr in mm/min (>= 0).
        spindle_speed: n in rpm (> 0).
    Returns:
        Feed per revolution f in mm/rev.
    """
    _require_unit(feed_rate, Unit.MM_MIN, "feed_rate")
    _require_unit(spindle_speed, Unit.RPM, "spindle_speed")
    _require_non_negative(feed_rate.value, "feed_rate")
    _require_positive(spindle_speed.value, "spindle_speed")

    f = feed_rate.value / spindle_speed.value
    return Quantity(value=f, unit=Unit.MM_REV)


def spindle_speed_from_feed_rate_feed_per_rev(
    feed_rate: Quantity,
    feed_per_rev: Quantity,
) -> Quantity:
    """n = fr / f

    Args:
        feed_rate: fr in mm/min (>= 0).
        feed_per_rev: f in mm/rev (> 0).
    Returns:
        Spindle speed n in rpm.
    """
    _require_unit(feed_rate, Unit.MM_MIN, "feed_rate")
    _require_unit(feed_per_rev, Unit.MM_REV, "feed_per_rev")
    _require_non_negative(feed_rate.value, "feed_rate")
    _require_positive(feed_per_rev.value, "feed_per_rev")

    n = feed_rate.value / feed_per_rev.value
    return Quantity(value=n, unit=Unit.RPM)


# ---------------------------------------------------------------------------
# Milling feed relations
# ---------------------------------------------------------------------------
def feed_rate_from_rpm_tooth_feed(
    spindle_speed: Quantity,
    tooth_count: int,
    feed_per_tooth: Quantity,
) -> Quantity:
    """fr = n * z * fz

    Args:
        spindle_speed: n in rpm (>= 0).
        tooth_count: z, positive integer number of teeth.
        feed_per_tooth: fz in mm/tooth (>= 0).
    Returns:
        Feed rate fr in mm/min (>= 0).
    """
    _require_unit(spindle_speed, Unit.RPM, "spindle_speed")
    _require_unit(feed_per_tooth, Unit.MM_TOOTH, "feed_per_tooth")
    _require_non_negative(spindle_speed.value, "spindle_speed")
    _require_non_negative(feed_per_tooth.value, "feed_per_tooth")
    if not isinstance(tooth_count, int) or isinstance(tooth_count, bool):
        raise MachiningMathError(
            f"tooth_count must be an integer, got {type(tooth_count).__name__}"
        )
    if tooth_count <= 0:
        raise MachiningMathError(
            f"tooth_count must be strictly positive, got {tooth_count}"
        )

    fr = spindle_speed.value * Decimal(tooth_count) * feed_per_tooth.value
    return Quantity(value=fr, unit=Unit.MM_MIN)


def feed_per_tooth_from_feed_rate(
    feed_rate: Quantity,
    spindle_speed: Quantity,
    tooth_count: int,
) -> Quantity:
    """fz = fr / (n * z)

    Args:
        feed_rate: fr in mm/min (>= 0).
        spindle_speed: n in rpm (> 0).
        tooth_count: z, positive integer number of teeth.
    Returns:
        Feed per tooth fz in mm/tooth.
    """
    _require_unit(feed_rate, Unit.MM_MIN, "feed_rate")
    _require_unit(spindle_speed, Unit.RPM, "spindle_speed")
    _require_non_negative(feed_rate.value, "feed_rate")
    _require_positive(spindle_speed.value, "spindle_speed")
    if not isinstance(tooth_count, int) or isinstance(tooth_count, bool):
        raise MachiningMathError(
            f"tooth_count must be an integer, got {type(tooth_count).__name__}"
        )
    if tooth_count <= 0:
        raise MachiningMathError(
            f"tooth_count must be strictly positive, got {tooth_count}"
        )

    fz = feed_rate.value / (spindle_speed.value * Decimal(tooth_count))
    return Quantity(value=fz, unit=Unit.MM_TOOTH)


def spindle_speed_from_feed_rate_tooth_feed(
    feed_rate: Quantity,
    tooth_count: int,
    feed_per_tooth: Quantity,
) -> Quantity:
    """n = fr / (z * fz)

    Args:
        feed_rate: fr in mm/min (>= 0).
        tooth_count: z, positive integer number of teeth.
        feed_per_tooth: fz in mm/tooth (> 0).
    Returns:
        Spindle speed n in rpm.
    """
    _require_unit(feed_rate, Unit.MM_MIN, "feed_rate")
    _require_unit(feed_per_tooth, Unit.MM_TOOTH, "feed_per_tooth")
    _require_non_negative(feed_rate.value, "feed_rate")
    _require_positive(feed_per_tooth.value, "feed_per_tooth")
    if not isinstance(tooth_count, int) or isinstance(tooth_count, bool):
        raise MachiningMathError(
            f"tooth_count must be an integer, got {type(tooth_count).__name__}"
        )
    if tooth_count <= 0:
        raise MachiningMathError(
            f"tooth_count must be strictly positive, got {tooth_count}"
        )

    n = feed_rate.value / (Decimal(tooth_count) * feed_per_tooth.value)
    return Quantity(value=n, unit=Unit.RPM)


def tooth_count_from_feed_rate(
    feed_rate: Quantity,
    spindle_speed: Quantity,
    feed_per_tooth: Quantity,
) -> int:
    """z = fr / (n * fz)

    Args:
        feed_rate: fr in mm/min (>= 0).
        spindle_speed: n in rpm (> 0).
        feed_per_tooth: fz in mm/tooth (> 0).
    Returns:
        Tooth count z as a positive integer.
    """
    _require_unit(feed_rate, Unit.MM_MIN, "feed_rate")
    _require_unit(spindle_speed, Unit.RPM, "spindle_speed")
    _require_unit(feed_per_tooth, Unit.MM_TOOTH, "feed_per_tooth")
    _require_non_negative(feed_rate.value, "feed_rate")
    _require_positive(spindle_speed.value, "spindle_speed")
    _require_positive(feed_per_tooth.value, "feed_per_tooth")

    z = feed_rate.value / (spindle_speed.value * feed_per_tooth.value)
    return _to_positive_int(z, "tooth_count")


# ---------------------------------------------------------------------------
# Material removal rate (milling)
# ---------------------------------------------------------------------------
def milling_material_removal_rate(
    axial_depth: Quantity,
    radial_width: Quantity,
    feed_rate: Quantity,
) -> Quantity:
    """MRR = ap * ae * fr

    Args:
        axial_depth: ap in mm (>= 0).
        radial_width: ae in mm (>= 0).
        feed_rate: fr in mm/min (>= 0).
    Returns:
        Material removal rate in mm3/min (>= 0).
    """
    _require_unit(axial_depth, Unit.MM, "axial_depth")
    _require_unit(radial_width, Unit.MM, "radial_width")
    _require_unit(feed_rate, Unit.MM_MIN, "feed_rate")
    _require_non_negative(axial_depth.value, "axial_depth")
    _require_non_negative(radial_width.value, "radial_width")
    _require_non_negative(feed_rate.value, "feed_rate")

    mrr = axial_depth.value * radial_width.value * feed_rate.value
    return Quantity(value=mrr, unit=Unit.MM3_MIN)


# ---------------------------------------------------------------------------
# Machining time
# ---------------------------------------------------------------------------
def machining_time_from_distance_feed_rate(
    distance: Quantity,
    feed_rate: Quantity,
) -> Quantity:
    """t = L / fr

    Args:
        distance: L in mm (>= 0).
        feed_rate: fr in mm/min (> 0).
    Returns:
        Machining time t in min (>= 0).
    """
    _require_unit(distance, Unit.MM, "distance")
    _require_unit(feed_rate, Unit.MM_MIN, "feed_rate")
    _require_non_negative(distance.value, "distance")
    _require_positive(feed_rate.value, "feed_rate")

    t = distance.value / feed_rate.value
    return Quantity(value=t, unit=Unit.MIN)


# ---------------------------------------------------------------------------
# Power / torque (rotational SI relation)
# ---------------------------------------------------------------------------
def torque_from_power_rpm(
    power: Quantity,
    spindle_speed: Quantity,
) -> Quantity:
    """T = (P * 60000) / (2 * pi * n)

    SI derivation: P(W) = T(Nm) * omega(rad/s), omega = 2*pi*n/60.
    With P in kW: T(Nm) = P(kW) * 1000 * 60 / (2*pi*n) = P * 60000 / (2*pi*n).

    Args:
        power: P in kW (>= 0).
        spindle_speed: n in rpm (> 0).
    Returns:
        Torque T in Nm (>= 0).
    """
    _require_unit(power, Unit.KW, "power")
    _require_unit(spindle_speed, Unit.RPM, "spindle_speed")
    _require_non_negative(power.value, "power")
    _require_positive(spindle_speed.value, "spindle_speed")

    torque = (power.value * _KW_NM_RPM_FACTOR) / (Decimal("2") * PI * spindle_speed.value)
    return Quantity(value=torque, unit=Unit.NM)


def power_from_torque_rpm(
    torque: Quantity,
    spindle_speed: Quantity,
) -> Quantity:
    """P = (2 * pi * n * T) / 60000

    Inverse of :func:`torque_from_power_rpm`. See that function for the
    SI derivation.

    Args:
        torque: T in Nm (>= 0).
        spindle_speed: n in rpm (>= 0).
    Returns:
        Power P in kW (>= 0).
    """
    _require_unit(torque, Unit.NM, "torque")
    _require_unit(spindle_speed, Unit.RPM, "spindle_speed")
    _require_non_negative(torque.value, "torque")
    _require_non_negative(spindle_speed.value, "spindle_speed")

    power = (Decimal("2") * PI * spindle_speed.value * torque.value) / _KW_NM_RPM_FACTOR
    return Quantity(value=power, unit=Unit.KW)
