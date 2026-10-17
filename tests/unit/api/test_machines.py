"""
Tests for GET /api/machines/* endpoints (MACHINE_CATALOG_DATA_INTEGRATION_01).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.machines.seed_catalog import MACHINE_CATALOG_RECORDS, seed_machine_catalog

client = TestClient(app)

# ---------------------------------------------------------------------------
# Seed data contract
# ---------------------------------------------------------------------------

class TestSeedCatalogData:
    def test_record_count_positive(self):
        records = seed_machine_catalog()
        assert len(records) >= 1

    def test_stable_ids_unique(self):
        records = seed_machine_catalog()
        ids = [r["stable_id"] for r in records]
        assert len(ids) == len(set(ids)), "Duplicate stable_id detected"

    def test_no_zero_for_missing_numeric(self):
        """MISSING_VALUE_AS_ZERO=NO — numeric fields must be None not 0.0 when missing."""
        nullable_numeric = [
            "spindle_max_rpm", "spindle_power_kw", "spindle_torque_nm",
            "travel_x_mm", "travel_y_mm", "travel_z_mm",
            "table_length_mm", "table_width_mm", "table_load_kg",
            "max_turning_diameter_mm", "max_turning_length_mm",
            "bar_capacity_mm", "machine_weight_kg",
        ]
        for rec in seed_machine_catalog():
            for field in nullable_numeric:
                val = rec.get(field)
                assert val != 0.0, (
                    f"Record '{rec['stable_id']}' has {field}=0.0 — "
                    "use None for unknown values"
                )

    def test_mandatory_identity_fields_present(self):
        for rec in seed_machine_catalog():
            for field in ("stable_id", "manufacturer", "model", "machine_type", "machine_type_code"):
                assert rec.get(field), f"Record missing {field}: {rec}"

    def test_supported_processes_non_empty(self):
        for rec in seed_machine_catalog():
            assert len(rec["supported_processes"]) >= 1, (
                f"Record '{rec['stable_id']}' has no supported_processes"
            )

    def test_multiple_manufacturers_present(self):
        manufacturers = {r["manufacturer"] for r in seed_machine_catalog()}
        assert len(manufacturers) >= 2

    def test_multiple_machine_types_present(self):
        types = {r["machine_type"] for r in seed_machine_catalog()}
        assert len(types) >= 2

    def test_missing_fields_list_populated(self):
        for rec in seed_machine_catalog():
            assert isinstance(rec["missing_fields"], list)

    def test_source_title_non_empty(self):
        for rec in seed_machine_catalog():
            assert rec["source_title"], f"Empty source_title in {rec['stable_id']}"

    def test_evidence_status_is_manufacturer_datasheet(self):
        for rec in seed_machine_catalog():
            assert rec["evidence_status"] == "MANUFACTURER_DATASHEET"

    def test_no_private_path_in_source(self):
        """PRIVATE_SOURCE_PATH_EXPOSED=NO."""
        import re
        path_pattern = re.compile(r"[A-Za-z]:\\|/home/|/Users/|C:/")
        for rec in seed_machine_catalog():
            src = rec.get("source_title", "") + rec.get("source_note", "")
            assert not path_pattern.search(src), (
                f"Private path detected in source for '{rec['stable_id']}'"
            )

    def test_idempotent_reseed(self):
        """INGESTION_IDEMPOTENT=YES — two calls return same count, no accumulation."""
        r1 = seed_machine_catalog()
        r2 = seed_machine_catalog()
        assert len(r1) == len(r2)
        ids1 = {r["stable_id"] for r in r1}
        ids2 = {r["stable_id"] for r in r2}
        assert ids1 == ids2


# ---------------------------------------------------------------------------
# API — /api/machines/schema
# ---------------------------------------------------------------------------

class TestMachinesSchema:
    def test_schema_ok(self):
        r = client.get("/api/machines/schema")
        assert r.status_code == 200

    def test_schema_has_manufacturers(self):
        r = client.get("/api/machines/schema")
        data = r.json()
        assert "manufacturers" in data
        assert len(data["manufacturers"]) >= 1

    def test_schema_has_machine_types(self):
        r = client.get("/api/machines/schema")
        data = r.json()
        assert "machine_types" in data
        assert len(data["machine_types"]) >= 1

    def test_schema_has_processes(self):
        r = client.get("/api/machines/schema")
        data = r.json()
        assert "processes" in data
        assert len(data["processes"]) >= 1

    def test_schema_machine_count_positive(self):
        r = client.get("/api/machines/schema")
        assert r.json()["machine_count"] >= 1


# ---------------------------------------------------------------------------
# API — /api/machines/summary
# ---------------------------------------------------------------------------

class TestMachinesSummary:
    def test_summary_ok(self):
        r = client.get("/api/machines/summary")
        assert r.status_code == 200

    def test_summary_machine_count(self):
        r = client.get("/api/machines/summary")
        data = r.json()
        assert data["machine_count"] >= 1

    def test_summary_manufacturer_count(self):
        r = client.get("/api/machines/summary")
        data = r.json()
        assert data["manufacturer_count"] >= 2

    def test_summary_machine_type_count(self):
        r = client.get("/api/machines/summary")
        data = r.json()
        assert data["machine_type_count"] >= 2

    def test_summary_evidence_status(self):
        r = client.get("/api/machines/summary")
        data = r.json()
        assert data["evidence_status"] == "MANUFACTURER_DATASHEET"


# ---------------------------------------------------------------------------
# API — /api/machines/manufacturers
# ---------------------------------------------------------------------------

class TestMachinesManufacturers:
    def test_manufacturers_ok(self):
        r = client.get("/api/machines/manufacturers")
        assert r.status_code == 200

    def test_manufacturers_list_non_empty(self):
        r = client.get("/api/machines/manufacturers")
        data = r.json()
        assert len(data["manufacturers"]) >= 1


# ---------------------------------------------------------------------------
# API — /api/machines (list + filters)
# ---------------------------------------------------------------------------

class TestMachinesList:
    def test_list_ok(self):
        r = client.get("/api/machines")
        assert r.status_code == 200

    def test_list_returns_array(self):
        r = client.get("/api/machines")
        assert isinstance(r.json(), list)

    def test_list_all_have_stable_id(self):
        r = client.get("/api/machines")
        for m in r.json():
            assert m["stable_id"]

    def test_list_no_fabricated_ai_claim(self):
        """FALSE_AI_CLAIM=NO — no AI recommendation language in responses."""
        r = client.get("/api/machines")
        text = str(r.json()).lower()
        forbidden = ["ai recommended", "best machine", "optimal machine", "ai suggestion"]
        for phrase in forbidden:
            assert phrase not in text, f"Forbidden phrase '{phrase}' found in list response"

    def test_filter_by_manufacturer(self):
        r = client.get("/api/machines?manufacturer=Haas+Automation")
        data = r.json()
        assert all(m["manufacturer"] == "Haas Automation" for m in data)
        assert len(data) >= 1

    def test_filter_by_manufacturer_case_insensitive(self):
        r = client.get("/api/machines?manufacturer=haas+automation")
        assert r.status_code == 200
        data = r.json()
        assert all(m["manufacturer"] == "Haas Automation" for m in data)

    def test_filter_by_machine_type_lathe(self):
        r = client.get("/api/machines?machine_type=CNC+Lathe")
        data = r.json()
        assert len(data) >= 1
        assert all(m["machine_type"] == "CNC Lathe" for m in data)

    def test_filter_by_machine_type_vmc(self):
        r = client.get("/api/machines?machine_type=Vertical+Machining+Center")
        data = r.json()
        assert len(data) >= 1

    def test_filter_by_process_milling(self):
        r = client.get("/api/machines?process=milling")
        data = r.json()
        assert len(data) >= 1
        assert all("milling" in m["supported_processes"] for m in data)

    def test_filter_by_axis_count(self):
        r = client.get("/api/machines?axis_count=5")
        data = r.json()
        assert len(data) >= 1
        assert all(m["axis_count"] == 5 for m in data)

    def test_filter_no_match_returns_empty(self):
        r = client.get("/api/machines?manufacturer=NonexistentBrand9999")
        assert r.status_code == 200
        assert r.json() == []

    def test_filter_combined(self):
        r = client.get("/api/machines?manufacturer=Haas+Automation&machine_type=CNC+Lathe")
        data = r.json()
        assert all(
            m["manufacturer"] == "Haas Automation" and m["machine_type"] == "CNC Lathe"
            for m in data
        )


# ---------------------------------------------------------------------------
# API — /api/machines/{machine_id}
# ---------------------------------------------------------------------------

class TestMachineDetail:
    def test_detail_valid_id(self):
        r = client.get("/api/machines/haas-vf-2ss")
        assert r.status_code == 200

    def test_detail_correct_fields(self):
        r = client.get("/api/machines/haas-vf-2ss")
        data = r.json()
        assert data["stable_id"] == "haas-vf-2ss"
        assert data["manufacturer"] == "Haas Automation"
        assert data["model"] == "VF-2 SS"
        assert data["machine_type"] == "Vertical Machining Center"

    def test_detail_spindle_rpm_positive(self):
        r = client.get("/api/machines/haas-vf-2ss")
        data = r.json()
        assert data["spindle_max_rpm"] > 0

    def test_detail_has_supported_processes(self):
        r = client.get("/api/machines/haas-vf-2ss")
        data = r.json()
        assert len(data["supported_processes"]) >= 1

    def test_detail_has_evidence(self):
        r = client.get("/api/machines/haas-vf-2ss")
        data = r.json()
        assert data["evidence_status"] == "MANUFACTURER_DATASHEET"
        assert data["source_title"]

    def test_detail_has_missing_fields_list(self):
        r = client.get("/api/machines/haas-vf-2ss")
        data = r.json()
        assert isinstance(data["missing_fields"], list)

    def test_detail_invalid_id_404(self):
        r = client.get("/api/machines/nonexistent-machine-xyz")
        assert r.status_code == 404

    def test_detail_no_private_path(self):
        """PRIVATE_PATH_IN_API_RESPONSE=NO."""
        import re
        path_pattern = re.compile(r"[A-Za-z]:\\|/home/|/Users/")
        for sid in ["haas-vf-2ss", "dmg-dmu-50-3g", "mazak-integrex-i200"]:
            r = client.get(f"/api/machines/{sid}")
            assert not path_pattern.search(str(r.json())), (
                f"Private path found in response for {sid}"
            )

    def test_detail_no_false_ai_claim(self):
        """FALSE_AI_CLAIM=NO."""
        r = client.get("/api/machines/haas-vf-2ss")
        text = str(r.json()).lower()
        for phrase in ["ai recommended", "best machine", "optimal"]:
            assert phrase not in text

    def test_detail_lathe_has_turning_capable(self):
        r = client.get("/api/machines/haas-st-20")
        data = r.json()
        assert data["turning_capable"] is True

    def test_detail_vmc_milling_capable(self):
        r = client.get("/api/machines/haas-vf-2ss")
        data = r.json()
        assert data["milling_capable"] is True

    def test_detail_5axis_simultaneous(self):
        r = client.get("/api/machines/haas-umc-750")
        data = r.json()
        assert data["axis_count"] == 5
        assert data["simultaneous_axis_count"] == 5

    def test_detail_mill_turn_both_capable(self):
        r = client.get("/api/machines/mazak-integrex-i200")
        data = r.json()
        assert data["turning_capable"] is True
        assert data["milling_capable"] is True
