"""
Tests for GET /api/cutting-parameters/query, /schema and POST /calculate.

All tests use synthetic data injected through monkeypatching — the real
external reference file is never required during unit tests.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.api import cutting_parameters as cp_module
from backend.api.app import app
from backend.cutting_parameters.models import (
    ApplicabilityScope,
    CuttingParameterRecord,
    EvidenceStatus,
    ParameterType,
    QuantityRange,
)
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.domain.base import Provenance
from backend.domain.enums import IsoMaterialGroup, OperationType, ProvenanceType, ToolMaterial
from backend.domain.units import Quantity, Unit

client = TestClient(app)

# ---------------------------------------------------------------------------
# Test registry factory — injects a clean, seeded registry per test
# ---------------------------------------------------------------------------

def _make_record(
    record_id: str,
    parameter_type: ParameterType,
    unit: Unit,
    lo: str,
    hi: str,
    operation: OperationType,
    iso: IsoMaterialGroup,
    tool_mat: ToolMaterial | None = None,
    notes: str | None = None,
) -> CuttingParameterRecord:
    return CuttingParameterRecord(
        record_id=record_id,
        parameter_type=parameter_type,
        value_range=QuantityRange(
            min_value=Quantity(value=Decimal(lo), unit=unit),
            max_value=Quantity(value=Decimal(hi), unit=unit),
        ),
        applicability=ApplicabilityScope(
            operation_type=operation,
            iso_material_group=iso,
            tool_material=tool_mat,
        ),
        provenance=Provenance(
            source_type=ProvenanceType.LITERATURE,
            source_reference="Synthetic test reference",
            page_section="Test section",
        ),
        evidence_status=EvidenceStatus.REFERENCE_ONLY,
        notes=notes,
    )


def _make_test_registry() -> CuttingParameterRegistry:
    reg = CuttingParameterRegistry()
    # Turning P — Vc, fn, ap
    reg.register(_make_record(
        "t_vc_P", ParameterType.CUTTING_SPEED, Unit.M_MIN, "120", "280",
        OperationType.TURNING, IsoMaterialGroup.P, ToolMaterial.CARBIDE,
    ))
    reg.register(_make_record(
        "t_fn_P", ParameterType.FEED_PER_REV, Unit.MM_REV, "0.10", "0.45",
        OperationType.TURNING, IsoMaterialGroup.P, ToolMaterial.CARBIDE,
    ))
    reg.register(_make_record(
        "t_ap_P", ParameterType.AXIAL_DEPTH_OF_CUT, Unit.MM, "0.5", "4.0",
        OperationType.TURNING, IsoMaterialGroup.P, ToolMaterial.CARBIDE,
    ))
    # Milling P — Vc, fz, ap
    reg.register(_make_record(
        "m_vc_P", ParameterType.CUTTING_SPEED, Unit.M_MIN, "120", "260",
        OperationType.MILLING, IsoMaterialGroup.P, ToolMaterial.CARBIDE,
    ))
    reg.register(_make_record(
        "m_fz_P", ParameterType.FEED_PER_TOOTH, Unit.MM_TOOTH, "0.03", "0.18",
        OperationType.MILLING, IsoMaterialGroup.P, ToolMaterial.CARBIDE,
    ))
    reg.register(_make_record(
        "m_ap_P", ParameterType.AXIAL_DEPTH_OF_CUT, Unit.MM, "0.2", "6.0",
        OperationType.MILLING, IsoMaterialGroup.P, ToolMaterial.CARBIDE,
    ))
    # Drilling P — Vc, fn (NO ap — HR-12)
    reg.register(_make_record(
        "d_vc_P", ParameterType.CUTTING_SPEED, Unit.M_MIN, "80", "180",
        OperationType.DRILLING, IsoMaterialGroup.P,
    ))
    reg.register(_make_record(
        "d_fn_P", ParameterType.FEED_PER_REV, Unit.MM_REV, "0.08", "0.30",
        OperationType.DRILLING, IsoMaterialGroup.P,
    ))
    # Reaming P — Vc, fn (NO ap — HR-12)
    reg.register(_make_record(
        "r_vc_P", ParameterType.CUTTING_SPEED, Unit.M_MIN, "40", "120",
        OperationType.REAMING, IsoMaterialGroup.P,
    ))
    reg.register(_make_record(
        "r_fn_P", ParameterType.FEED_PER_REV, Unit.MM_REV, "0.15", "0.50",
        OperationType.REAMING, IsoMaterialGroup.P,
    ))
    # Turning S — Vc only (to test ISO group filtering)
    reg.register(_make_record(
        "t_vc_S", ParameterType.CUTTING_SPEED, Unit.M_MIN, "35", "90",
        OperationType.TURNING, IsoMaterialGroup.S, ToolMaterial.CARBIDE,
    ))
    return reg


@pytest.fixture(autouse=True)
def inject_test_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the module-level singleton with a synthetic test registry."""
    monkeypatch.setattr(cp_module, "_registry", _make_test_registry())
    monkeypatch.setattr(cp_module, "_seeded_path", "synthetic")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_schema_returns_operations(self):
        r = client.get("/api/cutting-parameters/schema")
        assert r.status_code == 200
        data = r.json()
        assert "turning" in data["operations"]
        assert "milling" in data["operations"]
        assert "drilling" in data["operations"]
        assert "reaming" in data["operations"]

    def test_schema_returns_iso_groups(self):
        r = client.get("/api/cutting-parameters/schema")
        data = r.json()
        assert set(data["iso_material_groups"]) == {"P", "M", "K", "N", "S", "H"}

    def test_schema_returns_iso_labels(self):
        r = client.get("/api/cutting-parameters/schema")
        data = r.json()
        assert "P" in data["iso_material_labels"]
        assert "Steel" in data["iso_material_labels"]["P"]

    def test_schema_returns_tool_materials(self):
        r = client.get("/api/cutting-parameters/schema")
        data = r.json()
        assert "carbide" in data["tool_materials"]
        assert "CBN" in data["tool_materials"]


# ---------------------------------------------------------------------------
# Query — matched cases
# ---------------------------------------------------------------------------

class TestQueryMatched:
    def test_turning_P_returns_matched(self):
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=P")
        assert r.status_code == 200
        data = r.json()
        assert data["matched"] is True
        assert data["match_level"] == "ISO_GROUP_MATCH"

    def test_turning_P_contains_cutting_speed(self):
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=P")
        data = r.json()
        types = [p["parameter_type"] for p in data["parameters"]]
        assert "CUTTING_SPEED" in types

    def test_turning_P_contains_feed_per_rev(self):
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=P")
        data = r.json()
        types = [p["parameter_type"] for p in data["parameters"]]
        assert "FEED_PER_REV" in types

    def test_turning_P_contains_ap(self):
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=P")
        data = r.json()
        types = [p["parameter_type"] for p in data["parameters"]]
        assert "AXIAL_DEPTH_OF_CUT" in types

    def test_milling_P_contains_feed_per_tooth_not_per_rev(self):
        r = client.get("/api/cutting-parameters/query?operation=milling&iso_material_group=P")
        data = r.json()
        types = [p["parameter_type"] for p in data["parameters"]]
        assert "FEED_PER_TOOTH" in types
        assert "FEED_PER_REV" not in types

    def test_drilling_P_no_ap(self):
        r = client.get("/api/cutting-parameters/query?operation=drilling&iso_material_group=P")
        data = r.json()
        types = [p["parameter_type"] for p in data["parameters"]]
        assert "AXIAL_DEPTH_OF_CUT" not in types

    def test_reaming_P_no_ap(self):
        r = client.get("/api/cutting-parameters/query?operation=reaming&iso_material_group=P")
        data = r.json()
        types = [p["parameter_type"] for p in data["parameters"]]
        assert "AXIAL_DEPTH_OF_CUT" not in types

    def test_authority_label_is_reference_guidance(self):
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=P")
        data = r.json()
        assert data["authority_label"] == "Reference Guidance"

    def test_evidence_status_is_reference_only(self):
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=P")
        data = r.json()
        assert data["evidence_status"] == "REFERENCE_ONLY"

    def test_provenance_no_file_path(self):
        """source_document (private path) must never appear in response."""
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=P")
        text = r.text
        assert "\\" not in text, "Response must not contain backslashes (Windows paths)"
        assert "C:" not in text, "Response must not contain drive letters"

    def test_provenance_source_reference_present(self):
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=P")
        data = r.json()
        assert data["provenance"]["source_reference"] == "Synthetic test reference"

    def test_tool_material_filter_respected(self):
        r = client.get(
            "/api/cutting-parameters/query"
            "?operation=turning&iso_material_group=P&tool_material=carbide"
        )
        assert r.status_code == 200
        data = r.json()
        assert data["matched"] is True

    def test_iso_group_S_turning_matches(self):
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=S")
        assert r.status_code == 200
        data = r.json()
        assert data["matched"] is True

    def test_missing_values_absent_not_zero(self):
        """Parameters with no records are absent, not returned as 0."""
        r = client.get("/api/cutting-parameters/query?operation=drilling&iso_material_group=P")
        data = r.json()
        for p in data["parameters"]:
            assert p["min_value"] != 0 or p["max_value"] != 0, (
                f"Parameter {p['parameter_type']} suspiciously shows 0–0 range"
            )


# ---------------------------------------------------------------------------
# Query — no-match cases
# ---------------------------------------------------------------------------

class TestQueryNoMatch:
    def test_no_match_for_unknown_iso_group_in_registry(self):
        # ISO K has no records in the synthetic registry
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=K")
        assert r.status_code == 200
        data = r.json()
        assert data["matched"] is False
        assert data["match_level"] == "NO_MATCH"

    def test_no_match_returns_empty_parameters(self):
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=K")
        data = r.json()
        assert data["parameters"] == []

    def test_no_match_provenance_none(self):
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=K")
        data = r.json()
        assert data["provenance"] is None

    def test_unknown_operation_returns_422(self):
        r = client.get("/api/cutting-parameters/query?operation=honing&iso_material_group=P")
        assert r.status_code == 422

    def test_invalid_iso_group_returns_422(self):
        r = client.get("/api/cutting-parameters/query?operation=turning&iso_material_group=Z")
        assert r.status_code == 422

    def test_unknown_tool_material_returns_422(self):
        r = client.get(
            "/api/cutting-parameters/query"
            "?operation=turning&iso_material_group=P&tool_material=unobtainium"
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Calculate
# ---------------------------------------------------------------------------

class TestCalculate:
    def test_rpm_calculation_basic(self):
        """n = 1000 × 150 / (π × 20) ≈ 2387"""
        r = client.post("/api/cutting-parameters/calculate", json={
            "vc_m_min": 150.0,
            "diameter_mm": 20.0,
            "operation": "turning",
        })
        assert r.status_code == 200
        data = r.json()
        assert 2380 < data["rpm"] < 2395

    def test_rpm_formula_label(self):
        r = client.post("/api/cutting-parameters/calculate", json={
            "vc_m_min": 100.0, "diameter_mm": 10.0, "operation": "turning",
        })
        assert r.json()["rpm_formula"] == "n = 1000 × Vc / (π × D)"

    def test_milling_feed_rate(self):
        """Vf = n × z × fz = (1000×120/(π×40)) × 4 × 0.08 ≈ 305.6 mm/min"""
        r = client.post("/api/cutting-parameters/calculate", json={
            "vc_m_min": 120.0,
            "diameter_mm": 40.0,
            "operation": "milling",
            "feed_per_tooth_mm": 0.08,
            "tooth_count": 4,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["feed_rate_mm_min"] is not None
        assert 300 < data["feed_rate_mm_min"] < 315

    def test_milling_feed_formula_label(self):
        r = client.post("/api/cutting-parameters/calculate", json={
            "vc_m_min": 120.0, "diameter_mm": 40.0, "operation": "milling",
            "feed_per_tooth_mm": 0.08, "tooth_count": 4,
        })
        assert r.json()["feed_rate_formula"] == "Vf = n × z × fz"

    def test_turning_feed_rate(self):
        """fr = n × f"""
        r = client.post("/api/cutting-parameters/calculate", json={
            "vc_m_min": 200.0,
            "diameter_mm": 50.0,
            "operation": "turning",
            "feed_per_rev_mm": 0.20,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["feed_rate_mm_min"] is not None
        assert data["feed_rate_formula"] == "fr = n × f"

    def test_no_feed_inputs_returns_null_feed_rate(self):
        r = client.post("/api/cutting-parameters/calculate", json={
            "vc_m_min": 150.0, "diameter_mm": 20.0, "operation": "milling",
        })
        assert r.status_code == 200
        assert r.json()["feed_rate_mm_min"] is None

    def test_zero_vc_returns_422(self):
        r = client.post("/api/cutting-parameters/calculate", json={
            "vc_m_min": 0.0, "diameter_mm": 20.0, "operation": "turning",
        })
        assert r.status_code == 422

    def test_zero_diameter_returns_422(self):
        r = client.post("/api/cutting-parameters/calculate", json={
            "vc_m_min": 100.0, "diameter_mm": 0.0, "operation": "turning",
        })
        assert r.status_code == 422

    def test_machine_limit_note_present(self):
        r = client.post("/api/cutting-parameters/calculate", json={
            "vc_m_min": 150.0, "diameter_mm": 20.0, "operation": "turning",
        })
        note = r.json()["machine_limit_note"]
        assert len(note) > 10
