"""Cross-pipeline safety invariant tests.

Verifies all FABRICATED_*=NO and UNKNOWN_DATA_TREATED_AS_PASS=NO invariants.
"""
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.manufacturing_plan.builder import build_manufacturing_plan
from backend.manufacturing_plan.characteristic import CharacteristicCriticality
from backend.manufacturing_plan.export import _safe_cell, export_csv_operations, export_json
from backend.manufacturing_plan.models import ManufacturingPlanStatus

client = TestClient(app)


class TestAutoApprovalInvariants:
    """AUTO_GENERATED_PLAN_MARKED_APPROVED=NO at every level."""

    def test_builder_always_draft(self):
        plan = build_manufacturing_plan(
            source_id="safety", optimized_plan=None, req_set=None,
            drawing_number="S-001", revision="A",
        )
        assert plan.status == ManufacturingPlanStatus.DRAFT
        assert plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False

    def test_api_generate_always_draft(self):
        r = client.post("/api/manufacturing-plan/generate", json={
            "source_id": "api-safety",
            "drawing_number": "S-API",
            "revision": "A",
        })
        data = r.json()
        assert data["status"] == "DRAFT"
        assert data["AUTO_GENERATED_PLAN_MARKED_APPROVED"] is False

    def test_api_approve_from_draft_blocked(self):
        plan_id = client.post("/api/manufacturing-plan/generate", json={
            "source_id": "s", "drawing_number": "S", "revision": "A",
        }).json()["plan_id"]
        r = client.post(f"/api/manufacturing-plan/{plan_id}/approve",
                        json={"engineer_note": ""})
        assert r.status_code in (400, 409, 422)


class TestKeyCharacteristicInvariants:
    """KEY_CHARACTERISTIC never auto-assigned."""

    def _build_with_reqs(self, reqs):
        return build_manufacturing_plan(
            source_id="key-test", optimized_plan=None, req_set=reqs,
            drawing_number="KC-TEST", revision="A",
        )

    def test_no_key_characteristic_auto_assigned_from_dimensions(self):
        reqs = {"dimensional_requirements": [
            {"requirement_id": "K1", "feature_id": "F1",
             "nominal_value": 25.0, "upper_deviation": 0.005, "lower_deviation": -0.005,
             "unit": "mm"},
        ]}
        plan = self._build_with_reqs(reqs)
        for char in plan.characteristics:
            assert char.criticality != CharacteristicCriticality.KEY_CHARACTERISTIC, \
                f"KEY_CHARACTERISTIC was auto-assigned to {char.label}"

    def test_no_key_characteristic_auto_assigned_from_gdt(self):
        reqs = {"geometric_requirements": [
            {"requirement_id": "K2", "feature_id": "F1",
             "characteristic": "POSITION", "tolerance_value": 0.01,
             "datum_frame": {"primary": {"label": "A", "precedence": 1, "modifier": "NONE"}}},
        ]}
        plan = self._build_with_reqs(reqs)
        for char in plan.characteristics:
            assert char.criticality != CharacteristicCriticality.KEY_CHARACTERISTIC

    def test_no_key_characteristic_from_critical_surface_finish(self):
        reqs = {"surface_finish_requirements": [
            {"requirement_id": "K3", "feature_id": "F1", "ra_max": 0.1},
        ]}
        plan = self._build_with_reqs(reqs)
        for char in plan.characteristics:
            assert char.criticality != CharacteristicCriticality.KEY_CHARACTERISTIC


class TestInsufficientDataInvariants:
    """INSUFFICIENT_DATA never silently treated as pass."""

    def test_unknown_capability_returns_insufficient_data(self):
        r = client.post("/api/calibration/tolerance/evaluate", json={
            "operation": "NONEXISTENT_OPERATION_FOR_SAFETY_TEST",
            "required_tolerance_um": 5.0,
            "nominal_size_mm": 25.0,
        })
        assert r.status_code == 200
        data = r.json()
        status = data.get("status", "")
        assert status != "ROBUST", \
            "Unknown operation returned ROBUST — INSUFFICIENT_DATA_TREATED_AS_PASS violation"

    def test_plan_with_no_ops_has_v002_finding(self):
        from backend.manufacturing_plan.validator import ValidationCode, validate_manufacturing_plan
        plan = build_manufacturing_plan(
            source_id="v002-test", optimized_plan=None, req_set=None,
            drawing_number="V002", revision="A",
        )
        result = validate_manufacturing_plan(plan)
        v002 = [f for f in result.findings if f.code == ValidationCode.V002]
        assert len(v002) >= 1


class TestExportSafetyInvariants:
    """No private paths, no CSV injection in exports."""

    def test_json_export_no_private_path(self):
        plan = build_manufacturing_plan(
            source_id="export-safety", optimized_plan=None, req_set=None,
            drawing_number="EXP-S", revision="A",
        )
        content = export_json(plan)
        assert "C:\\Users" not in content
        assert "/home/" not in content

    def test_csv_safe_cell_formula_guard(self):
        for dangerous in ["=SUM(A1)", "+cmd", "-1+2", "@formula"]:
            result = _safe_cell(dangerous)
            assert result.startswith("'"), f"_safe_cell did not guard: {dangerous!r}"

    def test_csv_injection_not_in_operations_export(self):
        plan = build_manufacturing_plan(
            source_id="csv-safety", optimized_plan=None, req_set=None,
            drawing_number="CSV-S", revision="A",
        )
        content = export_csv_operations(plan)
        lines = content.strip().split("\n")
        for line in lines[1:]:
            for cell in line.split(","):
                cell = cell.strip('"')
                if cell and cell[0] in ("=", "+", "-", "@"):
                    assert cell.startswith("'"), f"Unguarded: {cell!r}"
