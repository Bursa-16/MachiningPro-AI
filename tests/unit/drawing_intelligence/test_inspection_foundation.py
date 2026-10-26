"""Tests for drawing_intelligence.inspection_foundation (EPIC_04 Phase 2)."""

import pytest
from decimal import Decimal

from backend.domain.enums import OperationType
from backend.drawing_intelligence.inspection_foundation import (
    InspectionMethod,
    InspectionTrigger,
    InspectionPlanner,
    build_inspection_plan,
)
from backend.drawing_intelligence.requirements import (
    DatumReference,
    DatumReferenceFrame,
    DimensionalRequirement,
    DrawingRequirementSet,
    ExpandedFeatureControlFrame,
    GdtCharacteristic,
    GeometricRequirement,
    RequirementExtractionStatus,
    SurfaceFinishRequirement,
    ThreadRequirement,
)


def _make_req_set(**kwargs):
    defaults = {
        "source_id": "test",
        "drawing_number": None,
        "revision": None,
        "extraction_status": RequirementExtractionStatus.PARTIAL,
        "dimensional": (),
        "geometric": (),
        "surface_finish": (),
        "threads": (),
        "material": None,
        "heat_treatment": (),
    }
    defaults.update(kwargs)
    return DrawingRequirementSet(**defaults)


class TestGdtInspection:
    def test_flatness_gdt_triggers_cmm(self):
        fcf = ExpandedFeatureControlFrame(
            characteristic=GdtCharacteristic.FLATNESS,
            tolerance_value=Decimal("0.05"),
            tolerance_unit="mm",
        )
        geom = GeometricRequirement(req_id="G-0001", fcf=fcf)
        rs = _make_req_set(geometric=(geom,))
        plan = build_inspection_plan(rs)
        assert plan.step_count >= 1
        cmm_steps = [s for s in plan.steps if s.method == InspectionMethod.CMM]
        assert len(cmm_steps) >= 1

    def test_multiple_gdt_multiple_cmm_steps(self):
        geoms = tuple(
            GeometricRequirement(
                req_id=f"G-{i:04d}",
                fcf=ExpandedFeatureControlFrame(
                    characteristic=GdtCharacteristic.FLATNESS,
                    tolerance_value=Decimal("0.05"),
                    tolerance_unit="mm",
                ),
            )
            for i in range(3)
        )
        rs = _make_req_set(geometric=geoms)
        plan = build_inspection_plan(rs)
        assert plan.step_count == 3
        assert plan.has_cmm

    def test_gdt_inspection_operation_is_inspection(self):
        fcf = ExpandedFeatureControlFrame(
            characteristic=GdtCharacteristic.POSITION,
            tolerance_value=Decimal("0.02"),
            tolerance_unit="mm",
        )
        geom = GeometricRequirement(req_id="G-0001", fcf=fcf)
        rs = _make_req_set(geometric=(geom,))
        plan = build_inspection_plan(rs)
        for step in plan.steps:
            assert step.operation == OperationType.INSPECTION


class TestSurfaceFinishInspection:
    def test_fine_ra_triggers_roughness_tester(self):
        sf = SurfaceFinishRequirement(req_id="SF-0001", ra_um=Decimal("0.8"))
        rs = _make_req_set(surface_finish=(sf,))
        plan = build_inspection_plan(rs)
        methods = [s.method for s in plan.steps]
        assert InspectionMethod.SURFACE_ROUGHNESS_TESTER in methods

    def test_coarse_ra_no_inspection(self):
        sf = SurfaceFinishRequirement(req_id="SF-0001", ra_um=Decimal("6.3"))
        rs = _make_req_set(surface_finish=(sf,))
        plan = build_inspection_plan(rs)
        roughness_steps = [s for s in plan.steps
                           if s.method == InspectionMethod.SURFACE_ROUGHNESS_TESTER]
        assert len(roughness_steps) == 0

    def test_boundary_ra_1_6_triggers_inspection(self):
        sf = SurfaceFinishRequirement(req_id="SF-0001", ra_um=Decimal("1.6"))
        rs = _make_req_set(surface_finish=(sf,))
        plan = build_inspection_plan(rs)
        methods = [s.method for s in plan.steps]
        assert InspectionMethod.SURFACE_ROUGHNESS_TESTER in methods


class TestThreadInspection:
    def test_thread_triggers_thread_gauge(self):
        t = ThreadRequirement(req_id="T-0001", designation="M12x1.75")
        rs = _make_req_set(threads=(t,))
        plan = build_inspection_plan(rs)
        methods = [s.method for s in plan.steps]
        assert InspectionMethod.THREAD_GAUGE in methods

    def test_thread_inspection_follows_tapping(self):
        t = ThreadRequirement(req_id="T-0001", designation="M10x1.5")
        rs = _make_req_set(threads=(t,))
        plan = build_inspection_plan(rs)
        thread_steps = [s for s in plan.steps
                        if s.method == InspectionMethod.THREAD_GAUGE]
        assert all(s.insert_after_op == OperationType.TAPPING for s in thread_steps)


class TestTightToleranceInspection:
    def test_very_tight_bore_triggers_bore_gauge(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("25"),
            unit="mm",
            tolerance_upper=Decimal("0.013"),
            tolerance_lower=Decimal("-0.000"),
        )
        rs = _make_req_set(dimensional=(dim,))
        plan = build_inspection_plan(rs)
        methods = [s.method for s in plan.steps]
        assert InspectionMethod.BORE_GAUGE in methods

    def test_loose_bore_no_bore_gauge(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("25"),
            unit="mm",
            tolerance_upper=Decimal("0.1"),
        )
        rs = _make_req_set(dimensional=(dim,))
        plan = build_inspection_plan(rs)
        methods = [s.method for s in plan.steps]
        assert InspectionMethod.BORE_GAUGE not in methods


class TestEmptyRequirements:
    def test_no_requirements_empty_plan(self):
        rs = _make_req_set()
        plan = build_inspection_plan(rs)
        assert plan.step_count == 0
        assert not plan.has_cmm
