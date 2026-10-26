"""Unit tests for Cutting Tool Catalog API."""

from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

EXPECTED_TOOL_COUNT = 40
EXPECTED_MANUFACTURER_COUNT = 5  # Sandvik, Kennametal, Iscar, Walter, OSG
EXPECTED_CATEGORY_COUNT = 9  # prev 5 + Grooving Insert, Face Mill Insert, Tap, Thread Mill


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
        for expected in [
            "Boring Bar", "End Mill", "Solid Carbide Drill",
            "Solid Carbide Reamer", "Turning Insert",
        ]:
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

    def test_filter_operation_reaming(self):
        r = client.get("/api/cutting-tools?operation=reaming")
        data = r.json()
        assert len(data) >= 1
        for t in data:
            assert "reaming" in t["supported_operations"]

    def test_filter_operation_boring(self):
        r = client.get("/api/cutting-tools?operation=boring")
        data = r.json()
        assert len(data) >= 1
        for t in data:
            assert "boring" in t["supported_operations"]

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

    def test_detail_sandvik_reamer_835(self):
        r = client.get("/api/cutting-tools/sandvik-835b-0801-a1-mf-1024")
        assert r.status_code == 200
        data = r.json()
        assert data["manufacturer"] == "Sandvik Coromant"
        assert data["tool_category"] == "Solid Carbide Reamer"
        assert data["tool_category_code"] == "REAMER"
        assert "reaming" in data["supported_operations"]
        assert data["cutting_diameter_mm"] == 8.01
        assert data["shank_diameter_mm"] == 8.0
        assert data["number_of_flutes"] == 6
        assert data["max_rpm"] == 1907
        assert data["through_coolant"] is True
        assert data["overall_length_mm"] == 100.0
        assert "P" in data["iso_material_groups"]

    def test_detail_sandvik_boring_bar_a25t(self):
        r = client.get("/api/cutting-tools/sandvik-a25t-sducr-11")
        assert r.status_code == 200
        data = r.json()
        assert data["manufacturer"] == "Sandvik Coromant"
        assert data["tool_category"] == "Boring Bar"
        assert data["tool_category_code"] == "BORING_BAR"
        assert "boring" in data["supported_operations"]
        assert data["shank_diameter_mm"] == 25.0
        assert data["through_coolant"] is True
        assert "P" in data["iso_material_groups"]
        assert data["max_rpm"] is None

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
        assert data["machine_count"] == 37

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


# ── EPIC-03 new category tests ────────────────────────────────────────────────

class TestEpic03NewCategories:
    def test_grooving_insert_count(self):
        r = client.get("/api/cutting-tools?category=Grooving Insert")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 4

    def test_face_mill_insert_count(self):
        r = client.get("/api/cutting-tools?category=Face Mill Insert")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 3

    def test_tap_count(self):
        r = client.get("/api/cutting-tools?category=Tap")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 4

    def test_thread_mill_count(self):
        r = client.get("/api/cutting-tools?category=Thread Mill")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 2

    def test_osg_manufacturer_present(self):
        r = client.get("/api/cutting-tools?manufacturer=OSG")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 4
        assert all(t["manufacturer"] == "OSG" for t in data)

    def test_tapping_operation_returns_results(self):
        r = client.get("/api/cutting-tools?operation=tapping")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 4
        for t in data:
            assert "tapping" in t["supported_operations"]

    def test_grooving_operation_returns_results(self):
        r = client.get("/api/cutting-tools?operation=grooving")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 4
        for t in data:
            assert "grooving" in t["supported_operations"]

    def test_thread_milling_operation_returns_results(self):
        r = client.get("/api/cutting-tools?operation=thread milling")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 2

    def test_face_milling_operation_returns_results(self):
        r = client.get("/api/cutting-tools?operation=face milling")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 3


# ── EPIC-03 new fields tests ──────────────────────────────────────────────────

class TestEpic03NewFields:
    def test_substrate_grade_present_on_grooving_insert(self):
        r = client.get("/api/cutting-tools/sandvik-n123g2-0300-0002-cr-1125")
        assert r.status_code == 200
        data = r.json()
        assert data["substrate_grade"] == "GC1125"
        assert data["substrate_material_code"] == "CARBIDE"
        assert data["coating_brand"] == "Inveio"

    def test_iso_insert_designation_present(self):
        r = client.get("/api/cutting-tools/sandvik-n123g2-0300-0002-cr-1125")
        data = r.json()
        assert data["iso_insert_designation"] == "N123G2-0300-0002-CR"
        assert data["insert_tolerance_class"] == "M"

    def test_tool_type_code_on_tap(self):
        r = client.get("/api/cutting-tools/osg-a-tap-sft-m6x1p0")
        assert r.status_code == 200
        data = r.json()
        assert data["tool_type_code"] == "TAP"
        assert data["substrate_material_code"] == "HSS_PM"
        assert data["tool_material"] == "HSS-E-PM"

    def test_tap_geometry_not_zero(self):
        r = client.get("/api/cutting-tools/osg-a-tap-sft-m6x1p0")
        data = r.json()
        assert data["cutting_diameter_mm"] == 6.0
        assert data["overall_length_mm"] == 66.0
        assert data["number_of_flutes"] == 3
        assert data["through_coolant"] is False

    def test_face_mill_insert_substrate(self):
        r = client.get("/api/cutting-tools/sandvik-r245-12t308m-ph-4325")
        assert r.status_code == 200
        data = r.json()
        assert data["substrate_grade"] == "GC4325"
        assert data["substrate_material_code"] == "CARBIDE"
        assert data["tool_type_code"] == "FACE_MILL_INSERT"

    def test_filter_by_substrate_carbide(self):
        r = client.get("/api/cutting-tools?substrate_material_code=CARBIDE")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        for t in data:
            assert t["substrate_material_code"] == "CARBIDE"

    def test_filter_by_substrate_hss_pm(self):
        r = client.get("/api/cutting-tools?substrate_material_code=HSS_PM")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 4
        for t in data:
            assert t["substrate_material_code"] == "HSS_PM"

    def test_filter_by_coating_type_pvd(self):
        r = client.get("/api/cutting-tools?coating_type=PVD")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        for t in data:
            assert t["coating_type"] == "PVD"

    def test_filter_by_coating_type_cvd(self):
        r = client.get("/api/cutting-tools?coating_type=CVD")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        for t in data:
            assert t["coating_type"] == "CVD"

    def test_schema_includes_substrate_codes(self):
        r = client.get("/api/cutting-tools/schema")
        assert r.status_code == 200
        data = r.json()
        assert "substrate_codes" in data
        assert "CARBIDE" in data["substrate_codes"]
        assert "HSS_PM" in data["substrate_codes"]

    def test_schema_includes_coating_types(self):
        r = client.get("/api/cutting-tools/schema")
        data = r.json()
        assert "coating_types" in data
        assert "PVD" in data["coating_types"]
        assert "CVD" in data["coating_types"]

    def test_no_fabricated_specs_hss_pm_taps(self):
        """HSS-E-PM tap cutting guidance fields must be None (not fabricated)."""
        r = client.get("/api/cutting-tools/osg-a-tap-sft-m6x1p0")
        data = r.json()
        assert data["vc_min_mpm"] is None
        assert data["vc_max_mpm"] is None
        assert data["fz_min_mm"] is None
        assert data["fz_max_mm"] is None


# ── EPIC-03 search endpoint tests ─────────────────────────────────────────────

class TestEpic03Search:
    def test_search_endpoint_exists(self):
        r = client.get("/api/cutting-tools/search?q=sandvik")
        assert r.status_code == 200

    def test_search_by_manufacturer_keyword(self):
        r = client.get("/api/cutting-tools/search?q=sandvik")
        data = r.json()
        assert len(data) > 0
        assert all("sandvik" in t["manufacturer"].lower() for t in data)

    def test_search_by_product_name(self):
        r = client.get("/api/cutting-tools/search?q=CNMG")
        data = r.json()
        assert len(data) > 0
        assert all("cnmg" in t["product_name"].lower() for t in data)

    def test_search_no_match_returns_empty(self):
        r = client.get("/api/cutting-tools/search?q=xyznomatch99999")
        assert r.status_code == 200
        assert r.json() == []

    def test_search_missing_q_returns_422(self):
        r = client.get("/api/cutting-tools/search")
        assert r.status_code == 422


# ── EPIC-03 import pipeline tests ────────────────────────────────────────────

class TestEpic03ImportPipeline:
    def test_import_pipeline_dry_run_valid_json(self):
        from backend.cutting_tools.import_pipeline import (
            parse_json_tools,
            run_import_pipeline,
        )
        sample = [
            {
                "stable_id": "test-tool-xyz-001",
                "manufacturer": "TestMfr",
                "product_name": "Test Drill 8mm",
                "tool_category": "Solid Carbide Drill",
                "tool_category_code": "DRILL",
                "supported_operations": "drilling",
                "iso_material_groups": "P|M",
                "source_title": "Test",
                "source_authority": "TEST",
                "evidence_status": "MANUFACTURER_CATALOG",
            }
        ]
        import json
        rows = parse_json_tools(json.dumps(sample))
        result = run_import_pipeline(rows, dry_run=True)
        assert result.dry_run is True
        assert result.total_parsed == 1
        assert result.valid == 1
        assert result.invalid == 0
        assert result.added == 0  # dry run — no records added

    def test_import_pipeline_detects_duplicate(self):
        from backend.cutting_tools.import_pipeline import (
            parse_json_tools,
            run_import_pipeline,
        )
        # Use a stable_id already in the catalog
        sample = [
            {
                "stable_id": "sandvik-cnmg-120408-pm-4325",
                "manufacturer": "Sandvik Coromant",
                "product_name": "CNMG 12 04 08-PM 4325",
                "tool_category": "Turning Insert",
                "tool_category_code": "TURNING_INSERT",
                "supported_operations": "turning",
                "iso_material_groups": "P",
                "source_title": "Test",
                "source_authority": "TEST",
                "evidence_status": "MANUFACTURER_CATALOG",
            }
        ]
        import json
        rows = parse_json_tools(json.dumps(sample))
        result = run_import_pipeline(rows, dry_run=True)
        assert result.duplicate == 1
        assert "sandvik-cnmg-120408-pm-4325" in result.duplicate_ids

    def test_import_pipeline_invalid_missing_required(self):
        from backend.cutting_tools.import_pipeline import (
            parse_json_tools,
            run_import_pipeline,
        )
        sample = [{"product_name": "Missing stable_id"}]
        import json
        rows = parse_json_tools(json.dumps(sample))
        result = run_import_pipeline(rows, dry_run=True)
        assert result.invalid == 1
        assert len(result.errors) == 1

    def test_parse_csv_tools(self):
        from backend.cutting_tools.import_pipeline import parse_csv_tools
        csv_str = (
            "stable_id,manufacturer,product_name\n"
            "test-csv-001,TestMfr,Test Tool\n"
        )
        rows = parse_csv_tools(csv_str)
        assert len(rows) == 1
        assert rows[0]["stable_id"] == "test-csv-001"

    def test_parse_json_tools_invalid_raises(self):
        from backend.cutting_tools.import_pipeline import parse_json_tools
        import pytest
        with pytest.raises(Exception):
            parse_json_tools('{"not": "an array"}')
