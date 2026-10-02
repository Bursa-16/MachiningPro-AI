"""Deterministic machine-capability validation functions (Stage 3H).

Answers the question:

    "Can this machine safely support this requested machining condition?"

Design principles
-----------------
* Pure functions — no side effects, no I/O, no AI.
* Fail-closed: a missing machine limit is never treated as "no constraint".
  An unknown limit returns :func:`~backend.domain.result.insufficient_data`,
  not PASS.
* No ranking — these functions evaluate ONE machine against ONE requested
  value.  Ranking across machines is a future concern.
* Units are explicit in every check; wrong units are rejected.
* Capability margin is reported as an additional output, not as a scoring
  heuristic.

All returned values are :class:`~backend.domain.result.EngineeringResult`
instances (PASS / WARNING / FAIL / INSUFFICIENT_DATA).

Supported capability checks (by domain model coverage)
-------------------------------------------------------
R-2601  spindle_speed in [machine.spindle_speed_min, machine.spindle_speed_max]
R-2602  feed_rate <= machine.feed_rate_max  (when feed_rate_max is known)
R-2603  required_power <= machine.spindle_power
R-2604  required_torque <= machine.spindle_torque  (when spindle_torque is known)
R-2605  work_envelope: checks requested dimension against machine envelope key

Work-envelope (R-2605) and tool-envelope checks are limited to what the
:class:`~backend.domain.machine.Machine` model explicitly stores in
``working_envelope`` (a ``Mapping[str, Quantity]``).  No invented fields.
"""

from __future__ import annotations

from decimal import Decimal

from backend.domain.machine import Machine
from backend.domain.result import (
    EngineeringResult,
    failure,
    insufficient_data,
    success,
)
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError

__all__ = [
    "check_spindle_speed",
    "check_feed_rate",
    "check_power",
    "check_torque",
    "check_work_envelope_dimension",
]

_RULE_VERSION = "1.0.0"


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


def _margin_quantity(limit: Quantity, requested: Quantity) -> Quantity:
    """Deterministic margin = limit − requested, in the shared unit."""
    return Quantity(value=limit.value - requested.value, unit=limit.unit)


def _utilization(requested: Quantity, limit: Quantity) -> Decimal:
    """Utilization ratio = requested / limit (both same unit, dimensionless)."""
    return requested.value / limit.value


# ---------------------------------------------------------------------------
# R-2601 — Spindle speed
# ---------------------------------------------------------------------------

def check_spindle_speed(
    machine: Machine,
    requested_rpm: Quantity,
) -> EngineeringResult:
    """R-2601: Validate *requested_rpm* against the machine's spindle range.

    Checks both minimum and maximum spindle speed.

    Args:
        machine:       The machine to validate against.
        requested_rpm: Requested spindle speed; must use :attr:`Unit.RPM`.

    Returns:
        ``PASS``  — requested RPM is within [spindle_speed_min, spindle_speed_max].
        ``FAIL``  — requested RPM is outside the machine's range.
        ``FAIL``  — unit mismatch.
    """
    rule_id = "R-2601"

    try:
        _require_unit(requested_rpm, Unit.RPM, "requested_rpm")
        _require_positive(requested_rpm.value, "requested_rpm")
    except MachiningMathError as exc:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            violations=(str(exc),),
            summary="spindle speed validation rejected: invalid input",
        )

    lo = machine.spindle_speed_min.value
    hi = machine.spindle_speed_max.value
    req = requested_rpm.value

    violations: list[str] = []
    if req < lo:
        violations.append(
            f"requested spindle speed {req} rpm is below machine minimum "
            f"{lo} rpm for {machine.machine_id!r}"
        )
    if req > hi:
        violations.append(
            f"requested spindle speed {req} rpm exceeds machine maximum "
            f"{hi} rpm for {machine.machine_id!r}"
        )

    margin_qty = _margin_quantity(machine.spindle_speed_max, requested_rpm)
    util = _utilization(requested_rpm, machine.spindle_speed_max)

    if violations:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            violations=tuple(violations),
            outputs={
                "requested_rpm": requested_rpm,
                "spindle_speed_min": machine.spindle_speed_min,
                "spindle_speed_max": machine.spindle_speed_max,
            },
            summary=(
                f"spindle speed {req} rpm outside machine range "
                f"[{lo}, {hi}] rpm"
            ),
        )

    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
        outputs={
            "requested_rpm": requested_rpm,
            "spindle_speed_min": machine.spindle_speed_min,
            "spindle_speed_max": machine.spindle_speed_max,
            "margin_rpm": margin_qty,
            "utilization_ratio": Quantity(
                value=util.quantize(Decimal("0.0001")),
                unit=Unit.DIMENSIONLESS,
            ),
        },
        summary=(
            f"spindle speed {req} rpm within machine range "
            f"[{lo}, {hi}] rpm for {machine.machine_id!r}"
        ),
    )


# ---------------------------------------------------------------------------
# R-2602 — Feed rate
# ---------------------------------------------------------------------------

def check_feed_rate(
    machine: Machine,
    requested_feed_rate: Quantity,
) -> EngineeringResult:
    """R-2602: Validate *requested_feed_rate* against machine.feed_rate_max.

    Fails closed when ``machine.feed_rate_max`` is ``None`` (unknown limit).

    Args:
        machine:              The machine to validate against.
        requested_feed_rate:  Requested feed rate; must use :attr:`Unit.MM_MIN`.

    Returns:
        ``PASS``              — feed rate within machine limit.
        ``FAIL``              — feed rate exceeds machine limit.
        ``INSUFFICIENT_DATA`` — machine's feed rate limit is unknown.
    """
    rule_id = "R-2602"

    try:
        _require_unit(requested_feed_rate, Unit.MM_MIN, "requested_feed_rate")
        _require_positive(requested_feed_rate.value, "requested_feed_rate")
    except MachiningMathError as exc:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            violations=(str(exc),),
            summary="feed rate validation rejected: invalid input",
        )

    if machine.feed_rate_max is None:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            missing_inputs=("machine.feed_rate_max",),
            summary=(
                f"machine {machine.machine_id!r} does not declare a feed rate "
                "limit; validation refused (fail closed)"
            ),
        )

    limit = machine.feed_rate_max
    req = requested_feed_rate.value

    if req > limit.value:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            violations=(
                f"requested feed rate {req} mm/min exceeds machine maximum "
                f"{limit.value} mm/min for {machine.machine_id!r}",
            ),
            outputs={
                "requested_feed_rate": requested_feed_rate,
                "feed_rate_max": limit,
            },
            summary=f"feed rate {req} mm/min exceeds machine limit {limit.value} mm/min",
        )

    margin_qty = _margin_quantity(limit, requested_feed_rate)
    util = _utilization(requested_feed_rate, limit)

    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
        outputs={
            "requested_feed_rate": requested_feed_rate,
            "feed_rate_max": limit,
            "margin_mm_min": margin_qty,
            "utilization_ratio": Quantity(
                value=util.quantize(Decimal("0.0001")),
                unit=Unit.DIMENSIONLESS,
            ),
        },
        summary=(
            f"feed rate {req} mm/min within machine limit "
            f"{limit.value} mm/min for {machine.machine_id!r}"
        ),
    )


# ---------------------------------------------------------------------------
# R-2603 — Spindle power
# ---------------------------------------------------------------------------

def check_power(
    machine: Machine,
    required_power: Quantity,
) -> EngineeringResult:
    """R-2603: Validate *required_power* against machine.spindle_power.

    ``machine.spindle_power`` is always present (required field on Machine).

    Args:
        machine:        The machine to validate against.
        required_power: Required cutting power; must use :attr:`Unit.KW`.

    Returns:
        ``PASS`` — required power is within machine's declared spindle power.
        ``FAIL`` — required power exceeds machine's spindle power.

    Note:
        No efficiency factor is applied here.  Efficiency is an explicit
        caller concern.  If the caller wants to validate against derated
        power, they must supply the derated value as *required_power*.
    """
    rule_id = "R-2603"

    try:
        _require_unit(required_power, Unit.KW, "required_power")
        _require_positive(required_power.value, "required_power")
    except MachiningMathError as exc:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            violations=(str(exc),),
            summary="power validation rejected: invalid input",
        )

    limit = machine.spindle_power
    req = required_power.value

    if req > limit.value:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            violations=(
                f"required power {req} kW exceeds machine spindle power "
                f"{limit.value} kW for {machine.machine_id!r}",
            ),
            outputs={
                "required_power": required_power,
                "spindle_power": limit,
            },
            summary=(
                f"required power {req} kW exceeds machine spindle power "
                f"{limit.value} kW"
            ),
        )

    margin_qty = _margin_quantity(limit, required_power)
    util = _utilization(required_power, limit)

    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
        outputs={
            "required_power": required_power,
            "spindle_power": limit,
            "margin_kw": margin_qty,
            "utilization_ratio": Quantity(
                value=util.quantize(Decimal("0.0001")),
                unit=Unit.DIMENSIONLESS,
            ),
        },
        summary=(
            f"required power {req} kW within machine spindle power "
            f"{limit.value} kW for {machine.machine_id!r}"
        ),
    )


# ---------------------------------------------------------------------------
# R-2604 — Spindle torque
# ---------------------------------------------------------------------------

def check_torque(
    machine: Machine,
    required_torque: Quantity,
) -> EngineeringResult:
    """R-2604: Validate *required_torque* against machine.spindle_torque.

    Fails closed when ``machine.spindle_torque`` is ``None`` (unknown limit).

    Args:
        machine:         The machine to validate against.
        required_torque: Required torque; must use :attr:`Unit.NM`.

    Returns:
        ``PASS``              — torque within machine limit.
        ``FAIL``              — torque exceeds machine limit.
        ``INSUFFICIENT_DATA`` — machine's spindle torque limit is unknown.
    """
    rule_id = "R-2604"

    try:
        _require_unit(required_torque, Unit.NM, "required_torque")
        _require_positive(required_torque.value, "required_torque")
    except MachiningMathError as exc:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            violations=(str(exc),),
            summary="torque validation rejected: invalid input",
        )

    if machine.spindle_torque is None:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            missing_inputs=("machine.spindle_torque",),
            summary=(
                f"machine {machine.machine_id!r} does not declare a spindle "
                "torque limit; validation refused (fail closed)"
            ),
        )

    limit = machine.spindle_torque
    req = required_torque.value

    if req > limit.value:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            violations=(
                f"required torque {req} Nm exceeds machine spindle torque "
                f"{limit.value} Nm for {machine.machine_id!r}",
            ),
            outputs={
                "required_torque": required_torque,
                "spindle_torque": limit,
            },
            summary=(
                f"required torque {req} Nm exceeds machine spindle torque "
                f"{limit.value} Nm"
            ),
        )

    margin_qty = _margin_quantity(limit, required_torque)
    util = _utilization(required_torque, limit)

    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
        outputs={
            "required_torque": required_torque,
            "spindle_torque": limit,
            "margin_nm": margin_qty,
            "utilization_ratio": Quantity(
                value=util.quantize(Decimal("0.0001")),
                unit=Unit.DIMENSIONLESS,
            ),
        },
        summary=(
            f"required torque {req} Nm within machine spindle torque "
            f"{limit.value} Nm for {machine.machine_id!r}"
        ),
    )


# ---------------------------------------------------------------------------
# R-2605 — Work envelope dimension
# ---------------------------------------------------------------------------

def check_work_envelope_dimension(
    machine: Machine,
    dimension_key: str,
    requested_value: Quantity,
) -> EngineeringResult:
    """R-2605: Validate *requested_value* against a named machine envelope limit.

    The :class:`~backend.domain.machine.Machine` model stores work-envelope
    dimensions in ``working_envelope: Mapping[str, Quantity]`` with
    caller-defined keys (e.g. ``"X"``, ``"Y"``, ``"Z"``).  This function
    performs a deterministic ``requested_value <= envelope[dimension_key]``
    check.

    Fails closed when:
    - *dimension_key* is not in ``machine.working_envelope``.
    - Units of ``requested_value`` and the envelope entry differ.

    Args:
        machine:          The machine to validate against.
        dimension_key:    Key in ``machine.working_envelope`` (e.g. ``"Z"``).
        requested_value:  Requested dimension; must share the unit of the
                          envelope entry for that key.

    Returns:
        ``PASS``              — requested dimension is within envelope.
        ``FAIL``              — requested dimension exceeds envelope.
        ``INSUFFICIENT_DATA`` — dimension key is absent from envelope.
    """
    rule_id = "R-2605"

    envelope = machine.working_envelope
    if dimension_key not in envelope:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            missing_inputs=(f"machine.working_envelope[{dimension_key!r}]",),
            summary=(
                f"machine {machine.machine_id!r} does not declare a "
                f"{dimension_key!r} envelope limit; validation refused"
            ),
        )

    limit = envelope[dimension_key]

    if requested_value.unit is not limit.unit:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            violations=(
                f"unit mismatch for envelope dimension {dimension_key!r}: "
                f"requested {requested_value.unit.value}, "
                f"limit is in {limit.unit.value}",
            ),
            summary="work envelope validation rejected: unit mismatch",
        )

    if not isinstance(requested_value, type(limit)):
        pass  # both are Quantity — unit check above is sufficient

    req = requested_value.value

    if req > limit.value:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            violations=(
                f"requested {dimension_key} dimension {req} {limit.unit.value} "
                f"exceeds machine {dimension_key} envelope "
                f"{limit.value} {limit.unit.value} "
                f"for {machine.machine_id!r}",
            ),
            outputs={
                f"requested_{dimension_key}": requested_value,
                f"envelope_{dimension_key}": limit,
            },
            summary=(
                f"{dimension_key} {req} {limit.unit.value} exceeds "
                f"envelope {limit.value} {limit.unit.value}"
            ),
        )

    margin_qty = _margin_quantity(limit, requested_value)
    util = _utilization(requested_value, limit)

    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
        outputs={
            f"requested_{dimension_key}": requested_value,
            f"envelope_{dimension_key}": limit,
            f"margin_{dimension_key}": margin_qty,
            "utilization_ratio": Quantity(
                value=util.quantize(Decimal("0.0001")),
                unit=Unit.DIMENSIONLESS,
            ),
        },
        summary=(
            f"{dimension_key} {req} {limit.unit.value} within "
            f"envelope {limit.value} {limit.unit.value} "
            f"for {machine.machine_id!r}"
        ),
    )
