"""Tests for Manufacturing Plan API — 10 endpoints."""
import pytest
from fastapi.testclient import TestClient
from backend.api.app import app

client = TestClient(app)

BASE = "/api/manufacturing-plan"


def _generate(req_set=None, drawing_number="DWG-API"):
    """EP-01: generate a new plan."""
    payload = {
        "source_id": "test-api",
        "drawing_number": drawing_number,
        "revision": "A",
        "req_set": req_set,
        "optimized_plan": None,
    }
    return client.post(f"{BASE}/generate", json=payload)


class TestEP01GeneratePlan:
    def test_returns_200(self):
        r = _generate()
        assert r.status_code == 200

    def test_returns_plan_id(self):
        r = _generate()
        data = r.json()
        assert "plan_id" in data

    def test_status_is_draft(self):
        r = _generate()
        data = r.json()
        assert data["status"] == "DRAFT"

    def test_auto_approved_flag_false(self):
        r = _generate()
        data = r.json()
        assert data.get("AUTO_GENERATED_PLAN_MARKED_APPROVED") is False

    def test_with_req_set_extracts_characteristics(self):
        req_set = {
            "dimensional_requirements": [
                {"requirement_id": "r1", "feature_id": "f1",
                 "nominal_value": 25.0, "upper_deviation": 0.021,
                 "lower_deviation": 0.0, "unit": "mm"}
            ]
        }
        r = _generate(req_set=req_set)
        data = r.json()
        assert data["characteristics_count"] >= 1

    def test_disclaimer_in_response(self):
        r = _generate()
        data = r.json()
        assert "disclaimer" in data
        assert "REFERENCE_ONLY" in data["disclaimer"]


class TestEP02ListPlans:
    def test_returns_list(self):
        _generate(drawing_number="LIST-TEST")
        r = client.get(f"{BASE}")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_filter_by_drawing_number(self):
        _generate(drawing_number="FILTER-DWG-001")
        r = client.get(f"{BASE}?drawing_number=FILTER-DWG-001")
        assert r.status_code == 200
        results = r.json()
        assert all(p.get("drawing_number") == "FILTER-DWG-001" for p in results)


class TestEP03GetPlan:
    def test_get_existing_plan(self):
        plan_id = _generate().json()["plan_id"]
        r = client.get(f"{BASE}/{plan_id}")
        assert r.status_code == 200

    def test_get_missing_plan_404(self):
        r = client.get(f"{BASE}/nonexistent-id")
        assert r.status_code == 404

    def test_response_has_plan_id(self):
        plan_id = _generate().json()["plan_id"]
        r = client.get(f"{BASE}/{plan_id}")
        data = r.json()
        assert "plan_id" in data


class TestEP04GetSummary:
    def test_returns_summary(self):
        plan_id = _generate().json()["plan_id"]
        r = client.get(f"{BASE}/{plan_id}/summary")
        assert r.status_code == 200
        data = r.json()
        assert "plan_id" in data
        assert "status" in data

    def test_404_for_missing(self):
        r = client.get(f"{BASE}/nope/summary")
        assert r.status_code == 404


class TestEP05Validate:
    def test_returns_validation_result(self):
        plan_id = _generate().json()["plan_id"]
        r = client.post(f"{BASE}/{plan_id}/validate")
        assert r.status_code == 200
        data = r.json()
        assert "passed" in data
        assert "findings" in data

    def test_404_for_missing(self):
        r = client.post(f"{BASE}/nope/validate")
        assert r.status_code == 404

    def test_findings_is_list(self):
        plan_id = _generate().json()["plan_id"]
        r = client.post(f"{BASE}/{plan_id}/validate")
        data = r.json()
        assert isinstance(data["findings"], list)


class TestEP06Review:
    def test_mark_reviewed(self):
        plan_id = _generate().json()["plan_id"]
        r = client.post(f"{BASE}/{plan_id}/review", json={"engineer_note": "checked"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ENGINEER_REVIEWED"

    def test_404_for_missing(self):
        r = client.post(f"{BASE}/nope/review", json={"engineer_note": ""})
        assert r.status_code == 404


class TestEP07Approve:
    def test_approve_after_review(self):
        plan_id = _generate().json()["plan_id"]
        client.post(f"{BASE}/{plan_id}/review", json={"engineer_note": "ok"})
        r = client.post(f"{BASE}/{plan_id}/approve", json={"engineer_note": "Approved"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "APPROVED"

    def test_approve_from_draft_rejected(self):
        """Plan must be ENGINEER_REVIEWED before APPROVED."""
        plan_id = _generate().json()["plan_id"]
        r = client.post(f"{BASE}/{plan_id}/approve", json={"engineer_note": ""})
        # Should be 409 or 400 — not 200 from DRAFT
        assert r.status_code in (400, 409, 422)

    def test_404_for_missing(self):
        r = client.post(f"{BASE}/nope/approve", json={"engineer_note": ""})
        assert r.status_code == 404


class TestEP08Reject:
    def test_reject_plan(self):
        plan_id = _generate().json()["plan_id"]
        r = client.post(f"{BASE}/{plan_id}/reject", json={"engineer_note": "needs revision"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "REJECTED"

    def test_404_for_missing(self):
        r = client.post(f"{BASE}/nope/reject", json={"engineer_note": ""})
        assert r.status_code == 404


class TestEP09NCHandoff:
    def test_returns_nc_handoff_packages(self):
        plan_id = _generate().json()["plan_id"]
        r = client.get(f"{BASE}/{plan_id}/nc-handoff")
        assert r.status_code == 200
        data = r.json()
        assert "packages" in data
        assert isinstance(data["packages"], list)

    def test_nc_file_not_executed(self):
        plan_id = _generate().json()["plan_id"]
        r = client.get(f"{BASE}/{plan_id}/nc-handoff")
        data = r.json()
        for pkg in data.get("packages", []):
            assert pkg.get("NC_FILE_EXECUTED") is False

    def test_404_for_missing(self):
        r = client.get(f"{BASE}/nope/nc-handoff")
        assert r.status_code == 404


class TestEP10Export:
    def _plan_id(self):
        return _generate().json()["plan_id"]

    def test_json_export(self):
        pid = self._plan_id()
        r = client.get(f"{BASE}/{pid}/export?format=json")
        assert r.status_code == 200
        data = r.json()
        assert data.get("format") == "json" or "content" in data or "plan_id" in data

    def test_html_export(self):
        pid = self._plan_id()
        r = client.get(f"{BASE}/{pid}/export?format=html")
        assert r.status_code == 200

    def test_404_for_missing(self):
        r = client.get(f"{BASE}/nope/export?format=json")
        assert r.status_code == 404


class TestSafetyInvariants:
    def test_auto_approved_never_true_on_generate(self):
        """AUTO_GENERATED_PLAN_MARKED_APPROVED=NO — generated plan is always DRAFT."""
        r = _generate()
        data = r.json()
        assert data.get("AUTO_GENERATED_PLAN_MARKED_APPROVED") is False

    def test_disclaimer_always_present(self):
        r = _generate()
        data = r.json()
        assert "disclaimer" in data
        assert "REFERENCE_ONLY" in data["disclaimer"]

    def test_no_private_path_in_json_export(self):
        pid = _generate().json()["plan_id"]
        r = client.get(f"{BASE}/{pid}/export?format=json")
        content = str(r.json())
        assert "C:\\Users" not in content
