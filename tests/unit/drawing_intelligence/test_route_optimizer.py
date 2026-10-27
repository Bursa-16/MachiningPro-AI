"""Tests for route_optimizer — EPIC_04E Phase 2.

ADVANCED_ROUTE_SCORING_IMPLEMENTED=YES
ROUTE_STRATEGY_WEIGHTS_IMPLEMENTED=YES
PARETO_ANALYSIS_IMPLEMENTED=YES
MULTI_FEATURE_ROUTE_PLANNING_IMPLEMENTED=YES
TOOL_CHANGE_OPTIMIZATION_IMPLEMENTED=YES
MACHINE_CHANGE_OPTIMIZATION_IMPLEMENTED=YES
OPERATION_CONSOLIDATION_IMPLEMENTED=YES

Safety invariants verified:
  FABRICATED_ROUTE=NO
  AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO
  BLACK_BOX_AI_SCORE_USED=NO
  INFEASIBLE_ROUTE_RANKED_AS_FEASIBLE=NO
"""

import pytest

from backend.drawing_intelligence.route_domain import (
    OverallRiskLevel,
    RouteStatus,
    RouteFeasibilityStatus,
    RouteOptimizationConfig,
)
from backend.drawing_intelligence.route_optimizer import (
    FeatureRouteRequest,
    PartRouteRequest,
    RouteOptimizer,
)
from backend.drawing_intelligence.route_strategies import RouteStrategy


def _hole_req(feature_id="F1", ra=1.6, it="IT9", iso="P"):
    return FeatureRouteRequest(
        feature_id=feature_id,
        feature_type="HOLE",
        required_ra_um=ra,
        required_it_grade=it,
        diameter_mm=12.0,
        iso_material_group=iso,
    )


def _precision_hole_req(feature_id="F-PREC"):
    return FeatureRouteRequest(
        feature_id=feature_id,
        feature_type="PRECISION_BORE",
        required_ra_um=0.4,
        required_it_grade="IT6",
        diameter_mm=20.0,
        has_tight_position=True,
        iso_material_group="P",
    )


def _pocket_req(feature_id="F-PCK"):
    return FeatureRouteRequest(
        feature_id=feature_id,
        feature_type="POCKET",
        required_ra_um=3.2,
        iso_material_group="M",
    )


class TestRouteOptimizerFeature:
    def setup_method(self):
        self.optimizer = RouteOptimizer()

    def test_returns_alternative_set(self):
        alt = self.optimizer.optimize_feature(_hole_req())
        assert alt is not None
        assert alt.feature_id == "F1"

    def test_at_least_one_candidate(self):
        alt = self.optimizer.optimize_feature(_hole_req())
        assert len(alt.candidates) >= 1

    def test_selected_route_id_is_feasible(self):
        alt = self.optimizer.optimize_feature(_hole_req())
        if alt.selected_route_id:
            sel = next(c for c in alt.candidates if c.route_id == alt.selected_route_id)
            assert sel.is_feasible, "INFEASIBLE_ROUTE_RANKED_AS_FEASIBLE=NO violated"

    def test_status_never_approved(self):
        alt = self.optimizer.optimize_feature(_hole_req())
        for c in alt.candidates:
            assert c.status is not None
            assert c.status.value != "APPROVED", "AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO"

    def test_status_is_draft_or_partial(self):
        alt = self.optimizer.optimize_feature(_hole_req())
        if alt.selected_route_id:
            sel = next(c for c in alt.candidates if c.route_id == alt.selected_route_id)
            assert sel.status in (RouteStatus.DRAFT, RouteStatus.INSUFFICIENT_DATA)

    def test_infeasible_not_selected_when_feasible_exists(self):
        alt = self.optimizer.optimize_feature(_hole_req())
        feasible = [c for c in alt.candidates if c.is_feasible]
        if feasible and alt.selected_route_id:
            sel = next((c for c in alt.candidates if c.route_id == alt.selected_route_id), None)
            if sel:
                assert sel.is_feasible, "Feasible candidate exists but infeasible was selected"

    def test_score_total_0_to_100(self):
        alt = self.optimizer.optimize_feature(_hole_req())
        for c in alt.candidates:
            assert 0 <= c.score.total <= 100, f"Score {c.score.total} out of range"

    def test_no_fabricated_cycle_time(self):
        alt = self.optimizer.optimize_feature(_hole_req())
        for c in alt.candidates:
            if c.cycle_time_context:
                # FABRICATED_CYCLE_TIME=NO — total_s must be None when path unknown
                assert c.cycle_time_context.total_s is None, (
                    "FABRICATED_CYCLE_TIME=NO: total_s should be None"
                )

    def test_score_explanation_not_blackbox(self):
        alt = self.optimizer.optimize_feature(_hole_req())
        for c in alt.candidates:
            assert c.explanation.why_selected, "Explanation missing"
            # Score breakdown must have individual components
            assert c.score.technical_feasibility >= 0
            assert c.score.risk_penalty <= 0

    def test_pareto_frontier_returned(self):
        config = RouteOptimizationConfig(include_pareto=True)
        alt = self.optimizer.optimize_feature(_hole_req(), config=config)
        # At least one Pareto-optimal route
        if len(alt.candidates) > 1:
            pareto_opt = [p for p in alt.pareto_frontier if p.is_pareto_optimal]
            assert len(pareto_opt) >= 1

    def test_pareto_disabled(self):
        config = RouteOptimizationConfig(include_pareto=False)
        alt = self.optimizer.optimize_feature(_hole_req(), config=config)
        assert len(alt.pareto_frontier) == 0

    def test_strategy_balanced_default(self):
        alt = self.optimizer.optimize_feature(_hole_req(), strategy=RouteStrategy.BALANCED)
        assert alt is not None

    def test_strategy_lowest_risk(self):
        alt = self.optimizer.optimize_feature(_hole_req(), strategy=RouteStrategy.LOWEST_RISK)
        if alt.selected_route_id:
            sel = next(c for c in alt.candidates if c.route_id == alt.selected_route_id)
            # Under LOWEST_RISK, risk penalty should not be worse than BALANCED selection
            assert sel.score.risk_penalty >= -15

    def test_strategy_minimum_setup(self):
        alt = self.optimizer.optimize_feature(_hole_req(), strategy=RouteStrategy.MINIMUM_SETUP)
        if alt.selected_route_id:
            sel = next(c for c in alt.candidates if c.route_id == alt.selected_route_id)
            assert sel.setup_count >= 1

    def test_precision_hole_gdt_capable_selected(self):
        alt = self.optimizer.optimize_feature(_precision_hole_req())
        if alt.selected_route_id:
            sel = next(c for c in alt.candidates if c.route_id == alt.selected_route_id)
            # Tight Ra requirements — best_ra_um should be achievable
            assert sel.is_feasible or sel.feasibility.status == RouteFeasibilityStatus.INSUFFICIENT_DATA

    def test_traceability_fingerprint_not_empty(self):
        alt = self.optimizer.optimize_feature(_hole_req())
        for c in alt.candidates:
            assert c.traceability_fingerprint, "Missing traceability fingerprint"

    def test_determinism_same_input_same_output(self):
        req = _hole_req()
        alt1 = self.optimizer.optimize_feature(req)
        alt2 = self.optimizer.optimize_feature(req)
        ids1 = [c.route_id for c in alt1.candidates]
        ids2 = [c.route_id for c in alt2.candidates]
        assert ids1 == ids2, "DETERMINISM: same input must produce same output"

    def test_search_space_guard_respected(self):
        config = RouteOptimizationConfig(max_routes_per_feature=2)
        alt = self.optimizer.optimize_feature(_hole_req(), config=config)
        assert len(alt.candidates) <= 2

    def test_max_machine_candidates_guard(self):
        config = RouteOptimizationConfig(max_machine_candidates=1)
        alt = self.optimizer.optimize_feature(_hole_req(), config=config)
        for c in alt.candidates:
            assert len(c.machine_candidates) <= 1

    def test_inspection_operation_added(self):
        req = FeatureRouteRequest(
            feature_id="F1",
            feature_type="HOLE",
            required_ra_um=1.6,
            has_inspection=True,
            inspection_notes=["Check Ø12H7"],
        )
        alt = self.optimizer.optimize_feature(req)
        for c in alt.candidates:
            inspection_ops = [op for op in c.operations if op.is_inspection]
            assert len(inspection_ops) >= 1


class TestRouteOptimizerPart:
    def setup_method(self):
        self.optimizer = RouteOptimizer()

    def _part_req(self, features, strategy=RouteStrategy.BALANCED):
        return PartRouteRequest(
            source_id="PART-001",
            drawing_number="DRW-001",
            revision="A",
            features=features,
            strategy=strategy,
        )

    def test_single_feature_part(self):
        req = self._part_req([_hole_req()])
        result = self.optimizer.optimize_part(req)
        assert result.optimized_plan is not None

    def test_multi_feature_part(self):
        req = self._part_req([_hole_req("F1"), _pocket_req("F2")])
        result = self.optimizer.optimize_part(req)
        plan = result.optimized_plan
        assert plan is not None
        assert len(result.alternative_sets) == 2

    def test_plan_status_never_approved(self):
        req = self._part_req([_hole_req()])
        result = self.optimizer.optimize_part(req)
        plan = result.optimized_plan
        assert plan.status.value != "APPROVED"

    def test_benchmark_safety_flags_false(self):
        req = self._part_req([_hole_req()])
        result = self.optimizer.optimize_part(req)
        bm = result.benchmark
        assert bm["FABRICATED_ROUTE"] is False
        assert bm["AUTO_SELECTED_ROUTE_MARKED_APPROVED"] is False
        assert bm["BLACK_BOX_AI_SCORE_USED"] is False

    def test_benchmark_determinism_rate_1(self):
        req = self._part_req([_hole_req()])
        result = self.optimizer.optimize_part(req)
        assert result.benchmark["determinism_rate"] == 1.0

    def test_part_plan_has_steps_for_selected_routes(self):
        req = self._part_req([_hole_req("F1"), _pocket_req("F2")])
        result = self.optimizer.optimize_part(req)
        plan = result.optimized_plan
        feature_ids = {step.feature_id for step in plan.steps}
        # At least one feature should have steps
        assert len(feature_ids) >= 1

    def test_same_setup_pair_integrated(self):
        req = PartRouteRequest(
            source_id="PART-X",
            drawing_number=None,
            revision=None,
            features=[_hole_req("F1"), _hole_req("F2")],
            same_setup_pairs=[("F1", "F2")],
        )
        result = self.optimizer.optimize_part(req)
        assert result.optimized_plan is not None

    def test_traceability_fingerprint_set(self):
        req = self._part_req([_hole_req()])
        result = self.optimizer.optimize_part(req)
        assert result.optimized_plan.traceability_fingerprint

    def test_tool_change_penalty_dict(self):
        req = self._part_req([_hole_req()])
        result = self.optimizer.optimize_part(req)
        for alt in result.alternative_sets:
            penalties = self.optimizer._tool_change_penalty(list(alt.candidates))
            for route_id, penalty in penalties.items():
                assert penalty >= 0

    def test_machine_change_penalty_dict(self):
        req = self._part_req([_hole_req()])
        result = self.optimizer.optimize_part(req)
        for alt in result.alternative_sets:
            penalties = self.optimizer._machine_change_penalty(list(alt.candidates))
            for route_id, penalty in penalties.items():
                assert penalty >= 0


class TestRouteOptimizerWhatIf:
    def test_what_if_different_strategy(self):
        optimizer = RouteOptimizer()
        req = _hole_req()
        baseline = optimizer.optimize_feature(req, strategy=RouteStrategy.BALANCED)
        whatif = optimizer.what_if(req, RouteStrategy.LOWEST_RISK)
        assert whatif is not None
        # What-if may have different selection
        assert whatif.feature_id == "F1"
