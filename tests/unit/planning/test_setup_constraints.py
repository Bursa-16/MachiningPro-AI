"""Tests for PLANNING-01G sequence-dependent setup/changeover modeling.

The critical property under test throughout this module: setup/changeover
time is charged *only* between two operations that end up directly,
immediately consecutive on the same machine in the achieved schedule --
never between an operation and some other, non-adjacent operation that
merely comes later in the same machine's sequence. See
``docs/planning/SETUP_CHANGEOVER_CONSTRAINTS.md`` for the full model.

This file is new (PLANNING-01G); it does not modify or weaken any existing
test in ``test_scheduler.py`` or ``test_optimizer_adapter.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.domain.base import Provenance
from backend.domain.enums import MachineType, OperationType, ProvenanceType
from backend.domain.machine import Machine
from backend.domain.operation import Operation
from backend.domain.units import Quantity, Unit
from backend.machines.catalog import MachineCatalog
from backend.planning.exceptions import (
    InvalidSolverProblemError,
    SchedulerResultValidationError,
    UnknownSetupTransitionError,
)
from backend.planning.models import (
    AvailabilityWindow,
    MaintenanceWindow,
    MissingTransitionPolicy,
    OptimizationStatus,
    ResourceCalendar,
    Routing,
    SetupMatrix,
)
from backend.planning.scheduler import schedule_routing
from backend.planning.solver_models import (
    SolverAssignment,
    SolverConfig,
    SolverProblem,
    SolverSolution,
)

HORIZON_START = datetime(2030, 1, 1, 8, 0, 0, tzinfo=UTC)
HORIZON_END = datetime(2030, 1, 2, 8, 0, 0, tzinfo=UTC)
CREATED_AT = datetime(2030, 1, 1, 7, 0, 0, tzinfo=UTC)
DETERMINISTIC_CONFIG = SolverConfig(time_limit_seconds=10.0, num_workers=1, random_seed=42)


def _hh(hour, minute=0, day=1):
    return datetime(2030, 1, day, hour, minute, 0, tzinfo=UTC)

_PROV = Provenance(source_type=ProvenanceType.USER_INPUT)


def _rpm(value):
    return Quantity.of(value, Unit.RPM)


def _kw(value):
    return Quantity.of(value, Unit.KW)


def _machine(machine_id, op_types=(OperationType.MILLING,)):
    return Machine(
        machine_id=machine_id,
        name=f"Machine {machine_id}",
        machine_type=MachineType.MILL,
        axis_count=3,
        spindle_speed_min=_rpm(100),
        spindle_speed_max=_rpm(10000),
        spindle_power=_kw(10),
        provenance=_PROV,
        supported_operations=tuple(op_types),
    )


def _operation(operation_id, part_id="PART1", seq=1, op_type=OperationType.MILLING):
    return Operation(
        operation_id=operation_id,
        part_id=part_id,
        operation_type=op_type,
        sequence_index=seq,
        provenance=_PROV,
    )


def _catalog(*machines):
    catalog = MachineCatalog()
    for m in machines:
        catalog.register(m)
    return catalog


def _routing(operation_ids, precedence=None, routing_id="R1", plan_id="PLAN1"):
    return Routing(
        routing_id=routing_id,
        process_plan_id=plan_id,
        ordered_operation_ids=tuple(operation_ids),
        precedence=precedence or {},
    )


def _base_kwargs(**overrides):
    kwargs = dict(
        schedule_id="SCHED1",
        result_id="RESULT1",
        scenario_id="SCEN1",
        created_at=CREATED_AT,
        solver_config=DETERMINISTIC_CONFIG,
    )
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# Mandatory regression test 1: A -> B -> C, non-adjacent A->C must NOT apply.
#
# 1 machine, 3 operations (A, B, C), 20 minutes each, 60-minute availability
# window. A->B = 0, B->C = 0, A->C = 45. The sequence A, B, C is feasible
# with makespan = 60 minutes *only* if setup is never charged for the
# non-adjacent A->C pair (B sits between them in the actual sequence). Under
# the pre-fix "any earlier op before any later op charges setup" semantics
# this ticket describes, A->C's 45 minutes would be (incorrectly) charged
# somewhere in the model and the 60-minute makespan would be unreachable
# within the 60-minute window -- this test must FAIL against that defective
# behavior and PASS after the fix.
# ---------------------------------------------------------------------------

def _consecutive_only_matrix(machine_id="M1"):
    return SetupMatrix(
        matrix_id="SM1",
        machine_id=machine_id,
        entries={
            ("A", "B"): timedelta(minutes=0),
            ("B", "C"): timedelta(minutes=0),
            ("A", "C"): timedelta(minutes=45),
            # The reverse directions are never exercised by a feasible
            # A -> B -> C sequence, but NOT_ALLOWED requires every candidate
            # pair to be resolvable, so they are supplied too.
            ("B", "A"): timedelta(minutes=45),
            ("C", "B"): timedelta(minutes=45),
            ("C", "A"): timedelta(minutes=45),
        },
    )


def test_setup_applies_only_between_directly_consecutive_operations():
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {
        "OPA": _operation("OPA", seq=1),
        "OPB": _operation("OPB", seq=2),
        "OPC": _operation("OPC", seq=3),
    }
    routing = _routing(["OPA", "OPB", "OPC"])
    durations = {
        "OPA": timedelta(minutes=20),
        "OPB": timedelta(minutes=20),
        "OPC": timedelta(minutes=20),
    }
    setup_keys = {"OPA": "A", "OPB": "B", "OPC": "C"}
    setup_matrices = {"M1": _consecutive_only_matrix("M1")}

    result = schedule_routing(
        routing,
        ops,
        durations,
        catalog,
        HORIZON_START,
        horizon_end=HORIZON_START + timedelta(minutes=60),
        machine_calendars={},
        setup_keys=setup_keys,
        setup_matrices=setup_matrices,
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.horizon_end == HORIZON_START + timedelta(minutes=60)

    by_id = {o.operation_id: o for o in result.schedule.operations}
    ordered = sorted(by_id.values(), key=lambda o: o.start_time)
    assert [o.operation_id for o in ordered] == ["OPA", "OPB", "OPC"]

    # No idle time anywhere: the achieved sequence is A, B, C back-to-back,
    # which is only reachable at all if the 45-minute A->C transition was
    # never charged (it would blow the 60-minute window on its own).
    assert ordered[0].start_time == HORIZON_START
    assert ordered[1].start_time == ordered[0].end_time
    assert ordered[2].start_time == ordered[1].end_time
    assert ordered[2].end_time == HORIZON_START + timedelta(minutes=60)

    # Zero-duration transitions are not recorded as a changeover window.
    assert ordered[1].setup_start is None
    assert ordered[1].setup_end is None
    assert ordered[2].setup_start is None
    assert ordered[2].setup_end is None
    # The first operation never carries a setup window either.
    assert ordered[0].setup_start is None
    assert ordered[0].setup_end is None


# ---------------------------------------------------------------------------
# Mandatory regression test 2 (golden): asymmetric setup, only the true
# adjacent transitions are charged.
#
# A->B = 10, B->C = 20, A->C = 50. For sequence A, B, C only 10+20 = 30
# minutes of setup may be charged; the 50-minute A->C transition must remain
# entirely dormant/unused.
# ---------------------------------------------------------------------------

def test_golden_asymmetric_setup_only_true_adjacent_transitions_charged():
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {
        "OPA": _operation("OPA", seq=1),
        "OPB": _operation("OPB", seq=2),
        "OPC": _operation("OPC", seq=3),
    }
    routing = _routing(["OPA", "OPB", "OPC"])
    durations = {
        "OPA": timedelta(minutes=20),
        "OPB": timedelta(minutes=20),
        "OPC": timedelta(minutes=20),
    }
    setup_keys = {"OPA": "A", "OPB": "B", "OPC": "C"}
    setup_matrices = {
        "M1": SetupMatrix(
            matrix_id="SM2",
            machine_id="M1",
            entries={
                ("A", "B"): timedelta(minutes=10),
                ("B", "C"): timedelta(minutes=20),
                ("A", "C"): timedelta(minutes=50),
                ("B", "A"): timedelta(minutes=10),
                ("C", "B"): timedelta(minutes=20),
                ("C", "A"): timedelta(minutes=50),
            },
        )
    }

    result = schedule_routing(
        routing,
        ops,
        durations,
        catalog,
        HORIZON_START,
        horizon_end=HORIZON_START + timedelta(hours=6),
        machine_calendars={},
        setup_keys=setup_keys,
        setup_matrices=setup_matrices,
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.OPTIMAL
    by_id = {o.operation_id: o for o in result.schedule.operations}
    ordered = sorted(by_id.values(), key=lambda o: o.start_time)
    assert [o.operation_id for o in ordered] == ["OPA", "OPB", "OPC"]

    a, b, c = ordered
    # A -> B: 10 minutes of setup, independently re-verified.
    assert b.start_time - a.end_time == timedelta(minutes=10)
    assert b.setup_start == a.end_time
    assert b.setup_end == b.start_time
    # B -> C: 20 minutes of setup.
    assert c.start_time - b.end_time == timedelta(minutes=20)
    assert c.setup_start == b.end_time
    assert c.setup_end == c.start_time

    # Total makespan reflects exactly 20+20+20 (durations) + 10+20 (the two
    # true adjacent setups) = 90 minutes -- the 50-minute A->C transition
    # contributes nothing at all.
    assert result.schedule.horizon_end == HORIZON_START + timedelta(minutes=90)


# ---------------------------------------------------------------------------
# Backward compatibility: omitting setup_keys/setup_matrices reproduces
# PLANNING-01E/F's original setup-unaware behavior exactly.
# ---------------------------------------------------------------------------

def test_setup_unaware_mode_unaffected_when_setup_keys_omitted():
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"])
    durations = {"OPA": timedelta(seconds=600), "OPB": timedelta(seconds=300)}

    result = schedule_routing(
        routing, ops, durations, catalog, HORIZON_START, **_base_kwargs()
    )

    assert result.status == OptimizationStatus.OPTIMAL
    by_id = {o.operation_id: o for o in result.schedule.operations}
    assert by_id["OPA"].setup_start is None
    assert by_id["OPB"].setup_start is None
    assert result.schedule.horizon_end == HORIZON_START + timedelta(seconds=900)


# ---------------------------------------------------------------------------
# Fail-closed: setup_keys and setup_matrices must be supplied together.
# ---------------------------------------------------------------------------

def test_setup_keys_and_matrices_must_be_supplied_together():
    m1 = _machine("M1")
    catalog = _catalog(m1)
    op = _operation("OPA")
    routing = _routing(["OPA"])

    with pytest.raises(InvalidSolverProblemError):
        schedule_routing(
            routing,
            {"OPA": op},
            {"OPA": timedelta(seconds=600)},
            catalog,
            HORIZON_START,
            setup_keys={"OPA": "A"},
            **_base_kwargs(),
        )


def test_missing_setup_key_for_setup_aware_machine_is_rejected():
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"])

    with pytest.raises(InvalidSolverProblemError):
        schedule_routing(
            routing,
            ops,
            {"OPA": timedelta(seconds=600), "OPB": timedelta(seconds=600)},
            catalog,
            HORIZON_START,
            setup_keys={"OPA": "A"},  # OPB has no entry
            setup_matrices={
                "M1": SetupMatrix(
                    matrix_id="SM3",
                    machine_id="M1",
                    entries={("A", "B"): timedelta(minutes=1), ("B", "A"): timedelta(minutes=1)},
                )
            },
            **_base_kwargs(),
        )


def test_unresolvable_transition_raises_unknown_setup_transition_error():
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"])

    with pytest.raises(UnknownSetupTransitionError):
        schedule_routing(
            routing,
            ops,
            {"OPA": timedelta(seconds=600), "OPB": timedelta(seconds=600)},
            catalog,
            HORIZON_START,
            setup_keys={"OPA": "A", "OPB": "B"},
            # NOT_ALLOWED (the default) with no entries at all: every
            # candidate transition is unresolvable.
            setup_matrices={"M1": SetupMatrix(matrix_id="SM4", machine_id="M1", entries={})},
            **_base_kwargs(),
        )


# ---------------------------------------------------------------------------
# Independent post-solve validation actually catches a violated gap -- a
# fake solve_fn hands back a hand-crafted SolverSolution that places two
# operations immediately consecutive with less than the required setup gap
# between them, without touching CP-SAT at all.
# ---------------------------------------------------------------------------

def test_validation_rejects_solver_result_with_insufficient_setup_gap():
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"])

    def _fake_solve(problem: SolverProblem, config: SolverConfig) -> SolverSolution:
        # OPB starts only 1 minute after OPA ends, but the matrix requires
        # 10 minutes -- a solver bug (or a tampered result) that the
        # independent post-solve check must catch on its own, never trusting
        # the solver's OPTIMAL claim.
        return SolverSolution(
            status=OptimizationStatus.OPTIMAL,
            assignments=(
                SolverAssignment(
                    operation_id="OPA",
                    machine_id="M1",
                    start=timedelta(0),
                    end=timedelta(minutes=20),
                ),
                SolverAssignment(
                    operation_id="OPB",
                    machine_id="M1",
                    start=timedelta(minutes=21),
                    end=timedelta(minutes=41),
                ),
            ),
            makespan=timedelta(minutes=41),
        )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing,
            ops,
            {"OPA": timedelta(minutes=20), "OPB": timedelta(minutes=20)},
            catalog,
            HORIZON_START,
            solve_fn=_fake_solve,
            setup_keys={"OPA": "A", "OPB": "B"},
            setup_matrices={
                "M1": SetupMatrix(
                    matrix_id="SM5",
                    machine_id="M1",
                    entries={("A", "B"): timedelta(minutes=10), ("B", "A"): timedelta(minutes=10)},
                )
            },
            **_base_kwargs(),
        )


# ---------------------------------------------------------------------------
# PLANNING-01G P1 FIX: the setup span itself, [B.start - setup, B.end), must
# fit entirely inside ONE machine-availability window -- never merely
# satisfy the timing gap (start[B] >= end[A] + setup), which is trivially
# satisfied by any idle time, calendar-available or not.
# ---------------------------------------------------------------------------

_TIGHT_SETUP_MATRIX = SetupMatrix(
    matrix_id="SM_TIGHT",
    machine_id="M1",
    entries={
        ("A", "B"): timedelta(minutes=10),
        ("B", "A"): timedelta(minutes=10),
    },
)


def test_exact_fit_setup_before_successor_inside_one_window_pass():
    """1. Setup fits exactly before successor inside one window -> PASS."""
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"], precedence={"OPB": ("OPA",)})
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(
            AvailabilityWindow(start=_hh(8), end=_hh(12)),
            AvailabilityWindow(start=_hh(13), end=_hh(17)),
        ),
    )

    result = schedule_routing(
        routing,
        ops,
        {"OPA": timedelta(minutes=20), "OPB": timedelta(minutes=20)},
        catalog,
        HORIZON_START,
        machine_calendars={"M1": calendar},
        horizon_end=_hh(17),
        setup_keys={"OPA": "A", "OPB": "B"},
        setup_matrices={"M1": _TIGHT_SETUP_MATRIX},
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.OPTIMAL
    by_id = {o.operation_id: o for o in result.schedule.operations}
    a, b = by_id["OPA"], by_id["OPB"]
    # Both the processing intervals *and* the setup span must land inside a
    # single window -- there is ample room in the 4-hour morning window, so
    # the whole thing (A, the 10-minute setup, B) comfortably fits in it.
    in_first = _hh(8) <= a.start_time and b.end_time <= _hh(12)
    in_second = _hh(13) <= a.start_time and b.end_time <= _hh(17)
    assert in_first or in_second
    assert b.start_time - a.end_time == timedelta(minutes=10)
    assert b.setup_start == a.end_time
    assert b.setup_end == b.start_time


def test_setup_crossing_closed_shift_gap_is_infeasible():
    """2. Setup would cross a closed shift gap -> INFEASIBLE.

    Window1 holds exactly A's 20 minutes with zero slack; window2 holds
    exactly B's 20 minutes with zero slack. Precedence pins A before B, so
    the only structurally sensible assignment is A->window1, B->window2 --
    which requires the 10-minute setup to start at 12:50, before window2
    opens at 13:00. Under the PRE-FIX model (timing gap only) this exact
    scenario was FEASIBLE, since the ~4h40m shift gap trivially satisfies
    "start[B] >= end[A] + setup" without regard for whether that gap is
    calendar-available time. Post-fix, this must be INFEASIBLE.
    """
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"], precedence={"OPB": ("OPA",)})
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(
            AvailabilityWindow(start=_hh(8), end=_hh(8, 20)),
            AvailabilityWindow(start=_hh(13), end=_hh(13, 20)),
        ),
    )

    result = schedule_routing(
        routing,
        ops,
        {"OPA": timedelta(minutes=20), "OPB": timedelta(minutes=20)},
        catalog,
        HORIZON_START,
        machine_calendars={"M1": calendar},
        horizon_end=_hh(17),
        setup_keys={"OPA": "A", "OPB": "B"},
        setup_matrices={"M1": _TIGHT_SETUP_MATRIX},
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.INFEASIBLE
    assert result.schedule is None


def test_setup_overlapping_maintenance_is_infeasible():
    """3. Setup would overlap maintenance -> INFEASIBLE.

    Same shape as the closed-shift-gap case, expressed via a single
    availability window with a MaintenanceWindow carved out of the middle
    (normalizes to the identical [8:00,8:20) / [13:00,13:20) effective
    windows -- window2 must remain exactly sized to B's own 20-minute
    processing time, with zero slack, otherwise the solver can simply delay
    B further into a larger window and still fit the setup, which would
    make the scenario feasible again and defeat the point of this test)
    rather than two separate declared shifts.
    """
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"], precedence={"OPB": ("OPA",)})
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(
            AvailabilityWindow(start=_hh(8), end=_hh(13, 20)),
        ),
        maintenance_windows=(
            MaintenanceWindow(machine_id="M1", start=_hh(8, 20), end=_hh(13)),
        ),
    )

    result = schedule_routing(
        routing,
        ops,
        {"OPA": timedelta(minutes=20), "OPB": timedelta(minutes=20)},
        catalog,
        HORIZON_START,
        machine_calendars={"M1": calendar},
        horizon_end=_hh(17),
        setup_keys={"OPA": "A", "OPB": "B"},
        setup_matrices={"M1": _TIGHT_SETUP_MATRIX},
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.INFEASIBLE
    assert result.schedule is None


def _adversarial_gap_solution() -> SolverSolution:
    # A entirely fills window1 [8:00,8:20); B entirely fills window2
    # [13:00,13:20). Each operation's OWN processing interval is
    # individually valid (existing calendar check), and the plain timing
    # gap (13:00 - 8:20 = 4h40m >= 10min) is trivially satisfied. Only the
    # PLANNING-01G P1 setup-span containment check catches this: the
    # 10-minute setup, [12:50, 13:00), lies entirely in the gap between the
    # two windows.
    return SolverSolution(
        status=OptimizationStatus.OPTIMAL,
        assignments=(
            SolverAssignment(
                operation_id="OPA",
                machine_id="M1",
                start=timedelta(0),
                end=timedelta(minutes=20),
            ),
            SolverAssignment(
                operation_id="OPB",
                machine_id="M1",
                start=timedelta(hours=5),
                end=timedelta(hours=5, minutes=20),
            ),
        ),
        makespan=timedelta(hours=5, minutes=20),
    )


def test_adversarial_setup_crossing_gap_rejected_by_validation():
    """4. Adversarial: processing interval valid, setup span crosses a gap
    -> SchedulerResultValidationError."""
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"])
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(
            AvailabilityWindow(start=_hh(8), end=_hh(8, 20)),
            AvailabilityWindow(start=_hh(13), end=_hh(13, 20)),
        ),
    )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing,
            ops,
            {"OPA": timedelta(minutes=20), "OPB": timedelta(minutes=20)},
            catalog,
            HORIZON_START,
            solve_fn=lambda problem, config: _adversarial_gap_solution(),
            machine_calendars={"M1": calendar},
            horizon_end=_hh(17),
            setup_keys={"OPA": "A", "OPB": "B"},
            setup_matrices={"M1": _TIGHT_SETUP_MATRIX},
            **_base_kwargs(),
        )


def test_adversarial_setup_overlapping_maintenance_rejected_by_validation():
    """5. Adversarial: setup overlaps maintenance -> SchedulerResultValidationError."""
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"])
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(8), end=_hh(17)),),
        maintenance_windows=(
            MaintenanceWindow(machine_id="M1", start=_hh(8, 20), end=_hh(13)),
        ),
    )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing,
            ops,
            {"OPA": timedelta(minutes=20), "OPB": timedelta(minutes=20)},
            catalog,
            HORIZON_START,
            solve_fn=lambda problem, config: _adversarial_gap_solution(),
            machine_calendars={"M1": calendar},
            horizon_end=_hh(17),
            setup_keys={"OPA": "A", "OPB": "B"},
            setup_matrices={"M1": _TIGHT_SETUP_MATRIX},
            **_base_kwargs(),
        )


def test_setup_starting_exactly_at_window_start_is_allowed():
    """6. Setup starts exactly at availability-window start -> PASS
    (boundary: setup_start == window.start is inclusive)."""
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"])
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(
            AvailabilityWindow(start=_hh(8), end=_hh(12)),
            AvailabilityWindow(start=_hh(13), end=_hh(17)),
        ),
    )

    # A finishes well inside window1; B's setup begins at exactly 13:00 --
    # the instant window2 opens -- and B itself runs 13:10-13:30.
    def _boundary_solution(problem, config):
        return SolverSolution(
            status=OptimizationStatus.OPTIMAL,
            assignments=(
                SolverAssignment(
                    operation_id="OPA",
                    machine_id="M1",
                    start=timedelta(hours=3, minutes=30),
                    end=timedelta(hours=3, minutes=50),
                ),
                SolverAssignment(
                    operation_id="OPB",
                    machine_id="M1",
                    start=timedelta(hours=5, minutes=10),
                    end=timedelta(hours=5, minutes=30),
                ),
            ),
            makespan=timedelta(hours=5, minutes=30),
        )

    result = schedule_routing(
        routing,
        ops,
        {"OPA": timedelta(minutes=20), "OPB": timedelta(minutes=20)},
        catalog,
        HORIZON_START,
        solve_fn=_boundary_solution,
        machine_calendars={"M1": calendar},
        horizon_end=_hh(17),
        setup_keys={"OPA": "A", "OPB": "B"},
        setup_matrices={"M1": _TIGHT_SETUP_MATRIX},
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.OPTIMAL
    by_id = {o.operation_id: o for o in result.schedule.operations}
    assert by_id["OPB"].setup_start == _hh(13)


def test_successor_ending_exactly_at_window_end_is_allowed():
    """7. Successor processing ends exactly at availability-window end
    -> PASS (boundary: B.end == window.end is inclusive)."""
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"])
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(
            AvailabilityWindow(start=_hh(8), end=_hh(12)),
            AvailabilityWindow(start=_hh(13), end=_hh(17)),
        ),
    )

    # B runs 16:40-17:00 -- ending exactly when window2 closes.
    def _boundary_solution(problem, config):
        return SolverSolution(
            status=OptimizationStatus.OPTIMAL,
            assignments=(
                SolverAssignment(
                    operation_id="OPA",
                    machine_id="M1",
                    start=timedelta(0),
                    end=timedelta(minutes=20),
                ),
                SolverAssignment(
                    operation_id="OPB",
                    machine_id="M1",
                    start=timedelta(hours=8, minutes=40),
                    end=timedelta(hours=9),
                ),
            ),
            makespan=timedelta(hours=9),
        )

    result = schedule_routing(
        routing,
        ops,
        {"OPA": timedelta(minutes=20), "OPB": timedelta(minutes=20)},
        catalog,
        HORIZON_START,
        solve_fn=_boundary_solution,
        machine_calendars={"M1": calendar},
        horizon_end=_hh(17),
        setup_keys={"OPA": "A", "OPB": "B"},
        setup_matrices={"M1": _TIGHT_SETUP_MATRIX},
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.OPTIMAL
    by_id = {o.operation_id: o for o in result.schedule.operations}
    assert by_id["OPB"].end_time == _hh(17)


# ---------------------------------------------------------------------------
# P2 — COVERAGE HARDENING
# ---------------------------------------------------------------------------

def test_same_setup_family_zero_setup():
    """Two operations sharing the same setup key/family incur zero setup."""
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"])

    result = schedule_routing(
        routing,
        ops,
        {"OPA": timedelta(minutes=20), "OPB": timedelta(minutes=20)},
        catalog,
        HORIZON_START,
        setup_keys={"OPA": "FAMILY_X", "OPB": "FAMILY_X"},
        setup_matrices={
            "M1": SetupMatrix(
                matrix_id="SM_SAME",
                machine_id="M1",
                entries={("FAMILY_X", "FAMILY_X"): timedelta(0)},
            )
        },
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.OPTIMAL
    by_id = {o.operation_id: o for o in result.schedule.operations}
    ordered = sorted(by_id.values(), key=lambda o: o.start_time)
    assert ordered[1].start_time == ordered[0].end_time
    assert ordered[1].setup_start is None
    assert ordered[1].setup_end is None


def test_default_fallback_policy_used_for_unlisted_transition():
    """DEFAULT_FALLBACK yields exactly SetupMatrix.default_duration for an
    unlisted transition, without raising UnknownSetupTransitionError."""
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    routing = _routing(["OPA", "OPB"], precedence={"OPB": ("OPA",)})

    result = schedule_routing(
        routing,
        ops,
        {"OPA": timedelta(minutes=20), "OPB": timedelta(minutes=20)},
        catalog,
        HORIZON_START,
        setup_keys={"OPA": "A", "OPB": "B"},
        setup_matrices={
            "M1": SetupMatrix(
                matrix_id="SM_FALLBACK",
                machine_id="M1",
                entries={},  # no explicit entries at all
                policy=MissingTransitionPolicy.DEFAULT_FALLBACK,
                default_duration=timedelta(minutes=15),
            )
        },
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.OPTIMAL
    by_id = {o.operation_id: o for o in result.schedule.operations}
    a, b = by_id["OPA"], by_id["OPB"]
    assert b.start_time - a.end_time == timedelta(minutes=15)
    assert b.setup_start == a.end_time
    assert b.setup_end == b.start_time


def test_alternative_machine_flexibility_preserved_with_setup_awareness():
    """A setup-unaware alternative machine remains freely selectable even
    when the problem overall is setup-aware -- picking it avoids the
    setup-aware machine's changeover penalty entirely, and the solver (which
    minimizes makespan) is expected to prefer it here."""
    m1 = _machine("M1")  # setup-aware, expensive changeover
    m2 = _machine("M2")  # not setup-aware at all (no entry in setup_matrices)
    catalog = _catalog(m1, m2)
    ops = {"OPA": _operation("OPA", seq=1), "OPB": _operation("OPB", seq=2)}
    # Precedence forces OPB strictly after OPA regardless of machine choice,
    # so the 20+20=40 minute floor is unavoidable -- without it the solver
    # could simply run both operations in parallel on M1 and M2, which would
    # reach 20 minutes and prove nothing about setup-aware/unaware machine
    # choice.
    routing = _routing(["OPA", "OPB"], precedence={"OPB": ("OPA",)})

    result = schedule_routing(
        routing,
        ops,
        {"OPA": timedelta(minutes=20), "OPB": timedelta(minutes=20)},
        catalog,
        HORIZON_START,
        setup_keys={"OPA": "A", "OPB": "B"},
        setup_matrices={
            "M1": SetupMatrix(
                matrix_id="SM_EXPENSIVE",
                machine_id="M1",
                entries={
                    ("A", "B"): timedelta(hours=5),
                    ("B", "A"): timedelta(hours=5),
                },
            )
            # M2 deliberately has no entry -- setup-unaware for M2.
        },
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.OPTIMAL
    # Makespan of just 40 minutes (back-to-back, zero setup) is reachable by
    # keeping at least the M1->M1 adjacency off the table -- either running
    # both operations on M2 (setup-unaware, so no changeover charged at all)
    # or splitting them across M1 and M2 (no arc between operations on
    # different machines, so no changeover charged either). The 5-hour M1
    # changeover is only paid if both operations land on M1 back-to-back,
    # which the solver avoids since it minimizes makespan -- proving
    # alternative-machine flexibility survives setup-awareness being active
    # for the problem overall.
    assert result.schedule.horizon_end == HORIZON_START + timedelta(minutes=40)


def test_setup_aware_scheduling_is_deterministic_across_repeated_runs():
    """Identical inputs and a fixed-seed, single-worker SolverConfig produce
    byte-identical schedules across repeated calls in setup-aware mode."""
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {
        "OPA": _operation("OPA", seq=1),
        "OPB": _operation("OPB", seq=2),
        "OPC": _operation("OPC", seq=3),
    }
    routing = _routing(["OPA", "OPB", "OPC"])
    durations = {
        "OPA": timedelta(minutes=20),
        "OPB": timedelta(minutes=20),
        "OPC": timedelta(minutes=20),
    }
    setup_keys = {"OPA": "A", "OPB": "B", "OPC": "C"}
    setup_matrices = {"M1": _consecutive_only_matrix("M1")}

    results = [
        schedule_routing(
            routing,
            ops,
            durations,
            catalog,
            HORIZON_START,
            setup_keys=setup_keys,
            setup_matrices=setup_matrices,
            **_base_kwargs(),
        )
        for _ in range(3)
    ]

    reference = [
        (o.operation_id, o.machine_id, o.start_time, o.end_time, o.setup_start, o.setup_end)
        for o in results[0].schedule.operations
    ]
    for result in results[1:]:
        assert result.status == results[0].status
        assert result.schedule.horizon_end == results[0].schedule.horizon_end
        candidate = [
            (o.operation_id, o.machine_id, o.start_time, o.end_time, o.setup_start, o.setup_end)
            for o in result.schedule.operations
        ]
        assert candidate == reference
