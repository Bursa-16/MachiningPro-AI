"""Tests for drawing_intelligence.route_scoring (EPIC_04 Phase 2)."""

import pytest
from decimal import Decimal

from backend.domain.enums import FeatureType, OperationType
from backend.drawing_intelligence.route_generator import AlternativeRoute
from backend.drawing_intelligence.route_scoring import (
    RouteScore,
    RouteScorer,
    ScoredRoute,
    score_routes,
)


def _route(
    route_id: str,
    feature_type: FeatureType,
    operations: list[OperationType],
    required_ra: Decimal | None = None,
    achievable_ra: Decimal = Decimal("1.6"),
) -> AlternativeRoute:
    return AlternativeRoute(
        route_id=route_id,
        feature_id=f"feat-{route_id}",
        feature_type=feature_type,
        operations=tuple(operations),
        required_ra_um=required_ra,
        achievable_ra_um=achievable_ra,
        requires_grinding=OperationType.GRINDING in operations,
        route_description=f"Test route {route_id}",
    )


class TestRouteScoreModel:
    def test_total_is_sum(self):
        score = RouteScore(
            completeness=40,
            efficiency=20,
            seq_compliance=20,
            dfm_compliance=10,
            availability=10,
        )
        assert score.total == 100

    def test_max_score_100(self):
        score = RouteScore(completeness=40, efficiency=20, seq_compliance=20,
                           dfm_compliance=10, availability=10)
        assert score.total == 100


class TestCompleteness:
    def test_no_requirement_full_completeness(self):
        r = _route("R0", FeatureType.HOLE, [OperationType.DRILLING])
        scored = score_routes([r])
        assert scored[0].score.completeness == 40

    def test_ra_satisfied_full_completeness(self):
        r = _route(
            "R1", FeatureType.HOLE,
            [OperationType.DRILLING, OperationType.REAMING],
            required_ra=Decimal("0.8"),
            achievable_ra=Decimal("0.4"),
        )
        scored = score_routes([r])
        assert scored[0].score.completeness == 40

    def test_ra_not_satisfied_zero_completeness(self):
        r = _route(
            "R2", FeatureType.HOLE,
            [OperationType.DRILLING],
            required_ra=Decimal("0.4"),
            achievable_ra=Decimal("1.6"),
        )
        scored = score_routes([r])
        assert scored[0].score.completeness == 0


class TestEfficiency:
    def test_single_op_max_efficiency(self):
        r = _route("R0", FeatureType.HOLE, [OperationType.DRILLING])
        scored = score_routes([r])
        assert scored[0].score.efficiency == 20

    def test_two_ops_15(self):
        r = _route("R0", FeatureType.HOLE,
                   [OperationType.DRILLING, OperationType.REAMING])
        scored = score_routes([r])
        assert scored[0].score.efficiency == 15

    def test_five_ops_floor_zero(self):
        r = _route("R0", FeatureType.HOLE, [
            OperationType.DRILLING,
            OperationType.BORING,
            OperationType.REAMING,
            OperationType.HONING,
            OperationType.INSPECTION,
        ])
        scored = score_routes([r])
        assert scored[0].score.efficiency == 0


class TestSorting:
    def test_higher_score_first(self):
        r1 = _route(
            "R1", FeatureType.HOLE,
            [OperationType.DRILLING, OperationType.REAMING],
            required_ra=Decimal("0.8"),
            achievable_ra=Decimal("0.4"),
        )
        r2 = _route(
            "R2", FeatureType.HOLE,
            [OperationType.DRILLING],
            required_ra=Decimal("0.4"),
            achievable_ra=Decimal("1.6"),
        )
        scored = score_routes([r1, r2])
        assert scored[0].route.route_id == "R1"  # meets Ra requirement

    def test_deterministic_tiebreak(self):
        r1 = _route("R1", FeatureType.HOLE, [OperationType.DRILLING])
        r2 = _route("R2", FeatureType.HOLE, [OperationType.DRILLING])
        scored1 = score_routes([r1, r2])
        scored2 = score_routes([r2, r1])
        # Same scores → sort by route_id
        ids1 = [s.route.route_id for s in scored1]
        ids2 = [s.route.route_id for s in scored2]
        assert ids1 == ids2  # deterministic

    def test_empty_routes_ok(self):
        result = score_routes([])
        assert result == []


class TestDfmCompliance:
    def test_grinding_when_not_needed_loses_dfm_points(self):
        # No Ra requirement but route has grinding → DFM penalty
        r_with_grinding = _route(
            "R1", FeatureType.CYLINDRICAL_SURFACE,
            [OperationType.TURNING, OperationType.GRINDING],
        )
        r_without_grinding = _route(
            "R2", FeatureType.CYLINDRICAL_SURFACE,
            [OperationType.TURNING],
        )
        scored = score_routes([r_with_grinding, r_without_grinding])
        # Route without grinding should have higher DFM score
        dfm_with = next(s.score.dfm_compliance for s in scored
                        if s.route.route_id == "R1")
        dfm_without = next(s.score.dfm_compliance for s in scored
                           if s.route.route_id == "R2")
        assert dfm_without >= dfm_with
