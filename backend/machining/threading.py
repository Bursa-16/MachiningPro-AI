"""Deterministic threading & tapping calculations (Stage 3E).

Basic thread geometry and synchronized-feed relationships from
EXPLICIT INPUTS.  No standards database, no automatic thread recognition,
no empirical constants.

Scope:
  - lead from pitch and start count
  - pitch from lead and start count
  - threads per unit length
  - thread feed synchronization (Vf = n × lead)
  - spindle speed from feed and lead
  - effective threading travel with explicit allowances
  - threading machining time (composed from Stage 3A)
  - revolutions required

Stage 3E REUSES Stage 3A shared formulas:
  - feed_rate_from_rpm_feed_per_rev   (Vf = n × f, treating lead as f)
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
    "lead_from_pitch",
    "pitch_from_lead",
    "threads_per_mm",
    "thread_feed_rate",
    "spindle_speed_from_thread_feed",
    "effective_threading_travel",
    "threading_machining_time",
    "threading_revolutions",
]


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


def _require_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise MachiningMathError(
            f"{name} must be an integer, got {type(value).__name__}"
        )
    if value <= 0:
        raise MachiningMathError(
            f"{name} must be strictly positive, got {value}"
        )


# ---------------------------------------------------------------------------
# Lead / pitch relationships
# ---------------------------------------------------------------------------

def lead_from_pitch(
    pitch: Quantity,
    number_of_starts: int = 1,
) -> Quantity:
    """lead = pitch × number_of_starts.

    Single-start: lead = pitch.
    Multi-start:  lead = pitch × starts.

    Args:
        pitch: thread pitch in mm/rev (> 0).
        number_of_starts: positive integer (default 1).
    Returns:
        Lead in mm/rev.
    """
    _require_unit(pitch, Unit.MM_REV, "pitch")
    _require_positive(pitch.value, "pitch")
    _require_positive_int(number_of_starts, "number_of_starts")

    lead = pitch.value * Decimal(number_of_starts)
    return Quantity(value=lead, unit=Unit.MM_REV)


def pitch_from_lead(
    lead: Quantity,
    number_of_starts: int = 1,
) -> Quantity:
    """pitch = lead / number_of_starts.

    Args:
        lead: thread lead in mm/rev (> 0).
        number_of_starts: positive integer (default 1).
    Returns:
        Pitch in mm/rev.
    """
    _require_unit(lead, Unit.MM_REV, "lead")
    _require_positive(lead.value, "lead")
    _require_positive_int(number_of_starts, "number_of_starts")

    pitch = lead.value / Decimal(number_of_starts)
    return Quantity(value=pitch, unit=Unit.MM_REV)


def threads_per_mm(
    pitch: Quantity,
) -> Quantity:
    """threads_per_mm = 1 / pitch.

    Returns a dimensionless scalar representing thread count per mm.

    Args:
        pitch: thread pitch in mm/rev (> 0).
    Returns:
        Dimensionless threads-per-mm value.
    """
    _require_unit(pitch, Unit.MM_REV, "pitch")
    _require_positive(pitch.value, "pitch")

    tpmm = Decimal("1") / pitch.value
    return Quantity(value=tpmm, unit=Unit.DIMENSIONLESS)


# ---------------------------------------------------------------------------
# Synchronized feed
# ---------------------------------------------------------------------------

def thread_feed_rate(
    spindle_speed: Quantity,
    lead: Quantity,
) -> Quantity:
    """Vf = n × lead.

    Synchronized threading/tapping feed.  For single-start tapping,
    lead equals pitch, so Vf = n × pitch.

    Composed via Stage 3A feed_rate_from_rpm_feed_per_rev treating
    lead as feed-per-revolution.

    Args:
        spindle_speed: n in rpm (>= 0).
        lead: thread lead in mm/rev (>= 0).
    Returns:
        Feed rate Vf in mm/min.
    """
    return feed_rate_from_rpm_feed_per_rev(spindle_speed, lead)


def spindle_speed_from_thread_feed(
    feed_rate: Quantity,
    lead: Quantity,
) -> Quantity:
    """n = Vf / lead.

    Args:
        feed_rate: Vf in mm/min (>= 0).
        lead: thread lead in mm/rev (> 0).
    Returns:
        Spindle speed n in rpm.
    """
    _require_unit(feed_rate, Unit.MM_MIN, "feed_rate")
    _require_unit(lead, Unit.MM_REV, "lead")
    _require_non_negative(feed_rate.value, "feed_rate")
    _require_positive(lead.value, "lead")

    n = feed_rate.value / lead.value
    return Quantity(value=n, unit=Unit.RPM)


# ---------------------------------------------------------------------------
# Effective threading travel
# ---------------------------------------------------------------------------

def effective_threading_travel(
    thread_length: Quantity,
    approach_allowance: Quantity | None = None,
    overtravel_allowance: Quantity | None = None,
) -> Quantity:
    """L_eff = thread_length + approach + overtravel.

    All allowances explicit.  No hidden constants.

    Args:
        thread_length: nominal thread engagement length in mm (>= 0).
        approach_allowance: explicit approach in mm (>= 0), optional.
        overtravel_allowance: explicit overtravel in mm (>= 0), optional.
    Returns:
        Effective feed travel in mm.
    """
    _require_unit(thread_length, Unit.MM, "thread_length")
    _require_non_negative(thread_length.value, "thread_length")

    total = thread_length.value
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
# Threading machining time
# ---------------------------------------------------------------------------

def threading_machining_time(
    spindle_speed: Quantity,
    lead: Quantity,
    thread_length: Quantity,
    approach_allowance: Quantity | None = None,
    overtravel_allowance: Quantity | None = None,
) -> Quantity:
    """Threading time = L_eff / Vf, where Vf = n × lead.

    Composed from Stage 3A.

    Args:
        spindle_speed: n in rpm.
        lead: thread lead in mm/rev.
        thread_length: in mm (>= 0).
        approach_allowance: in mm (>= 0), optional.
        overtravel_allowance: in mm (>= 0), optional.
    Returns:
        Machining time in min.
    """
    travel = effective_threading_travel(
        thread_length, approach_allowance, overtravel_allowance
    )
    vf = thread_feed_rate(spindle_speed, lead)
    return machining_time_from_distance_feed_rate(travel, vf)


# ---------------------------------------------------------------------------
# Revolutions required
# ---------------------------------------------------------------------------

def threading_revolutions(
    effective_travel: Quantity,
    lead: Quantity,
) -> Quantity:
    """revolutions = effective_travel / lead.

    May be fractional — no silent rounding.

    Args:
        effective_travel: L_eff in mm (>= 0).
        lead: thread lead in mm/rev (> 0).
    Returns:
        Dimensionless revolution count.
    """
    _require_unit(effective_travel, Unit.MM, "effective_travel")
    _require_unit(lead, Unit.MM_REV, "lead")
    _require_non_negative(effective_travel.value, "effective_travel")
    _require_positive(lead.value, "lead")

    revs = effective_travel.value / lead.value
    return Quantity(value=revs, unit=Unit.DIMENSIONLESS)
