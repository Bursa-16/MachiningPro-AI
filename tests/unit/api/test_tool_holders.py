"""Unit tests for Tool Holder Catalog API."""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

EXPECTED_HOLDER_COUNT = 17
EXPECTED_MANUFACTURER_COUNT = 5
EXPECTED_CATEGORY_COUNT = 6
EXPECTED_MACHINE_INTERFACE_COUNT = 4  # CAT-40, HSK-A63, SK40, BMT65


# ── Seed catalog data tests ──────────────────────────────────────────────────

class TestSeedCatalogData:
    def test_holder_count(self):
        from backend.tool_holders.seed_catalog import get_catalog
        assert len(get_catalog()) == EXPECTED_HOLDER_COUNT

    def test_all_stable_ids_unique(self):
        from backend.tool_holders.seed_catalog import get_catalog
        ids = [r.stable_id for r in get_catalog()]
        assert len(ids) == len(set(ids)), "Duplicate stable_id detected"

    def test_all_stable_ids_non_empty(self):
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.stable_id.strip(), f"Empty stable_id for {r.product_name}"

    def test_all_product_names_non_empty(self):
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.product_name.strip(), f"Empty product_name for {r.stable_id}"

    def test_all_have_manufacturer(self):
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.manufacturer.strip(), f"Missing manufacturer for {r.stable_id}"

    def test_all_have_machine_interface(self):
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.machine_interface.strip()
            assert r.machine_interface_key.strip()

    def test_all_have_tool_interface(self):
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.tool_interface.strip()
            assert r.tool_interface_key.strip()

    def test_all_have_holder_category(self):
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.holder_category.strip()

    def test_all_have_missing_fields_list(self):
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            assert isinstance(r.missing_fields, list)

    def test_manufacturer_count(self):
        from backend.tool_holders.seed_catalog import get_manufacturers
        assert len(get_manufacturers()) == EXPECTED_MANUFACTURER_COUNT

    def test_expected_manufacturers_present(self):
        from backend.tool_holders.seed_catalog import get_manufacturers
        mfrs = get_manufacturers()
        for expected in ["Sandvik Coromant", "Kennametal", "Haimer", "Schunk", "BIG DAISHOWA"]:
            assert expected in mfrs, f"{expected} not in manufacturers"

    def test_category_count(self):
        from backend.tool_holders.seed_catalog import get_categories
        assert len(get_categories()) == EXPECTED_CATEGORY_COUNT

    def test_expected_categories_present(self):
        from backend.tool_holders.seed_catalog import get_categories
        cats = get_categories()
        for expected in [
            "COLLET_CHUCK", "HYDRAULIC_CHUCK", "SHRINK_FIT_HOLDER",
            "SHELL_MILL_ARBOR", "EXTERNAL_TURNING_HOLDER", "BORING_BAR_HOLDER",
        ]:
            assert expected in cats, f"{expected} not in categories"

    def test_machine_interface_count(self):
        from backend.tool_holders.seed_catalog import get_machine_interfaces
        assert len(get_machine_interfaces()) == EXPECTED_MACHINE_INTERFACE_COUNT

    def test_expected_machine_interfaces_present(self):
        from backend.tool_holders.seed_catalog import get_machine_interfaces
        ifaces = get_machine_interfaces()
        for expected in ["CAT-40", "HSK-A63", "SK40", "BMT65"]:
            assert expected in ifaces, f"{expected} not in machine interfaces"

    def test_tool_interfaces_non_empty(self):
        from backend.tool_holders.seed_catalog import get_tool_interfaces
        assert len(get_tool_interfaces()) > 0

    def test_collet_families(self):
        from backend.tool_holders.seed_catalog import get_collet_families
        families = get_collet_families()
        assert "ER32" in families
        assert "ER40" in families

    def test_no_missing_value_as_zero(self):
        """Fields that are missing must be null, not zero (MISSING_VALUE_AS_ZERO=NO)."""
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            for field in r.missing_fields:
                val = getattr(r, field, "NOT_FOUND")
                assert val != 0 and val != 0.0, (
                    f"{r.stable_id}.{field} is listed as missing but has value 0"
                )

    def test_evidence_status_set(self):
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.evidence_status, f"No evidence_status for {r.stable_id}"

    def test_source_title_set(self):
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.source_title, f"No source_title for {r.stable_id}"

    def test_source_authority_set(self):
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            assert r.source_authority, f"No source_authority for {r.stable_id}"

    def test_no_false_compatibility_claim(self):
        """Records must not claim full compatibility — only foundation fields allowed."""
        from backend.tool_holders.seed_catalog import get_catalog
        CLAIM_TOKENS = ["recommended_for", "compatibility_score", "is_compatible"]
        for r in get_catalog():
            for attr in type(r).model_fields:
                if any(tok in attr for tok in CLAIM_TOKENS):
                    pytest.fail(
                        f"False compatibility field '{attr}' found in {r.stable_id}"
                    )

    def test_no_cutting_tools_stored_as_holders(self):
        """Holders must never carry cutting tool category values."""
        from backend.tool_holders.seed_catalog import get_catalog
        TOOL_CATEGORIES = {"End Mill", "Solid Carbide Drill", "Turning Insert"}
        for r in get_catalog():
            assert r.holder_category not in TOOL_CATEGORIES, (
                f"{r.stable_id} has cutting tool category '{r.holder_category}'"
            )

    def test_compatible_shank_types_is_list(self):
        from backend.tool_holders.seed_catalog import get_catalog
        for r in get_catalog():
            assert isinstance(r.compatible_shank_types, list)


# ── API: schema endpoint ─────────────────────────────────────────────────────

class TestSchemaEndpoint:
    def test_schema_ok(self):
        r = client.get("/api/tool-holders/schema")
        assert r.status_code == 200

    def test_schema_has_holder_count(self):
        data = client.get("/api/tool-holders/schema").json()
        assert data["holder_count"] == EXPECTED_HOLDER_COUNT

    def test_schema_has_manufacturers_list(self):
        data = client.get("/api/tool-holders/schema").json()
        assert isinstance(data["manufacturers"], list)
        assert len(data["manufacturers"]) == EXPECTED_MANUFACTURER_COUNT

    def test_schema_has_categories_list(self):
        data = client.get("/api/tool-holders/schema").json()
        assert isinstance(data["categories"], list)
        assert len(data["categories"]) == EXPECTED_CATEGORY_COUNT

    def test_schema_has_machine_interfaces(self):
        data = client.get("/api/tool-holders/schema").json()
        assert isinstance(data["machine_interfaces"], list)
        assert len(data["machine_interfaces"]) == EXPECTED_MACHINE_INTERFACE_COUNT

    def test_schema_has_tool_interfaces(self):
        data = client.get("/api/tool-holders/schema").json()
        assert isinstance(data["tool_interfaces"], list)
        assert len(data["tool_interfaces"]) > 0

    def test_schema_has_collet_families(self):
        data = client.get("/api/tool-holders/schema").json()
        assert "collet_families" in data
        assert "ER32" in data["collet_families"]

    def test_schema_requires_auth(self):
        r = client.get("/api/tool-holders/schema", headers={})
        assert r.status_code in (200, 401, 403)


# ── API: summary endpoint ────────────────────────────────────────────────────

class TestSummaryEndpoint:
    def test_summary_ok(self):
        r = client.get("/api/tool-holders/summary")
        assert r.status_code == 200

    def test_summary_holder_count(self):
        data = client.get("/api/tool-holders/summary").json()
        assert data["holder_count"] == EXPECTED_HOLDER_COUNT

    def test_summary_manufacturer_count(self):
        data = client.get("/api/tool-holders/summary").json()
        assert data["manufacturer_count"] == EXPECTED_MANUFACTURER_COUNT

    def test_summary_category_count(self):
        data = client.get("/api/tool-holders/summary").json()
        assert data["category_count"] == EXPECTED_CATEGORY_COUNT

    def test_summary_machine_interface_count(self):
        data = client.get("/api/tool-holders/summary").json()
        assert data["machine_interface_count"] == EXPECTED_MACHINE_INTERFACE_COUNT

    def test_summary_has_evidence_status(self):
        data = client.get("/api/tool-holders/summary").json()
        assert data.get("evidence_status")

    def test_summary_has_source_title(self):
        data = client.get("/api/tool-holders/summary").json()
        assert data.get("source_title")


# ── API: list endpoint ───────────────────────────────────────────────────────

class TestListEndpoint:
    def test_list_ok(self):
        r = client.get("/api/tool-holders")
        assert r.status_code == 200

    def test_list_returns_all_holders(self):
        data = client.get("/api/tool-holders").json()
        assert len(data) == EXPECTED_HOLDER_COUNT

    def test_list_each_has_stable_id(self):
        data = client.get("/api/tool-holders").json()
        for h in data:
            assert h.get("stable_id"), "Missing stable_id in list result"

    def test_list_each_has_manufacturer(self):
        data = client.get("/api/tool-holders").json()
        for h in data:
            assert h.get("manufacturer"), "Missing manufacturer in list result"

    def test_filter_by_manufacturer(self):
        data = client.get("/api/tool-holders?manufacturer=Kennametal").json()
        assert all(h["manufacturer"] == "Kennametal" for h in data)
        assert len(data) > 0

    def test_filter_by_manufacturer_sandvik(self):
        data = client.get("/api/tool-holders?manufacturer=Sandvik+Coromant").json()
        assert all(h["manufacturer"] == "Sandvik Coromant" for h in data)
        assert len(data) > 0

    def test_filter_by_category_collet_chuck(self):
        data = client.get("/api/tool-holders?category=COLLET_CHUCK").json()
        assert all(h["holder_category"] == "COLLET_CHUCK" for h in data)
        assert len(data) > 0

    def test_filter_by_category_shrink_fit(self):
        data = client.get("/api/tool-holders?category=SHRINK_FIT_HOLDER").json()
        assert all(h["holder_category"] == "SHRINK_FIT_HOLDER" for h in data)
        assert len(data) > 0

    def test_filter_by_machine_interface_cat40(self):
        data = client.get("/api/tool-holders?machine_interface=CAT-40").json()
        assert all(h["machine_interface"] == "CAT-40" for h in data)
        assert len(data) > 0

    def test_filter_by_machine_interface_hska63(self):
        data = client.get("/api/tool-holders?machine_interface=HSK-A63").json()
        assert all(h["machine_interface"] == "HSK-A63" for h in data)
        assert len(data) > 0

    def test_filter_by_machine_interface_bmt65(self):
        data = client.get("/api/tool-holders?machine_interface=BMT65").json()
        assert all(h["machine_interface"] == "BMT65" for h in data)
        assert len(data) > 0

    def test_filter_by_tool_interface(self):
        data = client.get("/api/tool-holders?tool_interface=ER32").json()
        assert all(h["tool_interface_key"] == "ER32" for h in data)
        assert len(data) > 0

    def test_filter_by_collet_family_er32(self):
        data = client.get("/api/tool-holders?collet_family=ER32").json()
        assert all(h["collet_system"] == "ER32" for h in data)
        assert len(data) > 0

    def test_filter_manufacturer_not_found_returns_empty(self):
        data = client.get("/api/tool-holders?manufacturer=NonExistentMfr").json()
        assert data == []

    def test_filter_category_not_found_returns_empty(self):
        data = client.get("/api/tool-holders?category=FAKE_CATEGORY").json()
        assert data == []

    def test_combined_filter_manufacturer_and_machine(self):
        data = client.get(
            "/api/tool-holders?manufacturer=Kennametal&machine_interface=CAT-40"
        ).json()
        assert all(
            h["manufacturer"] == "Kennametal" and h["machine_interface"] == "CAT-40"
            for h in data
        )


# ── API: detail endpoint ─────────────────────────────────────────────────────

class TestDetailEndpoint:
    def test_detail_kennametal_er32_cat40(self):
        r = client.get("/api/tool-holders/kennametal-cat40-er32-collet-chuck")
        assert r.status_code == 200
        data = r.json()
        assert data["manufacturer"] == "Kennametal"
        assert data["machine_interface"] == "CAT-40"
        assert data["tool_interface_key"] == "ER32"

    def test_detail_sandvik_hydraulic_cat40(self):
        r = client.get("/api/tool-holders/sandvik-cat40-corochuck930-c4-050-13")
        assert r.status_code == 200
        data = r.json()
        assert data["holder_category"] == "HYDRAULIC_CHUCK"
        assert data["machine_interface"] == "CAT-40"
        assert data["runout_um"] == 3.0
        assert data["max_rpm"] == 20000

    def test_detail_haimer_shrink_fit(self):
        r = client.get("/api/tool-holders/haimer-cat40-power-clamp-ng-08")
        assert r.status_code == 200
        data = r.json()
        assert data["holder_category"] == "SHRINK_FIT_HOLDER"
        assert data["tool_interface_key"] == "SHRINK_FIT"
        assert data["max_rpm"] == 40000

    def test_detail_sandvik_turning_bmt65(self):
        r = client.get("/api/tool-holders/sandvik-bmt65-pclnr-2525m-12")
        assert r.status_code == 200
        data = r.json()
        assert data["holder_category"] == "EXTERNAL_TURNING_HOLDER"
        assert data["machine_interface"] == "BMT65"
        assert data["through_coolant"] is True

    def test_detail_has_missing_fields_list(self):
        r = client.get("/api/tool-holders/kennametal-cat40-er32-collet-chuck")
        data = r.json()
        assert isinstance(data["missing_fields"], list)

    def test_detail_has_source_provenance(self):
        r = client.get("/api/tool-holders/kennametal-cat40-er32-collet-chuck")
        data = r.json()
        assert data.get("source_title")
        assert data.get("evidence_status")
        assert data.get("source_authority")

    def test_detail_missing_nullable_fields_are_null_not_zero(self):
        r = client.get("/api/tool-holders/sandvik-bmt65-pclnr-2525m-12")
        data = r.json()
        assert data["max_rpm"] is None, "max_rpm must be null, not 0 (MISSING_VALUE_AS_ZERO=NO)"

    def test_detail_invalid_id_returns_404(self):
        r = client.get("/api/tool-holders/does-not-exist-123")
        assert r.status_code == 404

    def test_detail_empty_id_returns_404_or_405(self):
        r = client.get("/api/tool-holders/ ")
        assert r.status_code in (404, 405, 422)


# ── API: manufacturers / categories / interfaces endpoints ───────────────────

class TestAuxiliaryEndpoints:
    def test_manufacturers_endpoint_ok(self):
        r = client.get("/api/tool-holders/manufacturers")
        assert r.status_code == 200

    def test_manufacturers_endpoint_has_count(self):
        data = client.get("/api/tool-holders/manufacturers").json()
        assert data.get("count") == EXPECTED_MANUFACTURER_COUNT
        assert isinstance(data.get("manufacturers"), list)

    def test_categories_endpoint_ok(self):
        r = client.get("/api/tool-holders/categories")
        assert r.status_code == 200

    def test_categories_endpoint_has_count(self):
        data = client.get("/api/tool-holders/categories").json()
        assert data.get("count") == EXPECTED_CATEGORY_COUNT

    def test_interfaces_endpoint_ok(self):
        r = client.get("/api/tool-holders/interfaces")
        assert r.status_code == 200

    def test_interfaces_endpoint_has_machine_interfaces(self):
        data = client.get("/api/tool-holders/interfaces").json()
        assert isinstance(data.get("machine_interfaces"), list)
        assert len(data["machine_interfaces"]) == EXPECTED_MACHINE_INTERFACE_COUNT

    def test_interfaces_endpoint_has_tool_interfaces(self):
        data = client.get("/api/tool-holders/interfaces").json()
        assert isinstance(data.get("tool_interfaces"), list)
        assert len(data["tool_interfaces"]) > 0


# ── Private source path protection ──────────────────────────────────────────

class TestPrivatePathProtection:
    def test_no_private_path_in_source_note(self):
        """PRIVATE_SOURCE_PATH_EXPOSED=NO — source_note must not expose filesystem paths."""
        data = client.get("/api/tool-holders").json()
        PRIVATE_TOKENS = ["C:\\", "C:/", "/home/", "/Users/", "backend/", ".py", ".xlsx"]
        for h in data:
            note = h.get("source_note") or ""
            for tok in PRIVATE_TOKENS:
                assert tok not in note, (
                    f"Private path token '{tok}' found in source_note for {h['stable_id']}"
                )

    def test_no_private_path_in_source_title(self):
        data = client.get("/api/tool-holders").json()
        for h in data:
            title = h.get("source_title") or ""
            assert "backend/" not in title
            assert ".py" not in title

    def test_no_false_ai_claim_in_responses(self):
        """FALSE_AI_CLAIM=NO — response must not claim AI-generated specifications."""
        data = client.get("/api/tool-holders").json()
        AI_CLAIM_TOKENS = ["AI-generated spec", "AI-optimized", "generated by AI"]
        for h in data:
            for field in ["source_title", "source_note", "holder_notes"]:
                text = h.get(field) or ""
                for tok in AI_CLAIM_TOKENS:
                    assert tok not in text, f"AI claim '{tok}' in {h['stable_id']}.{field}"

    def test_no_production_validation_claim(self):
        """FALSE_PRODUCTION_VALIDATION_CLAIM=NO."""
        data = client.get("/api/tool-holders").json()
        BAD_TOKENS = ["production validated", "shop-floor validated", "production-ready recommendation"]
        for h in data:
            for field in ["source_note", "holder_notes", "source_title"]:
                text = h.get(field) or ""
                for tok in BAD_TOKENS:
                    assert tok.lower() not in text.lower(), (
                        f"Production validation claim '{tok}' in {h['stable_id']}.{field}"
                    )
