"""Tests for backend.materials.models (EPIC_01)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.materials.models import (
    MaterialCuttingRef,
    MaterialHardnessEntry,
    MaterialConditionRecord,
    MaterialMachinabilityRecord,
    MaterialToolCompatEntry,
    MaterialRecord,
    MaterialListItem,
    MaterialSummary,
    IsoGroupInfo,
)


class TestMaterialHardnessEntry:
    def test_valid_hb(self):
        h = MaterialHardnessEntry(scale="HB", value_min=160.0, value_max=190.0,
                                   confidence="VERIFIED_STANDARD", source="EN 10083")
        assert h.scale == "HB"
        assert h.value_min == 160.0
        assert h.value_max == 190.0

    def test_valid_hrc(self):
        h = MaterialHardnessEntry(scale="HRC", value_min=30.0, value_max=36.0,
                                   confidence="VERIFIED_STANDARD", source="AMS 4928")
        assert h.scale == "HRC"

    def test_valid_hrb(self):
        h = MaterialHardnessEntry(scale="HRB", value_min=70.0, value_max=85.0,
                                   confidence="GENERAL_INDUSTRY", source="Test")
        assert h.scale == "HRB"

    def test_valid_hv(self):
        h = MaterialHardnessEntry(scale="HV", value_min=200.0, value_max=250.0,
                                   confidence="LITERATURE_REFERENCE", source="Test")
        assert h.scale == "HV"


class TestMaterialConditionRecord:
    def test_valid_condition(self):
        cond = MaterialConditionRecord(
            condition_code="ANNEALED",
            condition_label="Annealed",
            hardness=[MaterialHardnessEntry(scale="HB", value_min=160, value_max=190,
                                             confidence="VERIFIED_STANDARD", source="EN 10083")],
            tensile_strength_mpa=600.0,
            yield_strength_mpa=430.0,
            elongation_pct=14.0,
            confidence="VERIFIED_STANDARD",
            source="EN 10083",
        )
        assert cond.condition_code == "ANNEALED"
        assert len(cond.hardness) == 1

    def test_none_values_preserved(self):
        cond = MaterialConditionRecord(
            condition_code="QT",
            condition_label="Q+T",
            confidence="VERIFIED_STANDARD",
            source="Test",
        )
        assert cond.tensile_strength_mpa is None
        assert cond.yield_strength_mpa is None
        assert cond.elongation_pct is None

    def test_hardness_defaults_to_empty(self):
        cond = MaterialConditionRecord(condition_code="X", condition_label="X",
                                       confidence="UNKNOWN", source="")
        assert cond.hardness == []


class TestMaterialMachinabilityRecord:
    def test_defaults(self):
        mac = MaterialMachinabilityRecord()
        assert mac.evidence_status == "REFERENCE_ONLY"
        assert mac.machinability_index is None
        assert mac.chip_formation is None

    def test_with_fields(self):
        mac = MaterialMachinabilityRecord(
            chip_formation="CONTINUOUS",
            work_hardening="HIGH",
            bue_tendency="MODERATE",
            evidence_status="REFERENCE_ONLY",
            source="Programlar",
        )
        assert mac.chip_formation == "CONTINUOUS"
        assert mac.work_hardening == "HIGH"


class TestMaterialToolCompatEntry:
    def test_recommended(self):
        entry = MaterialToolCompatEntry(
            tool_material="carbide",
            rating="RECOMMENDED",
            evidence_status="REFERENCE_ONLY",
            source="Programlar",
        )
        assert entry.rating == "RECOMMENDED"
        assert entry.condition_notes is None

    def test_conditional_with_notes(self):
        entry = MaterialToolCompatEntry(
            tool_material="ceramic",
            rating="CONDITIONAL",
            condition_notes="High speed only",
            evidence_status="REFERENCE_ONLY",
            source="Programlar",
        )
        assert entry.rating == "CONDITIONAL"
        assert "High speed" in entry.condition_notes


class TestMaterialCuttingRef:
    def test_valid_turning_ref(self):
        cut = MaterialCuttingRef(
            operation="turning",
            tool_material="carbide",
            vc_min_m_min=120.0,
            vc_max_m_min=280.0,
            fn_min_mm_rev=0.10,
            fn_max_mm_rev=0.45,
            ap_min_mm=0.5,
            ap_max_mm=4.0,
            evidence_status="REFERENCE_ONLY",
            source="Programlar",
        )
        assert cut.vc_min_m_min == 120.0
        assert cut.vc_max_m_min == 280.0

    def test_none_fields_preserved(self):
        cut = MaterialCuttingRef(
            operation="milling",
            tool_material="carbide",
            vc_min_m_min=150.0,
            vc_max_m_min=300.0,
            evidence_status="REFERENCE_ONLY",
            source="Test",
        )
        assert cut.fn_min_mm_rev is None
        assert cut.ap_min_mm is None


class TestMaterialRecord:
    def test_minimal_valid_record(self):
        rec = MaterialRecord(
            material_id="P-TEST",
            designation="TestSteel",
            iso_group="P",
            iso_subgroup="P_STEEL",
            material_family="steel",
            data_confidence="VERIFIED_STANDARD",
            source_document="Test",
            evidence_status="REFERENCE_ONLY",
        )
        assert rec.material_id == "P-TEST"
        assert rec.density_kg_m3 is None
        assert rec.conditions == []
        assert rec.tool_compatibility == []

    def test_none_numeric_fields(self):
        rec = MaterialRecord(
            material_id="P-TEST2",
            designation="Test",
            iso_group="P",
            iso_subgroup="P_STEEL",
            material_family="steel",
            data_confidence="UNKNOWN",
            source_document="",
            evidence_status="REFERENCE_ONLY",
        )
        for field in ("density_kg_m3", "elastic_modulus_gpa", "thermal_conductivity_w_mk"):
            assert getattr(rec, field) is None, f"{field} should default to None"

    def test_aliases_default_empty(self):
        rec = MaterialRecord(
            material_id="P-T3",
            designation="T",
            iso_group="K",
            iso_subgroup="K_CAST_IRON",
            material_family="cast_iron",
            data_confidence="VERIFIED_STANDARD",
            source_document="",
            evidence_status="REFERENCE_ONLY",
        )
        assert rec.aliases == []


class TestMaterialSummary:
    def test_construction(self):
        s = MaterialSummary(
            material_count=19,
            iso_group_counts={"P": 8, "M": 3, "K": 2, "N": 4, "S": 2},
            family_counts={"steel": 8, "stainless_steel": 3},
            source_title="MachiningPro MVP",
            evidence_note="REFERENCE_ONLY",
        )
        assert s.material_count == 19
        assert s.iso_group_counts["P"] == 8


class TestIsoGroupInfo:
    def test_construction(self):
        info = IsoGroupInfo(code="P", label="Steels", description="Unalloyed steels",
                            color_hint="blue")
        assert info.code == "P"
        assert info.color_hint == "blue"
