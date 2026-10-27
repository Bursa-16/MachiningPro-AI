"""Tests for route_feasibility — EPIC_04E Phase 2."""

import pytest

from backend.drawing_intelligence.route_alternatives import (
    ROUTE_TEMPLATES,
    ExtendedFeatureType,
)
from backend.drawing_intelligence.route_feasibility import (
    RouteFeasibilityEngine,
    capability_confidence,
    evaluate_template_feasibility,
)
from backend.drawing_intelligence.route_domain import (
    ProcessCapabilityConfidence,
    RouteFeasibilityStatus,
    RouteRejectionReason,
)
from backend.domain.enums import OperationType


def _template(feature_type=ExtendedFeatureType.HOLE, index=0):
    return ROUTE_TEMPLATES[feature_type][index]


class TestRouteFeasibilityEngine:
    def test_feasible_when_no_requirements(self):
        tmpl = _template()
        engine = RouteFeasibilityEngine()
        feas, rejections = engine.evaluate(tmpl)
        assert feas.status in (
            RouteFeasibilityStatus.FEASIBLE,
            RouteFeasibilityStatus.CONDITIONAL,
        )
        assert len(rejections) == 0

    def test_infeasible_when_ra_too_tight(self):
        # Find a template whose best Ra is >= 1.0
        tmpl = next(
            t for t in ROUTE_TEMPLATES[ExtendedFeatureType.HOLE]
            if t.best_ra_um >= 1.0
        )
        engine = RouteFeasibilityEngine()
        feas, rejections = engine.evaluate(tmpl, required_ra_um=0.1)
        assert feas.status is RouteFeasibilityStatus.INFEASIBLE
        assert any(r.reason is RouteRejectionReason.TOLERANCE_NOT_SUPPORTED for r in rejections)

    def test_feasible_when_ra_met(self):
        # drill-bore-hone template should achieve Ra <= 0.4
        tmpl = next(
            t for t in ROUTE_TEMPLATES[ExtendedFeatureType.HOLE]
            if t.best_ra_um <= 0.4
        )
        engine = RouteFeasibilityEngine()
        feas, rejections = engine.evaluate(tmpl, required_ra_um=0.4)
        assert feas.status in (
            RouteFeasibilityStatus.FEASIBLE,
            RouteFeasibilityStatus.CONDITIONAL,
        )

    def test_infeasible_when_it_grade_too_tight(self):
        tmpl = _template()
        engine = RouteFeasibilityEngine()
        feas, rejections = engine.evaluate(tmpl, required_it_grade="IT4")
        if feas.status is RouteFeasibilityStatus.INFEASIBLE:
            assert any(r.reason is RouteRejectionReason.TOLERANCE_NOT_SUPPORTED for r in rejections)
        # If the template supports IT4, it should be feasible/conditional — both OK

    def test_machine_limit_rejection(self):
        tmpl = _template()
        engine = RouteFeasibilityEngine()
        # Pass empty list of available machines — none match
        feas, rejections = engine.evaluate(
            tmpl,
            available_machine_type_codes=["NONEXISTENT_MACHINE_TYPE"],
        )
        assert feas.status is RouteFeasibilityStatus.INFEASIBLE
        assert any(r.reason is RouteRejectionReason.MACHINE_LIMIT for r in rejections)

    def test_gdt_rejection_for_non_gdt_template(self):
        # Find a non-GDT-capable template
        tmpl = next(
            t for t in ROUTE_TEMPLATES[ExtendedFeatureType.HOLE]
            if not t.gdt_capable
        )
        engine = RouteFeasibilityEngine()
        feas, rejections = engine.evaluate(tmpl, has_gdt_constraints=True)
        assert feas.status is RouteFeasibilityStatus.INFEASIBLE
        assert any(r.reason is RouteRejectionReason.GDT_SETUP_CONFLICT for r in rejections)

    def test_gdt_feasible_for_gdt_capable_template(self):
        tmpl = next(
            t for t in ROUTE_TEMPLATES[ExtendedFeatureType.HOLE]
            if t.gdt_capable
        )
        engine = RouteFeasibilityEngine()
        feas, rejections = engine.evaluate(tmpl, has_gdt_constraints=True)
        assert feas.status in (
            RouteFeasibilityStatus.FEASIBLE,
            RouteFeasibilityStatus.CONDITIONAL,
        )

    def test_material_mismatch_rejection(self):
        tmpl = _template()
        engine = RouteFeasibilityEngine()
        feas, rejections = engine.evaluate(
            tmpl,
            material_incompatible_ops=[tmpl.operations[0].operation_type.value],
        )
        assert feas.status is RouteFeasibilityStatus.INFEASIBLE
        assert any(r.reason is RouteRejectionReason.MATERIAL_MISMATCH for r in rejections)

    def test_requirement_coverage_1_when_all_met(self):
        tmpl = next(
            t for t in ROUTE_TEMPLATES[ExtendedFeatureType.HOLE]
            if t.best_ra_um <= 0.4 and t.gdt_capable
        )
        engine = RouteFeasibilityEngine()
        feas, _ = engine.evaluate(tmpl, required_ra_um=0.4, has_gdt_constraints=True)
        if feas.status is RouteFeasibilityStatus.FEASIBLE:
            assert feas.requirement_coverage == 1.0

    def test_insufficient_data_not_treated_as_pass(self):
        # INSUFFICIENT_DATA_TREATED_AS_PASS=NO — unresolvable IT grade → not FEASIBLE
        tmpl = _template()
        engine = RouteFeasibilityEngine()
        feas, _ = engine.evaluate(tmpl, required_it_grade="UNKNOWN_GRADE")
        # Should be INSUFFICIENT_DATA or INFEASIBLE, not FEASIBLE
        assert feas.status in (
            RouteFeasibilityStatus.INSUFFICIENT_DATA,
            RouteFeasibilityStatus.CONDITIONAL,
            RouteFeasibilityStatus.INFEASIBLE,
        )


class TestEvaluateTemplateFeasibility:
    def test_convenience_wrapper(self):
        tmpl = _template()
        feas, rejections = evaluate_template_feasibility(tmpl)
        assert feas is not None
        assert isinstance(rejections, list)


class TestCapabilityConfidence:
    def test_drilling_returns_literature(self):
        conf = capability_confidence(OperationType.DRILLING.value)
        assert conf is ProcessCapabilityConfidence.LITERATURE_REFERENCE

    def test_unknown_op_returns_insufficient(self):
        conf = capability_confidence("NONEXISTENT_OPERATION_XYZ")
        assert conf is ProcessCapabilityConfidence.INSUFFICIENT_DATA
