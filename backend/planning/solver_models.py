"""Solver-neutral input/output models for the optimizer adapter (PLANNING-01B).

This module defines the data contracts that sit *between* the planning
domain layer (:mod:`backend.planning.models`, :mod:`backend.planning.eligibility`,
:mod:`backend.planning.routing`) and the OR-Tools CP-SAT adapter
(:mod:`backend.planning.optimizer_adapter`).

Design rule (per PLANNING-01B scope): this module MUST NOT import
``ortools``, ``gurobipy``, or ``pulp``. It describes solver-facing *data*
only — CP-SAT objects (``CpModel``, ``CpSolver``, ``IntVar``,
``IntervalVar``, ``BoolVar``) are strictly confined to
:mod:`backend.planning.optimizer_adapter` and never cross this boundary.

This module also does not duplicate or re-derive engineering truth: it does
not know what a ``Machine`` or an ``Operation`` *is*, and it does not
recompute machine eligibility or routing precedence. Callers are expected to
build :class:`SolverOperation` instances from already-resolved
:class:`~backend.planning.eligibility.EligibilityResult` /
:class:`~backend.planning.models.SchedulingOperation` /
:class:`~backend.planning.models.Routing` data — that conversion is
intentionally left to the caller (or a later stage) so this module stays a
minimal, solver-facing shape rather than a second domain model.

Time-unit policy
-----------------
CP-SAT requires integer decision variables. This module standardizes on
integer **seconds** as the sole internal solver unit (see
:func:`timedelta_to_solver_seconds` / :func:`solver_seconds_to_timedelta`).
Sub-second ``timedelta`` precision is rejected rather than silently
truncated — see those functions' docstrings for the exact policy.

PLANNING-01G adds only solver-facing setup metadata: an optional ``setup_key``
on each operation and an optional per-machine transition table already
resolved to integer seconds. Domain policy remains in ``SetupMatrix`` and the
scheduler; this module validates structure but does not infer setup families.

Fail-closed policy
-------------------
Structural problems (duplicate IDs, unknown predecessors, self-predecessors,
precedence cycles, zero eligible machines, non-positive durations, invalid
solver configuration) are rejected at construction time via
:class:`~backend.planning.exceptions.InvalidSolverProblemError` or
:class:`~backend.planning.exceptions.PrecedenceCycleError`. Nothing here is
silently dropped, widened, or defaulted away.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from types import MappingProxyType

from backend.planning.exceptions import InvalidSolverProblemError, PrecedenceCycleError
from backend.planning.models import OptimizationStatus

__all__ = [
    "SolverConfig",
    "SolverOperation",
    "SolverProblem",
    "SolverAssignment",
    "SolverSolution",
    "SolverAvailabilityWindow",
    "timedelta_to_solver_seconds",
    "solver_seconds_to_timedelta",
    "timedelta_offset_to_solver_seconds",
]


# ---------------------------------------------------------------------------
# Time-unit conversion
# ---------------------------------------------------------------------------

def timedelta_to_solver_seconds(duration: timedelta, field_name: str = "duration") -> int:
    """Convert a positive, whole-second :class:`timedelta` to integer seconds.

    Fail-closed: rejects non-``timedelta`` values, non-positive durations,
    and any duration that is not an exact whole number of seconds (no
    silent truncation of sub-second precision — PLANNING-01B does not
    support sub-second scheduling resolution).
    """
    if not isinstance(duration, timedelta):
        raise InvalidSolverProblemError(f"{field_name} must be a datetime.timedelta")
    if duration <= timedelta(0):
        raise InvalidSolverProblemError(
            f"{field_name} must be a strictly positive timedelta, got {duration}"
        )
    total_seconds = duration.total_seconds()
    seconds_int = int(total_seconds)
    if seconds_int != total_seconds:
        raise InvalidSolverProblemError(
            f"{field_name} must be an exact whole number of seconds for "
            f"integer-second CP-SAT solving; got {duration} "
            f"({total_seconds}s), which would require lossy truncation"
        )
    return seconds_int


def solver_seconds_to_timedelta(seconds: int) -> timedelta:
    """Convert an integer solver-second offset back to a :class:`timedelta`.

    Fail-closed: rejects non-``int`` values (including ``bool``, which is an
    ``int`` subclass) and negative values.
    """
    if isinstance(seconds, bool) or not isinstance(seconds, int):
        raise InvalidSolverProblemError("solver seconds value must be a plain int")
    if seconds < 0:
        raise InvalidSolverProblemError("solver seconds value must not be negative")
    return timedelta(seconds=seconds)


def timedelta_offset_to_solver_seconds(offset: timedelta, field_name: str = "offset") -> int:
    """Convert a non-negative, whole-second :class:`timedelta` *offset* to
    integer seconds (PLANNING-01F).

    Distinct from :func:`timedelta_to_solver_seconds`: that function
    converts a *duration* and rejects a zero or negative value, because a
    duration of zero or less is meaningless. This function converts an
    *offset from some reference instant* (e.g. a calendar availability
    window's start, relative to ``horizon_start``) — zero is a completely
    valid offset (a window that starts exactly at the horizon start), so
    only a *negative* offset is rejected, not a zero one. Whole-second
    precision is still required (no silent truncation), matching this
    module's overall time-unit policy.
    """
    if not isinstance(offset, timedelta):
        raise InvalidSolverProblemError(f"{field_name} must be a datetime.timedelta")
    if offset < timedelta(0):
        raise InvalidSolverProblemError(f"{field_name} must not be negative, got {offset}")
    total_seconds = offset.total_seconds()
    seconds_int = int(total_seconds)
    if seconds_int != total_seconds:
        raise InvalidSolverProblemError(
            f"{field_name} must be an exact whole number of seconds for "
            f"integer-second CP-SAT solving; got {offset} ({total_seconds}s), "
            "which would require lossy truncation"
        )
    return seconds_int


# ---------------------------------------------------------------------------
# Shared validation helpers (solver-layer local; mirrors backend.domain.base /
# backend.planning.models style without importing either)
# ---------------------------------------------------------------------------

def _require_non_empty_str(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidSolverProblemError(f"{field_name} must be a non-empty string")
    return value


def _clean_id_tuple(
    values: tuple[str, ...], field_name: str, *, reject_duplicates: bool = True
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise InvalidSolverProblemError(f"{field_name} must be a tuple of strings")
    cleaned = tuple(_require_non_empty_str(v, f"{field_name} entry") for v in values)
    if reject_duplicates and len(cleaned) != len(set(cleaned)):
        raise InvalidSolverProblemError(f"{field_name} must not contain duplicate IDs")
    return cleaned


# ---------------------------------------------------------------------------
# SolverConfig
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SolverConfig:
    """Immutable CP-SAT solver configuration.

    Deterministic by default: ``num_workers=1`` with a fixed
    ``random_seed`` reproduces the same search trajectory for the same
    problem. Raising ``num_workers`` above 1 enables CP-SAT's parallel
    portfolio search, which is *not* guaranteed to be deterministic across
    runs/machines — callers that need repeatable solves (e.g. the test
    suite) should keep the default.
    """

    time_limit_seconds: float = 30.0
    num_workers: int = 1
    random_seed: int = 0
    log_search_progress: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.time_limit_seconds, bool) or not isinstance(
            self.time_limit_seconds, (int, float)
        ):
            raise InvalidSolverProblemError("time_limit_seconds must be a number")
        if self.time_limit_seconds <= 0:
            raise InvalidSolverProblemError("time_limit_seconds must be strictly positive")
        if isinstance(self.num_workers, bool) or not isinstance(self.num_workers, int):
            raise InvalidSolverProblemError("num_workers must be an int")
        if self.num_workers < 1:
            raise InvalidSolverProblemError("num_workers must be >= 1")
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
            raise InvalidSolverProblemError("random_seed must be an int")
        if not isinstance(self.log_search_progress, bool):
            raise InvalidSolverProblemError("log_search_progress must be a bool")


# ---------------------------------------------------------------------------
# SolverOperation / SolverProblem
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SolverOperation:
    """The minimal per-operation shape the CP-SAT adapter needs.

    Deliberately narrow: this is not :class:`~backend.planning.models.SchedulingOperation`
    and does not carry anything the solver does not use directly. Callers
    convert from already-resolved domain/eligibility data.
    """

    operation_id: str
    duration: timedelta
    eligible_machine_ids: tuple[str, ...]
    predecessor_operation_ids: tuple[str, ...] = ()
    setup_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operation_id", _require_non_empty_str(self.operation_id, "operation_id")
        )
        # Validates positivity and whole-second precision; the converted
        # value itself is computed lazily by the adapter, not stored here,
        # so SolverOperation keeps carrying a timedelta as its public shape.
        timedelta_to_solver_seconds(self.duration, "duration")
        object.__setattr__(
            self,
            "eligible_machine_ids",
            _clean_id_tuple(self.eligible_machine_ids, "eligible_machine_ids"),
        )
        if not self.eligible_machine_ids:
            raise InvalidSolverProblemError(
                f"operation {self.operation_id!r} has zero eligible machines; "
                "refusing to let the solver invent an unsupported machine"
            )
        preds = _clean_id_tuple(
            self.predecessor_operation_ids, "predecessor_operation_ids"
        )
        if self.operation_id in preds:
            raise InvalidSolverProblemError(
                f"operation {self.operation_id!r} declares itself as a predecessor"
            )
        object.__setattr__(self, "predecessor_operation_ids", preds)
        if self.setup_key is not None:
            object.__setattr__(
                self,
                "setup_key",
                _require_non_empty_str(self.setup_key, "setup_key"),
            )


def _detect_cycle(operations: tuple[SolverOperation, ...]) -> None:
    """Raise :class:`PrecedenceCycleError` if the precedence graph has a cycle.

    Deterministic DFS (white/gray/black coloring) over operations and their
    predecessor lists, both already sorted by ID — so the traversal order,
    and therefore which cycle is reported first, is reproducible.
    """
    by_id = {op.operation_id: op for op in operations}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {op_id: WHITE for op_id in by_id}

    def visit(op_id: str, stack: tuple[str, ...]) -> None:
        color[op_id] = GRAY
        for pred_id in by_id[op_id].predecessor_operation_ids:
            if color[pred_id] == GRAY:
                cycle = " -> ".join((*stack, op_id, pred_id))
                raise PrecedenceCycleError(
                    f"precedence cycle detected: {cycle}"
                )
            if color[pred_id] == WHITE:
                visit(pred_id, (*stack, op_id))
        color[op_id] = BLACK

    for op_id in sorted(by_id):
        if color[op_id] == WHITE:
            visit(op_id, ())


@dataclass(frozen=True, slots=True)
class SolverAvailabilityWindow:
    """One machine's usable time window, as a solver-relative integer-second
    offset pair (PLANNING-01F).

    Contains no ``datetime`` — offsets are relative to whatever
    ``horizon_start`` the caller (:mod:`backend.planning.calendar_constraints`)
    converted from. This is the sole calendar-availability shape that
    crosses into the solver layer; everything upstream of it works in
    absolute, timezone-aware datetimes.
    """

    start_offset: int
    end_offset: int

    def __post_init__(self) -> None:
        if isinstance(self.start_offset, bool) or not isinstance(self.start_offset, int):
            raise InvalidSolverProblemError("start_offset must be a plain int")
        if self.start_offset < 0:
            raise InvalidSolverProblemError("start_offset must not be negative")
        if isinstance(self.end_offset, bool) or not isinstance(self.end_offset, int):
            raise InvalidSolverProblemError("end_offset must be a plain int")
        if self.end_offset <= self.start_offset:
            raise InvalidSolverProblemError("end_offset must be strictly after start_offset")


@dataclass(frozen=True, slots=True)
class SolverProblem:
    """An immutable, validated, solver-ready scheduling problem.

    Operations are normalized to a deterministic order (sorted by
    ``operation_id``) regardless of the order the caller supplied them in,
    so downstream model-building and result ordering do not depend on dict
    or list construction order.

    ``machine_availability`` (PLANNING-01F) is optional and defaults to an
    empty mapping, which means *fully calendar-unaware*: every machine is
    treated as continuously available, exactly matching PLANNING-01B/01E's
    original behavior before calendar constraints existed. This module
    validates only the *structural shape* of whatever is supplied here
    (types, no self-overlap within one machine's own windows, deterministic
    ordering) — it does not require an entry for every machine referenced
    by ``operations``. Ensuring complete, policy-correct coverage (e.g. the
    "no calendar = continuous availability" default for a machine with no
    explicit calendar) is the responsibility of the caller
    (:mod:`backend.planning.calendar_constraints` /
    :mod:`backend.planning.scheduler`), consistent with this module's
    existing division of labor: it stays a narrow, solver-facing shape, not
    a second domain/policy layer.
    """

    operations: tuple[SolverOperation, ...]
    machine_availability: Mapping[str, tuple[SolverAvailabilityWindow, ...]] = field(
        default_factory=dict
    )
    setup_matrix_seconds: Mapping[str, Mapping[tuple[str, str], int]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        ops = self.operations
        if not isinstance(ops, tuple) or not all(
            isinstance(op, SolverOperation) for op in ops
        ):
            raise InvalidSolverProblemError(
                "operations must be a tuple of SolverOperation instances"
            )
        if not ops:
            raise InvalidSolverProblemError("SolverProblem must contain at least one operation")

        op_ids = [op.operation_id for op in ops]
        if len(op_ids) != len(set(op_ids)):
            raise InvalidSolverProblemError("duplicate operation_id in SolverProblem")

        known_ids = set(op_ids)
        for op in ops:
            for pred_id in op.predecessor_operation_ids:
                if pred_id not in known_ids:
                    raise InvalidSolverProblemError(
                        f"operation {op.operation_id!r} references unknown "
                        f"predecessor {pred_id!r}"
                    )

        ordered = tuple(sorted(ops, key=lambda op: op.operation_id))
        object.__setattr__(self, "operations", ordered)

        _detect_cycle(ordered)

        availability = self.machine_availability
        if not isinstance(availability, Mapping):
            raise InvalidSolverProblemError(
                "machine_availability must be a Mapping[str, tuple[SolverAvailabilityWindow, ...]]"
            )
        normalized_availability: dict[str, tuple[SolverAvailabilityWindow, ...]] = {}
        for machine_id, windows in availability.items():
            clean_machine_id = _require_non_empty_str(machine_id, "machine_availability key")
            if not isinstance(windows, tuple) or not all(
                isinstance(w, SolverAvailabilityWindow) for w in windows
            ):
                raise InvalidSolverProblemError(
                    f"machine_availability[{clean_machine_id!r}] must be a tuple of "
                    "SolverAvailabilityWindow instances"
                )
            ordered_windows = tuple(sorted(windows, key=lambda w: (w.start_offset, w.end_offset)))
            for earlier, later in zip(ordered_windows, ordered_windows[1:], strict=False):
                if earlier.end_offset > later.start_offset:
                    raise InvalidSolverProblemError(
                        f"machine_availability[{clean_machine_id!r}] has overlapping "
                        f"windows: {earlier} and {later}"
                    )
            normalized_availability[clean_machine_id] = ordered_windows
        object.__setattr__(
            self,
            "machine_availability",
            MappingProxyType(dict(sorted(normalized_availability.items()))),
        )

        setup_matrix_seconds = self.setup_matrix_seconds
        if not isinstance(setup_matrix_seconds, Mapping):
            raise InvalidSolverProblemError(
                "setup_matrix_seconds must be a Mapping[str, Mapping[tuple[str, str], int]]"
            )

        normalized_setup: dict[str, MappingProxyType] = {}
        for machine_id, transitions in setup_matrix_seconds.items():
            clean_machine_id = _require_non_empty_str(machine_id, "setup_matrix_seconds key")
            if not isinstance(transitions, Mapping):
                raise InvalidSolverProblemError(
                    f"setup_matrix_seconds[{clean_machine_id!r}] must be a Mapping"
                )

            clean_transitions: dict[tuple[str, str], int] = {}
            for key, duration_seconds in transitions.items():
                if (
                    not isinstance(key, tuple)
                    or len(key) != 2
                    or not all(isinstance(part, str) for part in key)
                ):
                    raise InvalidSolverProblemError(
                        f"setup_matrix_seconds[{clean_machine_id!r}] keys must be "
                        "(from_setup_key, to_setup_key) string tuples"
                    )
                from_key = _require_non_empty_str(
                    key[0], "setup_matrix_seconds transition from_setup_key"
                )
                to_key = _require_non_empty_str(
                    key[1], "setup_matrix_seconds transition to_setup_key"
                )
                if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, int):
                    raise InvalidSolverProblemError(
                        f"setup_matrix_seconds[{clean_machine_id!r}]"
                        f"[{(from_key, to_key)!r}] must be a plain int"
                    )
                if duration_seconds < 0:
                    raise InvalidSolverProblemError(
                        f"setup_matrix_seconds[{clean_machine_id!r}]"
                        f"[{(from_key, to_key)!r}] must not be negative"
                    )
                clean_transitions[(from_key, to_key)] = duration_seconds

            normalized_setup[clean_machine_id] = MappingProxyType(
                dict(sorted(clean_transitions.items()))
            )

        # Every operation that could land on a setup-aware machine must carry
        # an explicit setup key. The scheduler resolves this metadata from
        # caller-supplied setup_keys; the solver layer never infers it.
        setup_aware_machine_ids = set(normalized_setup)
        for op in ordered:
            if (
                setup_aware_machine_ids.intersection(op.eligible_machine_ids)
                and op.setup_key is None
            ):
                raise InvalidSolverProblemError(
                    f"operation {op.operation_id!r} is eligible for a setup-aware machine "
                    "but has no setup_key"
                )

        object.__setattr__(
            self,
            "setup_matrix_seconds",
            MappingProxyType(dict(sorted(normalized_setup.items()))),
        )

    @property
    def horizon_seconds(self) -> int:
        """A safe upper bound on the scheduling horizon, from durations alone.

        The sum of every operation's duration is always sufficient when no
        calendar constraints are in play: even a fully serial schedule (no
        parallelism at all) finishes within that many seconds, so no
        operation ever needs a variable domain larger than this to find a
        feasible (let alone optimal) placement. This does **not** yet
        account for ``machine_availability`` windows that may extend later
        than the sum of durations (e.g. a machine's shift starting on a
        later day) — see :attr:`max_machine_availability_end_seconds`,
        which :func:`~backend.planning.optimizer_adapter.solve` combines
        with this property for the true CP-SAT variable-domain bound.
        """
        return sum(
            timedelta_to_solver_seconds(op.duration, f"{op.operation_id}.duration")
            for op in self.operations
        )

    @property
    def max_machine_availability_end_seconds(self) -> int:
        """The latest ``end_offset`` across every machine's availability windows.

        ``0`` when ``machine_availability`` is empty (calendar-unaware
        mode), in which case this contributes nothing beyond
        :attr:`horizon_seconds`.
        """
        return max(
            (
                window.end_offset
                for windows in self.machine_availability.values()
                for window in windows
            ),
            default=0,
        )

    @property
    def max_setup_seconds(self) -> int:
        """Largest resolved setup/changeover duration in integer seconds.

        ``0`` when setup-awareness is disabled. The optimizer uses this as a
        deliberately loose but safe horizon-widening term:
        ``len(operations) * max_setup_seconds``.
        """
        return max(
            (
                duration
                for transitions in self.setup_matrix_seconds.values()
                for duration in transitions.values()
            ),
            default=0,
        )


# ---------------------------------------------------------------------------
# SolverAssignment / SolverSolution
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SolverAssignment:
    """One solved operation placement. Contains no OR-Tools types."""

    operation_id: str
    machine_id: str
    start: timedelta
    end: timedelta

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operation_id", _require_non_empty_str(self.operation_id, "operation_id")
        )
        object.__setattr__(
            self, "machine_id", _require_non_empty_str(self.machine_id, "machine_id")
        )
        if not isinstance(self.start, timedelta) or not isinstance(self.end, timedelta):
            raise InvalidSolverProblemError("start and end must be timedeltas")
        if self.end <= self.start:
            raise InvalidSolverProblemError("end must be strictly after start")


@dataclass(frozen=True, slots=True)
class SolverSolution:
    """Solver-neutral result. Contains no ``CpModel``/``CpSolver``/``IntVar``/
    ``IntervalVar``/``BoolVar`` — see :mod:`backend.planning.optimizer_adapter`
    for the isolation boundary this type exists to enforce.
    """

    status: OptimizationStatus
    assignments: tuple[SolverAssignment, ...] = ()
    makespan: timedelta | None = None
    objective_value: Decimal | None = None
    solve_time_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.status, OptimizationStatus):
            raise InvalidSolverProblemError("status must be an OptimizationStatus")
        if not all(isinstance(a, SolverAssignment) for a in self.assignments):
            raise InvalidSolverProblemError("assignments must be SolverAssignment instances")
        ordered = tuple(sorted(self.assignments, key=lambda a: a.operation_id))
        object.__setattr__(self, "assignments", ordered)
        if self.makespan is not None and not isinstance(self.makespan, timedelta):
            raise InvalidSolverProblemError("makespan must be a timedelta or None")
        if self.objective_value is not None and not isinstance(self.objective_value, Decimal):
            raise InvalidSolverProblemError("objective_value must be a Decimal or None")
        if (
            isinstance(self.solve_time_seconds, bool)
            or not isinstance(self.solve_time_seconds, (int, float))
            or self.solve_time_seconds < 0
        ):
            raise InvalidSolverProblemError("solve_time_seconds must be a non-negative number")
