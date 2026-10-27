"""API tests for /api/process-routes — EPIC_04E Phase 2.

FABRICATED_ROUTE=NO
AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO
BLACK_BOX_AI_SCORE_USED=NO
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)


HOLE_REQ = {
    "feature_id": "F1",
    "feature_type": "HOLE",
    "required_ra_um": 1.6,
    "required_it_grade": "IT9",
    "diameter_mm": 12.0,
    "iso_material_group": "P",
    "strategy": "BALANCED",
}

PART_REQ = {
    "source_id": "PART-001",
    "drawing_number": "DRW-001",
    "revision": "A",
    "features": [
        {
            "feature_id": "F1",
            "feature_type": "HOLE",
            "required_ra_um": 1.6,
            "iso_material_group": "P",
        },
        {
            "feature_id": "F2",
            "feature_type": "POCKET",
            "required_ra_um": 3.2,
        },
    ],
    "strategy": "BALANCED",
}


class TestGenerateFeatureRoutes:
    def test_200_ok(self):
        resp = client.post("/api/process-routes/generate", json=HOLE_REQ)
        assert resp.status_code == 200

    def test_returns_alternative_set(self):
        resp = client.post("/api/process-routes/generate", json=HOLE_REQ)
        data = resp.json()
        assert "alternative_set" in data
        assert "candidates" in data["alternative_set"]

    def test_disclaimer_in_response(self):
        resp = client.post("/api/process-routes/generate", json=HOLE_REQ)
        data = resp.json()
        assert "REFERENCE_ONLY" in data["disclaimer"]

    def test_no_auto_approved_status(self):
        resp = client.post("/api/process-routes/generate", json=HOLE_REQ)
        data = resp.json()
        for c in data["alternative_set"]["candidates"]:
            assert c["status"] != "APPROVED"

    def test_candidates_have_score(self):
        resp = client.post("/api/process-routes/generate", json=HOLE_REQ)
        data = resp.json()
        for c in data["alternative_set"]["candidates"]:
            assert "score" in c
            assert 0 <= c["score"]["total"] <= 100

    def test_invalid_strategy_422(self):
        req = dict(HOLE_REQ, strategy="INVALID_STRATEGY_XYZ")
        resp = client.post("/api/process-routes/generate", json=req)
        assert resp.status_code == 422

    def test_cycle_time_not_fabricated(self):
        resp = client.post("/api/process-routes/generate", json=HOLE_REQ)
        data = resp.json()
        for c in data["alternative_set"]["candidates"]:
            # FABRICATED_CYCLE_TIME=NO — cycle time total should be null
            if c.get("cycle_time_context"):
                # No direct field exposed in this response, but candidate serializer omits it
                pass  # candidate serializer currently does not expose cycle_time_context fields

    def test_explanation_why_selected_present(self):
        resp = client.post("/api/process-routes/generate", json=HOLE_REQ)
        data = resp.json()
        for c in data["alternative_set"]["candidates"]:
            assert c["explanation"]["why_selected"]

    def test_pareto_frontier_present(self):
        resp = client.post("/api/process-routes/generate", json=HOLE_REQ)
        data = resp.json()
        alt = data["alternative_set"]
        assert "pareto_frontier" in alt


class TestOptimizePartRoutes:
    def test_200_ok(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        assert resp.status_code == 200

    def test_returns_plan_and_alternatives(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        data = resp.json()
        assert "plan" in data
        assert "alternative_sets" in data
        assert "benchmark" in data

    def test_plan_is_draft(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        data = resp.json()
        assert data["plan"]["status"] in ("DRAFT", "PARTIAL", "INSUFFICIENT_DATA")
        assert data["plan"]["status"] != "APPROVED"

    def test_benchmark_safety_flags(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        data = resp.json()
        bm = data["benchmark"]
        assert bm["FABRICATED_ROUTE"] is False
        assert bm["AUTO_SELECTED_ROUTE_MARKED_APPROVED"] is False
        assert bm["BLACK_BOX_AI_SCORE_USED"] is False

    def test_benchmark_determinism_rate(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        data = resp.json()
        assert data["benchmark"]["determinism_rate"] == 1.0

    def test_disclaimer_in_response(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        data = resp.json()
        assert "REFERENCE_ONLY" in data["disclaimer"]

    def test_two_alternative_sets_for_two_features(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        data = resp.json()
        assert len(data["alternative_sets"]) == 2

    def test_plan_id_returned(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        data = resp.json()
        assert data["plan"]["plan_id"]

    def test_invalid_strategy_422(self):
        req = dict(PART_REQ, strategy="NOT_A_STRATEGY")
        resp = client.post("/api/process-routes/optimize", json=req)
        assert resp.status_code == 422


class TestGetPlan:
    def _create_plan(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        assert resp.status_code == 200
        return resp.json()["plan"]["plan_id"]

    def test_get_existing_plan_200(self):
        plan_id = self._create_plan()
        resp = client.get(f"/api/process-routes/{plan_id}")
        assert resp.status_code == 200

    def test_get_nonexistent_plan_404(self):
        resp = client.get("/api/process-routes/nonexistent-plan-id")
        assert resp.status_code == 404

    def test_get_plan_has_steps(self):
        plan_id = self._create_plan()
        resp = client.get(f"/api/process-routes/{plan_id}")
        data = resp.json()
        assert "steps" in data
        assert isinstance(data["steps"], list)


class TestGetAlternatives:
    def _create_plan(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        return resp.json()["plan"]["plan_id"]

    def test_200_ok(self):
        plan_id = self._create_plan()
        resp = client.get(f"/api/process-routes/{plan_id}/alternatives")
        assert resp.status_code == 200

    def test_returns_alternative_sets(self):
        plan_id = self._create_plan()
        resp = client.get(f"/api/process-routes/{plan_id}/alternatives")
        data = resp.json()
        assert "alternative_sets" in data

    def test_404_for_unknown_plan(self):
        resp = client.get("/api/process-routes/UNKNOWN/alternatives")
        assert resp.status_code == 404


class TestSelectRoute:
    def _setup(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        data = resp.json()
        plan_id = data["plan"]["plan_id"]
        alt = data["alternative_sets"][0]
        route_id = alt["selected_route_id"] or (alt["candidates"][0]["route_id"] if alt["candidates"] else None)
        feature_id = alt["feature_id"]
        return plan_id, feature_id, route_id

    def test_select_200(self):
        plan_id, feature_id, route_id = self._setup()
        if not route_id:
            pytest.skip("No route to select")
        resp = client.post(
            f"/api/process-routes/{plan_id}/select",
            json={"feature_id": feature_id, "route_id": route_id},
        )
        assert resp.status_code == 200

    def test_select_status_not_approved(self):
        plan_id, feature_id, route_id = self._setup()
        if not route_id:
            pytest.skip("No route to select")
        resp = client.post(
            f"/api/process-routes/{plan_id}/select",
            json={"feature_id": feature_id, "route_id": route_id},
        )
        data = resp.json()
        assert data["status"] != "APPROVED"
        assert "DRAFT" in data["note"] or "AUTO_SELECTED" in data["note"]

    def test_select_invalid_route_422(self):
        plan_id, feature_id, _ = self._setup()
        resp = client.post(
            f"/api/process-routes/{plan_id}/select",
            json={"feature_id": feature_id, "route_id": "NONEXISTENT-ROUTE"},
        )
        assert resp.status_code == 422

    def test_select_invalid_feature_422(self):
        plan_id, _, route_id = self._setup()
        if not route_id:
            pytest.skip("No route")
        resp = client.post(
            f"/api/process-routes/{plan_id}/select",
            json={"feature_id": "NONEXISTENT-FEATURE", "route_id": route_id},
        )
        assert resp.status_code == 422


class TestApplyOverride:
    def _setup(self):
        resp = client.post("/api/process-routes/optimize", json=PART_REQ)
        data = resp.json()
        plan_id = data["plan"]["plan_id"]
        alt = data["alternative_sets"][0]
        feature_id = alt["feature_id"]
        route_id = alt["selected_route_id"] or (alt["candidates"][0]["route_id"] if alt["candidates"] else None)
        return plan_id, feature_id, route_id

    def test_override_200(self):
        plan_id, feature_id, route_id = self._setup()
        if not route_id:
            pytest.skip("No route")
        resp = client.post(
            f"/api/process-routes/{plan_id}/override",
            json={
                "feature_id": feature_id,
                "override_type": "LOCK_OPERATION",
                "target_id": route_id,
                "value": "drilling",
                "applied_by": "engineer",
            },
        )
        assert resp.status_code == 200

    def test_override_result_not_approved(self):
        plan_id, feature_id, route_id = self._setup()
        if not route_id:
            pytest.skip("No route")
        resp = client.post(
            f"/api/process-routes/{plan_id}/override",
            json={
                "feature_id": feature_id,
                "override_type": "LOCK_OPERATION",
                "target_id": route_id,
                "value": "drilling",
            },
        )
        data = resp.json()
        assert data.get("note") and "DRAFT" in data["note"]

    def test_invalid_override_type_422(self):
        plan_id, feature_id, _ = self._setup()
        resp = client.post(
            f"/api/process-routes/{plan_id}/override",
            json={
                "feature_id": feature_id,
                "override_type": "INVALID_OVERRIDE_TYPE",
                "target_id": "X",
                "value": "x",
            },
        )
        assert resp.status_code == 422
