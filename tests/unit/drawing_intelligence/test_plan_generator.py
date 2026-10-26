"""Tests for drawing_intelligence.plan_generator (EPIC_04 Phase 2)."""

import pytest
from decimal import Decimal

from backend.domain.enums import FeatureType, OperationType
from backend.drawing_intelligence.feature_recognition import recognize_features
from backend.drawing_intelligence.inspection_foundation import build_inspection_plan
from backend.drawing_intelligence.plan_generator import (
    GeneratedPlanStatus,
    PlanGenerator,
    generate_plan,
)
from backend.drawing_intelligence.requirements import (
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
        "source_id": "test-dwg",
        "drawing_number": "DWG-001",
        "revision": "A",
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


class TestGeneratedPlanStatus:
    def test_status_values_exist(self):
        assert GeneratedPlanStatus.DRAFT == "DRAFT"
        assert GeneratedPlanStatus.PARTIAL == "PARTIAL"
        assert GeneratedPlanStatus.INSUFFICIENT_DATA == "INSUFFICIENT_DATA"

    def test_plan_never_approved(self):
        from backend.drawing_intelligence.plan_generator import GeneratedProcessPlan
        from backend.drawing_intelligence.traceability import TraceabilityChain
        with pytest.raises(ValueError, match="APPROVED"):
            GeneratedProcessPlan(
                plan_id="x",
                source_id="s",
                drawing_number=None,
                revision=None,
                status="APPROVED",  # type: ignore
                steps=(),
                traceability=TraceabilityChain(source_id="s", drawing_number=None, revision=None, entries=()),
                route_results=(),
                best_routes=(),
                generation_warnings=(),
                disclaimer="test",
            )


class TestPlanGeneratorBasic:
    def test_hole_generates_draft_plan(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("10"),
            unit="mm",
        )
        rs = _make_req_set(dimensional=(dim,))
        recognition = recognize_features(rs)
        inspection = build_inspection_plan(rs)
        plan = generate_plan(rs, recognition, inspection)

        assert plan.status in (
            GeneratedPlanStatus.DRAFT,
            GeneratedPlanStatus.PARTIAL,
        )
        assert plan.step_count > 0
        # Disclaimer must not be empty
        assert plan.disclaimer

    def test_thread_plan_has_drill_and_tap(self):
        t = ThreadRequirement(req_id="T-0001", designation="M12x1.75")
        rs = _make_req_set(threads=(t,))
        recognition = recognize_features(rs)
        inspection = build_inspection_plan(rs)
        plan = generate_plan(rs, recognition, inspection)

        ops_in_plan = [s.operation for s in plan.steps]
        assert OperationType.DRILLING in ops_in_plan
        assert OperationType.TAPPING in ops_in_plan

    def test_gdt_requirement_adds_inspection_step(self):
        fcf = ExpandedFeatureControlFrame(
            characteristic=GdtCharacteristic.FLATNESS,
            tolerance_value=Decimal("0.05"),
            tolerance_unit="mm",
        )
        geom = GeometricRequirement(req_id="G-0001", fcf=fcf)
        rs = _make_req_set(geometric=(geom,))
        recognition = recognize_features(rs)
        inspection = build_inspection_plan(rs)
        plan = generate_plan(rs, recognition, inspection)

        inspection_steps = [s for s in plan.steps if s.is_inspection]
        assert len(inspection_steps) >= 1

    def test_sequence_numbers_monotonic(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("10"),
            unit="mm",
        )
        t = ThreadRequirement(req_id="T-0001", designation="M8x1.25")
        rs = _make_req_set(dimensional=(dim,), threads=(t,))
        recognition = recognize_features(rs)
        inspection = build_inspection_plan(rs)
        plan = generate_plan(rs, recognition, inspection)

        seq_nums = [s.sequence_number for s in plan.steps]
        assert seq_nums == sorted(seq_nums)
        assert seq_nums[0] == 1

    def test_plan_id_is_stable(self):
        rs = _make_req_set()
        recognition = recognize_features(rs)
        inspection = build_inspection_plan(rs)
        p1 = generate_plan(rs, recognition, inspection)
        p2 = generate_plan(rs, recognition, inspection)
        assert p1.plan_id == p2.plan_id


class TestTraceability:
    def test_hole_traceability_populated(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("25"),
            unit="mm",
        )
        rs = _make_req_set(dimensional=(dim,))
        recognition = recognize_features(rs)
        inspection = build_inspection_plan(rs)
        plan = generate_plan(rs, recognition, inspection)

        entries = plan.traceability.entries
        assert len(entries) > 0
        req_ids = {e.req_id for e in entries}
        assert "D-0001" in req_ids

    def test_traceability_links_req_to_step(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("10"),
            unit="mm",
        )
        rs = _make_req_set(dimensional=(dim,))
        recognition = recognize_features(rs)
        inspection = build_inspection_plan(rs)
        plan = generate_plan(rs, recognition, inspection)

        chain = plan.traceability
        entries_for_req = chain.by_req("D-0001")
        assert len(entries_for_req) > 0
        for e in entries_for_req:
            assert e.step_id.startswith("S-")


class TestHandoff:
    def test_handoff_dict_structure(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("10"),
            unit="mm",
        )
        rs = _make_req_set(dimensional=(dim,))
        recognition = recognize_features(rs)
        inspection = build_inspection_plan(rs)
        plan = generate_plan(rs, recognition, inspection)

        handoff = plan.to_handoff_dict()
        assert "part_name" in handoff
        assert "operations" in handoff
        assert isinstance(handoff["operations"], list)
        for op in handoff["operations"]:
            assert "step_id" in op
            assert "operation" in op


class TestEmptyInput:
    def test_empty_requirements_insufficient_data(self):
        rs = _make_req_set()
        recognition = recognize_features(rs)
        inspection = build_inspection_plan(rs)
        plan = generate_plan(rs, recognition, inspection)
        assert plan.status == GeneratedPlanStatus.INSUFFICIENT_DATA
        assert plan.step_count == 0
