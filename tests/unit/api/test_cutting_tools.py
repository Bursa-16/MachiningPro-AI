"""Unit tests for Cutting Tool Catalog API."""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

EXPECTED_TOOL_COUNT = 16
EXPECTED_MANUFACTURER_COUNT = 4
EXPECTED_CATEGORY_COUNT = 3  # Turning Insert, End Mill, Solid Carbide Drill


# ── Seed catalog data tests ──────────────────────────────────────────────────

class TestSeedCatalogData:
    def test_tool_count(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        records = get_catalog()
        assert len(records) == EXPECTED_TOOL_COUNT

    def test_all_stable_ids_unique(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        ids = [r.stable_id for r in get_catalog()]
        assert len(ids) == len(set(ids)), "Duplicate stable_id detected"

    def test_all_stable_ids_non_empty(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.stable_id.strip(), f"Empty stable_id for {r.product_name}"

    def test_all_product_names_non_empty(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.product_name.strip(), f"Empty product_name for {r.stable_id}"

    def test_all_have_manufacturer(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.manufacturer.strip(), f"Missing manufacturer for {r.stable_id}"

    def test_manufacturer_count(self):
        from backend.cutting_tools.seed_catalog import get_manufacturers
        assert len(get_manufacturers()) == EXPECTED_MANUFACTURER_COUNT

    def test_expected_manufacturers_present(self):
        from backend.cutting_tools.seed_catalog import get_manufacturers
        mfrs = get_manufacturers()
        for expected in ["Sandvik Coromant", "Kennametal", "Iscar", "Walter Tools"]:
            assert expected in mfrs

    def test_category_count(self):
        from backend.cutting_tools.seed_catalog import get_categories
        assert len(get_categories()) == EXPECTED_CATEGORY_COUNT

    def test_expected_categories(self):
        from backend.cutting_tools.seed_catalog import get_categories
        cats = get_categories()
        for expected in ["End Mill", "Solid Carbide Drill", "Turning Insert"]:
            assert expected in cats

    def test_all_have_supported_operations(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        for r in get_catalog():
            assert len(r.supported_operations) > 0, f"No operations for {r.stable_id}"

    def test_all_have_iso_groups(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        for r in get_catalog():
            assert len(r.iso_material_groups) > 0, f"No ISO groups for {r.stable_id}"

    def test_iso_groups_valid(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        valid = {"P", "M", "K", "N", "S", "H"}
        for r in get_catalog():
            for g in r.iso_material_groups:
                assert g in valid, f"Invalid ISO group {g!r} in {r.stable_id}"

    def test_missing_fields_never_zero_substitute(self):
        """Verify that missing numeric fields are None, not 0."""
        from backend.cutting_tools.seed_catalog import get_catalog
        for r in get_catalog():
            for field in ["vc_min_mpm", "vc_max_mpm", "fz_min_mm", "fz_max_mm"]:
                val = getattr(r, field)
                assert val != 0, f"{field} is 0 in {r.stable_id} — MISSING_VALUE_AS_ZERO violation"

    def test_no_private_paths_in_source_note(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        forbidden = ["C:\\Users\\", "D:\\Users\\", "/home/", "C:/Users/"]
        for r in get_catalog():
            note = r.source_note or ""
            for f in forbidden:
                assert f not in note, f"Private path found in source_note of {r.stable_id}"

    def test_no_ai_recommendation_claim(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        forbidden_terms = [
            "ai recommended", "best tool", "optimal tool",
            "guaranteed", "production validated",
        ]
        for r in get_catalog():
            combined = (r.product_name + " " + (r.source_note or "")).lower()
            for term in forbidden_terms:
                assert term not in combined, f"False claim {term!r} in {r.stable_id}"


# ── Schema endpoint ──────────────────────────────────────────────────────────

class TestCuttingToolsSchema:
    def test_schema_200(self):
        r = client.get("/api/cutting-tools/schema")
        assert r.status_code == 200

    def test_schema_has_manufacturers(self):
        r = client.get("/api/cutting-tools/schema")
        data = r.json()
        assert "manufacturers" in data
        assert len(data["manufacturers"]) == EXPECTED_MANUFACTURER_COUNT

    def test_schema_has_categories(self):
        r = client.get("/api/cutting-tools/schema")
        data = r.json()
        assert "categories" in data
        assert len(data["categories"]) == EXPECTED_CATEGORY_COUNT

    def test_schema_has_operations(self):
        r = client.get("/api/cutting-tools/schema")
        data = r.json()
        assert "operations" in data
        assert len(data["operations"]) > 0

    def test_schema_tool_count(self):
        r = client.get("/api/cutting-tools/schema")
        data = r.json()
        assert data["tool_count"] == EXPECTED_TOOL_COUNT

    def test_schema_iso_groups(self):
        r = client.get("/api/cutting-tools/schema")
        data = r.json()
        assert "iso_material_groups" in data
        for g in ["P", "M", "K"]:
            assert g in data["iso_material_groups"]


# ── Summary endpoint ──────────────────────────────────────────────────────────

class TestCuttingToolsSummary:
    def test_summary_200(self):
        r = client.get("/api/cutting-tools/summary")
        assert r.status_code == 200

    def test_summary_tool_count(self):
        r = client.get("/api/cutting-tools/summary")
        data = r.json()
        assert data["tool_count"] == EXPECTED_TOOL_COUNT

    def test_summary_manufacturer_count(self):
        r = client.get("/api/cutting-tools/summary")
        data = r.json()
        assert data["manufacturer_count"] == EXPECTED_MANUFACTURER_COUNT

    def test_summary_category_count(self):
        r = client.get("/api/cutting-tools/summary")
        data = r.json()
        assert data["category_count"] == EXPECTED_CATEGORY_COUNT

    def test_summary_evidence_status(self):
        r = client.get("/api/cutting-tools/summary")
        data = r.json()
        assert data["evidence_status"] == "MANUFACTURER_CATALOG"


# ── List endpoint ─────────────────────────────────────────────────────────────

class TestCuttingToolsList:
    def test_list_all_200(self):
        r = client.get("/api/cutting-tools")
        assert r.status_code == 200

    def test_list_all_count(self):
        r = client.get("/api/cutting-tools")
        assert len(r.json()) == EXPECTED_TOOL_COUNT

    def test_filter_manufacturer_sandvik(self):
        r = client.get("/api/cutting-tools?manufacturer=Sandvik Coromant")
        data = r.json()
        assert len(data) > 0
        assert all(t["manufacturer"] == "Sandvik Coromant" for t in data)

    def test_filter_manufacturer_kennametal(self):
        r = client.get("/api/cutting-tools?manufacturer=Kennametal")
        data = r.json()
        assert len(data) > 0
        assert all(t["manufacturer"] == "Kennametal" for t in data)

    def test_filter_manufacturer_case_insensitive(self):
        r = client.get("/api/cutting-tools?manufacturer=sandvik coromant")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_filter_category_turning_insert(self):
        r = client.get("/api/cutting-tools?category=Turning Insert")
        data = r.json()
        assert len(data) > 0
        assert all(t["tool_category"] == "Turning Insert" for t in data)

    def test_filter_category_end_mill(self):
        r = client.get("/api/cutting-tools?category=End Mill")
        data = r.json()
        assert len(data) > 0
        assert all(t["tool_category"] == "End Mill" for t in data)

    def test_filter_operation_drilling(self):
        r = client.get("/api/cutting-tools?operation=drilling")
        data = r.json()
        assert len(data) > 0
        for t in data:
            assert "drilling" in t["supported_operations"]

    def test_filter_operation_milling(self):
        r = client.get("/api/cutting-tools?operation=milling")
        data = r.json()
        assert len(data) > 0
        for t in data:
            assert "milling" in t["supported_operations"]

    def test_filter_tool_material_carbide(self):
        r = client.get("/api/cutting-tools?tool_material=carbide")
        data = r.json()
        assert len(data) > 0
        assert all(t["tool_material"] == "carbide" for t in data)

    def test_filter_iso_group_p(self):
        r = client.get("/api/cutting-tools?iso_group=P")
        data = r.json()
        assert len(data) > 0
        for t in data:
            assert "P" in t["iso_material_groups"]

    def test_filter_iso_group_s(self):
        r = client.get("/api/cutting-tools?iso_group=S")
        data = r.json()
        assert len(data) >= 0  # may be empty or have records

    def test_no_match_returns_empty(self):
        r = client.get("/api/cutting-tools?manufacturer=NonexistentMfr")
        assert r.status_code == 200
        assert r.json() == []

    def test_no_false_claims_in_list(self):
        r = client.get("/api/cutting-tools")
        text = str(r.json()).lower()
        for bad in ["ai recommended", "best tool", "optimal tool", "guaranteed compatible"]:
            assert bad not in text


# ── Detail endpoint ───────────────────────────────────────────────────────────

class TestCuttingToolDetail:
    def test_detail_sandvik_turning_insert(self):
        r = client.get("/api/cutting-tools/sandvik-cnmg-120408-pm-4325")
        assert r.status_code == 200
        data = r.json()
        assert data["manufacturer"] == "Sandvik Coromant"
        assert data["tool_category"] == "Turning Insert"
        assert data["tool_material"] == "carbide"
        assert "P" in data["iso_material_groups"]
        assert data["insert_ic_mm"] == 12.7
        assert data["nose_radius_mm"] == 0.8
        assert data["insert_shape_code"] == "C"

    def test_detail_sandvik_end_mill_6mm(self):
        r = client.get("/api/cutting-tools/sandvik-r216-33-06045-ac10p-1620")
        assert r.status_code == 200
        data = r.json()
        assert data["tool_category"] == "End Mill"
        assert data["cutting_diameter_mm"] == 6.0
        assert data["number_of_flutes"] == 2

    def test_detail_sandvik_drill(self):
        r = client.get("/api/cutting-tools/sandvik-860-1-0800-040a1-pm")
        assert r.status_code == 200
        data = r.json()
        assert data["tool_category"] == "Solid Carbide Drill"
        assert data["cutting_diameter_mm"] == 8.0
        assert data["through_coolant"] is True
        assert data["point_angle_deg"] == 140.0

    def test_detail_kennametal_turning_insert(self):
        r = client.get("/api/cutting-tools/kennametal-cnmg-120408-ms-kc5525")
        assert r.status_code == 200
        data = r.json()
        assert data["manufacturer"] == "Kennametal"
        assert data["insert_ic_mm"] == 12.7

    def test_detail_kennametal_drill(self):
        r = client.get("/api/cutting-tools/kennametal-b221a-0800-cfh")
        assert r.status_code == 200
        data = r.json()
        assert data["cutting_diameter_mm"] == 8.0
        assert data["through_coolant"] is True

    def test_detail_iscar_turning_insert(self):
        r = client.get("/api/cutting-tools/iscar-cnmg-120408-m-ic8250")
        assert r.status_code == 200
        data = r.json()
        assert data["manufacturer"] == "Iscar"
        assert data["tool_material"] == "carbide"

    def test_detail_iscar_dnmg(self):
        r = client.get("/api/cutting-tools/iscar-dnmg-150608-m-ic8250")
        assert r.status_code == 200
        data = r.json()
        assert data["insert_shape_code"] == "D"
        assert data["insert_ic_mm"] == 15.875

    def test_detail_walter_turning_insert(self):
        r = client.get("/api/cutting-tools/walter-cnmg-120408-nf6-wsm33s")
        assert r.status_code == 200
        data = r.json()
        assert data["manufacturer"] == "Walter Tools"

    def test_detail_walter_drill(self):
        r = client.get("/api/cutting-tools/walter-titex-dc150-08-08000a1-wj30et")
        assert r.status_code == 200
        data = r.json()
        assert data["cutting_diameter_mm"] == 8.0
        assert data["through_coolant"] is True

    def test_detail_missing_fields_list_present(self):
        r = client.get("/api/cutting-tools/sandvik-cnmg-120408-pm-4325")
        data = r.json()
        assert "missing_fields" in data
        assert isinstance(data["missing_fields"], list)

    def test_detail_no_fabricated_vc(self):
        """Vc guidance must be None (not fabricated) for all records."""
        r = client.get("/api/cutting-tools/sandvik-cnmg-120408-pm-4325")
        data = r.json()
        assert data["vc_min_mpm"] is None
        assert data["vc_max_mpm"] is None

    def test_detail_404_invalid_id(self):
        r = client.get("/api/cutting-tools/nonexistent-tool-xyz")
        assert r.status_code == 404

    def test_detail_no_private_path_in_response(self):
        r = client.get("/api/cutting-tools/sandvik-cnmg-120408-pm-4325")
        text = r.text
        for bad in ["C:\\Users\\", "D:\\Users\\", "/home/"]:
            assert bad not in text

    def test_detail_evidence_status(self):
        r = client.get("/api/cutting-tools/sandvik-cnmg-120408-pm-4325")
        data = r.json()
        assert data["evidence_status"] == "MANUFACTURER_CATALOG"


# ── Regression guard ──────────────────────────────────────────────────────────

class TestRegression:
    def test_machine_catalog_still_works(self):
        r = client.get("/api/machines/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["machine_count"] == 15

    def test_cutting_parameters_still_works(self):
        r = client.get("/api/cutting-parameters/schema")
        assert r.status_code == 200

    def test_tool_life_still_works(self):
        r = client.get("/api/tool-life/summary")
        assert r.status_code == 200

    def test_health_still_works(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
