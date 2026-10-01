"""Planning-domain exceptions (Stage 4 — PLANNING-01C).

These exceptions are distinct from
:class:`~backend.domain.exceptions.ValidationError` (which covers *input*
validation raised by ``__post_init__`` on the frozen planning entities) and
from :class:`~backend.empirical.exceptions.EmpiricalDataError` (data-catalog
lookup failures). :class:`PlanningError` and its subclasses cover
*planning-specific* invariant violations that are not simple field
validation, such as a :class:`~backend.planning.models.SetupMatrix` lookup
finding no configured transition under a strict (fail-closed) policy.

Fail-closed policy: a planning invariant violation must never be silently
swallowed or converted into a default value by downstream code.
"""

from __future__ import annotations

from backend.domain.exceptions import DomainError

__all__ = [
    "PlanningError",
    "UnknownSetupTransitionError",
    "UnknownOperationError",
    "InvalidMachineRecordError",
    "OperationIdentityMismatchError",
    "InvalidSolverProblemError",
    "PrecedenceCycleError",
    "SolverExecutionError",
    "SchedulerResultValidationError",
    "InvalidCalendarError",
]


class PlanningError(DomainError):
    """Base class for all planning-domain errors."""


class UnknownSetupTransitionError(PlanningError):
    """Raised by :meth:`~backend.planning.models.SetupMatrix.lookup`.

    Raised when no ``(from_setup_key, to_setup_key)`` entry is configured for
    the requested machine and the matrix's
    :class:`~backend.planning.models.MissingTransitionPolicy` is
    ``NOT_ALLOWED``. See :class:`~backend.planning.models.SetupMatrix` for the
    full missing-transition policy.
    """


class UnknownOperationError(PlanningError):
    """Raised by :func:`~backend.planning.routing.resolve_routing_eligibility`.

    Raised when a routing references an ``operation_id`` that is not present
    in the caller-supplied ``operations`` lookup (Stage 4 — PLANNING-01D).
    This is a reference-integrity failure, not a missing-data situation: the
    caller asserted an operation exists by including its ID in the routing,
    and the lookup did not confirm that assertion.
    """


class InvalidMachineRecordError(PlanningError):
    """Raised by :func:`~backend.planning.eligibility.resolve_eligible_machines`.

    Raised when ``machine_catalog.find_by_operation()`` returns a record that
    is not a :class:`~backend.domain.machine.Machine` instance. This should be
    unreachable through :class:`~backend.machines.catalog.MachineCatalog`
    (whose ``register()`` already enforces this), and exists as defense in
    depth against a future or alternative catalog implementation that does
    not enforce the same guarantee.
    """


class OperationIdentityMismatchError(PlanningError):
    """Raised by :func:`~backend.planning.routing.resolve_routing_eligibility`.

    Raised when the ``operations`` mapping supplied to
    ``resolve_routing_eligibility`` contains, under some ``operation_id``
    key, an :class:`~backend.domain.operation.Operation` whose own
    ``operation_id`` field does not match that key (e.g.
    ``operations["OP10"]`` holding an ``Operation`` whose real
    ``operation_id`` is ``"OP20"``). This is a reference-integrity failure
    distinct from :class:`UnknownOperationError` (a missing key): here the
    key exists, but the value it maps to does not agree with it, which would
    otherwise let a resolved :class:`~backend.planning.eligibility.EligibilityResult`
    silently disagree with its own position in the routing. Never coerced,
    never substituted, never partially resolved.
    """


class InvalidSolverProblemError(PlanningError):
    """Raised by :mod:`~backend.planning.solver_models` and
    :mod:`~backend.planning.optimizer_adapter` (Stage 4 — PLANNING-01B).

    Raised for any structural or configuration defect in a solver-facing
    problem that must be rejected before a CP-SAT model is built: an empty
    problem, a duplicate ``operation_id``, a non-positive or lossily
    sub-second duration, an operation with zero eligible machines, a
    duplicate eligible machine ID, a predecessor referencing an unknown
    operation, a self-predecessor, or an invalid
    :class:`~backend.planning.solver_models.SolverConfig`. Fail-closed: the
    adapter never silently drops a bad constraint or invents a machine
    assignment to route around missing eligibility data.
    """


class PrecedenceCycleError(PlanningError):
    """Raised by :mod:`~backend.planning.solver_models` (Stage 4 — PLANNING-01B).

    Raised when a :class:`~backend.planning.solver_models.SolverProblem`'s
    precedence graph contains a cycle, detected by an explicit deterministic
    graph traversal performed before the CP-SAT model is built. The adapter
    never relies on CP-SAT to expose a cycle indirectly (e.g. via
    ``INFEASIBLE``), since that would not distinguish "genuinely infeasible
    for capacity reasons" from "the input graph itself is malformed."
    """


class SolverExecutionError(PlanningError):
    """Raised by :mod:`~backend.planning.optimizer_adapter` (Stage 4 — PLANNING-01B).

    Wraps an unexpected failure while building or solving the CP-SAT model
    (as opposed to a structural input defect, which raises
    :class:`InvalidSolverProblemError` before the solver is ever invoked).
    The original exception is preserved via exception chaining
    (``raise ... from exc``) rather than swallowed — this adapter never
    converts an unexpected OR-Tools failure into a silently-returned
    default result.
    """


class SchedulerResultValidationError(PlanningError):
    """Raised by :mod:`~backend.planning.scheduler` (Stage 4 — PLANNING-01E).

    Raised when a solver result — whether from the real CP-SAT adapter or
    an injected ``solve_fn`` — fails the scheduler's independent post-solve
    validation: a missing or duplicate operation assignment, an assignment
    to an ineligible or unregistered machine, an end not strictly after
    start, a duration that does not match the requested duration, a
    violated precedence constraint, an overlapping same-machine assignment,
    or a reported makespan that does not match the maximum assignment end.
    The scheduler never constructs a :class:`~backend.planning.models.Schedule`
    from a result that fails this check — a solver reporting ``OPTIMAL`` or
    ``FEASIBLE`` is evidence, not proof, and is independently re-verified
    before being trusted.
    """


class InvalidCalendarError(PlanningError):
    """Raised by :mod:`~backend.planning.calendar_constraints` (Stage 4 — PLANNING-01F).

    Raised for a calendar-*data* defect, kept distinct from a horizon-
    *shape* defect (which raises :class:`InvalidSolverProblemError`, the
    same exception :mod:`~backend.planning.scheduler` already uses for
    every other horizon problem): a ``machine_calendars`` mapping that is
    not an actual mapping, a key that is not a non-empty machine id, a key
    that references a machine not registered in the supplied
    :class:`~backend.machines.catalog.MachineCatalog`, or a value that is
    not an actual :class:`~backend.planning.models.ResourceCalendar`
    instance. Never silently ignored, defaulted, or coerced.
    """
