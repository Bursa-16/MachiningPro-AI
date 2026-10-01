"""OR-Tools CP-SAT optimizer adapter foundation (PLANNING-01B; extended for
calendar/shift/maintenance availability in PLANNING-01F).

This is the *only* module in the planning package allowed to import
``ortools``. It consumes the solver-neutral
:class:`~backend.planning.solver_models.SolverProblem` /
:class:`~backend.planning.solver_models.SolverConfig` and returns a
solver-neutral :class:`~backend.planning.solver_models.SolverSolution` — no
``CpModel``, ``CpSolver``, ``IntVar``, ``IntervalVar``, or ``BoolVar`` ever
crosses :func:`solve` 's return boundary.

Scope (PLANNING-01B):

* one optional interval per (operation, eligible machine) pair, with
  ``AddExactlyOne`` over the per-operation assignment booleans;
* ``AddNoOverlap`` per machine over the intervals assigned to it;
* simple precedence (``pred.end <= succ.start``);
* a single objective: minimize makespan.

Scope added by PLANNING-01F (machine calendar availability):

* when ``problem.machine_availability`` carries an entry for a given
  (operation, eligible machine) pair, the operation may only use that
  machine if it fits *entirely* inside exactly one of that machine's
  windows — enforced inside the CP-SAT model itself (``OnlyEnforceIf``),
  never as an after-the-fact check;
* a machine is silently excluded from an operation's candidate pool (not
  merely constrained to zero) when none of its windows are even long
  enough to hold the operation's duration, or when it has zero windows at
  all — this keeps the model small and turns "no eligible machine can
  actually do this work in this horizon" into a clean, provable CP-SAT
  ``INFEASIBLE`` rather than a constraint CP-SAT has to discover is always
  false;
* operations are never split across two windows (non-preemptive) — an
  operation either fits entirely inside one window on one machine, or that
  machine cannot be used for it;
* a machine with *no* entry in ``problem.machine_availability`` at all is
  treated as fully calendar-unaware (continuously available) for that
  operation — this is what keeps PLANNING-01B/01E's original behavior
  byte-for-byte unchanged when ``machine_availability`` is empty (the
  default).

Scope added by PLANNING-01G (sequence-dependent setup/changeover):

* setup times are enforced only on the true immediate-successor arcs of a
  per-machine ``AddCircuit`` model; non-adjacent operations are never charged;
* the first operation on a machine carries no initial setup;
* asymmetric transition durations are preserved;
* when calendar-awareness is active, a positive setup plus its successor's
  processing interval must fit inside the same selected availability window.

Explicitly NOT implemented here: tool/fixture/operator/material constraints,
rescheduling, a frozen horizon, multi-objective optimization, or a fallback
solver. Those are later stages. See
``docs/planning/SETUP_CHANGEOVER_CONSTRAINTS.md`` and
``docs/planning/CALENDAR_CONSTRAINTS.md`` for scope and rationale.
"""

from __future__ import annotations

from decimal import Decimal

from ortools.sat.python import cp_model

from backend.planning.exceptions import SolverExecutionError
from backend.planning.models import OptimizationStatus
from backend.planning.solver_models import (
    SolverAssignment,
    SolverAvailabilityWindow,
    SolverConfig,
    SolverProblem,
    SolverSolution,
    solver_seconds_to_timedelta,
    timedelta_to_solver_seconds,
)

__all__ = ["solve", "STATUS_MAP"]


#: Explicit, documented CP-SAT status -> OptimizationStatus mapping.
#:
#: ``cp_model.UNKNOWN`` is mapped to ``TIME_LIMIT`` only as an adapter-level
#: interpretation of "the solver terminated without proving a feasible
#: solution" (it covers both an actual time-limit cutoff and any other
#: termination that leaves the search inconclusive under this adapter's
#: fixed, non-infinite time limit) — it is NEVER mapped to ``FEASIBLE`` or
#: ``OPTIMAL``, since CP-SAT itself distinguishes "found a solution"
#: (``FEASIBLE``/``OPTIMAL``) from "found nothing yet" (``UNKNOWN``), and
#: this adapter preserves that distinction rather than optimistically
#: upgrading it.
STATUS_MAP: dict[int, OptimizationStatus] = {
    cp_model.OPTIMAL: OptimizationStatus.OPTIMAL,
    cp_model.FEASIBLE: OptimizationStatus.FEASIBLE,
    cp_model.INFEASIBLE: OptimizationStatus.INFEASIBLE,
    cp_model.MODEL_INVALID: OptimizationStatus.ERROR,
    cp_model.UNKNOWN: OptimizationStatus.TIME_LIMIT,
}


def map_cp_sat_status(cp_status: int) -> OptimizationStatus:
    """Map a raw CP-SAT status int to :class:`OptimizationStatus`.

    Fail-closed on an unrecognized status rather than guessing: a future
    OR-Tools release adding a new status value must not be silently folded
    into an existing one.
    """
    try:
        return STATUS_MAP[cp_status]
    except KeyError as exc:
        raise SolverExecutionError(
            f"unrecognized CP-SAT status value {cp_status!r}; refusing to "
            "guess a mapping"
        ) from exc


def solve(problem: SolverProblem, config: SolverConfig | None = None) -> SolverSolution:
    """Solve *problem* with CP-SAT and return a solver-neutral solution.

    Args:
        problem: A validated :class:`~backend.planning.solver_models.SolverProblem`.
            Validation (duplicate IDs, unknown predecessors, cycles, zero
            eligible machines, etc.) already happened in
            ``SolverProblem.__post_init__`` — this function does not
            re-validate structural correctness, only builds and solves the
            model.
        config: Solver configuration. Defaults to
            :class:`~backend.planning.solver_models.SolverConfig`'s
            deterministic defaults (``num_workers=1``, fixed
            ``random_seed``) when omitted.

    Returns:
        A :class:`~backend.planning.solver_models.SolverSolution`. When
        ``status`` is ``INFEASIBLE``, ``ERROR``, or ``TIME_LIMIT`` with no
        incumbent found, ``assignments`` is empty and ``makespan`` /
        ``objective_value`` are ``None`` — mirroring the same
        no-partial-success invariant
        :class:`~backend.planning.models.OptimizationResult` already
        enforces for the domain layer.

    Raises:
        SolverExecutionError: an unexpected failure occurred while building
            or solving the model (as opposed to a structural input defect,
            which is rejected earlier by ``SolverProblem``/``SolverConfig``
            construction and never reaches this function in the first
            place).
    """
    if config is None:
        config = SolverConfig()

    try:
        model = cp_model.CpModel()
        # PLANNING-01F REVIEW FIX R1: this must be a *sum*, not a max. A
        # machine with no entry in problem.machine_availability at all
        # (fully calendar-unaware, e.g. when the whole problem is
        # calendar-unaware) is unbounded except by horizon_seconds -- but a
        # calendar-bound machine can force an operation to start as late as
        # max_machine_availability_end_seconds, and anything chained after
        # that operation (by precedence) onto a calendar-unaware machine
        # then needs up to horizon_seconds more on top of that, not instead
        # of it. Using max(...) here silently truncated the CP-SAT variable
        # domain and produced a false INFEASIBLE for such chains (see
        # docs/planning/CALENDAR_CONSTRAINTS.md and the regression test in
        # test_scheduler.py). When max_machine_availability_end_seconds is 0
        # (calendar-unaware problem), this reduces to exactly
        # horizon_seconds, preserving PLANNING-01B/01E behavior unchanged.
        horizon = (
            problem.horizon_seconds
            + problem.max_machine_availability_end_seconds
            + len(problem.operations) * problem.max_setup_seconds
        )

        # operations are already sorted by operation_id (SolverProblem
        # normalizes this), so all of the dict/list construction below is
        # deterministic without any extra sorting here.
        start_vars: dict[str, cp_model.IntVar] = {}
        end_vars: dict[str, cp_model.IntVar] = {}
        presence_by_op_machine: dict[tuple[str, str], cp_model.BoolVar] = {}
        intervals_by_machine: dict[str, list[cp_model.IntervalVar]] = {}
        windows_by_op_machine: dict[
            tuple[str, str],
            tuple[tuple[SolverAvailabilityWindow, ...], list[cp_model.BoolVar]],
        ] = {}

        for op in problem.operations:
            duration_seconds = timedelta_to_solver_seconds(
                op.duration, f"{op.operation_id}.duration"
            )
            start_var = model.NewIntVar(0, horizon, f"start_{op.operation_id}")
            end_var = model.NewIntVar(0, horizon, f"end_{op.operation_id}")
            start_vars[op.operation_id] = start_var
            end_vars[op.operation_id] = end_var

            presence_vars = []
            for machine_id in op.eligible_machine_ids:
                # `None` (no key at all) means calendar-unaware for this
                # machine: fully open, exactly PLANNING-01B/01E's original
                # behavior. A present-but-empty tuple means "this machine
                # has zero usable windows" -- also excludes it below.
                machine_windows = problem.machine_availability.get(machine_id)
                usable_windows = None
                if machine_windows is not None:
                    usable_windows = tuple(
                        window
                        for window in machine_windows
                        if (window.end_offset - window.start_offset) >= duration_seconds
                    )
                    if not usable_windows:
                        # Non-preemptive: no single window on this machine
                        # is even long enough to hold the operation.
                        # Excluded from the candidate pool entirely rather
                        # than constrained to an always-false choice — the
                        # solver never has to "discover" this machine is
                        # unusable, it is simply never offered.
                        continue

                presence = model.NewBoolVar(f"assign_{op.operation_id}_{machine_id}")
                presence_by_op_machine[(op.operation_id, machine_id)] = presence
                presence_vars.append(presence)
                interval = model.NewOptionalIntervalVar(
                    start_var,
                    duration_seconds,
                    end_var,
                    presence,
                    f"interval_{op.operation_id}_{machine_id}",
                )
                intervals_by_machine.setdefault(machine_id, []).append(interval)

                if usable_windows is not None:
                    window_chosen_vars = []
                    for index, window in enumerate(usable_windows):
                        chosen = model.NewBoolVar(
                            f"window_{op.operation_id}_{machine_id}_{index}"
                        )
                        window_chosen_vars.append(chosen)
                        # Non-preemptive containment: the whole operation
                        # must lie inside this one selected window.
                        model.Add(start_var >= window.start_offset).OnlyEnforceIf(chosen)
                        model.Add(end_var <= window.end_offset).OnlyEnforceIf(chosen)
                    # This machine is used for this operation iff exactly
                    # one of its usable windows is selected for it.
                    model.Add(sum(window_chosen_vars) == presence)
                    windows_by_op_machine[(op.operation_id, machine_id)] = (
                        usable_windows,
                        window_chosen_vars,
                    )

            if presence_vars:
                # Exactly one eligible, calendar-feasible machine is
                # selected — the solver may never leave an operation
                # unassigned or assign it to more than one machine at once.
                model.AddExactlyOne(presence_vars)
            else:
                # Every eligible machine was excluded above (no window on
                # any of them is long enough to hold this operation). Force
                # the model globally infeasible via two contradictory
                # constraints on a fresh variable, rather than calling
                # AddExactlyOne([]) (unsupported) or silently dropping the
                # operation. This yields a clean CP-SAT INFEASIBLE, never a
                # fabricated schedule.
                impossible = model.NewBoolVar(f"infeasible_{op.operation_id}")
                model.Add(impossible == 1)
                model.Add(impossible == 0)

        for intervals in intervals_by_machine.values():
            model.AddNoOverlap(intervals)

        # PLANNING-01G: direct-adjacency, sequence-dependent setup times.
        # AddCircuit gives one ordered path through the operations actually
        # assigned to each setup-aware machine. An absent operation uses its
        # self-loop (presence.Not()), while depot -> op and op -> depot arcs
        # model the first/last operations. Setup is charged only on a true
        # op -> op successor arc, never on non-adjacent pairs.
        operation_by_id = {op.operation_id: op for op in problem.operations}
        for machine_id, transition_seconds in problem.setup_matrix_seconds.items():
            candidate_op_ids = sorted(
                op_id
                for op_id, candidate_machine_id in presence_by_op_machine
                if candidate_machine_id == machine_id
            )
            if len(candidate_op_ids) < 2:
                continue
            if not transition_seconds or all(
                duration == 0 for duration in transition_seconds.values()
            ):
                # With no positive setup penalty, AddNoOverlap already gives
                # exactly the required machine-capacity behavior.
                continue

            node_by_operation = {
                op_id: index + 1 for index, op_id in enumerate(candidate_op_ids)
            }
            arcs = []
            depot_self = model.NewBoolVar(f"setup_depot_self_{machine_id}")
            arcs.append((0, 0, depot_self))

            for op_id in candidate_op_ids:
                node = node_by_operation[op_id]
                presence = presence_by_op_machine[(op_id, machine_id)]
                arcs.append((node, node, presence.Not()))
                first = model.NewBoolVar(f"setup_first_{machine_id}_{op_id}")
                last = model.NewBoolVar(f"setup_last_{machine_id}_{op_id}")
                arcs.append((0, node, first))
                arcs.append((node, 0, last))

            for from_id in candidate_op_ids:
                from_key = operation_by_id[from_id].setup_key
                for to_id in candidate_op_ids:
                    if from_id == to_id:
                        continue
                    to_key = operation_by_id[to_id].setup_key
                    if from_key is None or to_key is None:
                        raise SolverExecutionError(
                            "setup-aware operation reached optimizer without a setup_key: "
                            f"{from_id!r} -> {to_id!r} on {machine_id!r}"
                        )
                    required_seconds = transition_seconds.get((from_key, to_key))
                    if required_seconds is None:
                        raise SolverExecutionError(
                            "setup transition was not pre-resolved before solve: "
                            f"{from_key!r} -> {to_key!r} on {machine_id!r}"
                        )

                    successor = model.NewBoolVar(
                        f"setup_succ_{machine_id}_{from_id}_{to_id}"
                    )
                    arcs.append(
                        (
                            node_by_operation[from_id],
                            node_by_operation[to_id],
                            successor,
                        )
                    )
                    model.Add(
                        start_vars[to_id] >= end_vars[from_id] + required_seconds
                    ).OnlyEnforceIf(successor)

                    # PLANNING-01G P1 calendar fix: when the successor is
                    # placed in a selected availability window, its positive
                    # setup span must begin inside that SAME window. The
                    # existing processing containment already ensures the
                    # successor end is inside it, so together these constraints
                    # prove [setup_start, successor_end) never crosses a shift
                    # closure or maintenance gap.
                    if required_seconds > 0:
                        windows_to_operation = windows_by_op_machine.get(
                            (to_id, machine_id)
                        )
                        if windows_to_operation is not None:
                            windows, chosen_vars = windows_to_operation
                            for window, chosen in zip(windows, chosen_vars, strict=True):
                                model.Add(
                                    start_vars[to_id] - required_seconds
                                    >= window.start_offset
                                ).OnlyEnforceIf([successor, chosen])

            model.AddCircuit(arcs)

        for op in problem.operations:
            for pred_id in op.predecessor_operation_ids:
                model.Add(end_vars[pred_id] <= start_vars[op.operation_id])

        makespan_var = model.NewIntVar(0, horizon, "makespan")
        model.AddMaxEquality(makespan_var, list(end_vars.values()))
        model.Minimize(makespan_var)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = config.time_limit_seconds
        solver.parameters.num_search_workers = config.num_workers
        solver.parameters.random_seed = config.random_seed
        solver.parameters.log_search_progress = config.log_search_progress

        cp_status = solver.Solve(model)
    except SolverExecutionError:
        raise
    except Exception as exc:  # noqa: BLE001 - deliberately narrowed via chaining below
        raise SolverExecutionError(
            f"unexpected failure while building/solving the CP-SAT model: {exc}"
        ) from exc

    status = map_cp_sat_status(cp_status)

    if status not in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE):
        # INFEASIBLE / ERROR / TIME_LIMIT-with-no-incumbent: calling
        # solver.Value(...) here would be unsafe (CP-SAT does not guarantee
        # variable values are populated), so no partial result is
        # extracted — mirrors OptimizationResult's own
        # never-claim-success-with-nothing-to-show invariant.
        return SolverSolution(
            status=status,
            assignments=(),
            makespan=None,
            objective_value=None,
            solve_time_seconds=solver.WallTime(),
        )

    assignments = []
    for op in problem.operations:
        assigned_machine = None
        for machine_id in op.eligible_machine_ids:
            # A machine excluded above (no window long enough for this
            # operation) has no presence variable at all -- `.get()` skips
            # it rather than raising a KeyError.
            presence = presence_by_op_machine.get((op.operation_id, machine_id))
            if presence is not None and solver.Value(presence) == 1:
                assigned_machine = machine_id
                break
        if assigned_machine is None:  # pragma: no cover - defense in depth
            raise SolverExecutionError(
                f"CP-SAT reported {status.value} but no machine assignment "
                f"boolean was true for operation {op.operation_id!r}; "
                "refusing to return an incomplete solution"
            )
        assignments.append(
            SolverAssignment(
                operation_id=op.operation_id,
                machine_id=assigned_machine,
                start=solver_seconds_to_timedelta(solver.Value(start_vars[op.operation_id])),
                end=solver_seconds_to_timedelta(solver.Value(end_vars[op.operation_id])),
            )
        )

    makespan_seconds = solver.Value(makespan_var)

    return SolverSolution(
        status=status,
        assignments=tuple(assignments),
        makespan=solver_seconds_to_timedelta(makespan_seconds),
        objective_value=Decimal(makespan_seconds),
        solve_time_seconds=solver.WallTime(),
    )
