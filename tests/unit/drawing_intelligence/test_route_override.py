"""Tests for route_override — EPIC_04E Phase 2.

AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO
PROCESS_OPTIMIZATION_OVERRIDE_IMPLEMENTED=YES
"""

import pytest

from backend.drawing_intelligence.route_domain import (
    OverrideType,
    RouteOptimizationConfig,
    RouteOverride,
    RouteStatus,
)
from backend.drawing_intelligence.route_optimizer import FeatureRouteRequest, RouteOptimizer
from backend.drawing_intelligence.route_override import (
    RouteOverrideEngine,
    apply_override_to_candidate,
)


def _make_alt_set():
    optimizer = RouteOptimizer()
    req = FeatureRouteRequest(
        feature_id="F1",
        feature_type="HOLE",
        required_ra_um=1.6,
    )
    return optimizer.optimize_feature(req)


def _make_override(ot=OverrideType.LOCK_OPERATION, target="F1", value="drilling"):
    return RouteOverride(
        override_id="OVR-001",
        override_type=ot,
        target_id=target,
        value=value,
        applied_by="engineer",
        note="test override",
    )


class TestRouteOverrideEngine:
    def test_lock_operation_recorded(self):
        alt = _make_alt_set()
        override = _make_override(OverrideType.LOCK_OPERATION)
        engine = RouteOverrideEngine()
        result = engine.apply(alt, override)
        # Selected candidate should have the override recorded
        if result.selected_route_id:
            sel = next(c for c in result.candidates if c.route_id == result.selected_route_id)
            assert len(sel.overrides_applied) >= 1

    def test_status_remains_draft_after_override(self):
        alt = _make_alt_set()
        override = _make_override(OverrideType.LOCK_OPERATION)
        engine = RouteOverrideEngine()
        result = engine.apply(alt, override)
        for c in result.candidates:
            assert c.status.value != "APPROVED", "AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO"

    def test_exclude_operation_removes_op(self):
        alt = _make_alt_set()
        if not alt.selected_route_id:
            pytest.skip("No feasible route")
        sel = next(c for c in alt.candidates if c.route_id == alt.selected_route_id)
        if not sel.operations:
            pytest.skip("No operations")
        # Exclude the first operation type
        first_op_type = sel.operations[0].operation_type.value
        override = _make_override(OverrideType.EXCLUDE_OPERATION, target=sel.route_id, value=first_op_type)
        engine = RouteOverrideEngine()
        result = engine.apply(alt, override)
        updated_sel = next(c for c in result.candidates if c.route_id == sel.route_id)
        remaining = [op for op in updated_sel.operations if op.operation_type.value == first_op_type]
        assert len(remaining) == 0

    def test_lock_machine_filters_candidates(self):
        alt = _make_alt_set()
        if not alt.selected_route_id:
            pytest.skip("No feasible route")
        sel = next(c for c in alt.candidates if c.route_id == alt.selected_route_id)
        if not sel.machine_candidates:
            pytest.skip("No machine candidates")
        locked_id = sel.machine_candidates[0].machine_id
        override = _make_override(OverrideType.LOCK_MACHINE, target=sel.route_id, value=locked_id)
        engine = RouteOverrideEngine()
        result = engine.apply(alt, override)
        updated = next(c for c in result.candidates if c.route_id == sel.route_id)
        assert len(updated.machine_candidates) <= 1

    def test_override_does_not_affect_other_features(self):
        alt = _make_alt_set()
        override = RouteOverride(
            override_id="OVR-X",
            override_type=OverrideType.LOCK_OPERATION,
            target_id="F-OTHER",  # Different feature
            value="drilling",
            applied_by="engineer",
            note="",
        )
        engine = RouteOverrideEngine()
        result = engine.apply(alt, override)
        # No candidates should have override applied (different feature)
        for c in result.candidates:
            assert len(c.overrides_applied) == 0


class TestApplyOverrideToCandidate:
    def test_single_candidate_override(self):
        alt = _make_alt_set()
        if not alt.selected_route_id:
            pytest.skip("No feasible route")
        sel = next(c for c in alt.candidates if c.route_id == alt.selected_route_id)
        override = RouteOverride(
            override_id="OVR-X",
            override_type=OverrideType.LOCK_OPERATION,
            target_id=sel.route_id,
            value="drilling",
            applied_by="engineer",
            note="",
        )
        result = apply_override_to_candidate(sel, override)
        assert result is not None
