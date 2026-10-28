"""API tests for /api/calibration — EPIC_04F."""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)


class TestSchemaEndpoint:
    def test_get_schema_200(self):
        r = client.get("/api/calibration/schema")
        assert r.status_code == 200

    def test_schema_has_tolerance_operations(self):
        r = client.get("/api/calibration/schema")
        data = r.json()
        assert "tolerance_operations" in data
        assert "FINISH_TURNING" in data["tolerance_operations"]

    def test_schema_has_surface_operations(self):
        r = client.get("/api/calibration/schema")
        data = r.json()
        assert "surface_operations" in data
        assert "GRINDING" in data["surface_operations"]

    def test_schema_has_disclaimer(self):
        r = client.get("/api/calibration/schema")
        data = r.json()
        assert "disclaimer" in data
        assert "REFERENCE_ONLY" in data["disclaimer"] or "FABRICATED" in data["disclaimer"]


class TestToleranceEvaluate:
    def test_finish_turning_it8_returns_200(self):
        r = client.post("/api/calibration/tolerance/evaluate", json={
            "operation": "FINISH_TURNING",
            "required_tolerance_um": 33.0,
            "nominal_size_mm": 25.0,
        })
        assert r.status_code == 200

    def test_tolerance_result_has_status(self):
        r = client.post("/api/calibration/tolerance/evaluate", json={
            "operation": "FINISH_TURNING",
            "required_tolerance_um": 33.0,
            "nominal_size_mm": 25.0,
        })
        assert "status" in r.json()

    def test_unknown_operation_returns_insufficient_data(self):
        r = client.post("/api/calibration/tolerance/evaluate", json={
            "operation": "LASER_CUT",
            "required_tolerance_um": 10.0,
            "nominal_size_mm": 25.0,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "INSUFFICIENT_DATA"


class TestSurfaceEvaluate:
    def test_grinding_ra_0_4_returns_200(self):
        r = client.post("/api/calibration/surface/evaluate", json={
            "operation": "GRINDING",
            "required_ra_um": 0.4,
        })
        assert r.status_code == 200

    def test_surface_result_has_margin_ratio(self):
        r = client.post("/api/calibration/surface/evaluate", json={
            "operation": "GRINDING",
            "required_ra_um": 0.4,
        })
        assert "margin_ratio" in r.json()
        assert r.json()["margin_ratio"] is not None

    def test_unknown_surface_op_insufficient_data(self):
        r = client.post("/api/calibration/surface/evaluate", json={
            "operation": "SPARK_EROSION",
            "required_ra_um": 0.8,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "INSUFFICIENT_DATA"


class TestCycleTimeEstimate:
    def test_all_unknown_returns_200(self):
        r = client.post("/api/calibration/cycle-time/estimate", json={})
        assert r.status_code == 200

    def test_all_unknown_insufficient_data(self):
        r = client.post("/api/calibration/cycle-time/estimate", json={})
        data = r.json()
        assert data["completeness"] == "INSUFFICIENT_DATA"
        assert data["total_cycle_time_sec_min"] is None

    def test_known_cutting_partial(self):
        r = client.post("/api/calibration/cycle-time/estimate", json={
            "cutting_sec_min": 60.0,
            "cutting_sec_max": 65.0,
        })
        data = r.json()
        assert data["completeness"] in ("PARTIALLY_CALCULATED", "FULLY_CALCULATED")
        assert data["known_total_sec_min"] is not None

    def test_partial_total_not_presented_as_full(self):
        # PARTIAL_TIME_PRESENTED_AS_TOTAL=NO
        r = client.post("/api/calibration/cycle-time/estimate", json={
            "cutting_sec_min": 60.0,
        })
        data = r.json()
        if data["completeness"] == "PARTIALLY_CALCULATED":
            assert data["total_cycle_time_sec_min"] is None

    def test_with_batch_returns_batch_model(self):
        r = client.post("/api/calibration/cycle-time/estimate", json={
            "cutting_sec_min": 60.0,
            "cutting_sec_max": 60.0,
            "setup_sec": 1800.0,
            "batch_quantity": 10,
        })
        data = r.json()
        assert "batch_model" in data

    def test_atc_known_tool_change_reference(self):
        r = client.post("/api/calibration/cycle-time/estimate", json={
            "atc_time_sec": 5.0,
            "tool_changes": 3,
        })
        data = r.json()
        tool_change = next((c for c in data["components"] if c["component_id"] == "TOOL_CHANGE"), None)
        assert tool_change is not None
        assert tool_change["status"] == "REFERENCE"
        assert tool_change["value_sec_min"] == pytest.approx(15.0)


class TestProfilesCRUD:
    def test_create_profile_returns_201_or_200(self):
        r = client.post("/api/calibration/profiles", json={
            "label": "API test profile",
            "machine_id": "VF2SS",
            "atc_time_sec": 3.5,
        })
        assert r.status_code == 200

    def test_create_profile_has_id(self):
        r = client.post("/api/calibration/profiles", json={"label": "test"})
        assert "profile_id" in r.json()

    def test_list_profiles_200(self):
        r = client.get("/api/calibration/profiles")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_created_profile(self):
        create_r = client.post("/api/calibration/profiles", json={"label": "get-test"})
        pid = create_r.json()["profile_id"]
        r = client.get(f"/api/calibration/profiles/{pid}")
        assert r.status_code == 200
        assert r.json()["label"] == "get-test"

    def test_get_nonexistent_profile_404(self):
        r = client.get("/api/calibration/profiles/does-not-exist-00000")
        assert r.status_code == 404

    def test_patch_profile_updates_label(self):
        create_r = client.post("/api/calibration/profiles", json={"label": "original"})
        pid = create_r.json()["profile_id"]
        r = client.patch(f"/api/calibration/profiles/{pid}", json={"label": "updated"})
        assert r.status_code == 200
        assert r.json()["label"] == "updated"

    def test_patch_profile_increments_revision(self):
        create_r = client.post("/api/calibration/profiles", json={"label": "rev-test"})
        pid = create_r.json()["profile_id"]
        r = client.patch(f"/api/calibration/profiles/{pid}", json={"label": "v2"})
        assert r.json()["revision"] == 2

    def test_patch_nonexistent_404(self):
        r = client.patch("/api/calibration/profiles/bad-id", json={"label": "x"})
        assert r.status_code == 404
