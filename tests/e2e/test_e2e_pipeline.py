"""End-to-end API pipeline integration tests.

Tests the full drawing→plan workflow via FastAPI TestClient.
CUSTOMER_DATA_USED=NO
"""
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

DEMO_REQ_SET = {
    "dimensional_requirements": [
        {"requirement_id": "D1", "feature_id": "OD_MAIN", "nominal_value": 40.0,
         "upper_deviation": 0.0, "lower_deviation": -0.016, "unit": "mm"},
        {"requirement_id": "D2", "feature_id": "OD_LAND", "nominal_value": 38.0,
         "upper_deviation": 0.0, "lower_deviation": -0.011, "unit": "mm"},
    ],
    "geometric_requirements": [
        {"requirement_id": "G1", "feature_id": "OD_MAIN",
         "characteristic": "CIRCULAR_RUNOUT", "tolerance_value": 0.005,
         "datum_frame": {"primary": {"label": "A", "precedence": 1, "modifier": "NONE"}}},
    ],
    "surface_finish_requirements": [
        {"requirement_id": "SF1", "feature_id": "OD_MAIN", "ra_max": 0.4},
    ],
    "thread_requirements": [
        {"requirement_id": "T1", "feature_id": "PORT_THREAD", "thread_standard": "G1/4"},
    ],
    "material_requirements": [
        {"requirement_id": "MAT1", "raw_designation": "42CrMo4"},
    ],
}


class TestManufacturingPlanPipeline:
    """Tests: req_set → generate plan → validate → approve → export."""

    def _generate(self, req_set=None, source_id="e2e-test"):
        return client.post("/api/manufacturing-plan/generate", json={
            "source_id": source_id,
            "drawing_number": "E2E-TEST",
            "revision": "A",
            "req_set": req_set,
        })

    def test_generate_returns_draft(self):
        r = self._generate(DEMO_REQ_SET)
        assert r.status_code == 200
        assert r.json()["status"] == "DRAFT"

    def test_generate_never_auto_approved(self):
        r = self._generate(DEMO_REQ_SET)
        assert r.json()["AUTO_GENERATED_PLAN_MARKED_APPROVED"] is False

    def test_generate_has_disclaimer(self):
        r = self._generate(DEMO_REQ_SET)
        assert "REFERENCE_ONLY" in r.json()["disclaimer"]

    def test_generate_extracts_characteristics(self):
        r = self._generate(DEMO_REQ_SET)
        assert r.json()["characteristics_count"] >= 3

    def test_generate_and_get_full_plan(self):
        plan_id = self._generate(DEMO_REQ_SET).json()["plan_id"]
        r = client.get(f"/api/manufacturing-plan/{plan_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["plan_id"] == plan_id

    def test_validate_after_generate(self):
        plan_id = self._generate(DEMO_REQ_SET).json()["plan_id"]
        r = client.post(f"/api/manufacturing-plan/{plan_id}/validate")
        assert r.status_code == 200
        data = r.json()
        assert "passed" in data
        assert "findings" in data

    def test_review_then_approve_workflow(self):
        plan_id = self._generate(DEMO_REQ_SET).json()["plan_id"]
        r_review = client.post(f"/api/manufacturing-plan/{plan_id}/review",
                               json={"engineer_note": "reviewed"})
        assert r_review.status_code == 200
        assert r_review.json()["status"] == "ENGINEER_REVIEWED"
        r_approve = client.post(f"/api/manufacturing-plan/{plan_id}/approve",
                                json={"engineer_note": "approved"})
        assert r_approve.status_code == 200
        assert r_approve.json()["status"] == "APPROVED"

    def test_approve_from_draft_requires_review(self):
        plan_id = self._generate(DEMO_REQ_SET).json()["plan_id"]
        r = client.post(f"/api/manufacturing-plan/{plan_id}/approve",
                        json={"engineer_note": ""})
        assert r.status_code in (400, 409, 422)

    def test_export_json(self):
        plan_id = self._generate(DEMO_REQ_SET).json()["plan_id"]
        r = client.get(f"/api/manufacturing-plan/{plan_id}/export?format=json")
        assert r.status_code == 200
        data = r.json()
        assert "content" in data or "plan_id" in data

    def test_export_html_has_disclaimer(self):
        plan_id = self._generate(DEMO_REQ_SET).json()["plan_id"]
        r = client.get(f"/api/manufacturing-plan/{plan_id}/export?format=html")
        assert r.status_code == 200
        assert "REFERENCE_ONLY" in str(r.json())

    def test_export_csv_operations(self):
        plan_id = self._generate(DEMO_REQ_SET).json()["plan_id"]
        r = client.get(f"/api/manufacturing-plan/{plan_id}/export?format=csv_operations")
        assert r.status_code == 200

    def test_nc_handoff_not_executed(self):
        plan_id = self._generate(DEMO_REQ_SET).json()["plan_id"]
        r = client.get(f"/api/manufacturing-plan/{plan_id}/nc-handoff")
        assert r.status_code == 200
        data = r.json()
        assert data.get("NC_FILE_EXECUTED") is False

    def test_no_private_path_in_export(self):
        plan_id = self._generate(DEMO_REQ_SET).json()["plan_id"]
        r = client.get(f"/api/manufacturing-plan/{plan_id}/export?format=json")
        content = str(r.json())
        assert "C:\\Users" not in content


class TestCapabilityPipeline:
    def test_tolerance_evaluate(self):
        r = client.post("/api/calibration/tolerance/evaluate", json={
            "operation": "FINISH_TURNING",
            "required_tolerance_um": 16.0,
            "nominal_size_mm": 40.0,
        })
        assert r.status_code == 200
        data = r.json()
        assert "status" in data

    def test_surface_evaluate(self):
        r = client.post("/api/calibration/surface/evaluate", json={
            "operation": "GRINDING",
            "required_ra_um": 0.4,
        })
        assert r.status_code == 200
        data = r.json()
        assert "status" in data

    def test_unknown_operation_returns_insufficient_data(self):
        r = client.post("/api/calibration/tolerance/evaluate", json={
            "operation": "UNKNOWN_OPERATION_XYZ",
            "required_tolerance_um": 10.0,
            "nominal_size_mm": 25.0,
        })
        assert r.status_code == 200
        data = r.json()
        assert "INSUFFICIENT_DATA" in str(data) or "NOT_CAPABLE" in str(data)


class TestSafetyInvariantsPipeline:
    """Verify safety constraints across the pipeline."""

    def _generate(self):
        return client.post("/api/manufacturing-plan/generate", json={
            "source_id": "safety-test",
            "drawing_number": "SAFETY",
            "revision": "A",
            "req_set": None,
        })

    def test_auto_approved_never_true(self):
        r = self._generate()
        assert r.json()["AUTO_GENERATED_PLAN_MARKED_APPROVED"] is False

    def test_disclaimer_always_present(self):
        r = self._generate()
        assert "REFERENCE_ONLY" in r.json()["disclaimer"]

    def test_draft_cannot_skip_to_approved(self):
        plan_id = self._generate().json()["plan_id"]
        r = client.post(f"/api/manufacturing-plan/{plan_id}/approve",
                        json={"engineer_note": ""})
        assert r.status_code in (400, 409, 422)

    def test_reject_plan_status(self):
        plan_id = self._generate().json()["plan_id"]
        r = client.post(f"/api/manufacturing-plan/{plan_id}/reject",
                        json={"engineer_note": "rejected"})
        assert r.status_code == 200
        assert r.json()["status"] == "REJECTED"

    def test_csv_injection_guard(self):
        plan_id = self._generate().json()["plan_id"]
        r = client.get(f"/api/manufacturing-plan/{plan_id}/export?format=csv_operations")
        content = r.json().get("content", "")
        lines = content.strip().split("\n")
        for line in lines[1:]:
            for cell in line.split(","):
                cell = cell.strip('"')
                if cell:
                    assert not (cell[0] in ("=", "+") and not cell.startswith("'")), \
                        f"Unguarded formula injection: {cell}"
