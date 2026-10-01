"""Machine-eligibility resolution for planning operations (Stage 4 — PLANNING-01D).

This module answers exactly one question: *which registered machines are
engineering-feasible for a given* :class:`~backend.domain.operation.Operation`?
It is a thin, read-only query layer over existing MachiningPro engineering
data — it is **not** a second source of truth for machine capability.

Architectural rule (per the governing PLANNING-01A audit and PLANNING-01C
domain model): the planning layer never decides, on its own authority,
whether a machine can perform an operation. That decision is owned by:

* :class:`backend.domain.machine.Machine` — the capability envelope itself
  (spindle range, power, torque, feed, working envelope, supported
  operation types).
* :class:`backend.machines.catalog.MachineCatalog` — the registry and its
  ``find_by_operation()`` query.

This module only orchestrates a call into that existing machinery and wraps
the result in a small, deterministic, fail-closed value object. It never
recreates spindle-speed, power, torque, feed-rate, or working-envelope
checks.

Capability dimension used in this stage
----------------------------------------
Only **operation type** (:attr:`Operation.operation_type`, matched via
``MachineCatalog.find_by_operation()``) is used. The other dimensions the
``Machine``/``backend.machines.validation`` layer already supports —
spindle speed, spindle power, spindle torque, feed rate, working envelope —
require an explicit *requested value* (e.g. ``requested_rpm``,
``required_power``) that nothing in the planning layer computes yet;
deriving those values from cutting parameters is explicitly out of scope
for PLANNING-01D (no cycle-time/machining-formula work happens here). See
``docs/planning/MACHINE_CAPABILITY_INTEGRATION.md`` for the full dimension
audit.

Fail-closed policy
-------------------
* An ``operation`` that is not an actual
  :class:`~backend.domain.operation.Operation` instance is rejected
  (:class:`~backend.planning.exceptions.PlanningError`) — never silently
  coerced or skipped.
* A ``machine_catalog`` that is not an actual
  :class:`~backend.machines.catalog.MachineCatalog` is rejected the same
  way — this also guarantees a "fake planning-local capability map" can
  never be substituted for the real catalog.
* Zero capable machines is a legitimate, explicit result
  (``EligibilityDiagnosticCode.NO_CAPABLE_MACHINE``), never silently
  widened to "assume every machine is eligible."
* A non-``Machine`` record surfacing from the catalog raises
  :class:`~backend.planning.exceptions.InvalidMachineRecordError` rather
  than being coerced or ignored (defense in depth; unreachable through the
  real ``MachineCatalog``, whose own ``register()`` already enforces this).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.domain.base import entity_as_dict
from backend.domain.enums import OperationType
from backend.domain.machine import Machine
from backend.domain.operation import Operation
from backend.machines.catalog import MachineCatalog
from backend.planning.exceptions import InvalidMachineRecordError, PlanningError

__all__ = [
    "EligibilityDiagnosticCode",
    "EligibilityResult",
    "resolve_eligible_machines",
]


class EligibilityDiagnosticCode(StrEnum):
    """Structured, language-neutral outcome code for an eligibility query.

    Codes are data, not user-facing prose — frontend localization of any
    displayed message is a later stage's concern.
    """

    RESOLVED = "resolved"
    """At least one engineering-feasible machine was found."""

    NO_CAPABLE_MACHINE = "no_capable_machine"
    """The catalog was queried successfully but no registered machine
    supports this operation's ``operation_type``. This is a fail-closed
    result, not an error: it means exactly what it says."""


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    """The deterministic outcome of resolving eligible machines for one
    operation.

    This is intentionally **not** stored back onto
    :class:`~backend.planning.models.SchedulingOperation`. See this
    module's docstring and ``docs/planning/MACHINE_CAPABILITY_INTEGRATION.md``
    for why eligibility is kept as a separate, freshly-computed result
    rather than a factory/builder that populates
    ``SchedulingOperation.eligible_machine_ids``.
    """

    operation_id: str
    operation_type: OperationType
    eligible_machine_ids: tuple[str, ...]
    diagnostic_code: EligibilityDiagnosticCode

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


def resolve_eligible_machines(
    operation: Operation,
    machine_catalog: MachineCatalog,
) -> EligibilityResult:
    """Resolve which registered machines are engineering-feasible for
    *operation*.

    Pipeline (see module docstring for the full architectural rule):
        ``Operation.operation_type`` → ``MachineCatalog.find_by_operation()``
        → deterministically ordered ``eligible_machine_ids``.

    Args:
        operation:       An existing, already-constructed
                         :class:`~backend.domain.operation.Operation`. This
                         function does not look operations up by ID — see
                         :func:`backend.planning.routing.resolve_routing_eligibility`
                         for the ID-based bridge.
        machine_catalog: The existing, already-populated
                         :class:`~backend.machines.catalog.MachineCatalog`.
                         This is the sole source of truth for which
                         machines exist and what they support.

    Returns:
        An :class:`EligibilityResult`. ``eligible_machine_ids`` is empty
        (with ``diagnostic_code == NO_CAPABLE_MACHINE``) when no registered
        machine supports the operation's type — this is never treated as
        "no constraint" / "anything goes".

    Raises:
        PlanningError: ``operation`` is not an ``Operation`` instance, or
            ``machine_catalog`` is not a ``MachineCatalog`` instance.
        InvalidMachineRecordError: the catalog returned a non-``Machine``
            record (defense in depth; unreachable via the real catalog).
    """
    if not isinstance(operation, Operation):
        raise PlanningError(
            "operation must be an existing backend.domain.operation.Operation "
            "instance, not a re-derived or partial substitute"
        )
    if not isinstance(machine_catalog, MachineCatalog):
        raise PlanningError(
            "machine_catalog must be an existing backend.machines.catalog."
            "MachineCatalog instance — a planning-local capability map is "
            "not a substitute"
        )

    candidates = machine_catalog.find_by_operation(operation.operation_type)

    for machine in candidates:
        if not isinstance(machine, Machine):
            raise InvalidMachineRecordError(
                "machine_catalog.find_by_operation() returned a non-Machine "
                f"record while resolving eligibility for operation "
                f"{operation.operation_id!r}"
            )

    # Sorted explicitly and independently of the catalog's own ordering
    # guarantee: this function's determinism must not depend on trusting
    # an implementation detail of MachineCatalog.
    eligible_ids = tuple(sorted(machine.machine_id for machine in candidates))

    diagnostic_code = (
        EligibilityDiagnosticCode.RESOLVED
        if eligible_ids
        else EligibilityDiagnosticCode.NO_CAPABLE_MACHINE
    )

    return EligibilityResult(
        operation_id=operation.operation_id,
        operation_type=operation.operation_type,
        eligible_machine_ids=eligible_ids,
        diagnostic_code=diagnostic_code,
    )
