"""ISO 286-1-style IT grade tolerance table — EPIC_04F.

Uses the standard engineering derivation formula (public domain engineering knowledge).
No copyrighted table text is reproduced.

Standard tolerance unit (i, µm):
  i = 0.45 × D^(1/3) + 0.001 × D
where D is the geometric mean of the size step boundaries (mm).

IT grade multipliers (standard engineering ratios):
  IT5=7i, IT6=10i, IT7=16i, IT8=25i, IT9=40i, IT10=64i, IT11=100i,
  IT12=160i, IT13=250i, IT14=400i, IT15=640i, IT16=1000i, IT17=1600i, IT18=2500i

IT_TOLERANCE_TABLE_IMPLEMENTED=YES
IT_GRADE_RANGE=IT1–IT18
IT_SIZE_RANGE_MM=1–500
"""

from __future__ import annotations

import math

__all__ = [
    "it_tolerance_um",
    "it_tolerance_range_um",
    "IT_GRADE_MIN",
    "IT_GRADE_MAX",
    "IT_SIZE_MIN_MM",
    "IT_SIZE_MAX_MM",
]

IT_GRADE_MIN = 1
IT_GRADE_MAX = 18
IT_SIZE_MIN_MM = 1.0
IT_SIZE_MAX_MM = 500.0

_SIZE_STEPS: list[tuple[float, float]] = [
    (1, 3),
    (3, 6),
    (6, 10),
    (10, 18),
    (18, 30),
    (30, 50),
    (50, 80),
    (80, 120),
    (120, 180),
    (180, 250),
    (250, 315),
    (315, 400),
    (400, 500),
]

# IT1–IT4: precision grades approximated from standard engineering references
_IT_MULTIPLIERS: dict[int, float] = {
    1: 0.8,
    2: 1.2,
    3: 2.0,
    4: 3.0,
    5: 7.0,
    6: 10.0,
    7: 16.0,
    8: 25.0,
    9: 40.0,
    10: 64.0,
    11: 100.0,
    12: 160.0,
    13: 250.0,
    14: 400.0,
    15: 640.0,
    16: 1000.0,
    17: 1600.0,
    18: 2500.0,
}


def _geometric_mean(lo: float, hi: float) -> float:
    return math.sqrt(lo * hi)


def _tolerance_unit_i(d_mm: float) -> float:
    """Standard tolerance unit i in µm for diameter D (mm)."""
    return 0.45 * (d_mm ** (1.0 / 3.0)) + 0.001 * d_mm


def _size_step_for(nominal_mm: float) -> tuple[float, float] | None:
    for lo, hi in _SIZE_STEPS:
        if lo <= nominal_mm <= hi:
            return (lo, hi)
    return None


def it_tolerance_um(it_grade: int, nominal_size_mm: float) -> float | None:
    """Return IT grade tolerance width in µm for the given nominal size.

    Returns None when inputs are outside the supported range.
    IT_GRADE_RANGE=IT1–IT18, IT_SIZE_RANGE_MM=1–500.
    """
    if it_grade < IT_GRADE_MIN or it_grade > IT_GRADE_MAX:
        return None
    if nominal_size_mm < IT_SIZE_MIN_MM or nominal_size_mm > IT_SIZE_MAX_MM:
        return None
    step = _size_step_for(nominal_size_mm)
    if step is None:
        return None
    d_mean = _geometric_mean(step[0], step[1])
    i = _tolerance_unit_i(d_mean)
    return round(_IT_MULTIPLIERS[it_grade] * i, 2)


def it_tolerance_range_um(
    it_grade_min: int,
    it_grade_max: int,
    nominal_size_mm: float,
) -> tuple[float, float] | None:
    """Return (tightest_um, loosest_um) for an IT grade range at a given size.

    Grades are sorted so the return is always (smaller_um, larger_um).
    Returns None when any lookup fails.
    """
    lo_grade = min(it_grade_min, it_grade_max)
    hi_grade = max(it_grade_min, it_grade_max)
    t_lo = it_tolerance_um(lo_grade, nominal_size_mm)
    t_hi = it_tolerance_um(hi_grade, nominal_size_mm)
    if t_lo is None or t_hi is None:
        return None
    return (t_lo, t_hi)
