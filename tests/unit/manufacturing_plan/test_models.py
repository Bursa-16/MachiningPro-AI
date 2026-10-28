"""Tests for manufacturing plan domain models."""
import pytest
from backend.manufacturing_plan.models import (
    ManufacturingPlan,
    ManufacturingPlanStatus,
    ManufacturingOperation,
    ManufacturingSetup,
    PlanCompleteness,
    CompletenessStatus,
    OpenItem,
    OpenItemSeverity,
    OpenItemCategory,
    OpenItemStatus,
    ReleaseGateStatus,
    PFMEAHook,
    NCHandoffPackage,
    ProcessFlow,
    ProcessFlowNode,
)
import uuid


def _plan(**kwargs):
    defaults = dict(
        plan_id=str(uuid.uuid4()),
        source_id="src1",
        drawing_number="DWG-001",
        revision="A",
        part_id=None,
    )
    defaults.update(kwargs)
    return ManufacturingPlan(**defaults)


class TestManufacturingPlanStatus:
    def test_draft_is_default(self):
        p = _plan()
        assert p.status == ManufacturingPlanStatus.DRAFT

    def test_auto_approved_is_false(self):
        p = _plan()
        assert p.AUTO_GENERATED_PLAN_MARKED_APPROVED is False

    def test_disclaimer_contains_sentinel(self):
        p = _plan()
        assert "AUTO_GENERATED_PLAN_MARKED_APPROVED=NO" in p.disclaimer

    def test_all_status_values(self):
        vals = {e.value for e in ManufacturingPlanStatus}
        assert {"DRAFT", "ENGINEER_REVIEWED", "APPROVED", "REJECTED", "SUPERSEDED"} == vals


class TestPlanCompleteness:
    def test_empty_plan_incomplete(self):
        pc = PlanCompleteness()
        pc.compute()
        assert pc.completeness_status == CompletenessStatus.INCOMPLETE

    def test_all_full_complete(self):
        pc = PlanCompleteness(
            requirements_coverage=1.0,
            feature_coverage=1.0,
            operation_coverage=1.0,
            machine_assignment_coverage=1.0,
            tool_assignment_coverage=1.0,
            parameter_coverage=1.0,
            inspection_coverage=1.0,
        )
        pc.compute()
        assert pc.completeness_status == CompletenessStatus.COMPLETE
        assert pc.overall_completeness == pytest.approx(1.0)

    def test_threshold_substantially(self):
        pc = PlanCompleteness(
            requirements_coverage=1.0,
            feature_coverage=1.0,
            operation_coverage=1.0,
            machine_assignment_coverage=0.5,
            tool_assignment_coverage=0.5,
            parameter_coverage=0.8,
            inspection_coverage=1.0,
        )
        pc.compute()
        # Average > 0.80 required
        score = (1 + 1 + 1 + 0.5 + 0.5 + 0.8 + 1) / 7
        assert pc.overall_completeness == pytest.approx(score, abs=0.01)

    def test_partially_complete_threshold(self):
        pc = PlanCompleteness(
            requirements_coverage=0.5,
            feature_coverage=0.5,
            operation_coverage=0.5,
            machine_assignment_coverage=0.5,
            tool_assignment_coverage=0.5,
            parameter_coverage=0.5,
            inspection_coverage=0.5,
        )
        pc.compute()
        assert pc.completeness_status == CompletenessStatus.PARTIALLY_COMPLETE


class TestOpenItem:
    def test_open_by_default(self):
        item = OpenItem(
            item_id="i1",
            category=OpenItemCategory.MISSING_MACHINE,
            severity=OpenItemSeverity.REVIEW_REQUIRED,
            description="No machine assigned",
        )
        assert item.status == OpenItemStatus.OPEN

    def test_all_categories(self):
        vals = {e.value for e in OpenItemCategory}
        assert "MISSING_MACHINE" in vals
        assert "MISSING_TOOL" in vals
        assert "MISSING_INSPECTION" in vals


class TestPFMEAHook:
    def test_pfmea_not_implemented(self):
        hook = PFMEAHook(
            feature_id="f1",
            op_id="op1",
            failure_mode_hint="Failure hint",
            control="CMM inspection",
            severity_hint="CRITICAL",
        )
        d = hook.to_dict()
        assert d["PFMEA_GENERATOR_NOT_IMPLEMENTED"] is True

    def test_to_dict_keys(self):
        hook = PFMEAHook("f1", "op1", "hint", "control", "CRITICAL")
        d = hook.to_dict()
        assert "feature_id" in d
        assert "failure_mode_hint" in d


class TestNCHandoffPackage:
    def test_nc_file_not_executed(self):
        pkg = NCHandoffPackage(
            op_id="op1", machine_id=None, machine_label=None,
            tool_id=None, holder_id=None, operation_type="DRILLING",
            cutting_speed_m_min=None, feed_rate_mm_min=None, rpm=None,
            ap_mm=None, ae_mm=None, feature_geometry_ref=None,
            setup_id="s1", datum_reference=None, target_tolerance=None,
            surface_finish_target=None, coolant_note=None,
        )
        assert pkg.NC_FILE_EXECUTED is False
        assert pkg.MACHINE_KINEMATICS_SIMULATED is False
        assert pkg.REFERENCE_ONLY is True


class TestReleaseGateStatus:
    def test_all_values(self):
        vals = {e.value for e in ReleaseGateStatus}
        assert {"READY_FOR_ENGINEERING_REVIEW", "REVIEW_REQUIRED", "INCOMPLETE", "BLOCKED"} == vals
