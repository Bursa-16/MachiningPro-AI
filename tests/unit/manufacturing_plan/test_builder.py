"""Tests for manufacturing plan builder."""
import pytest
from backend.manufacturing_plan.builder import (
    build_manufacturing_plan,
    build_nc_handoff_packages,
    _build_setups,
    _build_operations,
    _build_process_flow,
    _compute_completeness,
    _evaluate_release_gate,
)
from backend.manufacturing_plan.models import (
    ManufacturingPlan,
    ManufacturingPlanStatus,
    ReleaseGateStatus,
    CompletenessStatus,
    PlanCompleteness,
    OpenItem,
    OpenItemSeverity,
    OpenItemStatus,
    OpenItemCategory,
)


def _step(step_id="s1", op="DRILLING", setup=1, machine="m1", tool="t1", rpm=1000):
    return {
        "step_id": step_id,
        "operation": op,
        "setup_number": setup,
        "machine_id": machine,
        "machine_label": f"Machine {machine}",
        "cutting_tool_id": tool,
        "holder_id": "h1",
        "cutting_speed_m_min": 100.0,
        "feed_rate_mm_min": 0.2,
        "rpm": rpm,
        "ap_mm": 2.0,
        "ae_mm": 1.0,
        "feature_id": "f1",
        "parameter_source": "EMPIRICAL",
    }


class FakeOptimizedPlan:
    def __init__(self, steps):
        self.steps = steps
        self.traceability_fingerprint = "abc123"


class TestBuildManufacturingPlan:
    def test_returns_manufacturing_plan(self):
        plan = build_manufacturing_plan("src1", None, None)
        assert isinstance(plan, ManufacturingPlan)

    def test_always_draft(self):
        plan = build_manufacturing_plan("src1", FakeOptimizedPlan([_step()]), None)
        assert plan.status == ManufacturingPlanStatus.DRAFT

    def test_auto_approved_false(self):
        plan = build_manufacturing_plan("src1", None, None)
        assert plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False

    def test_drawing_number_set(self):
        plan = build_manufacturing_plan(
            "src1", None, None, drawing_number="DWG-001", revision="A"
        )
        assert plan.drawing_number == "DWG-001"
        assert plan.revision == "A"

    def test_with_steps_creates_operations(self):
        steps = [_step("s1", "DRILLING"), _step("s2", "REAMING")]
        opt = FakeOptimizedPlan(steps)
        plan = build_manufacturing_plan("src1", opt, None)
        assert len(plan.operations) == 2

    def test_with_steps_creates_setups(self):
        steps = [_step("s1", setup=1), _step("s2", setup=2)]
        opt = FakeOptimizedPlan(steps)
        plan = build_manufacturing_plan("src1", opt, None)
        assert len(plan.setups) == 2

    def test_fingerprint_set(self):
        plan = build_manufacturing_plan("src1", FakeOptimizedPlan([_step()]), None)
        assert plan.traceability_fingerprint is not None

    def test_process_flow_generated(self):
        steps = [_step("s1")]
        plan = build_manufacturing_plan("src1", FakeOptimizedPlan(steps), None)
        assert plan.process_flow is not None
        assert len(plan.process_flow.nodes) >= 3

    def test_inspection_plan_generated(self):
        plan = build_manufacturing_plan("src1", None, None)
        assert plan.inspection_plan is not None

    def test_control_plan_generated(self):
        plan = build_manufacturing_plan("src1", None, None)
        assert plan.control_plan is not None

    def test_completeness_computed(self):
        plan = build_manufacturing_plan("src1", None, None)
        assert isinstance(plan.completeness, PlanCompleteness)
        assert 0.0 <= plan.completeness.overall_completeness <= 1.0

    def test_warnings_empty_by_default_with_steps(self):
        steps = [_step("s1")]
        plan = build_manufacturing_plan("src1", FakeOptimizedPlan(steps), None)
        assert isinstance(plan.generation_warnings, list)

    def test_calibration_profile_ids(self):
        plan = build_manufacturing_plan(
            "src1", None, None, calibration_profile_ids=["p1", "p2"]
        )
        assert plan.calibration_profile_ids == ["p1", "p2"]

    def test_source_id_set(self):
        plan = build_manufacturing_plan("source-abc", None, None)
        assert plan.source_id == "source-abc"


class TestBuildNCHandoffPackages:
    def test_empty_plan_empty_packages(self):
        plan = build_manufacturing_plan("s1", None, None)
        packages = build_nc_handoff_packages(plan)
        assert isinstance(packages, list)

    def test_excludes_inspection_ops(self):
        steps = [_step("s1", "DRILLING"), _step("s2", "INSPECTION")]
        plan = build_manufacturing_plan("s1", FakeOptimizedPlan(steps), None)
        packages = build_nc_handoff_packages(plan)
        op_types = [p.operation_type for p in packages]
        assert "INSPECTION" not in op_types

    def test_nc_file_executed_false(self):
        steps = [_step("s1", "DRILLING")]
        plan = build_manufacturing_plan("s1", FakeOptimizedPlan(steps), None)
        packages = build_nc_handoff_packages(plan)
        assert all(p.NC_FILE_EXECUTED is False for p in packages)


class TestEvaluateReleaseGate:
    def test_blocked_with_blocking_item(self):
        pc = PlanCompleteness(requirements_coverage=1, feature_coverage=1,
                              operation_coverage=1, machine_assignment_coverage=1,
                              tool_assignment_coverage=1, parameter_coverage=1,
                              inspection_coverage=1)
        pc.compute()
        item = OpenItem(
            item_id="i1",
            category=OpenItemCategory.MISSING_INSPECTION,
            severity=OpenItemSeverity.BLOCKING,
            description="blocking",
        )
        gate = _evaluate_release_gate(pc, [item])
        assert gate == ReleaseGateStatus.BLOCKED

    def test_ready_when_complete_no_items(self):
        pc = PlanCompleteness(requirements_coverage=1, feature_coverage=1,
                              operation_coverage=1, machine_assignment_coverage=1,
                              tool_assignment_coverage=1, parameter_coverage=1,
                              inspection_coverage=1)
        pc.compute()
        gate = _evaluate_release_gate(pc, [])
        assert gate == ReleaseGateStatus.READY_FOR_ENGINEERING_REVIEW

    def test_incomplete_when_completeness_low(self):
        pc = PlanCompleteness()
        pc.compute()
        gate = _evaluate_release_gate(pc, [])
        assert gate == ReleaseGateStatus.INCOMPLETE
