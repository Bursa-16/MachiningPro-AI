"""Tests for GET /api/materials/* endpoints (EPIC_01_MATERIAL_INTELLIGENCE_FOUNDATION)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Health: materials endpoints reachable
# ---------------------------------------------------------------------------

class TestMaterialsEndpointsReachable:
    def test_list_endpoint_200(self):
        r = client.get("/api/materials")
        assert r.status_code == 200

    def test_iso_groups_endpoint_200(self):
        r = client.get("/api/materials/iso-groups")
        assert r.status_code == 200

    def test_summary_endpoint_200(self):
        r = client.get("/api/materials/summary")
        assert r.status_code == 200

    def test_search_endpoint_200(self):
        r = client.get("/api/materials/search?q=C45")
        assert r.status_code == 200

    def test_detail_404_for_unknown(self):
        r = client.get("/api/materials/DOES_NOT_EXIST_XYZ")
        assert r.status_code == 404

    def test_machinability_404_for_unknown(self):
        r = client.get("/api/materials/DOES_NOT_EXIST_XYZ/machinability")
        assert r.status_code == 404

    def test_cutting_context_404_for_unknown(self):
        r = client.get("/api/materials/DOES_NOT_EXIST_XYZ/cutting-context")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# List endpoint
# ---------------------------------------------------------------------------

class TestMaterialsList:
    def test_returns_list(self):
        r = client.get("/api/materials")
        assert isinstance(r.json(), list)

    def test_list_has_records(self):
        r = client.get("/api/materials")
        data = r.json()
        assert len(data) >= 1

    def test_list_items_have_required_fields(self):
        r = client.get("/api/materials")
        for item in r.json():
            for field in ("material_id", "designation", "iso_group", "iso_subgroup",
                          "material_family", "data_confidence"):
                assert field in item, f"Missing field: {field}"

    def test_filter_by_iso_group_p(self):
        r = client.get("/api/materials?iso_group=P")
        for item in r.json():
            assert item["iso_group"] == "P"

    def test_filter_by_iso_group_s(self):
        r = client.get("/api/materials?iso_group=S")
        for item in r.json():
            assert item["iso_group"] == "S"

    def test_filter_by_iso_group_m(self):
        r = client.get("/api/materials?iso_group=M")
        for item in r.json():
            assert item["iso_group"] == "M"

    def test_search_by_name(self):
        r = client.get("/api/materials?search=C45")
        ids = [item["material_id"] for item in r.json()]
        assert "P-C45" in ids

    def test_search_by_aisi(self):
        r = client.get("/api/materials?search=304")
        ids = [item["material_id"] for item in r.json()]
        assert "M-304" in ids

    def test_limit_parameter(self):
        r = client.get("/api/materials?limit=2")
        assert len(r.json()) <= 2

    def test_offset_parameter(self):
        all_items = client.get("/api/materials").json()
        if len(all_items) > 1:
            page2 = client.get(f"/api/materials?limit={len(all_items)}&offset=1").json()
            assert len(page2) == len(all_items) - 1


# ---------------------------------------------------------------------------
# ISO Groups endpoint
# ---------------------------------------------------------------------------

class TestMaterialsIsoGroups:
    def test_returns_list(self):
        r = client.get("/api/materials/iso-groups")
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 6  # P, M, K, N, S, H

    def test_all_codes_present(self):
        r = client.get("/api/materials/iso-groups")
        codes = {g["code"] for g in r.json()}
        for code in ("P", "M", "K", "N", "S", "H"):
            assert code in codes

    def test_each_group_has_label_description_color(self):
        r = client.get("/api/materials/iso-groups")
        for g in r.json():
            assert g.get("label"), f"ISO group {g.get('code')} missing label"
            assert g.get("description"), f"ISO group {g.get('code')} missing description"
            assert g.get("color_hint"), f"ISO group {g.get('code')} missing color_hint"


# ---------------------------------------------------------------------------
# Summary endpoint
# ---------------------------------------------------------------------------

class TestMaterialsSummary:
    def test_returns_summary(self):
        r = client.get("/api/materials/summary")
        data = r.json()
        assert data["material_count"] >= 1
        assert "iso_group_counts" in data
        assert "source_title" in data

    def test_iso_group_counts_correct(self):
        r = client.get("/api/materials/summary")
        data = r.json()
        counts = data["iso_group_counts"]
        for g in ("P", "M", "K", "N", "S"):
            assert g in counts, f"ISO group {g} missing from counts"
            assert counts[g] >= 1


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------

class TestMaterialsSearch:
    def test_search_c45_returns_result(self):
        r = client.get("/api/materials/search?q=C45")
        assert r.status_code == 200
        ids = [item["material_id"] for item in r.json()]
        assert "P-C45" in ids

    def test_search_werkstoff_nr(self):
        r = client.get("/api/materials/search?q=1.7225")
        assert r.status_code == 200
        ids = [item["material_id"] for item in r.json()]
        assert "P-42CrMo4" in ids

    def test_search_inconel(self):
        r = client.get("/api/materials/search?q=Inconel")
        assert r.status_code == 200
        ids = [item["material_id"] for item in r.json()]
        assert "S-IN718" in ids

    def test_search_missing_q_422(self):
        r = client.get("/api/materials/search")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Detail endpoint
# ---------------------------------------------------------------------------

class TestMaterialDetail:
    def test_c45_detail(self):
        r = client.get("/api/materials/P-C45")
        assert r.status_code == 200
        data = r.json()
        assert data["record"]["designation"] == "C45"
        assert data["record"]["iso_group"] == "P"

    def test_304_detail(self):
        r = client.get("/api/materials/M-304")
        assert r.status_code == 200
        data = r.json()
        assert data["record"]["iso_group"] == "M"

    def test_detail_has_conditions(self):
        r = client.get("/api/materials/P-C45")
        data = r.json()
        assert len(data["record"]["conditions"]) >= 1

    def test_detail_has_tool_compat(self):
        r = client.get("/api/materials/P-C45")
        data = r.json()
        assert len(data["record"]["tool_compatibility"]) >= 1

    def test_detail_has_cutting_refs(self):
        r = client.get("/api/materials/P-C45")
        data = r.json()
        assert len(data["record"]["cutting_references"]) >= 1

    def test_detail_has_iso_group_label(self):
        r = client.get("/api/materials/P-C45")
        data = r.json()
        assert "iso_group_label" in data
        assert "P" in data["iso_group_label"]

    def test_ti64_iso_subgroup(self):
        r = client.get("/api/materials/S-Ti64")
        data = r.json()
        assert data["record"]["iso_subgroup"] == "S_TITANIUM"

    def test_in718_iso_subgroup(self):
        r = client.get("/api/materials/S-IN718")
        data = r.json()
        assert data["record"]["iso_subgroup"] == "S_NICKEL_HRSA"


# ---------------------------------------------------------------------------
# Machinability endpoint
# ---------------------------------------------------------------------------

class TestMaterialMachinability:
    def test_c45_machinability(self):
        r = client.get("/api/materials/P-C45/machinability")
        assert r.status_code == 200
        data = r.json()
        assert data["iso_group"] == "P"
        assert "machinability" in data
        assert "tool_compatibility" in data

    def test_machinability_has_evidence_note(self):
        r = client.get("/api/materials/P-C45/machinability")
        data = r.json()
        assert "evidence_note" in data
        assert "REFERENCE_ONLY" in data["evidence_note"]


# ---------------------------------------------------------------------------
# Cutting context endpoint
# ---------------------------------------------------------------------------

class TestMaterialCuttingContext:
    def test_p_c45_cutting_context(self):
        r = client.get("/api/materials/P-C45/cutting-context")
        assert r.status_code == 200
        data = r.json()
        assert "cutting_references" in data
        assert len(data["cutting_references"]) >= 1

    def test_cutting_context_operation_filter(self):
        r = client.get("/api/materials/P-C45/cutting-context?operation=turning")
        data = r.json()
        for ref in data["cutting_references"]:
            assert ref["operation"] == "turning"

    def test_cutting_context_evidence_note(self):
        r = client.get("/api/materials/P-C45/cutting-context")
        data = r.json()
        assert "REFERENCE_ONLY" in data["evidence_note"]

    def test_s_ti64_low_vc(self):
        r = client.get("/api/materials/S-Ti64/cutting-context?operation=turning&tool_material=carbide")
        data = r.json()
        for ref in data["cutting_references"]:
            assert ref["vc_max_m_min"] is None or ref["vc_max_m_min"] <= 100
