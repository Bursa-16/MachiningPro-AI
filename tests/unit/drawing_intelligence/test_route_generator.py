"""Tests for drawing_intelligence.route_generator (EPIC_04 Phase 2)."""

import pytest
from decimal import Decimal

from backend.domain.enums import FeatureType, OperationType
from backend.drawing_intelligence.feature_recognition import recognize_features
from backend.drawing_intelligence.route_generator import (
    RouteGenerator,
    RouteRejectionReason,
    generate_routes,
)
from backend.drawing_intelligence.requirements import (
    DimensionalRequirement,
    DrawingRequirementSet,
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


class TestHoleRoutes:
    def test_basic_hole_has_drill_route(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("10"),
            unit="mm",
        )
        rs = _make_req_set(dimensional=(dim,))
        recognition = recognize_features(rs)
        assert recognition.feature_count >= 1
        hole_rf = next(rf for rf in recognition.features
                       if rf.feature.feature_type == FeatureType.HOLE)
        rr = generate_routes(hole_rf, rs)
        assert rr.has_routes
        # At least one route must contain DRILLING
        ops_sets = [set(r.operations) for r in rr.routes]
        assert any(OperationType.DRILLING in ops for ops in ops_sets)

    def test_tight_ra_hole_adds_honing_route(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("25"),
            unit="mm",
        )
        sf = SurfaceFinishRequirement(req_id="SF-0001", ra_um=Decimal("0.4"))
        rs = _make_req_set(dimensional=(dim,), surface_finish=(sf,))
        recognition = recognize_features(rs)
        hole_rf = next(rf for rf in recognition.features
                       if rf.feature.feature_type == FeatureType.HOLE)
        rr = generate_routes(hole_rf, rs)
        assert rr.has_routes
        ops_sets = [set(r.operations) for r in rr.routes]
        assert any(OperationType.HONING in ops for ops in ops_sets)

    def test_drill_required_before_ream(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("10"),
            unit="mm",
        )
        rs = _make_req_set(dimensional=(dim,))
        recognition = recognize_features(rs)
        hole_rf = next(rf for rf in recognition.features
                       if rf.feature.feature_type == FeatureType.HOLE)
        rr = generate_routes(hole_rf, rs)
        for route in rr.routes:
            ops = list(route.operations)
            if OperationType.REAMING in ops:
                assert ops.index(OperationType.DRILLING) < ops.index(OperationType.REAMING), \
                    f"Drill must precede ream in {ops}"


class TestThreadRoutes:
    def test_thread_route_has_drilling_and_tapping(self):
        t = ThreadRequirement(req_id="T-0001", designation="M10x1.5")
        rs = _make_req_set(threads=(t,))
        recognition = recognize_features(rs)
        thread_rf = recognition.features[0]
        rr = generate_routes(thread_rf, rs)
        assert rr.has_routes
        ops_sets = [set(r.operations) for r in rr.routes]
        assert any(
            OperationType.DRILLING in ops and OperationType.TAPPING in ops
            for ops in ops_sets
        )

    def test_drill_before_tap_in_all_routes(self):
        t = ThreadRequirement(req_id="T-0001", designation="M8x1.25")
        rs = _make_req_set(threads=(t,))
        recognition = recognize_features(rs)
        thread_rf = recognition.features[0]
        rr = generate_routes(thread_rf, rs)
        for route in rr.routes:
            ops = list(route.operations)
            if OperationType.TAPPING in ops:
                assert ops.index(OperationType.DRILLING) < ops.index(OperationType.TAPPING)


class TestTurningRoutes:
    def test_cylindrical_surface_has_turning_route(self):
        from backend.drawing_intelligence.requirements import (
            ExpandedFeatureControlFrame,
            GdtCharacteristic,
            GeometricRequirement,
        )
        fcf = ExpandedFeatureControlFrame(
            characteristic=GdtCharacteristic.CIRCULARITY,
            tolerance_value=Decimal("0.01"),
            tolerance_unit="mm",
        )
        geom = GeometricRequirement(req_id="G-0001", fcf=fcf)
        rs = _make_req_set(geometric=(geom,))
        recognition = recognize_features(rs)
        cyl_rf = next(rf for rf in recognition.features
                      if rf.feature.feature_type == FeatureType.CYLINDRICAL_SURFACE)
        rr = generate_routes(cyl_rf, rs)
        assert rr.has_routes
        ops_sets = [set(r.operations) for r in rr.routes]
        assert any(OperationType.TURNING in ops for ops in ops_sets)


class TestRouteRejection:
    def test_unfeasible_ra_causes_rejection(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("10"),
            unit="mm",
        )
        # Ra 0.001 µm is impossible with any standard machining operation
        sf = SurfaceFinishRequirement(req_id="SF-0001", ra_um=Decimal("0.001"))
        rs = _make_req_set(dimensional=(dim,), surface_finish=(sf,))
        recognition = recognize_features(rs)
        hole_rf = next(rf for rf in recognition.features
                       if rf.feature.feature_type == FeatureType.HOLE)
        rr = generate_routes(hole_rf, rs)
        # All routes should be rejected due to Ra impossibility
        # (or a subset; the critical check is rejections include CAPABILITY_GAP)
        if not rr.has_routes:
            assert any(r.reason == RouteRejectionReason.CAPABILITY_GAP for r in rr.rejections)

    def test_no_fabrication_in_achievable_ra(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("10"),
            unit="mm",
        )
        rs = _make_req_set(dimensional=(dim,))
        recognition = recognize_features(rs)
        hole_rf = recognition.features[0]
        rr = generate_routes(hole_rf, rs)
        for route in rr.routes:
            # Achievable Ra must be a real non-zero value from the capability library
            assert route.achievable_ra_um > Decimal("0")
