"""Tests for the PLANNING-01E finite-capacity scheduler orchestration layer."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.domain.base import Provenance
from backend.domain.enums import MachineType, OperationType, ProvenanceType
from backend.domain.machine import Machine
from backend.domain.operation import Operation
from backend.domain.units import Quantity, Unit
from backend.machines.catalog import MachineCatalog
from backend.planning import optimizer_adapter, scheduler
from backend.planning.exceptions import (
    InvalidCalendarError,
    InvalidSolverProblemError,
    OperationIdentityMismatchError,
    SchedulerResultValidationError,
    UnknownOperationError,
)
from backend.planning.models import (
    AvailabilityWindow,
    MaintenanceWindow,
    OptimizationStatus,
    ResourceCalendar,
    Routing,
)
from backend.planning.scheduler import schedule_routing
from backend.planning.solver_models import (
    SolverAssignment,
    SolverAvailabilityWindow,
    SolverConfig,
    SolverOperation,
    SolverProblem,
    SolverSolution,
)

HORIZON_START = datetime(2030, 1, 1, 8, 0, 0, tzinfo=UTC)
HORIZON_END = datetime(2030, 1, 2, 8, 0, 0, tzinfo=UTC)
CREATED_AT = datetime(2030, 1, 1, 7, 0, 0, tzinfo=UTC)
DETERMINISTIC_CONFIG = SolverConfig(time_limit_seconds=5.0, num_workers=1, random_seed=42)


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
# 1. one operation / one machine -> valid Schedule
# ---------------------------------------------------------------------------

def test_one_operation_one_machine_valid_schedule():
    m1 = _machine("M1")
    catalog = _catalog(m1)
    op = _operation("OP1")
    routing = _routing(["OP1"])

    result = schedule_routing(
        routing,
        {"OP1": op},
        {"OP1": timedelta(seconds=600)},
        catalog,
        HORIZON_START,
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.OPTIMAL
    assert result.schedule is not None
    assert len(result.schedule.operations) == 1
    sched_op = result.schedule.operations[0]
    assert sched_op.operation_id == "OP1"
    assert sched_op.machine_id == "M1"
    assert sched_op.start_time == HORIZON_START
    assert sched_op.end_time == HORIZON_START + timedelta(seconds=600)
    assert result.schedule.horizon_end == HORIZON_START + timedelta(seconds=600)
    assert result.schedule.created_at == CREATED_AT


# ---------------------------------------------------------------------------
# 2. two operations / same machine -> no overlap
# ---------------------------------------------------------------------------

def test_two_operations_same_machine_no_overlap():
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {"OP1": _operation("OP1", seq=1), "OP2": _operation("OP2", seq=2)}
    routing = _routing(["OP1", "OP2"])

    result = schedule_routing(
        routing,
        ops,
        {"OP1": timedelta(seconds=600), "OP2": timedelta(seconds=300)},
        catalog,
        HORIZON_START,
        **_base_kwargs(),
    )

    assert result.status == OptimizationStatus.OPTIMAL
    by_id = {o.operation_id: o for o in result.schedule.operations}
    a, b = by_id["OP1"], by_id["OP2"]
    assert a.end_time <= b.start_time or b.end_time <= a.start_time


# ---------------------------------------------------------------------------
# 3. precedence -> successor starts after predecessor ends
# ---------------------------------------------------------------------------

def test_precedence_successor_starts_after_predecessor_ends():
    m1, m2 = _machine("M1"), _machine("M2")
    catalog = _catalog(m1, m2)
    ops = {"OP1": _operation("OP1", seq=1), "OP2": _operation("OP2", seq=2)}
    routing = _routing(["OP1", "OP2"], precedence={"OP2": ("OP1",)})

    result = schedule_routing(
        routing,
        ops,
        {"OP1": timedelta(seconds=600), "OP2": timedelta(seconds=300)},
        catalog,
        HORIZON_START,
        **_base_kwargs(),
    )

    by_id = {o.operation_id: o for o in result.schedule.operations}
    assert by_id["OP1"].end_time <= by_id["OP2"].start_time


# ---------------------------------------------------------------------------
# 4. alternative machines -> assignment remains inside eligibility
# ---------------------------------------------------------------------------

def test_alternative_machines_assignment_inside_eligibility():
    m1 = _machine("M1", op_types=(OperationType.MILLING,))
    m2 = _machine("M2", op_types=(OperationType.MILLING,))
    m3 = _machine("M3", op_types=(OperationType.TURNING,))  # not eligible for milling
    catalog = _catalog(m1, m2, m3)
    op = _operation("OP1", op_type=OperationType.MILLING)
    routing = _routing(["OP1"])

    result = schedule_routing(
        routing,
        {"OP1": op},
        {"OP1": timedelta(seconds=100)},
        catalog,
        HORIZON_START,
        **_base_kwargs(),
    )

    assert result.schedule.operations[0].machine_id in ("M1", "M2")


# ---------------------------------------------------------------------------
# 5. routing order preserved where relevant (eligibility resolution order)
# ---------------------------------------------------------------------------

def test_routing_order_preserved_in_eligibility_resolution():
    m1 = _machine("M1")
    catalog = _catalog(m1)
    ops = {
        "OPZ": _operation("OPZ", seq=1),
        "OPA": _operation("OPA", seq=2),
    }
    # Deliberately out-of-alphabetical routing order.
    routing = _routing(["OPZ", "OPA"])

    # _build_solver_problem returns a 4-tuple after PLANNING-01G: problem,
    # eligibility, normalized calendar availability, and the resolved setup
    # transition table. This test is setup-unaware, so the last value is {}.
    (
        problem,
        eligibility_by_operation,
        normalized_availability,
        setup_matrix_seconds,
    ) = scheduler._build_solver_problem(
        routing, ops, {"OPZ": timedelta(seconds=10), "OPA": timedelta(seconds=10)}, catalog
    )
    # SolverProblem itself normalizes to operation_id order (documented,
    # tested in PLANNING-01B), but eligibility resolution walks the routing
    # in its own declared order — both are independently correct.
    assert [op.operation_id for op in problem.operations] == ["OPA", "OPZ"]
    assert set(eligibility_by_operation) == {"OPZ", "OPA"}
    assert normalized_availability is None
    assert setup_matrix_seconds == {}


# ---------------------------------------------------------------------------
# 6. missing operation -> fail closed
# ---------------------------------------------------------------------------

def test_missing_operation_fails_closed():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    with pytest.raises(UnknownOperationError):
        schedule_routing(
            routing, {}, {"OP1": timedelta(seconds=10)}, catalog, HORIZON_START, **_base_kwargs()
        )


# ---------------------------------------------------------------------------
# 7. identity mismatch -> fail closed
# ---------------------------------------------------------------------------

def test_identity_mismatch_fails_closed():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    mismatched = {"OP1": _operation("OP_WRONG_ID")}
    with pytest.raises(OperationIdentityMismatchError):
        schedule_routing(
            routing,
            mismatched,
            {"OP1": timedelta(seconds=10)},
            catalog,
            HORIZON_START,
            **_base_kwargs(),
        )


# ---------------------------------------------------------------------------
# 8. missing duration -> fail closed
# ---------------------------------------------------------------------------

def test_missing_duration_fails_closed():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    with pytest.raises(InvalidSolverProblemError):
        schedule_routing(
            routing, {"OP1": _operation("OP1")}, {}, catalog, HORIZON_START, **_base_kwargs()
        )


# ---------------------------------------------------------------------------
# 9. zero eligible machines -> fail closed
# ---------------------------------------------------------------------------

def test_zero_eligible_machines_fails_closed():
    # Catalog has a machine, but it does not support this operation's type.
    catalog = _catalog(_machine("M1", op_types=(OperationType.TURNING,)))
    routing = _routing(["OP1"])
    op = _operation("OP1", op_type=OperationType.MILLING)
    with pytest.raises(InvalidSolverProblemError):
        schedule_routing(
            routing,
            {"OP1": op},
            {"OP1": timedelta(seconds=10)},
            catalog,
            HORIZON_START,
            **_base_kwargs(),
        )


# ---------------------------------------------------------------------------
# 10. deterministic repeated scheduling
# ---------------------------------------------------------------------------

def test_deterministic_repeated_scheduling():
    def build_args():
        catalog = _catalog(_machine("M1"), _machine("M2"))
        ops = {
            "OP1": _operation("OP1", seq=1),
            "OP2": _operation("OP2", seq=2),
            "OP3": _operation("OP3", seq=3),
        }
        routing = _routing(["OP1", "OP2", "OP3"], precedence={"OP3": ("OP1", "OP2")})
        durations = {
            "OP1": timedelta(seconds=100),
            "OP2": timedelta(seconds=150),
            "OP3": timedelta(seconds=50),
        }
        return routing, ops, durations, catalog

    results = []
    for _ in range(3):
        routing, ops, durations, catalog = build_args()
        results.append(
            schedule_routing(routing, ops, durations, catalog, HORIZON_START, **_base_kwargs())
        )

    first = results[0]
    for other in results[1:]:
        assert other.status == first.status
        assert other.schedule == first.schedule
        assert other.objective_values == first.objective_values


# ---------------------------------------------------------------------------
# 11. absolute datetime conversion from offsets
# ---------------------------------------------------------------------------

def test_absolute_datetime_conversion_from_offsets():
    catalog = _catalog(_machine("M1"))
    ops = {"OP1": _operation("OP1", seq=1), "OP2": _operation("OP2", seq=2)}
    routing = _routing(["OP1", "OP2"], precedence={"OP2": ("OP1",)})
    result = schedule_routing(
        routing,
        ops,
        {"OP1": timedelta(seconds=120), "OP2": timedelta(seconds=60)},
        catalog,
        HORIZON_START,
        **_base_kwargs(),
    )
    by_id = {o.operation_id: o for o in result.schedule.operations}
    assert by_id["OP1"].start_time == HORIZON_START
    assert by_id["OP1"].end_time == HORIZON_START + timedelta(seconds=120)
    assert by_id["OP2"].start_time == HORIZON_START + timedelta(seconds=120)
    assert by_id["OP2"].end_time == HORIZON_START + timedelta(seconds=180)


# ---------------------------------------------------------------------------
# 12. horizon_end equals horizon_start + makespan
# ---------------------------------------------------------------------------

def test_horizon_end_equals_horizon_start_plus_makespan():
    catalog = _catalog(_machine("M1"), _machine("M2"))
    ops = {"OP1": _operation("OP1", seq=1), "OP2": _operation("OP2", seq=2)}
    routing = _routing(["OP1", "OP2"])
    result = schedule_routing(
        routing,
        ops,
        {"OP1": timedelta(seconds=100), "OP2": timedelta(seconds=100)},
        catalog,
        HORIZON_START,
        **_base_kwargs(),
    )
    expected_makespan = timedelta(seconds=int(result.objective_values["makespan_seconds"]))
    assert result.schedule.horizon_end == HORIZON_START + expected_makespan
    # Parallel on two machines -> optimal makespan is 100s, not 200s.
    assert expected_makespan == timedelta(seconds=100)


# ---------------------------------------------------------------------------
# 13/14. no OR-Tools types escape scheduler / scheduler.py does not import ortools
# ---------------------------------------------------------------------------

def test_scheduler_module_does_not_import_ortools():
    source = inspect.getsource(scheduler)
    for line in source.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("import ortools")
        assert not stripped.startswith("from ortools")


def test_no_raw_ortools_types_in_result():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(seconds=60)},
        catalog,
        HORIZON_START,
        **_base_kwargs(),
    )

    def _assert_not_ortools(value):
        module = type(value).__module__
        assert not module.startswith("ortools")

    _assert_not_ortools(result.status)
    _assert_not_ortools(result.schedule)
    for op in result.schedule.operations:
        _assert_not_ortools(op.start_time)
        _assert_not_ortools(op.end_time)


# ---------------------------------------------------------------------------
# 15-21. malformed / adversarial solver results via injected solve_fn
# ---------------------------------------------------------------------------

def _fake_solution(**overrides):
    defaults = dict(
        status=OptimizationStatus.OPTIMAL,
        assignments=(
            SolverAssignment(
                operation_id="OP1",
                machine_id="M1",
                start=timedelta(seconds=0),
                end=timedelta(seconds=60),
            ),
        ),
        makespan=timedelta(seconds=60),
        objective_value=Decimal(60),
        solve_time_seconds=0.01,
    )
    defaults.update(overrides)
    return SolverSolution(**defaults)


def _single_op_setup():
    catalog = _catalog(_machine("M1"), _machine("M2"))
    routing = _routing(["OP1"])
    ops = {"OP1": _operation("OP1")}
    durations = {"OP1": timedelta(seconds=60)}
    return routing, ops, durations, catalog


def test_malformed_result_missing_operation_rejected():
    routing, ops, durations, catalog = _single_op_setup()
    ops["OP2"] = _operation("OP2", seq=2)
    durations["OP2"] = timedelta(seconds=30)
    routing = _routing(["OP1", "OP2"])

    def fake_solve(problem, config):
        # Only returns an assignment for OP1, silently dropping OP2.
        return _fake_solution()

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
        )


def test_duplicate_solver_assignment_rejected():
    routing, ops, durations, catalog = _single_op_setup()

    def fake_solve(problem, config):
        a = SolverAssignment(
            operation_id="OP1", machine_id="M1", start=timedelta(0), end=timedelta(seconds=60)
        )
        return _fake_solution(assignments=(a, a))

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
        )


def test_ineligible_machine_assignment_rejected():
    routing, ops, durations, catalog = _single_op_setup()
    catalog.register(_machine("M3", op_types=(OperationType.TURNING,)))

    def fake_solve(problem, config):
        return _fake_solution(
            assignments=(
                SolverAssignment(
                    operation_id="OP1",
                    machine_id="M3",  # registered, but not eligible for OP1's type
                    start=timedelta(0),
                    end=timedelta(seconds=60),
                ),
            )
        )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
        )


def test_overlapping_same_machine_assignments_rejected():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1", "OP2"])
    ops = {"OP1": _operation("OP1", seq=1), "OP2": _operation("OP2", seq=2)}
    durations = {"OP1": timedelta(seconds=60), "OP2": timedelta(seconds=60)}

    def fake_solve(problem, config):
        return _fake_solution(
            assignments=(
                SolverAssignment(
                    operation_id="OP1",
                    machine_id="M1",
                    start=timedelta(0),
                    end=timedelta(seconds=60),
                ),
                SolverAssignment(
                    operation_id="OP2",
                    machine_id="M1",
                    start=timedelta(seconds=30),  # overlaps OP1's 0-60 window
                    end=timedelta(seconds=90),
                ),
            ),
            makespan=timedelta(seconds=90),
        )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
        )


def test_precedence_violating_result_rejected():
    catalog = _catalog(_machine("M1"), _machine("M2"))
    routing = _routing(["OP1", "OP2"], precedence={"OP2": ("OP1",)})
    ops = {"OP1": _operation("OP1", seq=1), "OP2": _operation("OP2", seq=2)}
    durations = {"OP1": timedelta(seconds=60), "OP2": timedelta(seconds=30)}

    def fake_solve(problem, config):
        return _fake_solution(
            assignments=(
                SolverAssignment(
                    operation_id="OP1",
                    machine_id="M1",
                    start=timedelta(seconds=30),
                    end=timedelta(seconds=90),
                ),
                SolverAssignment(
                    # starts before OP1 (its predecessor) has finished
                    operation_id="OP2",
                    machine_id="M2",
                    start=timedelta(0),
                    end=timedelta(seconds=30),
                ),
            ),
            makespan=timedelta(seconds=90),
        )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
        )


def test_duration_mismatch_result_rejected():
    routing, ops, durations, catalog = _single_op_setup()

    def fake_solve(problem, config):
        return _fake_solution(
            assignments=(
                SolverAssignment(
                    operation_id="OP1",
                    machine_id="M1",
                    start=timedelta(0),
                    end=timedelta(seconds=45),  # requested duration is 60s
                ),
            ),
            makespan=timedelta(seconds=45),
        )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
        )


def test_unknown_machine_assignment_rejected():
    routing, ops, durations, catalog = _single_op_setup()

    def fake_solve(problem, config):
        return _fake_solution(
            assignments=(
                SolverAssignment(
                    operation_id="OP1",
                    machine_id="GHOST_MACHINE",  # not registered anywhere
                    start=timedelta(0),
                    end=timedelta(seconds=60),
                ),
            )
        )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
        )


# ---------------------------------------------------------------------------
# 22-28. PLANNING-01E REVIEW FIX R1 — additional adversarial / boundary tests
# ---------------------------------------------------------------------------

def test_makespan_none_with_assignments_rejected():
    routing, ops, durations, catalog = _single_op_setup()

    def fake_solve(problem, config):
        return _fake_solution(makespan=None)

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
        )


def test_negative_assignment_start_rejected():
    routing, ops, durations, catalog = _single_op_setup()

    def fake_solve(problem, config):
        # SolverAssignment itself only rejects end <= start, not a negative
        # start offset -- this is the narrowest valid seam through which a
        # negative start can reach the scheduler's own independent check,
        # without bypassing any other domain invariant.
        return _fake_solution(
            assignments=(
                SolverAssignment(
                    operation_id="OP1",
                    machine_id="M1",
                    start=timedelta(seconds=-10),
                    end=timedelta(seconds=50),
                ),
            ),
            makespan=timedelta(seconds=50),
        )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
        )


def test_makespan_mismatch_rejected():
    routing, ops, durations, catalog = _single_op_setup()

    def fake_solve(problem, config):
        return _fake_solution(
            assignments=(
                SolverAssignment(
                    operation_id="OP1",
                    machine_id="M1",
                    start=timedelta(0),
                    end=timedelta(seconds=20),
                ),
            ),
            makespan=timedelta(seconds=25),  # does not match the max end of 20s
        )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
        )


def test_unknown_operation_id_in_result_rejected():
    routing, ops, durations, catalog = _single_op_setup()

    def fake_solve(problem, config):
        return _fake_solution(
            assignments=(
                SolverAssignment(
                    operation_id="OP1",
                    machine_id="M1",
                    start=timedelta(0),
                    end=timedelta(seconds=60),
                ),
                SolverAssignment(
                    operation_id="OP_GHOST",  # never part of this problem
                    machine_id="M1",
                    start=timedelta(seconds=60),
                    end=timedelta(seconds=90),
                ),
            ),
            makespan=timedelta(seconds=90),
        )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
        )


def test_default_created_at_is_timezone_aware():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    before = datetime.now(UTC)

    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(seconds=60)},
        catalog,
        HORIZON_START,
        schedule_id="SCHED1",
        result_id="RESULT1",
        scenario_id="SCEN1",
        solver_config=DETERMINISTIC_CONFIG,
        # created_at deliberately omitted -- exercises the datetime.now(UTC)
        # default path, which no other test in this file exercises.
    )

    after = datetime.now(UTC)
    created_at = result.schedule.created_at
    assert created_at.tzinfo is not None and created_at.tzinfo.utcoffset(created_at) is not None
    assert before <= created_at <= after


def test_naive_horizon_start_rejected():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    naive_horizon_start = datetime(2030, 1, 1, 8, 0, 0)  # no tzinfo

    with pytest.raises(InvalidSolverProblemError):
        schedule_routing(
            routing,
            {"OP1": _operation("OP1")},
            {"OP1": timedelta(seconds=60)},
            catalog,
            naive_horizon_start,
            **_base_kwargs(),
        )


def test_naive_created_at_rejected():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    naive_created_at = datetime(2030, 1, 1, 7, 0, 0)  # no tzinfo

    with pytest.raises(InvalidSolverProblemError):
        schedule_routing(
            routing,
            {"OP1": _operation("OP1")},
            {"OP1": timedelta(seconds=60)},
            catalog,
            HORIZON_START,
            **_base_kwargs(created_at=naive_created_at),
        )


# ---------------------------------------------------------------------------
# Status handling: infeasible / error never fabricate a schedule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", [OptimizationStatus.INFEASIBLE, OptimizationStatus.ERROR])
def test_infeasible_and_error_never_fabricate_schedule(status):
    routing, ops, durations, catalog = _single_op_setup()

    def fake_solve(problem, config):
        return SolverSolution(status=status, solve_time_seconds=0.01)

    result = schedule_routing(
        routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
    )
    assert result.status == status
    assert result.schedule is None


def test_time_limit_with_no_incumbent_returns_no_schedule():
    routing, ops, durations, catalog = _single_op_setup()

    def fake_solve(problem, config):
        return SolverSolution(status=OptimizationStatus.TIME_LIMIT, solve_time_seconds=5.0)

    result = schedule_routing(
        routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
    )
    assert result.status == OptimizationStatus.TIME_LIMIT
    assert result.schedule is None


def test_time_limit_with_incumbent_is_validated_and_scheduled():
    # Defensive path: current PLANNING-01B adapter never actually returns
    # TIME_LIMIT with assignments (see module docstring), but scheduler.py
    # must not assume that forever - it checks solution.assignments, not
    # solution.status, to decide whether a schedule can be built.
    routing, ops, durations, catalog = _single_op_setup()

    def fake_solve(problem, config):
        return _fake_solution(status=OptimizationStatus.TIME_LIMIT)

    result = schedule_routing(
        routing, ops, durations, catalog, HORIZON_START, **_base_kwargs(solve_fn=fake_solve)
    )
    assert result.status == OptimizationStatus.TIME_LIMIT
    assert result.schedule is not None


# ---------------------------------------------------------------------------
# PLANNING-01F — calendar / shift / maintenance availability integration
# ---------------------------------------------------------------------------
#
# All tests below use schedule_routing's real CP-SAT adapter (not an
# injected solve_fn) unless noted otherwise, to prove the constraints are
# enforced *inside* the solver, not merely checked after the fact -- except
# tests 23/24, which specifically target the independent post-solve
# validation layer via an adversarial solve_fn (the same pattern already
# used throughout this file for PLANNING-01E's own adversarial tests).


def test_calendar_both_or_neither_enforced():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    with pytest.raises(InvalidSolverProblemError):
        schedule_routing(
            routing,
            {"OP1": _operation("OP1")},
            {"OP1": timedelta(seconds=60)},
            catalog,
            HORIZON_START,
            **_base_kwargs(horizon_end=HORIZON_END),  # machine_calendars omitted
        )
    calendar = ResourceCalendar(calendar_id="C1", timezone="UTC")
    with pytest.raises(InvalidSolverProblemError):
        schedule_routing(
            routing,
            {"OP1": _operation("OP1")},
            {"OP1": timedelta(seconds=60)},
            catalog,
            HORIZON_START,
            **_base_kwargs(machine_calendars={"M1": calendar}),  # horizon_end omitted
        )


def test_naive_horizon_end_fails_closed():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(calendar_id="C1", timezone="UTC")
    with pytest.raises(InvalidSolverProblemError):
        schedule_routing(
            routing,
            {"OP1": _operation("OP1")},
            {"OP1": timedelta(seconds=60)},
            catalog,
            HORIZON_START,
            **_base_kwargs(
                machine_calendars={"M1": calendar},
                horizon_end=datetime(2030, 1, 2, 8, 0, 0),  # naive
            ),
        )


def test_horizon_end_not_after_horizon_start_fails_closed():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(calendar_id="C1", timezone="UTC")
    with pytest.raises(InvalidSolverProblemError):
        schedule_routing(
            routing,
            {"OP1": _operation("OP1")},
            {"OP1": timedelta(seconds=60)},
            catalog,
            HORIZON_START,
            **_base_kwargs(machine_calendars={"M1": calendar}, horizon_end=HORIZON_START),
        )


def test_unknown_machine_in_machine_calendars_fails_closed():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(calendar_id="C1", timezone="UTC")
    with pytest.raises(InvalidCalendarError):
        schedule_routing(
            routing,
            {"OP1": _operation("OP1")},
            {"OP1": timedelta(seconds=60)},
            catalog,
            HORIZON_START,
            **_base_kwargs(machine_calendars={"GHOST": calendar}, horizon_end=HORIZON_END),
        )


# 1. machine continuously available -> existing scheduling behavior preserved
def test_1a_omitting_calendars_matches_original_planning_01e_behavior():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(seconds=600)},
        catalog,
        HORIZON_START,
        **_base_kwargs(),
    )
    assert result.status == OptimizationStatus.OPTIMAL
    assert result.schedule.operations[0].start_time == HORIZON_START
    assert result.schedule.operations[0].end_time == HORIZON_START + timedelta(seconds=600)


def test_1b_explicit_continuous_calendar_matches_calendar_unaware_result():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(AvailabilityWindow(start=HORIZON_START, end=HORIZON_END),),
    )
    baseline = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(seconds=600)},
        catalog,
        HORIZON_START,
        **_base_kwargs(),
    )
    calendar_aware = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(seconds=600)},
        catalog,
        HORIZON_START,
        **_base_kwargs(machine_calendars={"M1": calendar}, horizon_end=HORIZON_END),
    )
    assert calendar_aware.schedule.operations == baseline.schedule.operations
    assert calendar_aware.status == baseline.status


# 2. one shift window -> operation scheduled inside window
def test_2_operation_scheduled_inside_single_shift_window():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(10), end=_hh(14)),),
    )
    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(hours=2)},
        catalog,
        HORIZON_START,
        **_base_kwargs(machine_calendars={"M1": calendar}, horizon_end=HORIZON_END),
    )
    op = result.schedule.operations[0]
    assert _hh(10) <= op.start_time and op.end_time <= _hh(14)


# 3 & 4. operation cannot start before shift begins / cannot end after shift closes
def test_3_and_4_operation_stays_within_shift_bounds():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(9), end=_hh(9, 30)),),
    )
    # Duration exactly fills the window -- the only feasible placement is
    # start == window.start, end == window.end; any earlier start or later
    # end is impossible by construction, proving both bounds are enforced.
    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(minutes=30)},
        catalog,
        HORIZON_START,
        **_base_kwargs(machine_calendars={"M1": calendar}, horizon_end=HORIZON_END),
    )
    op = result.schedule.operations[0]
    assert op.start_time == _hh(9)
    assert op.end_time == _hh(9, 30)


# 5. two separate shifts -> operation uses one complete window
def test_5_operation_uses_one_complete_window_of_two_shifts():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC",
        availability_windows=(
            AvailabilityWindow(start=_hh(8), end=_hh(12)),
            AvailabilityWindow(start=_hh(13), end=_hh(17)),
        ),
    )
    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(hours=3)},
        catalog,
        HORIZON_START,
        **_base_kwargs(machine_calendars={"M1": calendar}, horizon_end=HORIZON_END),
    )
    op = result.schedule.operations[0]
    in_first = _hh(8) <= op.start_time and op.end_time <= _hh(12)
    in_second = _hh(13) <= op.start_time and op.end_time <= _hh(17)
    assert in_first or in_second
    assert not (op.start_time < _hh(12) < op.end_time)  # never straddles the gap


# 6. operation cannot span lunch/closed gap
def test_6_operation_cannot_span_closed_gap():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC",
        availability_windows=(
            AvailabilityWindow(start=_hh(8), end=_hh(12)),
            AvailabilityWindow(start=_hh(13), end=_hh(17)),
        ),
    )
    # 6 hours does not fit in either individual 4-hour window.
    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(hours=6)},
        catalog,
        HORIZON_START,
        **_base_kwargs(machine_calendars={"M1": calendar}, horizon_end=HORIZON_END),
    )
    assert result.status == OptimizationStatus.INFEASIBLE
    assert result.schedule is None


# 8. operation cannot overlap maintenance
def test_8_operation_never_overlaps_maintenance():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(8), end=_hh(17)),),
        maintenance_windows=(MaintenanceWindow(machine_id="M1", start=_hh(12), end=_hh(13, 30)),),
    )
    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(hours=3)},
        catalog,
        HORIZON_START,
        **_base_kwargs(machine_calendars={"M1": calendar}, horizon_end=HORIZON_END),
    )
    op = result.schedule.operations[0]
    maintenance_start, maintenance_end = _hh(12), _hh(13, 30)
    assert op.end_time <= maintenance_start or op.start_time >= maintenance_end


# 17. operation longer than every available window -> infeasible
def test_17_operation_longer_than_every_window_is_infeasible():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(8), end=_hh(10)),),  # 2h only
    )
    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(hours=3)},
        catalog,
        HORIZON_START,
        **_base_kwargs(machine_calendars={"M1": calendar}, horizon_end=HORIZON_END),
    )
    assert result.status == OptimizationStatus.INFEASIBLE
    assert result.schedule is None


# 18. precedence still respected with calendars
def test_18_precedence_respected_with_calendars():
    catalog = _catalog(_machine("M1"), _machine("M2"))
    ops = {"OP1": _operation("OP1", seq=1), "OP2": _operation("OP2", seq=2)}
    routing = _routing(["OP1", "OP2"], precedence={"OP2": ("OP1",)})
    calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(8), end=_hh(20)),),
    )
    result = schedule_routing(
        routing,
        ops,
        {"OP1": timedelta(hours=2), "OP2": timedelta(hours=1)},
        catalog,
        HORIZON_START,
        **_base_kwargs(
            machine_calendars={"M1": calendar, "M2": calendar}, horizon_end=HORIZON_END
        ),
    )
    by_id = {o.operation_id: o for o in result.schedule.operations}
    assert by_id["OP1"].end_time <= by_id["OP2"].start_time


# 19. same-machine non-overlap still respected with calendars
def test_19_same_machine_non_overlap_respected_with_calendars():
    catalog = _catalog(_machine("M1"))
    ops = {"OP1": _operation("OP1", seq=1), "OP2": _operation("OP2", seq=2)}
    routing = _routing(["OP1", "OP2"])
    calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(8), end=_hh(20)),),
    )
    result = schedule_routing(
        routing,
        ops,
        {"OP1": timedelta(hours=2), "OP2": timedelta(hours=2)},
        catalog,
        HORIZON_START,
        **_base_kwargs(machine_calendars={"M1": calendar}, horizon_end=HORIZON_END),
    )
    by_id = {o.operation_id: o for o in result.schedule.operations}
    a, b = by_id["OP1"], by_id["OP2"]
    assert a.end_time <= b.start_time or b.end_time <= a.start_time


# 20. alternative eligible machines with different calendars -> solver chooses feasible one
def test_20_solver_chooses_the_feasible_machine_among_alternatives():
    m1 = _machine("M1")
    m2 = _machine("M2")
    catalog = _catalog(m1, m2)
    routing = _routing(["OP1"])
    # M1 has no window big enough; M2 does.
    m1_calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(8), end=_hh(9)),),  # 1h only
    )
    m2_calendar = ResourceCalendar(
        calendar_id="C2", timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(8), end=_hh(20)),),
    )
    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(hours=3)},
        catalog,
        HORIZON_START,
        **_base_kwargs(
            machine_calendars={"M1": m1_calendar, "M2": m2_calendar}, horizon_end=HORIZON_END
        ),
    )
    assert result.status == OptimizationStatus.OPTIMAL
    assert result.schedule.operations[0].machine_id == "M2"


# 21. machine technically eligible but unavailable -> not chosen
def test_21_eligible_but_unavailable_machine_is_not_chosen():
    m1 = _machine("M1")
    m2 = _machine("M2")
    catalog = _catalog(m1, m2)
    routing = _routing(["OP1"])
    m1_closed = ResourceCalendar(calendar_id="C1", timezone="UTC", availability_windows=())
    m2_open = ResourceCalendar(
        calendar_id="C2", timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(8), end=_hh(20)),),
    )
    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(hours=1)},
        catalog,
        HORIZON_START,
        **_base_kwargs(
            machine_calendars={"M1": m1_closed, "M2": m2_open}, horizon_end=HORIZON_END
        ),
    )
    assert result.status == OptimizationStatus.OPTIMAL
    assert result.schedule.operations[0].machine_id == "M2"


# 22. all eligible machines unavailable -> INFEASIBLE, not fabricated
def test_22_all_eligible_machines_unavailable_is_infeasible_not_fabricated():
    catalog = _catalog(_machine("M1"), _machine("M2"))
    routing = _routing(["OP1"])
    closed = ResourceCalendar(calendar_id="C1", timezone="UTC", availability_windows=())
    result = schedule_routing(
        routing,
        {"OP1": _operation("OP1")},
        {"OP1": timedelta(hours=1)},
        catalog,
        HORIZON_START,
        **_base_kwargs(machine_calendars={"M1": closed, "M2": closed}, horizon_end=HORIZON_END),
    )
    assert result.status == OptimizationStatus.INFEASIBLE
    assert result.schedule is None


# 23. post-solve validation rejects assignment outside availability
def test_23_post_solve_validation_rejects_assignment_outside_availability():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(8), end=_hh(10)),),
    )

    def fake_solve(problem, config):
        # Placed at 11:00-12:00 -- entirely outside the only availability
        # window (08:00-10:00) -- an adversarial/buggy solve_fn result the
        # independent post-solve check must catch on its own.
        return SolverSolution(
            status=OptimizationStatus.OPTIMAL,
            assignments=(
                SolverAssignment(
                    operation_id="OP1",
                    machine_id="M1",
                    start=timedelta(hours=3),
                    end=timedelta(hours=4),
                ),
            ),
            makespan=timedelta(hours=4),
            solve_time_seconds=0.01,
        )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing,
            {"OP1": _operation("OP1")},
            {"OP1": timedelta(hours=1)},
            catalog,
            HORIZON_START,
            **_base_kwargs(
                machine_calendars={"M1": calendar}, horizon_end=HORIZON_END, solve_fn=fake_solve
            ),
        )


# 24. post-solve validation rejects maintenance overlap
def test_24_post_solve_validation_rejects_maintenance_overlap():
    catalog = _catalog(_machine("M1"))
    routing = _routing(["OP1"])
    calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC",
        availability_windows=(AvailabilityWindow(start=_hh(8), end=_hh(17)),),
        maintenance_windows=(MaintenanceWindow(machine_id="M1", start=_hh(12), end=_hh(13)),),
    )

    def fake_solve(problem, config):
        # 12:30-13:15 falls inside the raw 08:00-17:00 availability window
        # but squarely inside the maintenance-carved gap (12:00-13:00) --
        # this specifically proves the check catches a maintenance overlap,
        # not merely a generic "outside the raw calendar" mismatch.
        return SolverSolution(
            status=OptimizationStatus.OPTIMAL,
            assignments=(
                SolverAssignment(
                    operation_id="OP1",
                    machine_id="M1",
                    start=timedelta(hours=4, minutes=30),
                    end=timedelta(hours=5, minutes=15),
                ),
            ),
            makespan=timedelta(hours=5, minutes=15),
            solve_time_seconds=0.01,
        )

    with pytest.raises(SchedulerResultValidationError):
        schedule_routing(
            routing,
            {"OP1": _operation("OP1")},
            {"OP1": timedelta(minutes=45)},
            catalog,
            HORIZON_START,
            **_base_kwargs(
                machine_calendars={"M1": calendar}, horizon_end=HORIZON_END, solve_fn=fake_solve
            ),
        )


# 25. repeated identical request -> deterministic result (calendar-aware)
def test_25_deterministic_repeated_scheduling_with_calendars():
    def build_args():
        catalog = _catalog(_machine("M1"), _machine("M2"))
        ops = {
            "OP1": _operation("OP1", seq=1),
            "OP2": _operation("OP2", seq=2),
            "OP3": _operation("OP3", seq=3),
        }
        routing = _routing(["OP1", "OP2", "OP3"], precedence={"OP3": ("OP1", "OP2")})
        durations = {
            "OP1": timedelta(hours=1),
            "OP2": timedelta(hours=1, minutes=30),
            "OP3": timedelta(minutes=30),
        }
        calendar = ResourceCalendar(
            calendar_id="C1", timezone="UTC",
            availability_windows=(
                AvailabilityWindow(start=_hh(8), end=_hh(12)),
                AvailabilityWindow(start=_hh(13), end=_hh(20)),
            ),
            maintenance_windows=(
                MaintenanceWindow(machine_id="M2", start=_hh(9), end=_hh(9, 30)),
            ),
        )
        return routing, ops, durations, catalog, calendar

    results = []
    for _ in range(3):
        routing, ops, durations, catalog, calendar = build_args()
        results.append(
            schedule_routing(
                routing,
                ops,
                durations,
                catalog,
                HORIZON_START,
                **_base_kwargs(
                    machine_calendars={"M1": calendar, "M2": calendar}, horizon_end=HORIZON_END
                ),
            )
        )

    first = results[0]
    for other in results[1:]:
        assert other.status == first.status
        assert other.schedule == first.schedule
        assert other.objective_values == first.objective_values


# ---------------------------------------------------------------------------
# PLANNING-01F REVIEW FIX R1 -- horizon-bound regression
# ---------------------------------------------------------------------------
#
# 26. a calendar-bound predecessor forced into a late window, chained by
# precedence into a fully calendar-unaware successor, must not be falsely
# reported INFEASIBLE by too-tight a CP-SAT variable-domain bound.
#
# Important, verified during the review-fix: this exact mixed state (one
# machine with an explicit machine_availability entry, another machine with
# NO entry at all) cannot actually arise through schedule_routing()'s public
# API -- _build_solver_problem / calendar_constraints.resolve_machine_calendars
# always resolve *every* eligible machine into an explicit entry whenever
# calendar-awareness is enabled at all (a "calendar-unaware" machine gets the
# documented continuous-availability default, itself bounded by the caller's
# own horizon_end -- never a fully absent/unbounded entry). This was
# confirmed directly: the same scenario driven through schedule_routing()
# with a tight horizon_end already succeeds under the pre-fix max(...)
# formula too, because the "calendar-unaware" machine's own resolved window
# already reflects horizon_end.
#
# The defect lives one layer down, in optimizer_adapter.solve() /
# SolverProblem's own general contract: SolverProblem explicitly documents
# and allows partial machine_availability coverage (see its own docstring),
# and any direct caller of solve() -- not just schedule_routing() -- can
# construct exactly this mixed state. This regression test therefore
# exercises SolverProblem and optimizer_adapter.solve() directly: real
# domain objects (SolverOperation, SolverAvailabilityWindow, SolverProblem,
# SolverConfig), the real CP-SAT adapter, no fake solve_fn -- this is the
# layer where the bug is actually observable and where the fix actually
# needs to hold.
def test_26_horizon_bound_accommodates_calendar_unaware_successor_after_late_calendar_predecessor():
    # OP1: calendar-bound to M1, whose only usable window is late and exactly
    # duration-sized -- forces OP1 to run at [1000, 1050].
    # OP2: calendar-unaware -- M2 has NO entry in machine_availability at all
    # (the same meaning "fully calendar-unaware" has throughout PLANNING-01B/
    # 01E: continuously available, unbounded except by horizon_seconds).
    # OP2 depends on OP1 and needs 100s on top of OP1's late finish, so its
    # true required completion (1150) exceeds
    # max_machine_availability_end_seconds (1050) -- exactly the case the
    # old max(...) bound could not accommodate.
    problem = SolverProblem(
        operations=(
            SolverOperation(
                operation_id="OP1",
                duration=timedelta(seconds=50),
                eligible_machine_ids=("M1",),
            ),
            SolverOperation(
                operation_id="OP2",
                duration=timedelta(seconds=100),
                eligible_machine_ids=("M2",),
                predecessor_operation_ids=("OP1",),
            ),
        ),
        machine_availability={
            "M1": (SolverAvailabilityWindow(start_offset=1000, end_offset=1050),),
            # M2 deliberately has no key at all.
        },
    )
    assert problem.horizon_seconds == 150
    assert problem.max_machine_availability_end_seconds == 1050

    solution = optimizer_adapter.solve(problem, DETERMINISTIC_CONFIG)

    assert solution.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE)
    by_id = {a.operation_id: a for a in solution.assignments}
    assert by_id["OP1"].machine_id == "M1"
    assert by_id["OP2"].machine_id == "M2"
    assert by_id["OP1"].start == timedelta(seconds=1000)
    assert by_id["OP1"].end == timedelta(seconds=1050)
    assert by_id["OP2"].start >= by_id["OP1"].end
    # OP2's completion (1150s) legitimately exceeds
    # max_machine_availability_end_seconds (1050s) -- proving the variable
    # domain was not truncated to that value.
    assert by_id["OP2"].end == timedelta(seconds=1150)
    assert by_id["OP2"].end > timedelta(seconds=problem.max_machine_availability_end_seconds)
