"""Tests for route_benchmark — EPIC_04E Phase 2."""

import pytest

from backend.drawing_intelligence.route_benchmark import RouteBenchmark, compute_benchmark
from backend.drawing_intelligence.route_optimizer import (
    FeatureRouteRequest,
    PartRouteRequest,
    RouteOptimizer,
)


def _make_plan_and_alts():
    optimizer = RouteOptimizer()
    req = PartRouteRequest(
        source_id="PART-001",
        drawing_number="DRW-001",
        revision="A",
        features=[
            FeatureRouteRequest(feature_id="F1", feature_type="HOLE", required_ra_um=1.6),
            FeatureRouteRequest(feature_id="F2", feature_type="POCKET", required_ra_um=3.2),
        ],
    )
    result = optimizer.optimize_part(req)
    return result.optimized_plan, result.alternative_sets


class TestRouteBenchmark:
    def setup_method(self):
        self.plan, self.alt_sets = _make_plan_and_alts()
        self.benchmark = RouteBenchmark()

    def test_returns_metrics(self):
        metrics = self.benchmark.compute(self.plan, self.alt_sets)
        assert metrics is not None

    def test_total_candidates_positive(self):
        metrics = self.benchmark.compute(self.plan, self.alt_sets)
        assert metrics.total_candidates_generated >= 0

    def test_feasible_plus_infeasible_equals_total(self):
        metrics = self.benchmark.compute(self.plan, self.alt_sets)
        assert metrics.feasible_candidates + metrics.infeasible_candidates == metrics.total_candidates_generated

    def test_recall_in_range(self):
        metrics = self.benchmark.compute(self.plan, self.alt_sets)
        assert 0.0 <= metrics.valid_route_recall <= 1.0

    def test_rejection_rate_in_range(self):
        metrics = self.benchmark.compute(self.plan, self.alt_sets)
        assert 0.0 <= metrics.invalid_route_rejection_rate <= 1.0

    def test_requirement_coverage_in_range(self):
        metrics = self.benchmark.compute(self.plan, self.alt_sets)
        assert 0.0 <= metrics.requirement_coverage <= 1.0

    def test_determinism_rate_1(self):
        metrics = self.benchmark.compute(self.plan, self.alt_sets)
        assert metrics.determinism_rate == 1.0

    def test_safety_flags_false(self):
        metrics = self.benchmark.compute(self.plan, self.alt_sets)
        assert metrics.FABRICATED_ROUTE is False
        assert metrics.FABRICATED_CYCLE_TIME is False
        assert metrics.AUTO_SELECTED_ROUTE_MARKED_APPROVED is False
        assert metrics.BLACK_BOX_AI_SCORE_USED is False
        assert metrics.INSUFFICIENT_DATA_TREATED_AS_PASS is False

    def test_infeasible_not_ranked_as_feasible(self):
        metrics = self.benchmark.compute(self.plan, self.alt_sets)
        assert metrics.INFEASIBLE_ROUTE_RANKED_AS_FEASIBLE is False

    def test_feature_count_matches(self):
        metrics = self.benchmark.compute(self.plan, self.alt_sets)
        assert metrics.feature_count == 2

    def test_unresolved_count_nonnegative(self):
        metrics = self.benchmark.compute(self.plan, self.alt_sets)
        assert metrics.unresolved_feature_count >= 0


class TestComputeBenchmark:
    def test_convenience_wrapper(self):
        plan, alt_sets = _make_plan_and_alts()
        metrics = compute_benchmark(plan, alt_sets)
        assert metrics is not None
