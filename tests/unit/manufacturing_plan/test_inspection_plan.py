"""Tests for inspection plan building."""
import pytest
from backend.manufacturing_plan.characteristic import (
    ManufacturingCharacteristic, CharacteristicType, CharacteristicCriticality,
)
from backend.manufacturing_plan.inspection_plan import (
    InspectionStage,
    InspectionFrequency,
    FirstArticleInspection,
    FAIStatus,
    build_final_inspection_plan,
    _assign_stage,
    _assign_frequency,
    _pick_method,
    FinalInspectionPlan,
    InspectionPlanRow,
)
from backend.manufacturing_plan.inspection_library import InspectionMethod


def _make_char(
    char_type=CharacteristicType.DIMENSION,
    criticality=CharacteristicCriticality.STANDARD,
    nominal=25.0,
    upper=25.05,
    lower=24.95,
    gdt=None,
    cid="c1",
):
    return ManufacturingCharacteristic(
        characteristic_id=cid,
        source_requirement_id=None,
        feature_id="f1",
        char_type=char_type,
        label="test_char",
        nominal_value=nominal,
        upper_limit=upper,
        lower_limit=lower,
        criticality=criticality,
        gdt_characteristic=gdt,
    )


class TestAssignStage:
    def test_key_characteristic_post_operation(self):
        c = _make_char(criticality=CharacteristicCriticality.KEY_CHARACTERISTIC)
        assert _assign_stage(c) == InspectionStage.POST_OPERATION

    def test_critical_post_operation(self):
        c = _make_char(criticality=CharacteristicCriticality.CRITICAL)
        assert _assign_stage(c) == InspectionStage.POST_OPERATION

    def test_thread_post_operation(self):
        c = _make_char(char_type=CharacteristicType.THREAD, criticality=CharacteristicCriticality.STANDARD)
        assert _assign_stage(c) == InspectionStage.POST_OPERATION

    def test_surface_finish_post_operation(self):
        c = _make_char(char_type=CharacteristicType.SURFACE_FINISH, criticality=CharacteristicCriticality.STANDARD)
        assert _assign_stage(c) == InspectionStage.POST_OPERATION

    def test_standard_dimension_final(self):
        c = _make_char(criticality=CharacteristicCriticality.STANDARD)
        assert _assign_stage(c) == InspectionStage.FINAL


class TestAssignFrequency:
    def test_key_char_100_percent(self):
        c = _make_char(criticality=CharacteristicCriticality.KEY_CHARACTERISTIC)
        freq = _assign_frequency(c)
        assert freq.frequency == InspectionFrequency.ONE_HUNDRED_PERCENT

    def test_critical_100_percent(self):
        c = _make_char(criticality=CharacteristicCriticality.CRITICAL)
        freq = _assign_frequency(c)
        assert freq.frequency == InspectionFrequency.ONE_HUNDRED_PERCENT

    def test_important_per_setup(self):
        c = _make_char(criticality=CharacteristicCriticality.IMPORTANT)
        freq = _assign_frequency(c)
        assert freq.frequency == InspectionFrequency.PER_SETUP

    def test_standard_first_off(self):
        c = _make_char(criticality=CharacteristicCriticality.STANDARD)
        freq = _assign_frequency(c)
        assert freq.frequency == InspectionFrequency.FIRST_OFF

    def test_unknown_criticality_unknown_frequency(self):
        c = _make_char(criticality=CharacteristicCriticality.UNKNOWN)
        freq = _assign_frequency(c)
        assert freq.frequency == InspectionFrequency.UNKNOWN

    def test_no_fabricated_sample_size(self):
        c = _make_char(criticality=CharacteristicCriticality.IMPORTANT)
        freq = _assign_frequency(c)
        assert freq.sample_size is None


class TestFirstArticleInspection:
    def test_defaults(self):
        fai = FirstArticleInspection(
            fai_id="fai1", plan_id="p1", drawing_number="DWG-001",
            revision="A", char_ids_to_inspect=["c1", "c2"],
        )
        assert fai.AS9102_COMPLIANCE_CLAIMED is False
        assert fai.PPAP_COMPLIANCE_CLAIMED is False
        assert fai.REFERENCE_ONLY is True
        assert fai.status == FAIStatus.REQUIRED


class TestBuildFinalInspectionPlan:
    def test_empty_chars_returns_plan(self):
        plan = build_final_inspection_plan("mp1", [])
        assert isinstance(plan, FinalInspectionPlan)
        assert plan.coverage_rate == 1.0  # vacuously complete

    def test_chars_generate_rows(self):
        chars = [_make_char(cid="c1"), _make_char(cid="c2")]
        plan = build_final_inspection_plan("mp1", chars)
        assert len(plan.rows) == 2

    def test_coverage_100_when_all_covered(self):
        chars = [_make_char(cid="c1")]
        plan = build_final_inspection_plan("mp1", chars)
        assert plan.coverage_rate == 1.0

    def test_key_char_gets_100pct_frequency(self):
        c = _make_char(criticality=CharacteristicCriticality.KEY_CHARACTERISTIC, cid="key1")
        plan = build_final_inspection_plan("mp1", [c])
        row = plan.rows[0]
        assert row.frequency.frequency == InspectionFrequency.ONE_HUNDRED_PERCENT

    def test_thread_char_gets_thread_gauge(self):
        c = _make_char(char_type=CharacteristicType.THREAD, criticality=CharacteristicCriticality.STANDARD, cid="t1")
        plan = build_final_inspection_plan("mp1", [c])
        row = plan.rows[0]
        assert row.method == InspectionMethod.THREAD_GAUGE

    def test_disclaimer_set(self):
        plan = build_final_inspection_plan("mp1", [])
        assert "REFERENCE_ONLY" in plan.disclaimer or "advisory" in plan.disclaimer.lower()

    def test_rows_are_frozen(self):
        chars = [_make_char(cid="c1")]
        plan = build_final_inspection_plan("mp1", chars)
        row = plan.rows[0]
        with pytest.raises((AttributeError, TypeError)):
            row.char_label = "mutated"  # type: ignore
