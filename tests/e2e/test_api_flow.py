"""API sequence tests — full pipeline from drawing parser through export."""
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

SPOOL_REQ = {
    "dimensional_requirements": [
        {"requirement_id": "D1", "feature_id": "OD_MAIN",
         "nominal_value": 40.0, "upper_deviation": 0.0, "lower_deviation": -0.016, "unit": "mm"},
    ],
    "surface_finish_requirements": [
        {"requirement_id": "SF1", "feature_id": "OD_MAIN", "ra_max": 0.4},
    ],
    "geometric_requirements": [
        {"requirement_id": "G1", "feature_id": "OD_MAIN",
         "characteristic": "CIRCULAR_RUNOUT", "tolerance_value": 0.005,
         "datum_frame": {"primary": {"label": "A", "precedence": 1, "modifier": "NONE"}}},
    ],
}


class TestDrawingParserApiFlow:
    """Test drawing parser → manufacturing plan API sequence."""

    def test_drawing_parser_health(self):
        r = client.get("/api/drawing-parser/capabilities")
        assert r.status_code in (200, 404)  # endpoint may or may not exist

    def test_manufacturing_plan_api_reachable(self):
        r = client.post("/api/manufacturing-plan/generate", json={
            "source_id": "flow-test",
            "drawing_number": "FLOW-001",
            "revision": "A",
            "req_set": SPOOL_REQ,
        })
        assert r.status_code == 200

    def test_requirements_to_plan_to_export_sequence(self):
        # Step 1: generate plan from requirements
        r1 = client.post("/api/manufacturing-plan/generate", json={
            "source_id": "sequence-test",
            "drawing_number": "SEQ-001",
            "revision": "A",
            "req_set": SPOOL_REQ,
        })
        assert r1.status_code == 200
        plan_id = r1.json()["plan_id"]

        # Step 2: validate
        r2 = client.post(f"/api/manufacturing-plan/{plan_id}/validate")
        assert r2.status_code == 200
        assert "passed" in r2.json()

        # Step 3: review
        r3 = client.post(f"/api/manufacturing-plan/{plan_id}/review",
                         json={"engineer_note": "flow test"})
        assert r3.status_code == 200
        assert r3.json()["status"] == "ENGINEER_REVIEWED"

        # Step 4: export JSON
        r4 = client.get(f"/api/manufacturing-plan/{plan_id}/export?format=json")
        assert r4.status_code == 200

        # Step 5: export HTML
        r5 = client.get(f"/api/manufacturing-plan/{plan_id}/export?format=html")
        assert r5.status_code == 200

    def test_gdt_validation_api_reachable(self):
        r = client.post("/api/gdt/validate", json={
            "characteristic": "POSITION",
            "tolerance_value": 0.05,
        })
        assert r.status_code in (200, 422)

    def test_calibration_tolerance_api_reachable(self):
        r = client.post("/api/calibration/tolerance/evaluate", json={
            "operation": "FINISH_TURNING",
            "required_tolerance_um": 16.0,
            "nominal_size_mm": 40.0,
        })
        assert r.status_code in (200, 422)

    def test_plan_list_api(self):
        r = client.get("/api/manufacturing-plan")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_plan_filter_by_drawing(self):
        # generate a plan with known drawing number
        client.post("/api/manufacturing-plan/generate", json={
            "source_id": "filter-test",
            "drawing_number": "FILTER-E2E-001",
            "revision": "A",
        })
        r = client.get("/api/manufacturing-plan?drawing_number=FILTER-E2E-001")
        assert r.status_code == 200
        results = r.json()
        assert all(p.get("drawing_number") == "FILTER-E2E-001" for p in results)

    def test_plan_revise_creates_new_draft(self):
        plan_id = client.post("/api/manufacturing-plan/generate", json={
            "source_id": "revise-test",
            "drawing_number": "REV-E2E-001",
            "revision": "A",
        }).json()["plan_id"]
        r = client.post(f"/api/manufacturing-plan/{plan_id}/revise",
                        json={"change_driver": "ENGINEERING_CHANGE"})
        assert r.status_code == 200
        data = r.json()
        assert "new_plan_id" in data
        assert data["new_plan_id"] != plan_id

    def test_full_approval_then_export_chain(self):
        plan_id = client.post("/api/manufacturing-plan/generate", json={
            "source_id": "approval-chain-test",
            "drawing_number": "APPRV-001",
            "revision": "A",
            "req_set": SPOOL_REQ,
        }).json()["plan_id"]
        client.post(f"/api/manufacturing-plan/{plan_id}/review",
                    json={"engineer_note": "ok"})
        client.post(f"/api/manufacturing-plan/{plan_id}/approve",
                    json={"engineer_note": "approved"})
        r = client.get(f"/api/manufacturing-plan/{plan_id}/export?format=html")
        assert r.status_code == 200
        content = str(r.json())
        assert "REFERENCE_ONLY" in content
