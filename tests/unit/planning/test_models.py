"""Stage 4 (PLANNING-01C): planning domain model tests.

Covers each entity's immutability/validation invariants plus a compatibility
test proving the planning layer references existing MachiningPro engineering
entities (``backend.domain.operation.Operation``,
``backend.process_planning.ProcessPlan``) by ID rather than duplicating them.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.domain.base import Provenance
from backend.domain.enums import OperationType, ProvenanceType
from backend.domain.exceptions import ValidationError
from backend.domain.operation import Operation
from backend.planning.exceptions import UnknownSetupTransitionError
from backend.planning.models import (
    AvailabilityWindow,
    FixtureRequirement,
    Job,
    JobPriority,
    MaintenanceWindow,
    MaterialRequirement,
    MissingTransitionPolicy,
    OptimizationResult,
    OptimizationStatus,
    ResourceCalendar,
    Routing,
    Scenario,
    Schedule,
    ScheduleOperation,
    ScheduleOperationStatus,
    SchedulingOperation,
    SetupMatrix,
    ToolRequirement,
    WorkOrder,
)
from backend.process_planning.models import PlanStatus, ProcessPlan, ProcessPlanStep

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dt(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


def _prov() -> Provenance:
    return Provenance(
        source_type=ProvenanceType.USER_INPUT,
        source_reference="Fixture — test only",
    )


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------


class TestJob:
    def test_valid(self) -> None:
        job = Job(
            job_id="JOB-001",
            part_id="PART-001",
            quantity=10,
            priority=JobPriority.HIGH,
            release_date=_dt(2026, 1, 1),
            due_date=_dt(2026, 1, 15),
        )
        assert job.job_id == "JOB-001"
        assert job.priority is JobPriority.HIGH

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Job(job_id="   ", part_id="PART-001", quantity=1)

    def test_zero_quantity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Job(job_id="JOB-001", part_id="PART-001", quantity=0)

    def test_negative_quantity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Job(job_id="JOB-001", part_id="PART-001", quantity=-5)

    def test_invalid_date_ordering_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Job(
                job_id="JOB-001",
                part_id="PART-001",
                quantity=1,
                release_date=_dt(2026, 1, 15),
                due_date=_dt(2026, 1, 1),
            )

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Job(
                job_id="JOB-001",
                part_id="PART-001",
                quantity=1,
                due_date=datetime(2026, 1, 1),  # naive
            )

    def test_immutable(self) -> None:
        job = Job(job_id="JOB-001", part_id="PART-001", quantity=1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            job.quantity = 5  # type: ignore[misc]

    def test_invalid_priority_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Job(job_id="JOB-001", part_id="PART-001", quantity=1, priority="high")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# WorkOrder
# ---------------------------------------------------------------------------


class TestWorkOrder:
    def test_valid(self) -> None:
        wo = WorkOrder(
            work_order_id="WO-001",
            job_id="JOB-001",
            process_plan_id="PP-001",
            quantity=5,
        )
        assert wo.process_plan_id == "PP-001"

    def test_empty_process_plan_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkOrder(work_order_id="WO-001", job_id="JOB-001", process_plan_id="", quantity=1)

    def test_zero_quantity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkOrder(
                work_order_id="WO-001", job_id="JOB-001", process_plan_id="PP-001", quantity=0
            )


# ---------------------------------------------------------------------------
# AvailabilityWindow
# ---------------------------------------------------------------------------


class TestAvailabilityWindow:
    def test_valid(self) -> None:
        window = AvailabilityWindow(start=_dt(2026, 1, 1), end=_dt(2026, 1, 2))
        assert window.end > window.start

    def test_zero_duration_rejected(self) -> None:
        instant = _dt(2026, 1, 1)
        with pytest.raises(ValidationError):
            AvailabilityWindow(start=instant, end=instant)

    def test_reversed_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AvailabilityWindow(start=_dt(2026, 1, 2), end=_dt(2026, 1, 1))

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AvailabilityWindow(start=datetime(2026, 1, 1), end=_dt(2026, 1, 2))

    def test_overlaps(self) -> None:
        a = AvailabilityWindow(start=_dt(2026, 1, 1), end=_dt(2026, 1, 3))
        b = AvailabilityWindow(start=_dt(2026, 1, 2), end=_dt(2026, 1, 4))
        c = AvailabilityWindow(start=_dt(2026, 1, 3), end=_dt(2026, 1, 4))
        assert a.overlaps(b) is True
        assert a.overlaps(c) is False  # touching endpoints do not overlap


# ---------------------------------------------------------------------------
# MaintenanceWindow
# ---------------------------------------------------------------------------


class TestMaintenanceWindow:
    def test_valid(self) -> None:
        mw = MaintenanceWindow(
            machine_id="MILL-001",
            start=_dt(2026, 1, 1),
            end=_dt(2026, 1, 2),
            reason="Planned PM",
        )
        assert mw.reason == "Planned PM"

    def test_reversed_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaintenanceWindow(machine_id="MILL-001", start=_dt(2026, 1, 2), end=_dt(2026, 1, 1))

    def test_empty_machine_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaintenanceWindow(machine_id="", start=_dt(2026, 1, 1), end=_dt(2026, 1, 2))


# ---------------------------------------------------------------------------
# ResourceCalendar
# ---------------------------------------------------------------------------


class TestResourceCalendar:
    def test_immutable(self) -> None:
        cal = ResourceCalendar(calendar_id="CAL-001", timezone="Europe/Istanbul")
        with pytest.raises(dataclasses.FrozenInstanceError):
            cal.calendar_id = "OTHER"  # type: ignore[misc]

    def test_unknown_timezone_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ResourceCalendar(calendar_id="CAL-001", timezone="Not/AZone")

    def test_deterministic_ordering(self) -> None:
        w1 = AvailabilityWindow(start=_dt(2026, 1, 3), end=_dt(2026, 1, 4))
        w2 = AvailabilityWindow(start=_dt(2026, 1, 1), end=_dt(2026, 1, 2))
        cal = ResourceCalendar(
            calendar_id="CAL-001",
            timezone="UTC",
            availability_windows=(w1, w2),
        )
        assert cal.availability_windows == (w2, w1)

    def test_overlapping_availability_windows_rejected(self) -> None:
        w1 = AvailabilityWindow(start=_dt(2026, 1, 1), end=_dt(2026, 1, 3))
        w2 = AvailabilityWindow(start=_dt(2026, 1, 2), end=_dt(2026, 1, 4))
        with pytest.raises(ValidationError):
            ResourceCalendar(
                calendar_id="CAL-001",
                timezone="UTC",
                availability_windows=(w1, w2),
            )

    def test_duplicate_availability_windows_rejected(self) -> None:
        w1 = AvailabilityWindow(start=_dt(2026, 1, 1), end=_dt(2026, 1, 2))
        w2 = AvailabilityWindow(start=_dt(2026, 1, 1), end=_dt(2026, 1, 2))
        with pytest.raises(ValidationError):
            ResourceCalendar(
                calendar_id="CAL-001",
                timezone="UTC",
                availability_windows=(w1, w2),
            )

    def test_maintenance_may_overlap_availability(self) -> None:
        avail = AvailabilityWindow(start=_dt(2026, 1, 1), end=_dt(2026, 1, 10))
        maint = MaintenanceWindow(
            machine_id="MILL-001", start=_dt(2026, 1, 3), end=_dt(2026, 1, 4)
        )
        cal = ResourceCalendar(
            calendar_id="CAL-001",
            timezone="UTC",
            availability_windows=(avail,),
            maintenance_windows=(maint,),
        )
        assert cal.maintenance_windows == (maint,)

    def test_duplicate_maintenance_windows_rejected(self) -> None:
        m1 = MaintenanceWindow(machine_id="MILL-001", start=_dt(2026, 1, 1), end=_dt(2026, 1, 2))
        m2 = MaintenanceWindow(machine_id="MILL-001", start=_dt(2026, 1, 1), end=_dt(2026, 1, 2))
        with pytest.raises(ValidationError):
            ResourceCalendar(
                calendar_id="CAL-001",
                timezone="UTC",
                maintenance_windows=(m1, m2),
            )


# ---------------------------------------------------------------------------
# SetupMatrix
# ---------------------------------------------------------------------------


class TestSetupMatrix:
    def test_deterministic_lookup(self) -> None:
        matrix = SetupMatrix(
            matrix_id="SM-001",
            machine_id="MILL-001",
            entries={("turning", "milling"): timedelta(minutes=15)},
        )
        assert matrix.lookup("turning", "milling") == timedelta(minutes=15)
        assert matrix.lookup("turning", "milling") == matrix.lookup("turning", "milling")

    def test_unknown_transition_not_allowed_raises(self) -> None:
        matrix = SetupMatrix(matrix_id="SM-001", machine_id="MILL-001")
        with pytest.raises(UnknownSetupTransitionError):
            matrix.lookup("turning", "milling")

    def test_unknown_transition_default_fallback(self) -> None:
        matrix = SetupMatrix(
            matrix_id="SM-001",
            machine_id="MILL-001",
            policy=MissingTransitionPolicy.DEFAULT_FALLBACK,
            default_duration=timedelta(minutes=5),
        )
        assert matrix.lookup("turning", "milling") == timedelta(minutes=5)

    def test_default_fallback_requires_default_duration(self) -> None:
        with pytest.raises(ValidationError):
            SetupMatrix(
                matrix_id="SM-001",
                machine_id="MILL-001",
                policy=MissingTransitionPolicy.DEFAULT_FALLBACK,
            )

    def test_not_allowed_rejects_unused_default_duration(self) -> None:
        with pytest.raises(ValidationError):
            SetupMatrix(
                matrix_id="SM-001",
                machine_id="MILL-001",
                default_duration=timedelta(minutes=5),
            )

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SetupMatrix(
                matrix_id="SM-001",
                machine_id="MILL-001",
                entries={("a", "b"): timedelta(minutes=-1)},
            )

    def test_same_key_transition_is_not_silently_inferred(self) -> None:
        """No entry for (x, x) must still raise — nothing is inferred."""
        matrix = SetupMatrix(matrix_id="SM-001", machine_id="MILL-001")
        with pytest.raises(UnknownSetupTransitionError):
            matrix.lookup("turning", "turning")


# ---------------------------------------------------------------------------
# ToolRequirement / FixtureRequirement / MaterialRequirement
# ---------------------------------------------------------------------------


class TestToolRequirement:
    def test_valid(self) -> None:
        req = ToolRequirement(operation_id="OP-001", tool_id="TOOL-001", quantity=2)
        assert req.quantity == 2

    def test_window_reversed_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolRequirement(
                operation_id="OP-001",
                tool_id="TOOL-001",
                required_from=_dt(2026, 1, 2),
                required_until=_dt(2026, 1, 1),
            )


class TestFixtureRequirement:
    def test_valid(self) -> None:
        req = FixtureRequirement(operation_id="OP-001", fixture_id="FIX-001")
        assert req.fixture_id == "FIX-001"


class TestMaterialRequirement:
    def test_valid(self) -> None:
        req = MaterialRequirement(
            work_order_id="WO-001",
            material_id="MAT-001",
            quantity=Decimal("12.5"),
            quantity_unit="kg",
        )
        assert req.quantity == Decimal("12.5")

    def test_non_positive_quantity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaterialRequirement(
                work_order_id="WO-001",
                material_id="MAT-001",
                quantity=Decimal("0"),
                quantity_unit="kg",
            )

    def test_empty_unit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaterialRequirement(
                work_order_id="WO-001",
                material_id="MAT-001",
                quantity=Decimal("1"),
                quantity_unit="",
            )


# ---------------------------------------------------------------------------
# SchedulingOperation
# ---------------------------------------------------------------------------


class TestSchedulingOperation:
    def test_immutable(self) -> None:
        op = SchedulingOperation(
            operation_id="OP-001",
            work_order_id="WO-001",
            duration_estimate=timedelta(hours=2),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            op.duration_estimate = timedelta(hours=1)  # type: ignore[misc]

    def test_predecessor_ids_preserved(self) -> None:
        op = SchedulingOperation(
            operation_id="OP-002",
            work_order_id="WO-001",
            duration_estimate=timedelta(hours=1),
            predecessor_operation_ids=("OP-001",),
        )
        assert op.predecessor_operation_ids == ("OP-001",)

    def test_self_predecessor_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SchedulingOperation(
                operation_id="OP-001",
                work_order_id="WO-001",
                duration_estimate=timedelta(hours=1),
                predecessor_operation_ids=("OP-001",),
            )

    def test_eligible_machine_ids_deterministic(self) -> None:
        op = SchedulingOperation(
            operation_id="OP-001",
            work_order_id="WO-001",
            duration_estimate=timedelta(hours=1),
            eligible_machine_ids=("MILL-002", "MILL-001", "MILL-002"),
        )
        # sorted and deduplicated regardless of input order
        assert op.eligible_machine_ids == ("MILL-001", "MILL-002")

    def test_invalid_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SchedulingOperation(
                operation_id="OP-001",
                work_order_id="WO-001",
                duration_estimate=timedelta(0),
            )

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SchedulingOperation(
                operation_id="OP-001",
                work_order_id="WO-001",
                duration_estimate=timedelta(hours=-1),
            )

    def test_naive_earliest_start_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SchedulingOperation(
                operation_id="OP-001",
                work_order_id="WO-001",
                duration_estimate=timedelta(hours=1),
                earliest_start=datetime(2026, 1, 1),
            )


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class TestRouting:
    def test_valid(self) -> None:
        routing = Routing(
            routing_id="R-001",
            process_plan_id="PP-001",
            ordered_operation_ids=("OP-001", "OP-002"),
            precedence={"OP-002": ("OP-001",)},
        )
        assert routing.ordered_operation_ids == ("OP-001", "OP-002")
        assert routing.precedence["OP-002"] == ("OP-001",)

    def test_duplicate_operation_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Routing(
                routing_id="R-001",
                process_plan_id="PP-001",
                ordered_operation_ids=("OP-001", "OP-001"),
            )

    def test_unknown_predecessor_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Routing(
                routing_id="R-001",
                process_plan_id="PP-001",
                ordered_operation_ids=("OP-001",),
                precedence={"OP-001": ("OP-GHOST",)},
            )

    def test_self_precedence_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Routing(
                routing_id="R-001",
                process_plan_id="PP-001",
                ordered_operation_ids=("OP-001",),
                precedence={"OP-001": ("OP-001",)},
            )


# ---------------------------------------------------------------------------
# ScheduleOperation
# ---------------------------------------------------------------------------


class TestScheduleOperation:
    def test_valid_timestamps(self) -> None:
        so = ScheduleOperation(
            operation_id="OP-001",
            machine_id="MILL-001",
            start_time=_dt(2026, 1, 1, 8),
            end_time=_dt(2026, 1, 1, 10),
        )
        assert so.status is ScheduleOperationStatus.SCHEDULED

    def test_zero_duration_rejected(self) -> None:
        instant = _dt(2026, 1, 1, 8)
        with pytest.raises(ValidationError):
            ScheduleOperation(
                operation_id="OP-001",
                machine_id="MILL-001",
                start_time=instant,
                end_time=instant,
            )

    def test_reversed_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ScheduleOperation(
                operation_id="OP-001",
                machine_id="MILL-001",
                start_time=_dt(2026, 1, 1, 10),
                end_time=_dt(2026, 1, 1, 8),
            )

    def test_setup_must_finish_before_start(self) -> None:
        with pytest.raises(ValidationError):
            ScheduleOperation(
                operation_id="OP-001",
                machine_id="MILL-001",
                start_time=_dt(2026, 1, 1, 8),
                end_time=_dt(2026, 1, 1, 10),
                setup_start=_dt(2026, 1, 1, 7),
                setup_end=_dt(2026, 1, 1, 9),  # after start_time
            )

    def test_setup_partial_pair_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ScheduleOperation(
                operation_id="OP-001",
                machine_id="MILL-001",
                start_time=_dt(2026, 1, 1, 8),
                end_time=_dt(2026, 1, 1, 10),
                setup_start=_dt(2026, 1, 1, 7),
            )


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


class TestSchedule:
    def _op(
        self,
        op_id: str,
        start: datetime,
        end: datetime,
        machine: str = "MILL-001",
    ) -> ScheduleOperation:
        return ScheduleOperation(
            operation_id=op_id, machine_id=machine, start_time=start, end_time=end
        )

    def test_deterministic_ordering(self) -> None:
        op_late = self._op("OP-002", _dt(2026, 1, 2), _dt(2026, 1, 3))
        op_early = self._op("OP-001", _dt(2026, 1, 1), _dt(2026, 1, 2))
        schedule = Schedule(
            schedule_id="SCH-001",
            horizon_start=_dt(2026, 1, 1),
            horizon_end=_dt(2026, 1, 5),
            operations=(op_late, op_early),
            created_at=_dt(2026, 1, 1),
        )
        assert schedule.operations == (op_early, op_late)

    def test_duplicate_operation_ids_rejected(self) -> None:
        op1 = self._op("OP-001", _dt(2026, 1, 1), _dt(2026, 1, 2))
        op2 = self._op("OP-001", _dt(2026, 1, 2), _dt(2026, 1, 3))
        with pytest.raises(ValidationError):
            Schedule(
                schedule_id="SCH-001",
                horizon_start=_dt(2026, 1, 1),
                horizon_end=_dt(2026, 1, 5),
                operations=(op1, op2),
                created_at=_dt(2026, 1, 1),
            )

    def test_horizon_violation_rejected(self) -> None:
        op = self._op("OP-001", _dt(2026, 1, 1), _dt(2026, 1, 10))  # exceeds horizon_end
        with pytest.raises(ValidationError):
            Schedule(
                schedule_id="SCH-001",
                horizon_start=_dt(2026, 1, 1),
                horizon_end=_dt(2026, 1, 5),
                operations=(op,),
                created_at=_dt(2026, 1, 1),
            )

    def test_reversed_horizon_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Schedule(
                schedule_id="SCH-001",
                horizon_start=_dt(2026, 1, 5),
                horizon_end=_dt(2026, 1, 1),
                operations=(),
                created_at=_dt(2026, 1, 1),
            )

    def test_immutable(self) -> None:
        schedule = Schedule(
            schedule_id="SCH-001",
            horizon_start=_dt(2026, 1, 1),
            horizon_end=_dt(2026, 1, 5),
            operations=(),
            created_at=_dt(2026, 1, 1),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            schedule.schedule_id = "OTHER"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------


class TestScenario:
    def test_valid(self) -> None:
        scenario = Scenario(
            scenario_id="SC-001",
            name="Baseline",
            job_ids=("JOB-001",),
            locked_operation_ids=("OP-001", "OP-002"),
            frozen_horizon_end=_dt(2026, 1, 10),
            objective_configuration={"minimize": "makespan", "weight": 1.0},
        )
        assert scenario.locked_operation_ids == ("OP-001", "OP-002")

    def test_duplicate_locked_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Scenario(
                scenario_id="SC-001",
                name="Baseline",
                locked_operation_ids=("OP-001", "OP-001"),
            )

    def test_frozen_horizon_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Scenario(
                scenario_id="SC-001",
                name="Baseline",
                frozen_horizon_end=datetime(2026, 1, 10),
            )

    def test_objective_configuration_rejects_non_primitive(self) -> None:
        class _NotPrimitive:
            pass

        with pytest.raises(ValidationError):
            Scenario(
                scenario_id="SC-001",
                name="Baseline",
                objective_configuration={"solver_model": _NotPrimitive()},
            )


# ---------------------------------------------------------------------------
# OptimizationResult
# ---------------------------------------------------------------------------


class TestOptimizationResult:
    def _schedule(self) -> Schedule:
        op = ScheduleOperation(
            operation_id="OP-001",
            machine_id="MILL-001",
            start_time=_dt(2026, 1, 1),
            end_time=_dt(2026, 1, 2),
        )
        return Schedule(
            schedule_id="SCH-001",
            horizon_start=_dt(2026, 1, 1),
            horizon_end=_dt(2026, 1, 5),
            operations=(op,),
            created_at=_dt(2026, 1, 1),
        )

    def test_status_taxonomy(self) -> None:
        assert {s.value for s in OptimizationStatus} == {
            "optimal",
            "feasible",
            "infeasible",
            "time_limit",
            "error",
        }

    def test_optimal_requires_schedule(self) -> None:
        with pytest.raises(ValidationError):
            OptimizationResult(
                result_id="RES-001",
                scenario_id="SC-001",
                status=OptimizationStatus.OPTIMAL,
                schedule=None,
            )

    def test_infeasible_cannot_carry_a_schedule(self) -> None:
        with pytest.raises(ValidationError):
            OptimizationResult(
                result_id="RES-001",
                scenario_id="SC-001",
                status=OptimizationStatus.INFEASIBLE,
                schedule=self._schedule(),
            )

    def test_error_cannot_carry_a_schedule(self) -> None:
        with pytest.raises(ValidationError):
            OptimizationResult(
                result_id="RES-001",
                scenario_id="SC-001",
                status=OptimizationStatus.ERROR,
                schedule=self._schedule(),
            )

    def test_time_limit_may_omit_schedule(self) -> None:
        result = OptimizationResult(
            result_id="RES-001",
            scenario_id="SC-001",
            status=OptimizationStatus.TIME_LIMIT,
        )
        assert result.schedule is None

    def test_time_limit_may_carry_a_schedule(self) -> None:
        result = OptimizationResult(
            result_id="RES-001",
            scenario_id="SC-001",
            status=OptimizationStatus.TIME_LIMIT,
            schedule=self._schedule(),
        )
        assert result.schedule is not None

    def test_feasible_with_schedule_is_valid(self) -> None:
        result = OptimizationResult(
            result_id="RES-001",
            scenario_id="SC-001",
            status=OptimizationStatus.FEASIBLE,
            schedule=self._schedule(),
            objective_values={"makespan_hours": 24},
        )
        assert result.objective_values["makespan_hours"] == Decimal("24")

    def test_negative_solve_time_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OptimizationResult(
                result_id="RES-001",
                scenario_id="SC-001",
                status=OptimizationStatus.ERROR,
                solve_time=timedelta(seconds=-1),
            )


# ---------------------------------------------------------------------------
# Compatibility: reuse existing MachiningPro entities by reference
# ---------------------------------------------------------------------------


class TestExistingDomainCompatibility:
    def test_scheduling_operation_references_existing_operation_by_id(self) -> None:
        """SchedulingOperation must reference an existing Operation by ID,
        never redefine or copy its fields."""
        existing_operation = Operation(
            operation_id="OP-EXISTING-001",
            part_id="PART-001",
            operation_type=OperationType.MILLING,
            sequence_index=1,
            provenance=_prov(),
        )

        scheduling_op = SchedulingOperation(
            operation_id=existing_operation.operation_id,
            work_order_id="WO-001",
            duration_estimate=timedelta(minutes=45),
            eligible_machine_ids=("MILL-001",),
        )

        assert scheduling_op.operation_id == existing_operation.operation_id
        # SchedulingOperation carries none of Operation's own fields —
        # it is a reference, not a competing redefinition.
        assert not hasattr(scheduling_op, "operation_type")
        assert not hasattr(scheduling_op, "feature_ids")

    def test_routing_derives_from_existing_process_plan(self) -> None:
        """Routing must be derivable from an existing ProcessPlan's own
        ordering/precedence without re-implementing plan validation."""
        step_a = ProcessPlanStep(step_id="STEP-A", sequence_index=0)
        step_b = ProcessPlanStep(
            step_id="STEP-B", sequence_index=1, predecessor_step_ids=("STEP-A",)
        )
        plan = ProcessPlan(
            plan_id="PP-001",
            part_id="PART-001",
            steps=(step_b, step_a),
            engineering_status=PlanStatus.INCOMPLETE,
            provenance=_prov(),
        )

        routing = Routing.from_process_plan(plan, routing_id="ROUTING-001")

        assert routing.process_plan_id == plan.plan_id
        assert routing.ordered_operation_ids == ("STEP-A", "STEP-B")
        assert routing.precedence["STEP-B"] == ("STEP-A",)
