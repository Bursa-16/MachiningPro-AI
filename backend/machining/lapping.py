"""
MachiningPro AI — Lapping Engineering Core (Stage 3L)

Pure deterministic lapping calculations.

CLASSIFICATION GUIDE
--------------------
DETERMINISTIC  : pressure, volume, thickness, MRR-from-measurements,
                 cycle-time-from-MRR — in this module
EMPIRICAL      : Preston model, Preston K coefficient, abrasive grades,
                 slurry concentration, plate material — NOT in this module
MANUFACTURER_DERIVED : K_p values — must come from provenance-verified records
AI_ADVISORY    : process selection, parameter tuning — NOT here

THICKNESS UNIT CONVENTION
--------------------------
All thickness values (removed_thickness, target_thickness) are expressed
in MM (millimetres), NOT micrometres.

Rationale: Unit.UM is not currently in the Unit enum [ASSUMPTION A2].
The lapping engineering core uses MM throughout for dimensional consistency
with the rest of the machining domain.

Callers working at micrometre precision must convert:
    1 µm = 0.001 mm   (e.g., 3 µm → Quantity.of("0.003", Unit.MM))

PRESTON MODEL CLASSIFICATION
-----------------------------
The Preston equation:
    MRR_vol = K_p × P × v_r

is classified as EMPIRICAL.  It is NOT implemented as a deterministic rule
in this module.  It is provided as a clearly-named empirical evaluator:

    estimate_lapping_removal_rate_preston(K_p, pressure, relative_speed)

Requirements enforced at call time:
    - K_p must be supplied (no default)
    - K_p must carry a verified Provenance record
    - missing or unprovenanced K_p → MachiningMathError (fail closed)

This function is intentionally separated from the deterministic rules
(R-3001–R-3005) to make the empirical boundary explicit.
"""
from __future__ import annotations

from decimal import Decimal

from backend.domain.base import Provenance
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _chk(qty: Quantity, expected: Unit, name: str) -> None:
    if qty.unit is not expected:
        raise MachiningMathError(
            f"{name}: expected unit {expected.value!r}, "
            f"got {qty.unit.value!r}"
        )


def _pos(qty: Quantity, name: str) -> None:
    if qty.value <= Decimal("0"):
        raise MachiningMathError(
            f"{name} must be strictly positive; "
            f"got {qty.value} {qty.unit.value}"
        )


def _pos_decimal(value: Decimal, name: str) -> None:
    if value <= Decimal("0"):
        raise MachiningMathError(
            f"{name} must be strictly positive; got {value}"
        )


# ---------------------------------------------------------------------------
# R-3001  Lapping contact pressure
# ---------------------------------------------------------------------------

def lapping_contact_pressure(
    normal_force: Quantity,
    contact_area_mm2: Decimal,
) -> Quantity:
    """
    R-3001 — P = F / A

    Lapping pressure from applied normal force and workpiece contact area.

    Parameters
    ----------
    normal_force : Quantity[N]
        Normal force applied to the workpiece via lap plate or fixture.
    contact_area_mm2 : Decimal
        Workpiece–lap interface contact area in mm².
        Supplied as raw Decimal because Unit.MM2 is not in the current
        Unit enum. [ASSUMPTION A2]

    Returns
    -------
    Quantity[MPA]
        1 N / mm² = 1 MPa (dimensional identity — exact, no coefficient).

    Validity
    --------
    normal_force > 0; contact_area_mm2 > 0.

    Notes
    -----
    DETERMINISTIC.
    Typical ranges: 0.005–0.200 MPa (metals); 0.001–0.020 MPa (optics).
    """
    _chk(normal_force, Unit.N, "normal_force")
    _pos(normal_force, "normal_force")
    _pos_decimal(contact_area_mm2, "contact_area_mm2")

    pressure = normal_force.value / contact_area_mm2
    return Quantity.of(pressure, Unit.MPA)


# ---------------------------------------------------------------------------
# R-3002  Lapping removed volume
# ---------------------------------------------------------------------------

def lapping_removed_volume(
    contact_area_mm2: Decimal,
    removed_thickness: Quantity,
) -> Quantity:
    """
    R-3002 — V = A × Δh

    Volume of material removed from the workpiece surface.

    Parameters
    ----------
    contact_area_mm2 : Decimal
        Contact area in mm² (see R-3001 note on unit absence).
    removed_thickness : Quantity[MM]
        Linear depth of material removed. Express in MM.
        Example: 3 µm → Quantity.of("0.003", Unit.MM).

    Returns
    -------
    Quantity[MM3]

    Validity
    --------
    contact_area_mm2 > 0; removed_thickness > 0.

    Notes
    -----
    GEOMETRIC_MODEL.
    """
    _pos_decimal(contact_area_mm2, "contact_area_mm2")
    _chk(removed_thickness, Unit.MM, "removed_thickness")
    _pos(removed_thickness, "removed_thickness")

    v = contact_area_mm2 * removed_thickness.value
    return Quantity.of(v, Unit.MM3)


# ---------------------------------------------------------------------------
# R-3003  Volumetric MRR from measured removal and time
# ---------------------------------------------------------------------------

def lapping_volumetric_mrr(
    removed_volume: Quantity,
    process_time: Quantity,
) -> Quantity:
    """
    R-3003 — MRR_vol = V / t

    Volumetric material removal rate computed from a MEASURED removal and
    a measured time.  This is a post-process or in-process measurement
    result, not a prediction.

    Parameters
    ----------
    removed_volume : Quantity[MM3]
    process_time   : Quantity[MIN]

    Returns
    -------
    Quantity[MM3_MIN]

    Validity
    --------
    removed_volume > 0; process_time > 0.

    Notes
    -----
    DETERMINISTIC — given measured inputs.
    This is DISTINCT from the Preston-model MRR estimate.
    Use this when you have measured volume and time.
    Use estimate_lapping_removal_rate_preston() for predictive use.
    """
    _chk(removed_volume, Unit.MM3, "removed_volume")
    _chk(process_time, Unit.MIN, "process_time")
    _pos(removed_volume, "removed_volume")
    _pos(process_time, "process_time")

    mrr = removed_volume.value / process_time.value
    return Quantity.of(mrr, Unit.MM3_MIN)


# ---------------------------------------------------------------------------
# R-3004  Removed thickness from volume and area
# ---------------------------------------------------------------------------

def lapping_removed_thickness(
    removed_volume: Quantity,
    contact_area_mm2: Decimal,
) -> Quantity:
    """
    R-3004 — Δh = V / A

    Inverse of R-3002.  Given a volume and an area, computes the linear
    depth of material removed.

    Parameters
    ----------
    removed_volume   : Quantity[MM3]
    contact_area_mm2 : Decimal  [mm²]

    Returns
    -------
    Quantity[MM]

    Validity
    --------
    removed_volume > 0; contact_area_mm2 > 0.

    Notes
    -----
    DETERMINISTIC.
    """
    _chk(removed_volume, Unit.MM3, "removed_volume")
    _pos(removed_volume, "removed_volume")
    _pos_decimal(contact_area_mm2, "contact_area_mm2")

    delta_h = removed_volume.value / contact_area_mm2
    return Quantity.of(delta_h, Unit.MM)


# ---------------------------------------------------------------------------
# R-3005  Cycle time from volume and MRR
# ---------------------------------------------------------------------------

def lapping_cycle_time(
    target_removed_volume: Quantity,
    volumetric_mrr: Quantity,
) -> Quantity:
    """
    R-3005 — t = V_target / MRR_vol

    Required process time to achieve a target removal volume at a known MRR.

    Parameters
    ----------
    target_removed_volume : Quantity[MM3]
        Volume to be removed to reach target geometry.
    volumetric_mrr        : Quantity[MM3_MIN]
        Volumetric MRR — must come from a MEASURED value (R-3003) or from
        an empirical estimate (estimate_lapping_removal_rate_preston).
        The caller is responsible for the provenance of the MRR value.

    Returns
    -------
    Quantity[MIN]

    Validity
    --------
    target_removed_volume > 0; volumetric_mrr > 0.

    Notes
    -----
    DETERMINISTIC given inputs.
    """
    _chk(target_removed_volume, Unit.MM3, "target_removed_volume")
    _chk(volumetric_mrr, Unit.MM3_MIN, "volumetric_mrr")
    _pos(target_removed_volume, "target_removed_volume")
    _pos(volumetric_mrr, "volumetric_mrr")

    t = target_removed_volume.value / volumetric_mrr.value
    return Quantity.of(t, Unit.MIN)


# ---------------------------------------------------------------------------
# EMPIRICAL EVALUATOR — Preston model (NOT a deterministic rule)
# ---------------------------------------------------------------------------

def estimate_lapping_removal_rate_preston(
    preston_k: Quantity,
    pressure: Quantity,
    relative_speed: Quantity,
    k_provenance: Provenance,
) -> Quantity:
    """
    EMPIRICAL EVALUATOR — Preston (1927) material-removal-rate model.

    MODEL TYPE: EMPIRICAL
    Formula: MRR_vol = K_p × P × v_r
    Classification: NOT deterministic engineering truth.

    This function is intentionally named 'estimate_*' to distinguish it
    from the deterministic rules R-3001–R-3005.

    Parameters
    ----------
    preston_k : Quantity[DIMENSIONLESS]
        Preston coefficient K_p.
        [ASSUMPTION A2] Stored as DIMENSIONLESS because no compound unit
        mm³/(N·min) or equivalent exists in the current Unit enum.
        The caller must ensure dimensional consistency with pressure and
        relative_speed units when interpreting the result.

        K_p MUST be supplied. No default is provided.
        Missing K_p → caller must raise before calling.

    pressure : Quantity[MPA]
        Lapping contact pressure (from R-3001 or equivalent).

    relative_speed : Quantity[M_MIN]
        Relative speed between lap plate and workpiece surface.

    k_provenance : Provenance
        Provenance record for the K_p value.
        MUST have source_reference set (non-None).
        If source_reference is None → MachiningMathError (fail closed).

    Returns
    -------
    Quantity[MM3_MIN]
        Estimated volumetric MRR.
        [ASSUMPTION] Dimensional consistency: K_p in mm³/(N·min),
        P in N/mm², v_r in m/min → MRR in mm³/min after unit conversion.
        Because K_p is stored as DIMENSIONLESS the caller must have
        chosen K_p in consistent units.

    Raises
    ------
    MachiningMathError
        When K_p is zero/negative, pressure is zero/negative,
        relative_speed is zero/negative, or k_provenance is unverified.

    Notes
    -----
    EMPIRICAL — K_p varies with abrasive type, grit size, plate material,
    workpiece material, and slurry concentration. No universal K_p exists.

    Applicability
    -------------
    The Preston model assumes linear MRR dependence on P and v_r.
    Non-linear behaviour at high pressure or speed is not modelled here.
    Site-specific K_p from calibrated testing is the only reliable source.
    """
    # Provenance guard — fail closed if K_p has no source reference
    if k_provenance is None or k_provenance.source_reference is None:
        raise MachiningMathError(
            "Preston coefficient K_p requires a verified Provenance with "
            "source_reference. No global default K_p exists. "
            "Provide a provenance-backed CuttingParameterRecord."
        )

    _chk(preston_k, Unit.DIMENSIONLESS, "preston_k")
    _chk(pressure, Unit.MPA, "pressure")
    _chk(relative_speed, Unit.M_MIN, "relative_speed")
    _pos(preston_k, "preston_k")
    _pos(pressure, "pressure")
    _pos(relative_speed, "relative_speed")

    mrr = preston_k.value * pressure.value * relative_speed.value
    return Quantity.of(mrr, Unit.MM3_MIN)
