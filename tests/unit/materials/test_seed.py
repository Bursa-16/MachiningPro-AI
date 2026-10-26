"""Tests for the material seed catalog (EPIC_01).

FABRICATED_MATERIAL_PROPERTY=NO — every numeric value must have a cited source.
"""

from __future__ import annotations

import pytest

from backend.materials.seed_catalog import seed_material_catalog


class TestSeedCatalogStructure:
    def test_record_count_positive(self):
        records = seed_material_catalog()
        assert len(records) >= 1

    def test_stable_ids_unique(self):
        records = seed_material_catalog()
        ids = [r["material_id"] for r in records]
        assert len(ids) == len(set(ids)), "Duplicate material_id detected"

    def test_all_iso_groups_present(self):
        records = seed_material_catalog()
        groups = {r["iso_group"] for r in records}
        for g in ("P", "M", "K", "N", "S"):
            assert g in groups, f"ISO group {g} missing from seed"

    def test_p_group_has_multiple_steels(self):
        records = seed_material_catalog()
        p = [r for r in records if r["iso_group"] == "P"]
        assert len(p) >= 4

    def test_m_group_has_stainless(self):
        records = seed_material_catalog()
        m = [r for r in records if r["iso_group"] == "M"]
        assert len(m) >= 2

    def test_s_group_distinguishes_ti_vs_ni(self):
        records = seed_material_catalog()
        s = [r for r in records if r["iso_group"] == "S"]
        subgroups = {r["iso_subgroup"] for r in s}
        assert "S_TITANIUM" in subgroups, "S_TITANIUM subgroup missing"
        assert "S_NICKEL_HRSA" in subgroups, "S_NICKEL_HRSA subgroup missing"

    def test_n_group_has_aluminum_and_copper(self):
        records = seed_material_catalog()
        n = [r for r in records if r["iso_group"] == "N"]
        subgroups = {r["iso_subgroup"] for r in n}
        assert "N_ALUMINUM" in subgroups
        assert "N_COPPER" in subgroups

    def test_mandatory_fields_present(self):
        records = seed_material_catalog()
        for rec in records:
            for field in ("material_id", "designation", "iso_group", "iso_subgroup", "material_family"):
                assert rec.get(field), f"Record {rec.get('material_id')} missing {field}"


class TestSeedCatalogDataIntegrity:
    def test_no_zero_density(self):
        records = seed_material_catalog()
        for rec in records:
            d = rec.get("density_kg_m3")
            assert d != 0.0, f"{rec['material_id']} has density=0.0 — use None"

    def test_density_plausible_when_present(self):
        records = seed_material_catalog()
        for rec in records:
            d = rec.get("density_kg_m3")
            if d is not None:
                assert 1500 <= d <= 22000, f"{rec['material_id']} density {d} out of plausible range"

    def test_no_fabricated_tensile_strength(self):
        records = seed_material_catalog()
        for rec in records:
            for cond in rec.get("conditions", []):
                ts = cond.get("tensile_strength_mpa")
                if ts is not None:
                    assert ts <= 3500, f"{rec['material_id']} Rm={ts} exceeds 3500 MPa — likely fabricated"

    def test_hardness_ranges_not_inverted(self):
        records = seed_material_catalog()
        for rec in records:
            for cond in rec.get("conditions", []):
                for h in cond.get("hardness", []):
                    assert h["value_min"] <= h["value_max"], (
                        f"{rec['material_id']} has inverted hardness range"
                    )

    def test_hardness_scales_are_valid(self):
        records = seed_material_catalog()
        valid_scales = {"HB", "HRC", "HRB", "HV"}
        for rec in records:
            for cond in rec.get("conditions", []):
                for h in cond.get("hardness", []):
                    assert h["scale"] in valid_scales, (
                        f"{rec['material_id']} has unknown hardness scale: {h['scale']!r}"
                    )

    def test_c45_hardness_annealed_hb(self):
        records = seed_material_catalog()
        c45 = next((r for r in records if r["material_id"] == "P-C45"), None)
        assert c45 is not None, "P-C45 not found"
        annealed = next((c for c in c45["conditions"] if c["condition_code"] == "ANNEALED"), None)
        assert annealed is not None
        hb = next((h for h in annealed["hardness"] if h["scale"] == "HB"), None)
        assert hb is not None
        assert hb["value_min"] == 160.0
        assert hb["value_max"] == 190.0

    def test_c45_qt_strength(self):
        records = seed_material_catalog()
        c45 = next((r for r in records if r["material_id"] == "P-C45"), None)
        qt = next((c for c in c45["conditions"] if c["condition_code"] == "QT"), None)
        assert qt is not None
        assert qt["tensile_strength_mpa"] == 700.0
        assert qt["yield_strength_mpa"] == 490.0

    def test_ti64_hrc_hardness(self):
        records = seed_material_catalog()
        ti = next((r for r in records if r["material_id"] == "S-Ti64"), None)
        assert ti is not None
        annealed = next((c for c in ti["conditions"] if c["condition_code"] == "ANNEALED"), None)
        assert annealed is not None
        hrc = next((h for h in annealed["hardness"] if h["scale"] == "HRC"), None)
        assert hrc is not None
        assert hrc["value_min"] == 30.0
        assert hrc["value_max"] == 36.0

    def test_inconel718_has_ni_hrsa_subgroup(self):
        records = seed_material_catalog()
        in718 = next((r for r in records if r["material_id"] == "S-IN718"), None)
        assert in718 is not None
        assert in718["iso_subgroup"] == "S_NICKEL_HRSA"


class TestSeedCatalogCuttingData:
    def test_cutting_refs_are_reference_only(self):
        records = seed_material_catalog()
        for rec in records:
            for cut in rec.get("cutting_references", []):
                assert cut.get("evidence_status") == "REFERENCE_ONLY", (
                    f"{rec['material_id']} cutting ref missing REFERENCE_ONLY evidence_status"
                )

    def test_vc_ranges_are_positive(self):
        records = seed_material_catalog()
        for rec in records:
            for cut in rec.get("cutting_references", []):
                for field in ("vc_min_m_min", "vc_max_m_min"):
                    val = cut.get(field)
                    if val is not None:
                        assert val > 0, f"{rec['material_id']} {field}={val} must be positive"

    def test_s_titanium_vc_is_low(self):
        records = seed_material_catalog()
        ti = next((r for r in records if r["iso_subgroup"] == "S_TITANIUM"), None)
        assert ti is not None
        for cut in ti.get("cutting_references", []):
            if cut["operation"] == "turning" and cut["tool_material"] == "carbide":
                assert cut["vc_max_m_min"] <= 100, "Ti vc_max should be ≤ 100 m/min"

    def test_p_carbide_turning_vc_range(self):
        records = seed_material_catalog()
        p_steel = next((r for r in records if r["iso_group"] == "P"), None)
        assert p_steel is not None
        for cut in p_steel.get("cutting_references", []):
            if cut["operation"] == "turning" and cut["tool_material"] == "carbide":
                assert cut["vc_min_m_min"] >= 100
                assert cut["vc_max_m_min"] <= 350


class TestSeedCatalogToolCompat:
    def test_tool_compat_are_reference_only(self):
        records = seed_material_catalog()
        for rec in records:
            for tc in rec.get("tool_compatibility", []):
                assert tc.get("evidence_status") == "REFERENCE_ONLY", (
                    f"{rec['material_id']} tool compat missing REFERENCE_ONLY"
                )

    def test_p_carbide_is_recommended(self):
        records = seed_material_catalog()
        p = next((r for r in records if r["iso_group"] == "P"), None)
        assert p is not None
        carbide = next((tc for tc in p.get("tool_compatibility", [])
                        if tc["tool_material"] == "carbide"), None)
        assert carbide is not None
        assert carbide["rating"] == "RECOMMENDED"

    def test_s_titanium_hss_not_recommended(self):
        records = seed_material_catalog()
        ti = next((r for r in records if r["iso_subgroup"] == "S_TITANIUM"), None)
        assert ti is not None
        hss = next((tc for tc in ti.get("tool_compatibility", [])
                    if tc["tool_material"] == "HSS"), None)
        assert hss is not None
        assert hss["rating"] == "NOT_RECOMMENDED"
