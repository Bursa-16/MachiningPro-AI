"""
MachiningPro AI — Honing Engineering Core (Stage 3K)

Pure deterministic honing kinematic and geometric calculations.

All values are computed from EXPLICIT INPUTS only.
No parameter recommendations. No empirical defaults.
Fail-closed on any invalid input or unit mismatch.

Rule ID range: R-2901 – R-2999 (calculation: R-2901–R-2906)

CLASSIFICATION GUIDE
--------------------
DETERMINISTIC  : formulas in this module — reproducible from inputs alone
GEOMETRIC_MODEL: cylindrical annulus volume (R-2906) — exact geometry
EMPIRICAL      : overtravel ratio, stone pressure, grit selection,
                 honing oil selection, cycle-time prediction based on
                 removal rate — NOT in this module
MANUFACTURER_DERIVED : stone/abrasive grades, pressure ranges — NOT here
AI_ADVISORY    : process sequence, parameter suggestions — NOT here

CROSSHATCH ANGLE CONVENTION
----------------------------
The crosshatch angle reported by R-2902 is the INCLUDED ANGLE between the
two crossing groove families, as seen on the bore surface when the bore is
unrolled flat.  It is NOT the angle of a single groove relative to the
bore axis.

  If v_h = stroke speed (axial), v_p = peripheral speed (circumferential):
    half-angle of one groove family = arctan(v_h / v_p)
    included crosshatch angle = 2 × arctan(v_h / v_p)

  Example: v_p = 46 m/min, v_h = 12 m/min
    half-angle ≈ 14.5°   (single groove from bore axis)
    included α ≈ 29.0°   (between the two crossing families)

  This matches ISO 74344 and common industry usage for cylinder-bore
  crosshatch specification.
"""
from __future__ import annotations

import math
from decimal import Decimal

from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError

# ---------------------------------------------------------------------------
# Module-level constant — 50 significant digits, never binary float
# ---------------------------------------------------------------------------

_PI: Decimal = Decimal(
    "3.14159265358979323846264338327950288419716939937510"
)

# ---------------------------------------------------------------------------
# Internal validation helpers
# ---------------------------------------------------------------------------


def _chk(qty: Quantity, expected: Unit, name: str) -> None:
    """Raise MachiningMathError when qty carries the wrong unit."""
    if qty.unit is not expected:
        raise MachiningMathError(
            f"{name}: expected unit {expected.value!r}, "
            f"got {qty.unit.value!r}"
        )


def _pos(qty: Quantity, name: str) -> None:
    """Raise MachiningMathError when qty.value is not strictly positive."""
    if qty.value <= Decimal("0"):
        raise MachiningMathError(
            f"{name} must be strictly positive; "
            f"got {qty.value} {qty.unit.value}"
        )


def _nonneg(qty: Quantity, name: str) -> None:
    """Raise MachiningMathError when qty.value is negative."""
    if qty.value < Decimal("0"):
        raise MachiningMathError(
            f"{name} must be non-negative; "
            f"got {qty.value} {qty.unit.value}"
        )


# ---------------------------------------------------------------------------
# R-2901  Honing peripheral (circumferential) speed
# ---------------------------------------------------------------------------

def honing_peripheral_speed(
    bore_diameter: Quantity,
    spindle_speed: Quantity,
) -> Quantity:
    """
    R-2901 — v_p = (π × D × n) / 1000

    Circumferential speed of the honing stone against the bore wall.

    Parameters
    ----------
    bore_diameter : Quantity[MM]
        Nominal bore diameter at the start of the honing operation.
    spindle_speed : Quantity[RPM]
        Honing spindle rotational speed.

    Returns
    -------
    Quantity[M_MIN]
        Peripheral speed in m/min.

    Validity
    --------
    bore_diameter > 0, spindle_speed > 0.

    Notes
    -----
    DETERMINISTIC — reproducible from inputs alone.
    Typical range: 15–60 m/min for long-stroke internal honing.
    Values above 60 m/min trigger R-2951 (validation rule).
    """
    _chk(bore_diameter, Unit.MM, "bore_diameter")
    _chk(spindle_speed, Unit.RPM, "spindle_speed")
    _pos(bore_diameter, "bore_diameter")
    _pos(spindle_speed, "spindle_speed")

    v_p = (_PI * bore_diameter.value * spindle_speed.value) / Decimal("1000")
    return Quantity.of(v_p, Unit.M_MIN)


# ---------------------------------------------------------------------------
# R-2902  Honing crosshatch INCLUDED angle
# ---------------------------------------------------------------------------

def honing_crosshatch_included_angle(
    stroke_speed: Quantity,
    peripheral_speed: Quantity,
) -> Quantity:
    """
    R-2902 — α_included = 2 × arctan(v_h / v_p)

    Returns the INCLUDED angle between the two crossing groove families.
    See module docstring for the precise convention.

    Parameters
    ----------
    stroke_speed : Quantity[M_MIN]
        Axial reciprocating (stroke) speed.
    peripheral_speed : Quantity[M_MIN]
        Circumferential speed (from R-2901 or supplied directly).

    Returns
    -------
    Quantity[DIMENSIONLESS]
        Included crosshatch angle in degrees.
        Stored as DIMENSIONLESS because Unit.DEGREE is not in the current
        Unit enum; callers must treat the value as degrees.
        [ASSUMPTION A2 — Unit.DEGREE absent]

    Validity
    --------
    peripheral_speed > 0; stroke_speed ≥ 0.
    Zero stroke_speed → α = 0° (pure rotation, no axial component).

    Notes
    -----
    DETERMINISTIC.
    """
    _chk(stroke_speed, Unit.M_MIN, "stroke_speed")
    _chk(peripheral_speed, Unit.M_MIN, "peripheral_speed")
    _nonneg(stroke_speed, "stroke_speed")
    _pos(peripheral_speed, "peripheral_speed")

    ratio = float(stroke_speed.value) / float(peripheral_speed.value)
    alpha_deg = Decimal(str(2.0 * math.degrees(math.atan(ratio))))
    return Quantity.of(alpha_deg, Unit.DIMENSIONLESS)


# ---------------------------------------------------------------------------
# R-2903  Required stroke speed for a target crosshatch angle
# ---------------------------------------------------------------------------

def honing_required_stroke_speed(
    crosshatch_included_angle_deg: Quantity,
    peripheral_speed: Quantity,
) -> Quantity:
    """
    R-2903 — v_h = v_p × tan(α_included / 2)

    Inverse of R-2902.  Given a target included crosshatch angle and the
    peripheral speed, returns the required axial stroke speed.

    Parameters
    ----------
    crosshatch_included_angle_deg : Quantity[DIMENSIONLESS]
        Target included crosshatch angle in degrees (see module convention).
    peripheral_speed : Quantity[M_MIN]

    Returns
    -------
    Quantity[M_MIN]

    Validity
    --------
    peripheral_speed > 0; 0 < α < 180.

    Notes
    -----
    DETERMINISTIC.
    """
    _chk(crosshatch_included_angle_deg, Unit.DIMENSIONLESS, "crosshatch_included_angle_deg")
    _chk(peripheral_speed, Unit.M_MIN, "peripheral_speed")
    _pos(peripheral_speed, "peripheral_speed")

    alpha = float(crosshatch_included_angle_deg.value)
    if not (0.0 < alpha < 180.0):
        raise MachiningMathError(
            f"crosshatch_included_angle_deg must be in (0°, 180°); "
            f"got {alpha:.4f}°"
        )

    v_h = float(peripheral_speed.value) * math.tan(math.radians(alpha / 2.0))
    return Quantity.of(Decimal(str(v_h)), Unit.M_MIN)


# ---------------------------------------------------------------------------
# R-2904  Honing resultant (cutting) speed
# ---------------------------------------------------------------------------

def honing_resultant_speed(
    stroke_speed: Quantity,
    peripheral_speed: Quantity,
) -> Quantity:
    """
    R-2904 — v_c = √(v_p² + v_h²)

    Vector magnitude of the two orthogonal velocity components.

    Parameters
    ----------
    stroke_speed : Quantity[M_MIN]
    peripheral_speed : Quantity[M_MIN]

    Returns
    -------
    Quantity[M_MIN]

    Validity
    --------
    Both inputs ≥ 0; at least one must be > 0.

    Notes
    -----
    DETERMINISTIC.
    Typical range: 12–120 m/min (0.2–2 m/s).
    """
    _chk(stroke_speed, Unit.M_MIN, "stroke_speed")
    _chk(peripheral_speed, Unit.M_MIN, "peripheral_speed")
    _nonneg(stroke_speed, "stroke_speed")
    _nonneg(peripheral_speed, "peripheral_speed")

    if stroke_speed.value == Decimal("0") and peripheral_speed.value == Decimal("0"):
        raise MachiningMathError(
            "At least one of stroke_speed or peripheral_speed must be positive."
        )

    v_h = float(stroke_speed.value)
    v_p = float(peripheral_speed.value)
    v_c = Decimal(str(math.sqrt(v_h ** 2 + v_p ** 2)))
    return Quantity.of(v_c, Unit.M_MIN)


# ---------------------------------------------------------------------------
# R-2905  Honing radial stock removal
# ---------------------------------------------------------------------------

def honing_radial_stock(
    diameter_initial: Quantity,
    diameter_final: Quantity,
) -> Quantity:
    """
    R-2905 — s_radial = (D_final − D_initial) / 2

    For internal bore honing, D_final > D_initial (bore is enlarged).

    Parameters
    ----------
    diameter_initial : Quantity[MM]
        Bore diameter before honing.
    diameter_final : Quantity[MM]
        Target bore diameter after honing.

    Returns
    -------
    Quantity[MM]
        Radial material removed from each side of the bore wall.

    Validity
    --------
    diameter_initial > 0; diameter_final > diameter_initial.

    Notes
    -----
    DETERMINISTIC / GEOMETRIC_MODEL.
    """
    _chk(diameter_initial, Unit.MM, "diameter_initial")
    _chk(diameter_final, Unit.MM, "diameter_final")
    _pos(diameter_initial, "diameter_initial")
    _pos(diameter_final, "diameter_final")

    if diameter_final.value <= diameter_initial.value:
        raise MachiningMathError(
            f"diameter_final ({diameter_final.value} mm) must be greater "
            f"than diameter_initial ({diameter_initial.value} mm). "
            "Honing enlarges the bore; final must exceed initial."
        )

    s = (diameter_final.value - diameter_initial.value) / Decimal("2")
    return Quantity.of(s, Unit.MM)


# ---------------------------------------------------------------------------
# R-2906  Honing removed volume
# ---------------------------------------------------------------------------

def honing_removed_volume(
    diameter_initial: Quantity,
    diameter_final: Quantity,
    bore_length: Quantity,
) -> Quantity:
    """
    R-2906 — V = (π / 4) × (D_final² − D_initial²) × L

    Exact cylindrical annulus volume of material removed during honing.

    Parameters
    ----------
    diameter_initial : Quantity[MM]
    diameter_final   : Quantity[MM]
    bore_length      : Quantity[MM]

    Returns
    -------
    Quantity[MM3]

    Validity
    --------
    diameter_initial > 0; diameter_final > diameter_initial; bore_length > 0.

    Notes
    -----
    GEOMETRIC_MODEL — exact geometry, no empirical coefficients.
    """
    _chk(diameter_initial, Unit.MM, "diameter_initial")
    _chk(diameter_final, Unit.MM, "diameter_final")
    _chk(bore_length, Unit.MM, "bore_length")
    _pos(diameter_initial, "diameter_initial")
    _pos(diameter_final, "diameter_final")
    _pos(bore_length, "bore_length")

    if diameter_final.value <= diameter_initial.value:
        raise MachiningMathError(
            "diameter_final must be greater than diameter_initial."
        )

    d_fin_sq = diameter_final.value ** 2
    d_ini_sq = diameter_initial.value ** 2
    v = (_PI / Decimal("4")) * (d_fin_sq - d_ini_sq) * bore_length.value
    return Quantity.of(v, Unit.MM3)
