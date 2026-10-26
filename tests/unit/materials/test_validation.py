"""Tests for material catalog validation rules (EPIC_01)."""

from __future__ import annotations

import pytest

from backend.materials.validation import validate_material_record, validate_no_fabrication, ValidationIssue


def _valid_record() -> dict:
    return {
        "material_id": "P-TEST",
        "designation": "TestSteel",
        "iso_group": "P",
        "iso_subgroup": "P_STEEL",
        "material_family": "steel",
        "conditions": [],
        "cutting_references": [],
    }


class TestValidateMaterialRecord:
    def test_valid_record_no_issues(self):
        issues = validate_material_record(_valid_record())
        assert issues == []

    def test_missing_material_id(self):
        rec = _valid_record()
        rec["material_id"] = ""
        issues = validate_material_record(rec)
        codes = [i.code for i in issues]
        assert "REQUIRED_FIELD_MISSING" in codes

    def test_missing_iso_group(self):
        rec = _valid_record()
        rec["iso_group"] = ""
        issues = validate_material_record(rec)
        codes = [i.code for i in issues]
        assert "REQUIRED_FIELD_MISSING" in codes

    def test_invalid_iso_group(self):
        rec = _valid_record()
        rec["iso_group"] = "X"
        issues = validate_material_record(rec)
        codes = [i.code for i in issues]
        assert "INVALID_ISO_GROUP" in codes

    def test_s_group_undifferentiated_subgroup(self):
        rec = _valid_record()
        rec["iso_group"] = "S"
        rec["iso_subgroup"] = "UNSPECIFIED"
        issues = validate_material_record(rec)
        codes = [i.code for i in issues]
        assert "S_GROUP_NOT_DIFFERENTIATED" in codes

    def test_s_titanium_accepted(self):
        rec = _valid_record()
        rec["iso_group"] = "S"
        rec["iso_subgroup"] = "S_TITANIUM"
        issues = validate_material_record(rec)
        s_issues = [i for i in issues if i.code == "S_GROUP_NOT_DIFFERENTIATED"]
        assert s_issues == []

    def test_s_nickel_accepted(self):
        rec = _valid_record()
        rec["iso_group"] = "S"
        rec["iso_subgroup"] = "S_NICKEL_HRSA"
        issues = validate_material_record(rec)
        s_issues = [i for i in issues if i.code == "S_GROUP_NOT_DIFFERENTIATED"]
        assert s_issues == []

    def test_zero_density_rejected(self):
        rec = _valid_record()
        rec["density_kg_m3"] = 0.0
        issues = validate_material_record(rec)
        codes = [i.code for i in issues]
        assert "ZERO_FOR_MISSING" in codes

    def test_invalid_hardness_scale(self):
        rec = _valid_record()
        rec["conditions"] = [{
            "condition_code": "ANNEALED",
            "condition_label": "Annealed",
            "hardness": [{"scale": "ROCKWELL", "value_min": 60, "value_max": 70,
                          "confidence": "X", "source": ""}],
        }]
        issues = validate_material_record(rec)
        codes = [i.code for i in issues]
        assert "INVALID_HARDNESS_SCALE" in codes

    def test_inverted_hardness_range(self):
        rec = _valid_record()
        rec["conditions"] = [{
            "condition_code": "A",
            "condition_label": "A",
            "hardness": [{"scale": "HB", "value_min": 200, "value_max": 100,
                          "confidence": "X", "source": ""}],
        }]
        issues = validate_material_record(rec)
        codes = [i.code for i in issues]
        assert "HARDNESS_RANGE_INVERTED" in codes

    def test_non_positive_vc_rejected(self):
        rec = _valid_record()
        rec["cutting_references"] = [{
            "operation": "turning",
            "tool_material": "carbide",
            "vc_min_m_min": -50.0,
            "vc_max_m_min": 100.0,
        }]
        issues = validate_material_record(rec)
        codes = [i.code for i in issues]
        assert "NON_POSITIVE_VC" in codes


class TestValidateNoFabrication:
    def test_clean_record(self):
        issues = validate_no_fabrication({"density_kg_m3": 7850.0, "conditions": []})
        assert issues == []

    def test_implausible_tensile(self):
        rec = {"conditions": [{"tensile_strength_mpa": 5000}]}
        issues = validate_no_fabrication(rec)
        codes = [i.code for i in issues]
        assert "IMPLAUSIBLE_VALUE" in codes

    def test_implausible_density_low(self):
        rec = {"density_kg_m3": 100.0, "conditions": []}
        issues = validate_no_fabrication(rec)
        codes = [i.code for i in issues]
        assert "IMPLAUSIBLE_VALUE" in codes

    def test_implausible_density_high(self):
        rec = {"density_kg_m3": 30000.0, "conditions": []}
        issues = validate_no_fabrication(rec)
        codes = [i.code for i in issues]
        assert "IMPLAUSIBLE_VALUE" in codes

    def test_plausible_inconel_density(self):
        rec = {"density_kg_m3": 8220.0, "conditions": []}
        issues = validate_no_fabrication(rec)
        assert issues == []
