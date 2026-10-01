"""Tests for the PLANNING-01B OR-Tools CP-SAT optimizer adapter foundation."""

from __future__ import annotations

import inspect
from datetime import timedelta
from decimal import Decimal

import pytest

from backend.planning import optimizer_adapter, solver_models
from backend.planning.exceptions import (
    InvalidSolverProblemError,
    PlanningError,
    PrecedenceCycleError,
)
from backend.planning.models import OptimizationStatus
from backend.planning.optimizer_adapter import map_cp_sat_status, solve
from backend.planning.solver_models import (
    SolverConfig,
    SolverOperation,
    SolverProblem,
    solver_seconds_to_timedelta,
    timedelta_to_solver_seconds,
)


def _op(op_id, seconds, machines, preds=()):
    return SolverOperation(
        operation_id=op_id,
        duration=timedelta(seconds=seconds),
        eligible_machine_ids=tuple(machines),
        predecessor_operation_ids=tuple(preds),
    )


DETERMINISTIC_CONFIG = SolverConfig(time_limit_seconds=5.0, num_workers=1, random_seed=42)


# ---------------------------------------------------------------------------
# 1. single operation / single machine
# ---------------------------------------------------------------------------

def test_single_operation_single_machine():
    problem = SolverProblem(operations=(_op("OP1", 10, ["M1"]),))
    solution = solve(problem, DETERMINISTIC_CONFIG)
    assert solution.status == OptimizationStatus.OPTIMAL
    assert len(solution.assignments) == 1
    a = solution.assignments[0]
    assert a.operation_id == "OP1"
    assert a.machine_id == "M1"
    assert a.start == timedelta(seconds=0)
    assert a.end == timedelta(seconds=10)
    assert solution.makespan == timedelta(seconds=10)


# ---------------------------------------------------------------------------
# 2. two operations / same machine -> non-overlap
# ---------------------------------------------------------------------------

def test_two_operations_same_machine_no_overlap():
    problem = SolverProblem(
        operations=(_op("OP1", 10, ["M1"]), _op("OP2", 10, ["M1"]))
    )
    solution = solve(problem, DETERMINISTIC_CONFIG)
    assert solution.status == OptimizationStatus.OPTIMAL
    by_id = {a.operation_id: a for a in solution.assignments}
    a1, a2 = by_id["OP1"], by_id["OP2"]
    # Same machine, so the two intervals must not overlap.
    assert a1.end <= a2.start or a2.end <= a1.start
    assert solution.makespan == timedelta(seconds=20)


# ---------------------------------------------------------------------------
# 3. precedence enforced
# ---------------------------------------------------------------------------

def test_precedence_enforced():
    problem = SolverProblem(
        operations=(
            _op("OP1", 10, ["M1", "M2"]),
            _op("OP2", 10, ["M1", "M2"], preds=["OP1"]),
        )
    )
    solution = solve(problem, DETERMINISTIC_CONFIG)
    assert solution.status == OptimizationStatus.OPTIMAL
    by_id = {a.operation_id: a for a in solution.assignments}
    assert by_id["OP1"].end <= by_id["OP2"].start
    # Two machines available and no shared-machine constraint forced by
    # precedence alone, so the optimal makespan is exactly the serial chain.
    assert solution.makespan == timedelta(seconds=20)


# ---------------------------------------------------------------------------
# 4. two eligible machines -> one selected
# ---------------------------------------------------------------------------

def test_alternative_eligible_machines_exactly_one_selected():
    problem = SolverProblem(operations=(_op("OP1", 10, ["M1", "M2"]),))
    solution = solve(problem, DETERMINISTIC_CONFIG)
    assert solution.status == OptimizationStatus.OPTIMAL
    assert len(solution.assignments) == 1
    assert solution.assignments[0].machine_id in ("M1", "M2")


# ---------------------------------------------------------------------------
# 5. zero eligible machines -> rejected (fail closed)
# ---------------------------------------------------------------------------

def test_zero_eligible_machines_rejected():
    with pytest.raises(InvalidSolverProblemError):
        _op("OP1", 10, [])


# ---------------------------------------------------------------------------
# 6. duplicate operation ID -> rejected
# ---------------------------------------------------------------------------

def test_duplicate_operation_id_rejected():
    with pytest.raises(InvalidSolverProblemError):
        SolverProblem(operations=(_op("OP1", 10, ["M1"]), _op("OP1", 5, ["M2"])))


# ---------------------------------------------------------------------------
# 7. duplicate eligible machine ID -> rejected
# ---------------------------------------------------------------------------

def test_duplicate_eligible_machine_id_rejected():
    with pytest.raises(InvalidSolverProblemError):
        _op("OP1", 10, ["M1", "M1"])


# ---------------------------------------------------------------------------
# 8. missing predecessor -> rejected
# ---------------------------------------------------------------------------

def test_missing_predecessor_rejected():
    with pytest.raises(InvalidSolverProblemError):
        SolverProblem(operations=(_op("OP1", 10, ["M1"], preds=["DOES_NOT_EXIST"]),))


# ---------------------------------------------------------------------------
# 9. self predecessor -> rejected
# ---------------------------------------------------------------------------

def test_self_predecessor_rejected():
    with pytest.raises(InvalidSolverProblemError):
        _op("OP1", 10, ["M1"], preds=["OP1"])


# ---------------------------------------------------------------------------
# 10. precedence cycle -> rejected
# ---------------------------------------------------------------------------

def test_precedence_cycle_rejected():
    with pytest.raises(PrecedenceCycleError):
        SolverProblem(
            operations=(
                _op("OP1", 10, ["M1"], preds=["OP2"]),
                _op("OP2", 10, ["M1"], preds=["OP1"]),
            )
        )


def test_precedence_cycle_error_is_a_planning_error():
    # Confirms the narrow exception hierarchy requested by the ticket.
    assert issubclass(PrecedenceCycleError, PlanningError)
    assert issubclass(InvalidSolverProblemError, PlanningError)


# ---------------------------------------------------------------------------
# 11. makespan minimized on a tiny hand-checkable problem
# ---------------------------------------------------------------------------

def test_makespan_minimized_hand_checkable():
    # Two 10s operations, two machines, no precedence -> optimal makespan
    # is 10s (both run in parallel), never 20s.
    problem = SolverProblem(
        operations=(_op("OP1", 10, ["M1", "M2"]), _op("OP2", 10, ["M1", "M2"]))
    )
    solution = solve(problem, DETERMINISTIC_CONFIG)
    assert solution.status == OptimizationStatus.OPTIMAL
    assert solution.makespan == timedelta(seconds=10)
    by_id = {a.operation_id: a for a in solution.assignments}
    assert by_id["OP1"].machine_id != by_id["OP2"].machine_id


# ---------------------------------------------------------------------------
# 12. deterministic repeated solve
# ---------------------------------------------------------------------------

def test_deterministic_repeated_solve():
    def build_problem():
        return SolverProblem(
            operations=(
                _op("OP1", 10, ["M1", "M2"]),
                _op("OP2", 15, ["M1", "M2"], preds=["OP1"]),
                _op("OP3", 5, ["M1"]),
            )
        )

    results = [solve(build_problem(), DETERMINISTIC_CONFIG) for _ in range(3)]
    first = results[0]
    for other in results[1:]:
        assert other.status == first.status
        assert other.makespan == first.makespan
        assert other.objective_value == first.objective_value
        assert other.assignments == first.assignments


# ---------------------------------------------------------------------------
# 13. result contains no raw OR-Tools types
# ---------------------------------------------------------------------------

def test_result_contains_no_raw_ortools_types():
    problem = SolverProblem(operations=(_op("OP1", 10, ["M1"]),))
    solution = solve(problem, DETERMINISTIC_CONFIG)

    def _assert_not_ortools(value):
        module = type(value).__module__
        label = f"{module}.{type(value).__name__}"
        assert not module.startswith("ortools"), f"leaked raw OR-Tools type: {label}"

    _assert_not_ortools(solution.status)
    _assert_not_ortools(solution.makespan)
    _assert_not_ortools(solution.objective_value)
    for a in solution.assignments:
        _assert_not_ortools(a.start)
        _assert_not_ortools(a.end)
        _assert_not_ortools(a.machine_id)
        _assert_not_ortools(a.operation_id)
    assert isinstance(solution.objective_value, Decimal)


# ---------------------------------------------------------------------------
# 14. domain models remain OR-Tools-free
# ---------------------------------------------------------------------------

def _has_ortools_import_statement(source: str) -> bool:
    return any(
        line.strip().startswith("import ortools") or line.strip().startswith("from ortools")
        for line in source.splitlines()
    )


def test_solver_models_module_does_not_import_ortools():
    # Checks for an actual import *statement*, not just the word "ortools"
    # appearing in this module's own docstrings describing the boundary rule.
    source = inspect.getsource(solver_models)
    assert not _has_ortools_import_statement(source)


def test_planning_models_module_does_not_import_ortools():
    from backend.planning import models as planning_models

    source = inspect.getsource(planning_models)
    assert not _has_ortools_import_statement(source)


def test_only_optimizer_adapter_imports_ortools():
    source = inspect.getsource(optimizer_adapter)
    assert "from ortools" in source or "import ortools" in source


# ---------------------------------------------------------------------------
# 15. invalid solver config rejected
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kwargs",
    [
        {"time_limit_seconds": 0},
        {"time_limit_seconds": -1},
        {"num_workers": 0},
        {"num_workers": -1},
        {"num_workers": 1.5},
        {"random_seed": "not-an-int"},
        {"log_search_progress": "not-a-bool"},
    ],
)
def test_invalid_solver_config_rejected(kwargs):
    with pytest.raises(InvalidSolverProblemError):
        SolverConfig(**kwargs)


def test_default_solver_config_is_deterministic():
    config = SolverConfig()
    assert config.num_workers == 1


# ---------------------------------------------------------------------------
# 16. sub-second / lossy duration policy
# ---------------------------------------------------------------------------

def test_lossy_subsecond_duration_rejected():
    with pytest.raises(InvalidSolverProblemError):
        timedelta_to_solver_seconds(timedelta(milliseconds=500))


def test_whole_second_duration_accepted():
    assert timedelta_to_solver_seconds(timedelta(seconds=7)) == 7


def test_non_positive_duration_rejected():
    with pytest.raises(InvalidSolverProblemError):
        timedelta_to_solver_seconds(timedelta(seconds=0))
    with pytest.raises(InvalidSolverProblemError):
        timedelta_to_solver_seconds(timedelta(seconds=-1))


def test_seconds_to_timedelta_roundtrip():
    assert solver_seconds_to_timedelta(42) == timedelta(seconds=42)


def test_seconds_to_timedelta_rejects_negative_and_non_int():
    with pytest.raises(InvalidSolverProblemError):
        solver_seconds_to_timedelta(-1)
    with pytest.raises(InvalidSolverProblemError):
        solver_seconds_to_timedelta(1.5)
    with pytest.raises(InvalidSolverProblemError):
        solver_seconds_to_timedelta(True)


# ---------------------------------------------------------------------------
# 17. status-mapping helper tested explicitly
# ---------------------------------------------------------------------------

def test_status_mapping_explicit():
    from ortools.sat.python import cp_model

    assert map_cp_sat_status(cp_model.OPTIMAL) == OptimizationStatus.OPTIMAL
    assert map_cp_sat_status(cp_model.FEASIBLE) == OptimizationStatus.FEASIBLE
    assert map_cp_sat_status(cp_model.INFEASIBLE) == OptimizationStatus.INFEASIBLE
    assert map_cp_sat_status(cp_model.MODEL_INVALID) == OptimizationStatus.ERROR
    assert map_cp_sat_status(cp_model.UNKNOWN) == OptimizationStatus.TIME_LIMIT
    # Explicitly the behavior the ticket calls out as a defect to avoid:
    assert map_cp_sat_status(cp_model.UNKNOWN) != OptimizationStatus.FEASIBLE
    assert map_cp_sat_status(cp_model.UNKNOWN) != OptimizationStatus.OPTIMAL


def test_status_mapping_rejects_unknown_value():
    from backend.planning.exceptions import SolverExecutionError

    with pytest.raises(SolverExecutionError):
        map_cp_sat_status(9999)


# ---------------------------------------------------------------------------
# Extra: infeasible problem (a machine that cannot fit both ops at all given
# a tight precedence + single-machine constraint is not itself infeasible in
# this tiny model since durations always fit within the horizon, so instead
# this exercises the "no assignment forced onto an ineligible machine" path)
# ---------------------------------------------------------------------------

def test_three_operations_mixed_eligibility():
    problem = SolverProblem(
        operations=(
            _op("OP1", 10, ["M1"]),
            _op("OP2", 10, ["M2"]),
            _op("OP3", 5, ["M1", "M2"], preds=["OP1", "OP2"]),
        )
    )
    solution = solve(problem, DETERMINISTIC_CONFIG)
    assert solution.status == OptimizationStatus.OPTIMAL
    by_id = {a.operation_id: a for a in solution.assignments}
    assert by_id["OP1"].machine_id == "M1"
    assert by_id["OP2"].machine_id == "M2"
    assert by_id["OP3"].end - by_id["OP3"].start == timedelta(seconds=5)
    assert by_id["OP3"].start >= by_id["OP1"].end
    assert by_id["OP3"].start >= by_id["OP2"].end
    assert solution.makespan == timedelta(seconds=15)
