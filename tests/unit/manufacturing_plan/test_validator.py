"""Tests for manufacturing plan validator — V-001 through V-007."""
import pytest
from backend.manufacturing_plan.characteristic import (
    ManufacturingCharacteristic, CharacteristicType, CharacteristicCriticality,
)
from backend.manufacturing_plan.models import (
    ManufacturingPlan, ManufacturingPlanStatus, ManufacturingOperation,
    PlanCompleteness, CompletenessStatus, OpenItemSeverity, OpenItemStatus,
    ReleaseGateStatus,
)
from backend.manufacturing_plan.inspection_plan import (
    FinalInspectionPlan, InspectionPlanRow, InspectionStage,
    InspectionFrequency, InspectionFrequencySpec,
)
from backend.manufacturing_plan.inspection_library import InspectionMethod
from backend.manufacturing_plan.validator import (
    validate_manufacturing_plan, ValidationCode,
)
from datetime import datetime
import uuid


def _plan_with(**kwargs):
    defaults = dict(
        plan_id=str(uuid.uuid4()),
        source_id="test",
        drawing_number="DWG-001",
        revision="A",
        part_id=None,
        status=ManufacturingPlanStatus.DRAFT,
        characteristics=[],
        setups=[],
        operations=[],
        tool_list=[],
        machine_list=[],
        parameter_table=[],
        inspection_plan=None,
        control_plan=None,
        process_flow=None,
        completeness=PlanCompleteness(),
        open_items=[],
        AUTO_GENERATED_PLAN_MARKED_APPROVED=False,
        traceability_fingerprint="fp-test",
        generation_warnings=[],
        revision_history=[],
        pfmea_hooks=[],
    )
    defaults.update(kwargs)
    return ManufacturingPlan(**defaults)


def _op(op_id=None, op_number=10, operation_type="MILLING", machine_id=None, tool_id=None, setup_id="s1"):
    return ManufacturingOperation(
        op_id=op_id or str(uuid.uuid4()),
        op_number=op_number,
        setup_id=setup_id,
        feature_id=None,
        operation_type=operation_type,
        machine_id=machine_id,
        machine_label=None,
        tool_id=tool_id,
        holder_id=None,
        cutting_speed_m_min=None,
        feed_rate_mm_min=None,
        rpm=None,
        ap_mm=None,
        ae_mm=None,
        coolant_note=None,
        target_tolerance=None,
        surface_finish=None,
        inspection_note=None,
        cycle_time_context=None,
        capability_context=None,
        surface_capability_context=None,
    )


def _critical_char(char_id=None):
    return ManufacturingCharacteristic(
        characteristic_id=char_id or str(uuid.uuid4()),
        source_requirement_id=None,
        feature_id=None,
        char_type=CharacteristicType.GDT,
        label="Position critical",
        criticality=CharacteristicCriticality.CRITICAL,
    )


def _inspection_plan_covering(plan_id, char_ids):
    rows = [
        InspectionPlanRow(
            row_id=str(uuid.uuid4()),
            char_id=c,
            char_label="char",
            char_type=CharacteristicType.GDT,
            criticality=CharacteristicCriticality.CRITICAL,
            feature_ref=None,
            op_id=None,
            inspection_op_id=None,
            stage=InspectionStage.FINAL,
            method=InspectionMethod.CMM,
            gage_suggestion=None,
            frequency=InspectionFrequencySpec(InspectionFrequency.ONE_HUNDRED_PERCENT),
            acceptance_criterion=None,
            status="COVERED",
        )
        for c in char_ids
    ]
    ip = FinalInspectionPlan(plan_id=plan_id, manufacturing_plan_id="mp1", rows=rows)
    ip.uninspected_chars = []
    ip.coverage_rate = 1.0
    return ip


class TestValidateV001DraftGuard:
    def test_auto_approved_false_no_v001(self):
        plan = _plan_with()
        result = validate_manufacturing_plan(plan)
        v001 = [f for f in result.findings if f.code == ValidationCode.V001]
        assert len(v001) == 0

    def test_returns_validation_result(self):
        plan = _plan_with()
        result = validate_manufacturing_plan(plan)
        assert hasattr(result, "passed")
        assert hasattr(result, "findings")


class TestValidateV002HasOperations:
    def test_no_operations_gives_review_required(self):
        plan = _plan_with(operations=[])
        result = validate_manufacturing_plan(plan)
        v002 = [f for f in result.findings if f.code == ValidationCode.V002]
        assert len(v002) >= 1

    def test_with_operations_no_v002(self):
        op = _op(machine_id="M1")
        plan = _plan_with(operations=[op])
        result = validate_manufacturing_plan(plan)
        v002 = [f for f in result.findings if f.code == ValidationCode.V002]
        assert len(v002) == 0


class TestValidateV003CriticalInspection:
    def test_critical_char_without_inspection_gives_blocking(self):
        char = _critical_char()
        plan = _plan_with(characteristics=[char], traceability_fingerprint="fp")
        result = validate_manufacturing_plan(plan)
        v003 = [f for f in result.findings if f.code == ValidationCode.V003]
        assert len(v003) >= 1
        assert all(f.severity == OpenItemSeverity.BLOCKING for f in v003)

    def test_critical_char_with_inspection_no_v003_blocking(self):
        char = _critical_char()
        ip = _inspection_plan_covering("mp", [char.characteristic_id])
        plan = _plan_with(characteristics=[char], inspection_plan=ip, traceability_fingerprint="fp")
        result = validate_manufacturing_plan(plan)
        v003 = [f for f in result.findings if f.code == ValidationCode.V003]
        assert len(v003) == 0

    def test_standard_char_no_v003(self):
        char = ManufacturingCharacteristic(
            characteristic_id="std1", source_requirement_id=None, feature_id=None,
            char_type=CharacteristicType.DIMENSION, label="standard",
            criticality=CharacteristicCriticality.STANDARD,
        )
        plan = _plan_with(characteristics=[char], traceability_fingerprint="fp")
        result = validate_manufacturing_plan(plan)
        v003 = [f for f in result.findings if f.code == ValidationCode.V003]
        assert len(v003) == 0


class TestValidateV006Completeness:
    def test_low_completeness_gives_advisory(self):
        pc = PlanCompleteness(overall_completeness=0.2, completeness_status=CompletenessStatus.INCOMPLETE)
        plan = _plan_with(completeness=pc, traceability_fingerprint="fp")
        result = validate_manufacturing_plan(plan)
        v006 = [f for f in result.findings if f.code == ValidationCode.V006]
        assert len(v006) >= 1

    def test_high_completeness_no_v006(self):
        pc = PlanCompleteness(overall_completeness=0.95, completeness_status=CompletenessStatus.COMPLETE)
        plan = _plan_with(completeness=pc, traceability_fingerprint="fp")
        result = validate_manufacturing_plan(plan)
        v006 = [f for f in result.findings if f.code == ValidationCode.V006]
        assert len(v006) == 0


class TestValidateV007Fingerprint:
    def test_missing_fingerprint_advisory(self):
        plan = _plan_with(traceability_fingerprint=None)
        result = validate_manufacturing_plan(plan)
        v007 = [f for f in result.findings if f.code == ValidationCode.V007]
        assert len(v007) >= 1

    def test_present_fingerprint_no_v007(self):
        plan = _plan_with(traceability_fingerprint="abc123")
        result = validate_manufacturing_plan(plan)
        v007 = [f for f in result.findings if f.code == ValidationCode.V007]
        assert len(v007) == 0


class TestValidateSafetyFlags:
    def test_empty_plan_no_crash(self):
        plan = _plan_with()
        result = validate_manufacturing_plan(plan)
        assert isinstance(result.findings, list)

    def test_insufficient_data_not_treated_as_pass(self):
        """INSUFFICIENT_DATA_TREATED_AS_PASS=NO — missing info is reported."""
        plan = _plan_with(operations=[], characteristics=[_critical_char()])
        result = validate_manufacturing_plan(plan)
        assert not result.passed or len(result.findings) > 0
