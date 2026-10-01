"""Finite-capacity scheduling orchestration layer (PLANNING-01E; extended
for calendar/shift/maintenance availability in PLANNING-01F and opt-in
sequence-dependent setup/changeover constraints in PLANNING-01G).

This is the first production-facing layer that actually connects the
existing pieces end to end:

``Routing`` (+ caller-supplied ``Operation``/duration/``MachineCatalog``)
    -> :func:`~backend.planning.routing.resolve_routing_eligibility`  (PLANNING-01D)
    -> :func:`~backend.planning.calendar_constraints.resolve_machine_calendars`
       (PLANNING-01F, only when ``machine_calendars`` is supplied)
    -> :class:`~backend.planning.solver_models.SolverProblem`          (PLANNING-01B)
    -> :func:`~backend.planning.optimizer_adapter.solve`               (PLANNING-01B)
    -> independent post-solve validation (this module)
    -> :class:`~backend.planning.models.Schedule` /
       :class:`~backend.planning.models.OptimizationResult`

**Scope.** This is still a finite-capacity scheduling orchestration layer,
not the final production APS feature set. It does not implement a UI, MRP,
tool/fixture/operator/material capacity constraints, rescheduling, or a
frozen horizon. Sequence-dependent setup/changeover is available only when
``setup_keys`` and ``setup_matrices`` are explicitly supplied together. See
``docs/planning/FINITE_CAPACITY_SCHEDULER.md``,
``docs/planning/CALENDAR_CONSTRAINTS.md``, and
``docs/planning/SETUP_CHANGEOVER_CONSTRAINTS.md`` for the full boundary.

**Calendar-awareness is opt-in and fully backward compatible.** Passing
neither ``machine_calendars`` nor ``horizon_end`` reproduces PLANNING-01E's
original behavior exactly (unbounded continuous availability, no calendar
resolution performed at all) — every PLANNING-01E test continues to pass
unmodified against this module. Calendar-awareness is enabled only when
**both** ``machine_calendars`` and ``horizon_end`` are supplied together;
supplying only one of the two is rejected (see
:func:`schedule_routing`'s docstring) rather than left ambiguous.

**Solver isolation.** This module does not import ``ortools`` directly and
never will — it only calls the solver-neutral
:mod:`~backend.planning.optimizer_adapter` API (by default; see
``solve_fn`` below for how tests substitute a fake solver without touching
CP-SAT at all).

**Result reuse.** This module does not invent a new "scheduler result"
type. :class:`~backend.planning.models.OptimizationResult` already encodes
exactly the right invariant for this stage (an ``INFEASIBLE``/``ERROR``
result must not carry a schedule; an ``OPTIMAL``/``FEASIBLE`` result must)
and already exists for a future solver stage to populate — this is that
stage.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.domain.operation import Operation
from backend.machines.catalog import MachineCatalog
from backend.planning import calendar_constraints, optimizer_adapter
from backend.planning.exceptions import (
    InvalidSolverProblemError,
    SchedulerResultValidationError,
)
from backend.planning.models import (
    AvailabilityWindow,
    OptimizationResult,
    OptimizationStatus,
    ResourceCalendar,
    Routing,
    Schedule,
    ScheduleOperation,
    ScheduleOperationStatus,
    SetupMatrix,
)
from backend.planning.routing import resolve_routing_eligibility
from backend.planning.solver_models import (
    SolverAssignment,
    SolverConfig,
    SolverOperation,
    SolverProblem,
    SolverSolution,
    timedelta_offset_to_solver_seconds,
)

__all__ = ["schedule_routing"]


SolveFn = Callable[[SolverProblem, SolverConfig], SolverSolution]


def _require_tz_aware(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise InvalidSolverProblemError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise InvalidSolverProblemError(
            f"{field_name} must be timezone-aware (naive datetimes are rejected)"
        )


def _resolve_setup_matrix_seconds(
    eligibility_by_operation: Mapping[str, tuple[str, ...]],
    setup_keys: Mapping[str, str],
    setup_matrices: Mapping[str, SetupMatrix],
) -> dict[str, dict[tuple[str, str], int]]:
    """Resolve every candidate setup/changeover transition up front.

    For each setup-aware machine, every *ordered pair* of operations that
    could conceivably both land on that machine (i.e. the machine appears in
    both operations' eligible sets) is looked up via
    :meth:`~backend.planning.models.SetupMatrix.lookup` right here, in
    Python, before the solver ever runs. Which pairs actually end up
    adjacent is a solver decision (that is the whole point of the
    direct-adjacency model in :mod:`~backend.planning.optimizer_adapter`),
    but *whether a transition is resolvable at all* is not a solver
    decision -- it is static data, so it is validated statically. This is
    also what keeps ``UnknownSetupTransitionError`` (``NOT_ALLOWED`` policy)
    a fail-closed, build-time error rather than something that could
    surface as a confusing mid-solve failure.

    Raises:
        InvalidSolverProblemError: a ``setup_matrices`` entry is not a
            :class:`SetupMatrix`, its ``machine_id`` does not match its own
            mapping key, or an operation eligible for a setup-aware machine
            has no entry in ``setup_keys``.
        UnknownSetupTransitionError: propagated unchanged from
            :meth:`SetupMatrix.lookup` for any candidate pair whose
            transition is not configured and whose policy is
            ``NOT_ALLOWED``.
    """
    resolved: dict[str, dict[tuple[str, str], int]] = {}
    for machine_id, matrix in setup_matrices.items():
        if not isinstance(matrix, SetupMatrix):
            raise InvalidSolverProblemError(
                f"setup_matrices[{machine_id!r}] must be a SetupMatrix instance"
            )
        if matrix.machine_id != machine_id:
            raise InvalidSolverProblemError(
                f"setup_matrices key {machine_id!r} does not match its own "
                f"SetupMatrix.machine_id {matrix.machine_id!r}"
            )
        candidate_op_ids = sorted(
            op_id
            for op_id, eligible in eligibility_by_operation.items()
            if machine_id in eligible
        )

        def _key_for(op_id: str, *, machine_id: str = machine_id) -> str:
            key = setup_keys.get(op_id)
            if key is None:
                raise InvalidSolverProblemError(
                    f"operation {op_id!r} is eligible for setup-aware machine "
                    f"{machine_id!r} but has no entry in setup_keys"
                )
            return key

        transitions: dict[tuple[str, str], int] = {}
        for from_id in candidate_op_ids:
            from_key = _key_for(from_id)
            for to_id in candidate_op_ids:
                if from_id == to_id:
                    continue
                to_key = _key_for(to_id)
                duration = matrix.lookup(from_key, to_key)
                transitions[(from_key, to_key)] = timedelta_offset_to_solver_seconds(
                    duration, f"setup duration {from_key!r} -> {to_key!r} on {machine_id!r}"
                )
        resolved[machine_id] = transitions
    return resolved


def _build_solver_problem(
    routing: Routing,
    operations: Mapping[str, Operation],
    durations: Mapping[str, timedelta],
    machine_catalog: MachineCatalog,
    *,
    horizon_start: datetime | None = None,
    horizon_end: datetime | None = None,
    machine_calendars: Mapping[str, ResourceCalendar] | None = None,
    setup_keys: Mapping[str, str] | None = None,
    setup_matrices: Mapping[str, SetupMatrix] | None = None,
) -> tuple[
    SolverProblem,
    dict[str, tuple[str, ...]],
    dict[str, tuple[AvailabilityWindow, ...]] | None,
    dict[str, dict[tuple[str, str], int]],
]:
    """Resolve eligibility (and, optionally, calendar availability) and
    build a validated :class:`SolverProblem`.

    Returns a 4-tuple: the problem, a ``{operation_id: eligible_machine_ids}``
    map, either ``None`` (calendar-unaware mode) or a
    ``{machine_id: normalized_windows}`` map (PLANNING-01F), and the resolved
    ``{machine_id: {(from_setup_key, to_setup_key): seconds}}`` transition
    table (empty in setup-unaware mode). The latter three values are retained
    for independent post-solve validation rather than re-derived.

    Raises (all fail-closed, all pre-existing exceptions reused rather than
    duplicated):

    * ``PlanningError`` — ``routing`` is not a ``Routing`` instance.
    * ``UnknownOperationError`` — a routed ``operation_id`` is missing from
      ``operations``.
    * ``OperationIdentityMismatchError`` — an ``operations`` entry's own
      ``operation_id`` disagrees with its mapping key.
    * ``InvalidSolverProblemError`` — a routed operation has no entry in
      ``durations``, a non-positive/lossy duration, zero eligible machines,
      or the overall problem is otherwise structurally invalid.
    * ``PrecedenceCycleError`` — the routing's precedence graph has a cycle.
    * ``InvalidCalendarError`` — (PLANNING-01F, calendar-aware mode only) a
      malformed ``machine_calendars`` mapping, per
      :func:`~backend.planning.calendar_constraints.resolve_machine_calendars`.
    """
    eligibility_results = resolve_routing_eligibility(routing, operations, machine_catalog)

    setup_aware = setup_matrices is not None
    if setup_aware != (setup_keys is not None):
        raise InvalidSolverProblemError(
            "setup_keys and setup_matrices must be supplied together for "
            "setup-aware scheduling, or both omitted for setup-unaware "
            "scheduling matching PLANNING-01E/F's original behavior"
        )

    eligibility_by_operation: dict[str, tuple[str, ...]] = {}
    for result in eligibility_results:
        eligibility_by_operation[result.operation_id] = result.eligible_machine_ids

    setup_matrix_seconds: dict[str, dict[tuple[str, str], int]] = {}
    if setup_aware:
        setup_matrix_seconds = _resolve_setup_matrix_seconds(
            eligibility_by_operation, setup_keys, setup_matrices
        )

    solver_operations = []
    for result in eligibility_results:
        op_id = result.operation_id
        if op_id not in durations:
            raise InvalidSolverProblemError(
                f"no duration supplied for routed operation {op_id!r}; every "
                "routed operation must have exactly one explicit duration"
            )
        solver_operations.append(
            SolverOperation(
                operation_id=op_id,
                duration=durations[op_id],
                eligible_machine_ids=result.eligible_machine_ids,
                predecessor_operation_ids=routing.precedence.get(op_id, ()),
                setup_key=setup_keys.get(op_id) if setup_aware else None,
            )
        )

    calendar_aware = horizon_end is not None or machine_calendars is not None
    normalized_availability: dict[str, tuple[AvailabilityWindow, ...]] | None = None
    machine_availability: dict[str, tuple] = {}

    if calendar_aware:
        if horizon_start is None or horizon_end is None:
            # schedule_routing() already enforces "both or neither" before
            # calling here -- this is not reachable through the public API,
            # but this function fails closed on its own rather than relying
            # on that caller-side guarantee (or a bare `assert`, which can
            # be stripped entirely under `python -O`).
            raise InvalidSolverProblemError(
                "calendar-aware mode requires both horizon_start and horizon_end"
            )
        all_machine_ids = {
            machine_id
            for result in eligibility_results
            for machine_id in result.eligible_machine_ids
        }
        normalized_availability = calendar_constraints.resolve_machine_calendars(
            all_machine_ids, machine_calendars, machine_catalog, horizon_start, horizon_end
        )
        machine_availability = calendar_constraints.to_solver_availability(
            normalized_availability, horizon_start
        )

    problem = SolverProblem(
        operations=tuple(solver_operations),
        machine_availability=machine_availability,
        setup_matrix_seconds=setup_matrix_seconds,
    )
    return problem, eligibility_by_operation, normalized_availability, setup_matrix_seconds


def _validate_solver_solution(
    problem: SolverProblem,
    solution: SolverSolution,
    routing: Routing,
    machine_catalog: MachineCatalog,
    eligibility_by_operation: Mapping[str, tuple[str, ...]],
    durations: Mapping[str, timedelta],
    *,
    horizon_start: datetime | None = None,
    normalized_availability: Mapping[str, tuple[AvailabilityWindow, ...]] | None = None,
    setup_keys: Mapping[str, str] | None = None,
    setup_matrix_seconds: Mapping[str, Mapping[tuple[str, str], int]] | None = None,
) -> dict[str, timedelta]:
    """Independently re-verify a solver result before it is ever trusted.

    Never relies on the solver's own ``OPTIMAL``/``FEASIBLE`` claim alone —
    see the module docstring and ``docs/planning/FINITE_CAPACITY_SCHEDULER.md``
    for why. Raises :class:`SchedulerResultValidationError` on the first
    defect found.

    When *normalized_availability* is not ``None`` (PLANNING-01F,
    calendar-aware mode), an additional check re-verifies that every
    assignment's absolute ``[start, end)`` (``horizon_start + offset``)
    lies entirely inside one of that machine's normalized availability
    windows. This single check subsumes three of the ticket's named
    concerns at once, by construction rather than by coincidence: a
    normalized window is already maintenance-subtracted and
    horizon-clipped (see :mod:`~backend.planning.calendar_constraints`), so
    "inside a normalized window" already means "not overlapping
    maintenance" and "not outside the horizon" — there is nothing left for
    a separate check to catch that this one would miss.

    When *setup_matrix_seconds* is non-empty (PLANNING-01G, setup-aware
    mode), an additional independent check re-derives, purely from each
    machine's achieved timeline (sorted by ``start``), which pairs of
    operations actually ended up immediately consecutive, and re-verifies
    the solver honored the required setup/changeover gap for exactly those
    pairs -- never for any other pair. This is deliberately independent of
    whichever CP-SAT circuit arcs the solver internally chose (those are not
    exposed in :class:`SolverSolution` at all): "adjacent" here means
    "adjacent in the achieved schedule," the only definition that matters
    for correctness. Returns a ``{operation_id: required_setup_duration}``
    mapping for every non-first operation on a setup-aware machine (empty
    when setup-unaware), used by the caller to populate
    :attr:`~backend.planning.models.ScheduleOperation.setup_start`/``setup_end``.
    """
    setup_durations_by_operation: dict[str, timedelta] = {}
    problem_op_ids = {op.operation_id for op in problem.operations}
    assignment_op_ids = [a.operation_id for a in solution.assignments]

    if len(assignment_op_ids) != len(set(assignment_op_ids)):
        raise SchedulerResultValidationError(
            "solver result contains duplicate operation_id assignments"
        )

    assigned_ids = set(assignment_op_ids)
    unknown_op_ids = assigned_ids - problem_op_ids
    if unknown_op_ids:
        raise SchedulerResultValidationError(
            f"solver result references unknown operation_id(s): {sorted(unknown_op_ids)}"
        )
    missing_op_ids = problem_op_ids - assigned_ids
    if missing_op_ids:
        raise SchedulerResultValidationError(
            "solver result is missing assignment(s) for operation_id(s): "
            f"{sorted(missing_op_ids)}"
        )

    by_operation: dict[str, SolverAssignment] = {a.operation_id: a for a in solution.assignments}
    assignments_by_machine: dict[str, list[SolverAssignment]] = {}

    for op_id, assignment in by_operation.items():
        if not machine_catalog.has(assignment.machine_id):
            raise SchedulerResultValidationError(
                f"solver result assigns operation {op_id!r} to machine "
                f"{assignment.machine_id!r}, which is not registered in machine_catalog"
            )
        eligible = eligibility_by_operation[op_id]
        if assignment.machine_id not in eligible:
            raise SchedulerResultValidationError(
                f"solver result assigns operation {op_id!r} to machine "
                f"{assignment.machine_id!r}, which is not in its eligible set {eligible}"
            )
        if assignment.start < timedelta(0):
            raise SchedulerResultValidationError(
                f"solver result for operation {op_id!r} has a negative start offset"
            )
        # SolverAssignment.__post_init__ already guarantees end > start
        # unconditionally for any constructed instance, so this branch is
        # unreachable in practice — it is kept only as cheap defense-in-depth,
        # not because it can actually fire. The load-bearing,
        # scheduler-specific half of this pair is the non-negative start
        # check above, which SolverAssignment does NOT enforce on its own.
        if assignment.end <= assignment.start:
            raise SchedulerResultValidationError(
                f"solver result for operation {op_id!r} has end <= start"
            )
        expected_duration = durations[op_id]
        actual_duration = assignment.end - assignment.start
        if actual_duration != expected_duration:
            raise SchedulerResultValidationError(
                f"solver result for operation {op_id!r} has duration "
                f"{actual_duration}, but {expected_duration} was requested"
            )
        assignments_by_machine.setdefault(assignment.machine_id, []).append(assignment)

    for op_id in routing.ordered_operation_ids:
        for pred_id in routing.precedence.get(op_id, ()):
            if by_operation[pred_id].end > by_operation[op_id].start:
                raise SchedulerResultValidationError(
                    f"solver result violates precedence: {pred_id!r} must finish "
                    f"at or before {op_id!r} starts"
                )

    for machine_id, assignments in assignments_by_machine.items():
        ordered = sorted(assignments, key=lambda a: a.start)
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            if earlier.end > later.start:
                raise SchedulerResultValidationError(
                    "solver result has overlapping assignments on machine "
                    f"{machine_id!r}: {earlier.operation_id!r} and {later.operation_id!r}"
                )

    if normalized_availability is not None:
        if horizon_start is None:
            raise SchedulerResultValidationError(
                "calendar-aware validation requires horizon_start"
            )
        for op_id, assignment in by_operation.items():
            windows = normalized_availability.get(assignment.machine_id, ())
            absolute_start = horizon_start + assignment.start
            absolute_end = horizon_start + assignment.end
            if not any(
                window.start <= absolute_start and absolute_end <= window.end
                for window in windows
            ):
                raise SchedulerResultValidationError(
                    f"solver result assigns operation {op_id!r} to machine "
                    f"{assignment.machine_id!r} at [{absolute_start}, {absolute_end}), "
                    "which does not lie entirely inside one of that machine's "
                    f"normalized availability windows {windows}"
                )

    if solution.assignments:
        if solution.makespan is None:
            raise SchedulerResultValidationError(
                "solver result has non-empty assignments but no reported "
                "makespan; a schedule cannot be built without one"
            )
        max_end = max(a.end for a in solution.assignments)
        if solution.makespan != max_end:
            raise SchedulerResultValidationError(
                f"solver-reported makespan {solution.makespan} does not match "
                f"the maximum assignment end {max_end}"
            )

    if setup_matrix_seconds:
        # setup_keys is guaranteed non-None here: _build_solver_problem only
        # ever produces a non-empty setup_matrix_seconds when setup_keys and
        # setup_matrices were supplied together (enforced there).
        for machine_id, assignments in assignments_by_machine.items():
            transitions = setup_matrix_seconds.get(machine_id)
            if not transitions:
                # This machine has no resolved transition table -- it is not
                # setup-aware (setup_matrix_seconds is opt-in per machine),
                # so nothing about adjacency on it is checked here.
                continue
            ordered = sorted(assignments, key=lambda a: a.start)
            for earlier, later in zip(ordered, ordered[1:], strict=False):
                earlier_key = setup_keys.get(earlier.operation_id)
                later_key = setup_keys.get(later.operation_id)
                if earlier_key is None or later_key is None:
                    # An operation eligible for this machine with no
                    # setup_key would already have been rejected by
                    # SolverProblem's own construction-time cross-check --
                    # this branch is unreachable in practice, kept only as
                    # defense in depth rather than trusted to fire.
                    raise SchedulerResultValidationError(
                        "solver result places an operation with no "
                        f"setup_key on setup-aware machine {machine_id!r}: "
                        f"{earlier.operation_id!r} -> {later.operation_id!r}"
                    )
                required_seconds = transitions.get((earlier_key, later_key))
                if required_seconds is None:
                    raise SchedulerResultValidationError(
                        "solver result places two operations immediately "
                        f"consecutive on machine {machine_id!r} "
                        f"({earlier.operation_id!r} -> {later.operation_id!r}) "
                        f"whose setup transition ({earlier_key!r} -> "
                        f"{later_key!r}) was never resolved -- this pair "
                        "should have been rejected before reaching the solver"
                    )
                required = timedelta(seconds=required_seconds)
                actual_gap = later.start - earlier.end
                if actual_gap < required:
                    raise SchedulerResultValidationError(
                        "solver result violates the required setup/changeover "
                        f"gap on machine {machine_id!r} between directly "
                        f"consecutive operations {earlier.operation_id!r} -> "
                        f"{later.operation_id!r}: achieved gap {actual_gap} is "
                        f"less than the required {required}"
                    )

                # PLANNING-01G P1 fix: the timing gap above is necessary but
                # not sufficient -- it is trivially satisfied by any idle
                # time, calendar-available or not. When this machine is
                # calendar-aware, independently re-verify that the *setup
                # span itself* -- [setup_start, later.end), not merely
                # later's own processing interval -- fits entirely inside
                # ONE of that machine's normalized availability windows.
                # This is what proves the setup never crosses a shift
                # closure and never overlaps a maintenance window (a
                # normalized window is already maintenance-subtracted and
                # horizon-clipped, exactly as the plain calendar check
                # above relies on). Only meaningful for a strictly positive
                # required duration -- a zero-length transition has no span
                # to place anywhere.
                if normalized_availability is not None and required > timedelta(0):
                    if horizon_start is None:
                        raise SchedulerResultValidationError(
                            "calendar-aware setup validation requires horizon_start"
                        )
                    windows = normalized_availability.get(machine_id, ())
                    absolute_setup_start = horizon_start + later.start - required
                    absolute_later_end = horizon_start + later.end
                    if not any(
                        window.start <= absolute_setup_start
                        and absolute_later_end <= window.end
                        for window in windows
                    ):
                        raise SchedulerResultValidationError(
                            "solver result places the setup/changeover for "
                            f"{earlier.operation_id!r} -> {later.operation_id!r} "
                            f"on machine {machine_id!r} at "
                            f"[{absolute_setup_start}, {absolute_later_end}), "
                            "which does not lie entirely inside one of that "
                            f"machine's normalized availability windows {windows} "
                            "-- the setup span crosses a shift closure, "
                            "overlaps maintenance, or leaves the horizon"
                        )

                # The changeover is modeled as finishing exactly at the
                # later operation's start (never later -- "setup_end must be
                # at or before start_time"), taking exactly the required
                # duration regardless of any additional idle time the
                # solver may have left beforehand.
                setup_durations_by_operation[later.operation_id] = required
                # The first operation in each machine's achieved sequence
                # (ordered[0]) deliberately gets no entry here -- no initial
                # setup is ever charged before it (first-operation-no-
                # initial-setup policy), which this loop already enforces by
                # construction: it only ever iterates consecutive *pairs*.

    return setup_durations_by_operation


def schedule_routing(
    routing: Routing,
    operations: Mapping[str, Operation],
    durations: Mapping[str, timedelta],
    machine_catalog: MachineCatalog,
    horizon_start: datetime,
    solver_config: SolverConfig | None = None,
    *,
    schedule_id: str,
    result_id: str,
    scenario_id: str,
    created_at: datetime | None = None,
    solve_fn: SolveFn = optimizer_adapter.solve,
    machine_calendars: Mapping[str, ResourceCalendar] | None = None,
    horizon_end: datetime | None = None,
    setup_keys: Mapping[str, str] | None = None,
    setup_matrices: Mapping[str, SetupMatrix] | None = None,
) -> OptimizationResult:
    """Schedule every operation in *routing* and return an
    :class:`~backend.planning.models.OptimizationResult`.

    setup_keys / setup_matrices (PLANNING-01G): opt-in, sequence-dependent
    setup/changeover modeling. Must be supplied together, or both omitted
    for setup-unaware scheduling matching PLANNING-01E/F's original
    behavior byte-for-byte (an empty ``setup_matrix_seconds`` on the
    resulting ``SolverProblem`` reproduces the exact same CP-SAT model as
    before this stage existed — see
    ``docs/planning/SETUP_CHANGEOVER_CONSTRAINTS.md``). ``setup_keys`` is
    ``operation_id -> setup_key``; only operations that could actually reach
    a setup-aware machine need an entry. ``setup_matrices`` is
    ``machine_id -> SetupMatrix``; a machine with no entry here never has
    setup charged for operations placed on it, even in setup-aware mode.
    Setup is applied *only* between operations that end up directly,
    immediately consecutive on the same machine in the solved schedule —
    never between an operation and some other, non-adjacent one that merely
    precedes it — which is the whole point of this stage (see
    :mod:`~backend.planning.optimizer_adapter`'s module docstring for the
    direct-adjacency model itself).

    Args:
        routing: An existing :class:`~backend.planning.models.Routing`.
        operations: ``operation_id -> Operation`` for every operation
            ``routing`` references. Not looked up or invented — the caller
            supplies real, already-resolved instances.
        durations: ``operation_id -> timedelta`` for every operation
            ``routing`` references. Not calculated here (no cutting-formula
            work happens in this stage) — every routed operation must have
            exactly one caller-supplied, positive, whole-second duration.
        machine_catalog: The existing, already-populated
            :class:`~backend.machines.catalog.MachineCatalog`.
        horizon_start: Timezone-aware. Continuous finite-capacity time
            starts here — see the module/doc note on what this does *not*
            yet mean (no calendars, no shifts, no maintenance windows).
        solver_config: Forwarded to ``solve_fn``. Defaults to
            :class:`~backend.planning.solver_models.SolverConfig`'s
            deterministic defaults when omitted.
        schedule_id: Caller-supplied ID for the resulting
            :class:`~backend.planning.models.Schedule` (only used when a
            schedule is actually produced). This layer does not invent IDs.
        result_id: Caller-supplied ID for the returned
            :class:`~backend.planning.models.OptimizationResult`.
        scenario_id: Caller-supplied scenario reference for the returned
            :class:`~backend.planning.models.OptimizationResult`. This
            stage does not construct or require a
            :class:`~backend.planning.models.Scenario` instance itself.
        created_at: Timezone-aware creation timestamp for the resulting
            ``Schedule``. Defaults to the current UTC time when omitted;
            pass an explicit value for reproducible/deterministic
            construction (e.g. in tests — this is the only source of
            non-determinism this function would otherwise have).
        solve_fn: The solver entry point to call, as
            ``solve_fn(problem, config) -> SolverSolution``. Defaults to
            :func:`backend.planning.optimizer_adapter.solve`. Tests inject
            a fake callable here to exercise the independent post-solve
            validation against a hand-crafted (including deliberately
            malformed) :class:`~backend.planning.solver_models.SolverSolution`
            without touching CP-SAT internals at all.
        machine_calendars: (PLANNING-01F) Caller-supplied
            ``machine_id -> ResourceCalendar`` mapping. Must be supplied
            together with *horizon_end*, or omitted together with it — see
            "Compatibility" below. An eligible machine with no entry here
            is treated as continuously available for
            ``[horizon_start, horizon_end)`` (the documented no-calendar
            policy; see ``docs/planning/CALENDAR_CONSTRAINTS.md``).
        horizon_end: (PLANNING-01F) Timezone-aware, strictly after
            *horizon_start*. Bounds calendar normalization and the CP-SAT
            search space when calendar-awareness is enabled. This is
            **not** the same value as the returned ``Schedule``'s own
            ``horizon_end`` — see "Compatibility" below.

    Compatibility (PLANNING-01E -> PLANNING-01F):
        Passing neither *machine_calendars* nor *horizon_end* reproduces
        PLANNING-01E's original behavior exactly: unbounded continuous
        machine availability, no calendar resolution performed, and the
        returned ``Schedule.horizon_end`` computed as
        ``horizon_start + solution.makespan`` (the *achieved* makespan),
        exactly as PLANNING-01E already documented. Supplying only one of
        *machine_calendars*/*horizon_end* is rejected
        (``InvalidSolverProblemError``) rather than left ambiguous.
        Supplying both enables calendar-aware scheduling; the caller-
        supplied *horizon_end* is used only to bound calendar
        normalization and the solver's search space — the returned
        ``Schedule.horizon_end`` still reflects the actual achieved
        makespan, not the caller-supplied outer bound, since a schedule's
        own horizon should describe the schedule's own span. These are two
        different concepts that happen to share a similar name; see
        ``docs/planning/CALENDAR_CONSTRAINTS.md`` for the full rationale.

    Returns:
        An :class:`~backend.planning.models.OptimizationResult`.
        ``OPTIMAL``/``FEASIBLE`` (and a ``TIME_LIMIT`` that happens to carry
        assignments — see the module doc for why that combination does not
        occur with the current adapter, but is still handled defensively)
        carry a validated ``schedule``. ``INFEASIBLE``/``ERROR`` (and a
        ``TIME_LIMIT`` with no incumbent) carry ``schedule=None`` — no
        result here ever fabricates a schedule the solver did not actually
        produce and this module did not independently verify.

    Raises:
        PlanningError / UnknownOperationError / OperationIdentityMismatchError:
            propagated unchanged from
            :func:`~backend.planning.routing.resolve_routing_eligibility`.
        InvalidSolverProblemError: a missing duration, an invalid duration,
            zero eligible machines for some operation, or an otherwise
            structurally invalid solver problem or config.
        PrecedenceCycleError: the routing's precedence graph has a cycle.
        SchedulerResultValidationError: the solver's result failed
            independent post-solve validation — see
            :func:`_validate_solver_solution`.
    """
    _require_tz_aware(horizon_start, "horizon_start")
    if created_at is not None:
        _require_tz_aware(created_at, "created_at")
    else:
        created_at = datetime.now(UTC)

    calendar_aware = machine_calendars is not None or horizon_end is not None
    if calendar_aware and (machine_calendars is None or horizon_end is None):
        raise InvalidSolverProblemError(
            "machine_calendars and horizon_end must be supplied together for "
            "calendar-aware scheduling, or both omitted for calendar-unaware "
            "scheduling matching PLANNING-01E's original behavior"
        )
    if calendar_aware:
        _require_tz_aware(horizon_end, "horizon_end")
        if horizon_end <= horizon_start:
            raise InvalidSolverProblemError("horizon_end must be strictly after horizon_start")

    if solver_config is None:
        solver_config = SolverConfig()

    problem, eligibility_by_operation, normalized_availability, setup_matrix_seconds = (
        _build_solver_problem(
            routing,
            operations,
            durations,
            machine_catalog,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            machine_calendars=machine_calendars,
            setup_keys=setup_keys,
            setup_matrices=setup_matrices,
        )
    )

    solution = solve_fn(problem, solver_config)

    solve_time = timedelta(seconds=solution.solve_time_seconds)

    produces_schedule = solution.status in (
        OptimizationStatus.OPTIMAL,
        OptimizationStatus.FEASIBLE,
    ) or (solution.status is OptimizationStatus.TIME_LIMIT and bool(solution.assignments))

    if not produces_schedule:
        return OptimizationResult(
            result_id=result_id,
            scenario_id=scenario_id,
            status=solution.status,
            solve_time=solve_time,
            objective_values={},
            schedule=None,
            constraint_violations=(),
            diagnostics=(f"solver reported {solution.status.value} with no schedule",),
        )

    setup_durations_by_operation = _validate_solver_solution(
        problem,
        solution,
        routing,
        machine_catalog,
        eligibility_by_operation,
        durations,
        horizon_start=horizon_start,
        normalized_availability=normalized_availability,
        setup_keys=setup_keys,
        setup_matrix_seconds=setup_matrix_seconds,
    )

    def _setup_fields(operation_id: str, start_time: datetime) -> tuple[
        datetime | None, datetime | None
    ]:
        # PLANNING-01G: populated only for a non-first operation on a
        # setup-aware machine whose independently re-verified required
        # setup duration is strictly positive -- a zero-length transition
        # (e.g. this ticket's "A->B = 0" mandatory case) is not a
        # changeover event worth recording as a window, and
        # ScheduleOperation itself requires setup_end strictly after
        # setup_start whenever both are set. setup_end always lands exactly
        # at start_time (never later), regardless of any additional idle
        # time the solver may have left before this operation.
        required = setup_durations_by_operation.get(operation_id)
        if not required:
            return None, None
        return start_time - required, start_time

    def _build_schedule_operation(assignment: SolverAssignment) -> ScheduleOperation:
        start_time = horizon_start + assignment.start
        setup_start, setup_end = _setup_fields(assignment.operation_id, start_time)
        return ScheduleOperation(
            operation_id=assignment.operation_id,
            machine_id=assignment.machine_id,
            start_time=start_time,
            end_time=horizon_start + assignment.end,
            status=ScheduleOperationStatus.SCHEDULED,
            setup_start=setup_start,
            setup_end=setup_end,
        )

    schedule_operations = tuple(
        _build_schedule_operation(assignment) for assignment in solution.assignments
    )

    # solution.makespan is guaranteed non-None here without relying on a
    # Python `assert` (which can be stripped entirely under `python -O`):
    # `produces_schedule` being True together with a successful
    # `_validate_solver_solution` call means `solution.assignments` is
    # non-empty (an empty-assignments result against a non-empty
    # SolverProblem always fails the missing-operation check above), and
    # `_validate_solver_solution` explicitly rejects a None makespan
    # whenever assignments are non-empty — see the makespan check there.
    #
    # This is the *achieved* horizon end (start + actual makespan), always
    # computed this way regardless of calendar-awareness -- deliberately
    # distinct from the caller-supplied `horizon_end` parameter above (which
    # only bounds calendar normalization and the solver's search space); see
    # the "Compatibility" section of this function's docstring.
    achieved_horizon_end = horizon_start + solution.makespan

    schedule = Schedule(
        schedule_id=schedule_id,
        horizon_start=horizon_start,
        horizon_end=achieved_horizon_end,
        operations=schedule_operations,
        created_at=created_at,
    )

    objective_values: dict[str, Decimal] = {}
    if solution.objective_value is not None:
        objective_values["makespan_seconds"] = solution.objective_value

    return OptimizationResult(
        result_id=result_id,
        scenario_id=scenario_id,
        status=solution.status,
        solve_time=solve_time,
        objective_values=objective_values,
        schedule=schedule,
        constraint_violations=(),
        diagnostics=(),
    )
