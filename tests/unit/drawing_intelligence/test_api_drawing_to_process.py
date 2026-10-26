"""Tests for backend.api.drawing_to_process endpoint (EPIC_04 Phase 2)."""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

_BASE_REQ = {
    "source_id": "test-dwg-001",
    "drawing_number": "DWG-TEST-001",
    "revision": "A",
    "extraction_status": "PARTIAL",
    "dimensional": [],
    "geometric": [],
    "surface_finish": [],
    "threads": [],
    "heat_treatment": [],
}


class TestSchemaEndpoint:
    def test_schema_returns_200(self):
        resp = client.get("/api/drawing-to-process/schema")
        assert resp.status_code == 200

    def test_schema_has_security_invariants(self):
        resp = client.get("/api/drawing-to-process/schema")
        data = resp.json()
        inv = data["security_invariants"]
        assert inv["AUTO_GENERATED_PLAN_MARKED_APPROVED"] == "NO"
        assert inv["FABRICATED_DRAWING_REQUIREMENT"] == "NO"
        assert inv["LLM_REQUIRED_FOR_ROUTE_GENERATION"] == "NO"

    def test_schema_has_gdt_characteristics(self):
        resp = client.get("/api/drawing-to-process/schema")
        data = resp.json()
        chars = data["supported_gdt_characteristics"]
        assert "FLATNESS" in chars
        assert "POSITION" in chars
        assert len(chars) >= 14

    def test_schema_has_plan_statuses(self):
        resp = client.get("/api/drawing-to-process/schema")
        data = resp.json()
        statuses = data["plan_status_values"]
        assert "DRAFT" in statuses
        assert "PARTIAL" in statuses


class TestGenerateEndpoint:
    def test_empty_requirements_returns_insufficient_data(self):
        resp = client.post("/api/drawing-to-process/generate", json=_BASE_REQ)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "INSUFFICIENT_DATA"
        assert data["step_count"] == 0

    def test_hole_diameter_returns_draft_plan(self):
        req = {
            **_BASE_REQ,
            "dimensional": [
                {
                    "req_id": "D-0001",
                    "dimension_type": "DIAMETER",
                    "nominal_value": 10.0,
                    "unit": "mm",
                }
            ],
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("DRAFT", "PARTIAL")
        assert data["step_count"] > 0

    def test_thread_generates_drill_tap_steps(self):
        req = {
            **_BASE_REQ,
            "threads": [
                {
                    "req_id": "T-0001",
                    "designation": "M12x1.75",
                    "hand": "RH",
                }
            ],
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        assert resp.status_code == 200
        data = resp.json()
        ops = [s["operation"].upper() for s in data["steps"]]
        assert "DRILLING" in ops
        assert "TAPPING" in ops

    def test_gdt_adds_inspection_step(self):
        req = {
            **_BASE_REQ,
            "geometric": [
                {
                    "req_id": "G-0001",
                    "fcf": {
                        "characteristic": "FLATNESS",
                        "tolerance_value": 0.05,
                        "tolerance_unit": "mm",
                    },
                }
            ],
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        assert resp.status_code == 200
        data = resp.json()
        inspection_steps = [s for s in data["steps"] if s["is_inspection"]]
        assert len(inspection_steps) >= 1

    def test_response_has_disclaimer(self):
        resp = client.post("/api/drawing-to-process/generate", json=_BASE_REQ)
        data = resp.json()
        assert "disclaimer" in data
        assert len(data["disclaimer"]) > 0

    def test_auto_generated_plan_not_approved(self):
        req = {
            **_BASE_REQ,
            "dimensional": [
                {
                    "req_id": "D-0001",
                    "dimension_type": "DIAMETER",
                    "nominal_value": 10.0,
                    "unit": "mm",
                }
            ],
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        data = resp.json()
        assert data["status"] != "APPROVED"
        assert "APPROVED" not in data["status"]

    def test_plan_has_plan_id(self):
        req = {
            **_BASE_REQ,
            "dimensional": [
                {
                    "req_id": "D-0001",
                    "dimension_type": "DIAMETER",
                    "nominal_value": 20.0,
                    "unit": "mm",
                }
            ],
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        data = resp.json()
        assert "plan_id" in data
        assert len(data["plan_id"]) > 0

    def test_plan_id_stable_same_input(self):
        req = {
            **_BASE_REQ,
            "source_id": "stable-test-001",
            "dimensional": [
                {
                    "req_id": "D-0001",
                    "dimension_type": "DIAMETER",
                    "nominal_value": 15.0,
                    "unit": "mm",
                }
            ],
        }
        resp1 = client.post("/api/drawing-to-process/generate", json=req)
        resp2 = client.post("/api/drawing-to-process/generate", json=req)
        assert resp1.json()["plan_id"] == resp2.json()["plan_id"]

    def test_traceability_populated(self):
        req = {
            **_BASE_REQ,
            "dimensional": [
                {
                    "req_id": "D-0001",
                    "dimension_type": "DIAMETER",
                    "nominal_value": 10.0,
                    "unit": "mm",
                }
            ],
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        data = resp.json()
        assert len(data["traceability"]) > 0
        entry = data["traceability"][0]
        assert "req_id" in entry
        assert "step_id" in entry
        assert "operation" in entry

    def test_material_resolution_present(self):
        req = {
            **_BASE_REQ,
            "material": {
                "req_id": "MAT-0001",
                "raw_designation": "42CrMo4",
            },
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        data = resp.json()
        assert "material_resolution" in data
        mat = data["material_resolution"]
        assert mat["raw_designation"] == "42CrMo4"
        assert mat["confidence"] in ("EXACT", "PARTIAL", "NONE")

    def test_no_fabricated_material_when_unknown(self):
        req = {
            **_BASE_REQ,
            "material": {
                "req_id": "MAT-0001",
                "raw_designation": "XYZXYZ_NO_SUCH_MATERIAL_9999",
            },
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        data = resp.json()
        mat = data["material_resolution"]
        assert mat["confidence"] == "NONE"
        assert mat["matched_material_id"] is None

    def test_surface_finish_triggers_inspection(self):
        req = {
            **_BASE_REQ,
            "dimensional": [
                {
                    "req_id": "D-0001",
                    "dimension_type": "DIAMETER",
                    "nominal_value": 20.0,
                    "unit": "mm",
                }
            ],
            "surface_finish": [
                {
                    "req_id": "SF-0001",
                    "ra_um": 0.8,
                }
            ],
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        data = resp.json()
        inspection_steps = [s for s in data["steps"] if s["is_inspection"]]
        assert len(inspection_steps) >= 1

    def test_best_routes_returned(self):
        req = {
            **_BASE_REQ,
            "dimensional": [
                {
                    "req_id": "D-0001",
                    "dimension_type": "DIAMETER",
                    "nominal_value": 10.0,
                    "unit": "mm",
                }
            ],
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        data = resp.json()
        assert len(data["best_routes"]) > 0
        route = data["best_routes"][0]
        assert "score" in route
        assert "total" in route["score"]

    def test_lhm_thread_route(self):
        req = {
            **_BASE_REQ,
            "threads": [
                {
                    "req_id": "T-0001",
                    "designation": "M10x1.5",
                    "hand": "LH",
                }
            ],
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        assert resp.status_code == 200
        data = resp.json()
        assert data["step_count"] > 0

    def test_invalid_fcf_tolerance_zero_skipped(self):
        req = {
            **_BASE_REQ,
            "geometric": [
                {
                    "req_id": "G-0001",
                    "fcf": {
                        "characteristic": "FLATNESS",
                        "tolerance_value": 0.0,  # invalid → should be skipped
                        "tolerance_unit": "mm",
                    },
                }
            ],
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        # Should not crash — skipped gracefully
        assert resp.status_code in (200, 422)

    def test_multiple_features_generates_steps_for_each(self):
        req = {
            **_BASE_REQ,
            "dimensional": [
                {
                    "req_id": "D-0001",
                    "dimension_type": "DIAMETER",
                    "nominal_value": 10.0,
                    "unit": "mm",
                },
                {
                    "req_id": "D-0002",
                    "dimension_type": "DIAMETER",
                    "nominal_value": 20.0,
                    "unit": "mm",
                },
            ],
        }
        resp = client.post("/api/drawing-to-process/generate", json=req)
        data = resp.json()
        assert data["step_count"] >= 2
