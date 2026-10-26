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

from dataclasses import dataclass, field
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
    "validate_machine_record",
    "MachineRecordValidationResult",
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


# ---------------------------------------------------------------------------
# Catalog-level record validation (V-01 through V-26)
# ---------------------------------------------------------------------------

@dataclass
class MachineRecordValidationResult:
    """Result of catalog-record validation for one MachineCatalogRecord dict."""

    stable_id: str
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def validate_machine_record(record: dict) -> MachineRecordValidationResult:
    """Validate a machine catalog record dict against V-01 through V-26 rules.

    Safety contract
    ---------------
    MISSING_VALUE_AS_ZERO=NO — None fields are never coerced to 0.
    FABRICATED_MACHINE_SPEC=NO — no synthetic values injected.
    UNKNOWN_LIMIT_TREATED_AS_UNLIMITED=NO — absent limits produce warnings,
      not passes.

    Returns :class:`MachineRecordValidationResult` with is_valid, errors,
    and warnings.  Records with errors are not safe to import.
    """
    stable_id = record.get("stable_id", "<unknown>")
    errors: list[str] = []
    warnings: list[str] = []

    # V-01: stable_id must be non-empty string, no whitespace
    sid = record.get("stable_id")
    if not sid or not isinstance(sid, str) or sid != sid.strip():
        errors.append("V-01: stable_id is missing, empty, or contains whitespace")

    # V-02: manufacturer must be non-empty
    if not record.get("manufacturer"):
        errors.append("V-02: manufacturer is required and must be non-empty")

    # V-03: model must be non-empty
    if not record.get("model"):
        errors.append("V-03: model is required and must be non-empty")

    # V-04: machine_type must be non-empty
    if not record.get("machine_type"):
        errors.append("V-04: machine_type is required and must be non-empty")

    # V-05: machine_type_code must be non-empty
    if not record.get("machine_type_code"):
        errors.append("V-05: machine_type_code is required and must be non-empty")

    # V-06: supported_processes must be a non-empty list
    procs = record.get("supported_processes")
    if not procs or not isinstance(procs, list):
        errors.append("V-06: supported_processes must be a non-empty list")

    # V-07: axis_count must be positive integer
    axis_count = record.get("axis_count")
    if axis_count is None or not isinstance(axis_count, int) or axis_count < 1:
        errors.append("V-07: axis_count must be a positive integer")

    # V-08: at least one of turning_capable / milling_capable / drilling_capable must be True
    if not any([
        record.get("turning_capable"),
        record.get("milling_capable"),
        record.get("drilling_capable"),
    ]):
        errors.append(
            "V-08: at least one of turning_capable, milling_capable, "
            "drilling_capable must be True"
        )

    # V-09: source_title must be non-empty
    if not record.get("source_title"):
        errors.append("V-09: source_title is required")

    # V-10: evidence_status must be non-empty
    if not record.get("evidence_status"):
        errors.append("V-10: evidence_status is required")

    # V-11: spindle_max_rpm must be positive when present
    rpm_max = record.get("spindle_max_rpm")
    if rpm_max is not None and (not isinstance(rpm_max, int) or rpm_max <= 0):
        errors.append("V-11: spindle_max_rpm must be a positive integer when provided")

    # V-12: spindle_min_rpm must be positive and < spindle_max_rpm when present
    rpm_min = record.get("spindle_min_rpm")
    if rpm_min is not None:
        if not isinstance(rpm_min, int) or rpm_min <= 0:
            errors.append("V-12: spindle_min_rpm must be a positive integer when provided")
        elif rpm_max is not None and rpm_min >= rpm_max:
            errors.append(
                f"V-12: spindle_min_rpm ({rpm_min}) must be < spindle_max_rpm ({rpm_max})"
            )

    # V-13: spindle_power_kw must be positive when present
    power = record.get("spindle_power_kw")
    if power is not None and (not isinstance(power, (int, float)) or power <= 0):
        errors.append("V-13: spindle_power_kw must be positive when provided")

    # V-14: spindle_torque_nm must be positive when present
    torque = record.get("spindle_torque_nm")
    if torque is not None and (not isinstance(torque, (int, float)) or torque <= 0):
        errors.append("V-14: spindle_torque_nm must be positive when provided")

    # V-15: travel dimensions must be positive when present
    for dim_key in ("travel_x_mm", "travel_y_mm", "travel_z_mm"):
        dim = record.get(dim_key)
        if dim is not None and (not isinstance(dim, (int, float)) or dim <= 0):
            errors.append(f"V-15: {dim_key} must be positive when provided")

    # V-16: table dimensions must be positive when present
    for dim_key in ("table_length_mm", "table_width_mm"):
        dim = record.get(dim_key)
        if dim is not None and (not isinstance(dim, (int, float)) or dim <= 0):
            errors.append(f"V-16: {dim_key} must be positive when provided")

    # V-17: table_load_kg must be positive when present
    tload = record.get("table_load_kg")
    if tload is not None and (not isinstance(tload, (int, float)) or tload <= 0):
        errors.append("V-17: table_load_kg must be positive when provided")

    # V-18: turning-related fields only when turning_capable=True
    if not record.get("turning_capable"):
        for field_name in ("max_turning_diameter_mm", "max_turning_length_mm"):
            if record.get(field_name) is not None:
                warnings.append(
                    f"V-18: {field_name} provided but turning_capable=False"
                )

    # V-19: bar_capacity_mm only when turning_capable=True
    if record.get("bar_capacity_mm") is not None and not record.get("turning_capable"):
        warnings.append("V-19: bar_capacity_mm provided but turning_capable=False")

    # V-20: tool_magazine_capacity must be positive when present
    mag_cap = record.get("tool_magazine_capacity")
    if mag_cap is not None and (not isinstance(mag_cap, int) or mag_cap <= 0):
        errors.append("V-20: tool_magazine_capacity must be a positive integer when provided")

    # V-21: rapid_traverse_mpm must be positive when present
    rapid = record.get("rapid_traverse_mpm")
    if rapid is not None and (not isinstance(rapid, (int, float)) or rapid <= 0):
        errors.append("V-21: rapid_traverse_mpm must be positive when provided")

    # V-22: simultaneous_axis_count must be <= axis_count when present
    sim = record.get("simultaneous_axis_count")
    if sim is not None and axis_count is not None:
        if not isinstance(sim, int) or sim < 1:
            errors.append("V-22: simultaneous_axis_count must be a positive integer")
        elif sim > axis_count:
            errors.append(
                f"V-22: simultaneous_axis_count ({sim}) cannot exceed axis_count ({axis_count})"
            )

    # V-23: capable_5axis_simultaneous requires simultaneous_axis_count == 5
    if record.get("capable_5axis_simultaneous") is True and sim != 5:
        warnings.append(
            "V-23: capable_5axis_simultaneous=True but simultaneous_axis_count != 5"
        )

    # V-24: has_y_axis should be True for LATHE_Y type
    mtc = record.get("machine_type_code", "")
    if mtc == "LATHE_Y" and not record.get("has_y_axis"):
        warnings.append("V-24: machine_type_code=LATHE_Y but has_y_axis=False")

    # V-25: spindle_max_rpm missing — INSUFFICIENT_DATA warning
    if rpm_max is None:
        warnings.append(
            "V-25: spindle_max_rpm is absent — INSUFFICIENT_DATA for spindle checks"
        )

    # V-26: spindle_power_kw missing — INSUFFICIENT_DATA warning
    if power is None:
        warnings.append(
            "V-26: spindle_power_kw is absent — INSUFFICIENT_DATA for power checks"
        )

    return MachineRecordValidationResult(
        stable_id=stable_id,
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
