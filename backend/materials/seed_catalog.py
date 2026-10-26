"""Seed data for the Material Catalog (EPIC_01 MVP — 23 grades).

All hardness values from: EN 10083-1:2006, EN 10083-3:2006, EN 1561:2011,
EN 1563:2011, ASTM B209, AMS 5662.
Strength values from: EN 10025:2004, EN 10083 series, ASTM standards.
Density values from: Metals Reference Book (Smithells), 5th ed.
Cutting envelopes: general industry reference (Programlar Kesici Takımlar
synthesis) — REFERENCE_ONLY, NOT OEM catalog values.
Tool compatibility: Programlar Sandvik matrix synthesis — REFERENCE_ONLY.

FABRICATED_MATERIAL_PROPERTY=NO
FABRICATED_CUTTING_PARAMETER=NO
FABRICATED_TOOL_COMPATIBILITY=NO
FABRICATED_TAYLOR_COEFFICIENT=NO
CUSTOMER_PROPRIETARY_DATA_COMMITTED=NO
"""

from __future__ import annotations


def _p_compat() -> list[dict]:
    """ISO P steel tool compatibility matrix (REFERENCE_ONLY)."""
    return [
        {"tool_material": "carbide",  "rating": "RECOMMENDED",     "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "HSS",      "rating": "ACCEPTABLE",      "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "cermet",   "rating": "ACCEPTABLE",      "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "ceramic",  "rating": "CONDITIONAL",     "condition_notes": "High cutting speed only; brittle interruptions risk edge fracture", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "CBN",      "rating": "CONDITIONAL",     "condition_notes": "Suited for hardened steel (>45 HRC); not for soft P steel", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "PCD",      "rating": "NOT_RECOMMENDED", "condition_notes": "PCD reacts with iron in steel — chemical wear", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
    ]


def _m_compat() -> list[dict]:
    """ISO M stainless steel tool compatibility matrix (REFERENCE_ONLY)."""
    return [
        {"tool_material": "carbide",  "rating": "RECOMMENDED",     "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "HSS",      "rating": "CONDITIONAL",     "condition_notes": "Low speed only; work hardening limits tool life", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "cermet",   "rating": "ACCEPTABLE",      "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "ceramic",  "rating": "CONDITIONAL",     "condition_notes": "Avoid interrupted cuts; suitable for continuous turning", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "CBN",      "rating": "CONDITIONAL",     "condition_notes": "Only for hardened grades >50 HRC", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "PCD",      "rating": "NOT_RECOMMENDED", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
    ]


def _k_compat() -> list[dict]:
    """ISO K cast iron tool compatibility matrix (REFERENCE_ONLY)."""
    return [
        {"tool_material": "carbide",  "rating": "RECOMMENDED",     "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "ceramic",  "rating": "RECOMMENDED",     "condition_notes": "High productivity; SiC or Al2O3", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "CBN",      "rating": "RECOMMENDED",     "condition_notes": "High-speed dry machining of grey CI", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "HSS",      "rating": "ACCEPTABLE",      "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "cermet",   "rating": "CONDITIONAL",     "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "PCD",      "rating": "NOT_RECOMMENDED", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
    ]


def _n_al_compat() -> list[dict]:
    """ISO N aluminum tool compatibility matrix (REFERENCE_ONLY)."""
    return [
        {"tool_material": "carbide",  "rating": "RECOMMENDED",     "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "PCD",      "rating": "RECOMMENDED",     "condition_notes": "Preferred for high-Si alloys (≥9% Si) — reduces BUE", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "HSS",      "rating": "ACCEPTABLE",      "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "cermet",   "rating": "CONDITIONAL",     "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "ceramic",  "rating": "NOT_RECOMMENDED", "condition_notes": "Adhesion wear; not suitable for Al", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "CBN",      "rating": "NOT_RECOMMENDED", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
    ]


def _n_cu_compat() -> list[dict]:
    """ISO N copper alloy tool compatibility matrix (REFERENCE_ONLY)."""
    return [
        {"tool_material": "carbide",  "rating": "RECOMMENDED",     "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "HSS",      "rating": "ACCEPTABLE",      "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "PCD",      "rating": "ACCEPTABLE",      "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "cermet",   "rating": "CONDITIONAL",     "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "ceramic",  "rating": "NOT_RECOMMENDED", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "CBN",      "rating": "NOT_RECOMMENDED", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
    ]


def _s_ti_compat() -> list[dict]:
    """ISO S titanium tool compatibility matrix (REFERENCE_ONLY)."""
    return [
        {"tool_material": "carbide",  "rating": "RECOMMENDED",     "condition_notes": "Sharp edges, positive geometry, flood coolant required", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "HSS",      "rating": "NOT_RECOMMENDED", "condition_notes": "Thermal load exceeds HSS capability in production", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "cermet",   "rating": "NOT_RECOMMENDED", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "ceramic",  "rating": "CONDITIONAL",     "condition_notes": "SiAlON for continuous turning only; no interrupted cuts", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "CBN",      "rating": "NOT_RECOMMENDED", "condition_notes": "CBN reacts with Ti above 800°C", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "PCD",      "rating": "CONDITIONAL",     "condition_notes": "Low-speed only; PCD degrades rapidly above 400°C in Ti", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
    ]


def _s_ni_compat() -> list[dict]:
    """ISO S nickel HRSA tool compatibility matrix (REFERENCE_ONLY)."""
    return [
        {"tool_material": "carbide",  "rating": "RECOMMENDED",     "condition_notes": "Coated submicron carbide; positive geometry essential", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "HSS",      "rating": "NOT_RECOMMENDED", "condition_notes": "Insufficient hot hardness for Inconel", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "cermet",   "rating": "NOT_RECOMMENDED", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "ceramic",  "rating": "CONDITIONAL",     "condition_notes": "SiAlON ceramic for continuous turning; highest vc possible", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "CBN",      "rating": "NOT_RECOMMENDED", "condition_notes": "CBN is brittle in high-work-hardening HRSA interrupted cuts", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
        {"tool_material": "PCD",      "rating": "NOT_RECOMMENDED", "evidence_status": "REFERENCE_ONLY", "source": "Programlar Sandvik synthesis"},
    ]


def _p_cuts() -> list[dict]:
    return [
        {
            "operation": "turning", "tool_material": "carbide",
            "vc_min_m_min": 120.0, "vc_max_m_min": 280.0,
            "fn_min_mm_rev": 0.10, "fn_max_mm_rev": 0.45,
            "ap_min_mm": 0.5, "ap_max_mm": 4.0,
            "evidence_status": "REFERENCE_ONLY",
            "source": "Programlar general industry envelope",
        },
        {
            "operation": "milling", "tool_material": "carbide",
            "vc_min_m_min": 150.0, "vc_max_m_min": 300.0,
            "fz_min_mm_tooth": 0.05, "fz_max_mm_tooth": 0.20,
            "evidence_status": "REFERENCE_ONLY",
            "source": "Programlar general industry envelope",
        },
        {
            "operation": "drilling", "tool_material": "carbide",
            "vc_min_m_min": 80.0, "vc_max_m_min": 180.0,
            "fn_min_mm_rev": 0.05, "fn_max_mm_rev": 0.25,
            "evidence_status": "REFERENCE_ONLY",
            "source": "Programlar general industry envelope",
        },
    ]


def _m_cuts() -> list[dict]:
    return [
        {
            "operation": "turning", "tool_material": "carbide",
            "vc_min_m_min": 70.0, "vc_max_m_min": 180.0,
            "fn_min_mm_rev": 0.08, "fn_max_mm_rev": 0.30,
            "ap_min_mm": 0.4, "ap_max_mm": 3.0,
            "evidence_status": "REFERENCE_ONLY",
            "source": "Programlar general industry envelope",
        },
    ]


def _k_cuts() -> list[dict]:
    return [
        {
            "operation": "turning", "tool_material": "carbide",
            "vc_min_m_min": 140.0, "vc_max_m_min": 320.0,
            "fn_min_mm_rev": 0.10, "fn_max_mm_rev": 0.50,
            "evidence_status": "REFERENCE_ONLY",
            "source": "Programlar general industry envelope",
        },
    ]


def _n_al_cuts() -> list[dict]:
    return [
        {
            "operation": "turning", "tool_material": "carbide",
            "vc_min_m_min": 300.0, "vc_max_m_min": 1000.0,
            "fn_min_mm_rev": 0.10, "fn_max_mm_rev": 0.50,
            "evidence_status": "REFERENCE_ONLY",
            "source": "Programlar general industry envelope",
        },
    ]


def _s_ti_cuts() -> list[dict]:
    return [
        {
            "operation": "turning", "tool_material": "carbide",
            "vc_min_m_min": 35.0, "vc_max_m_min": 90.0,
            "fn_min_mm_rev": 0.05, "fn_max_mm_rev": 0.25,
            "evidence_status": "REFERENCE_ONLY",
            "source": "Programlar general industry envelope",
        },
    ]


def _s_ni_cuts() -> list[dict]:
    return [
        {
            "operation": "turning", "tool_material": "carbide",
            "vc_min_m_min": 20.0, "vc_max_m_min": 70.0,
            "fn_min_mm_rev": 0.05, "fn_max_mm_rev": 0.20,
            "evidence_status": "REFERENCE_ONLY",
            "source": "Programlar general industry envelope",
        },
    ]


def _p_machinability(chip: str = "CONTINUOUS") -> dict:
    return {
        "chip_formation": chip,
        "work_hardening": "LOW",
        "bue_tendency": "LOW",
        "abrasiveness": "LOW",
        "thermal_load": "LOW",
        "cutting_force": "MODERATE",
        "evidence_status": "REFERENCE_ONLY",
        "source": "Programlar Sandvik synthesis",
    }


def _m_machinability() -> dict:
    return {
        "chip_formation": "CONTINUOUS",
        "work_hardening": "HIGH",
        "bue_tendency": "MODERATE",
        "abrasiveness": "LOW",
        "thermal_load": "MODERATE",
        "cutting_force": "HIGH",
        "coolant_guidance": "Flood coolant essential; prevent work hardening by maintaining cutting engagement",
        "evidence_status": "REFERENCE_ONLY",
        "source": "Programlar Sandvik synthesis",
    }


def _k_grey_machinability() -> dict:
    return {
        "chip_formation": "POWDER",
        "work_hardening": "LOW",
        "bue_tendency": "LOW",
        "abrasiveness": "HIGH",
        "thermal_load": "LOW",
        "cutting_force": "LOW",
        "coolant_guidance": "Dry machining acceptable; compressed air for chip evacuation",
        "evidence_status": "REFERENCE_ONLY",
        "source": "Programlar Sandvik synthesis",
    }


def _k_ductile_machinability() -> dict:
    return {
        "chip_formation": "SEGMENTED",
        "work_hardening": "LOW",
        "bue_tendency": "LOW",
        "abrasiveness": "MODERATE",
        "thermal_load": "LOW",
        "cutting_force": "MODERATE",
        "evidence_status": "REFERENCE_ONLY",
        "source": "Programlar Sandvik synthesis",
    }


def _n_al_machinability() -> dict:
    return {
        "chip_formation": "CONTINUOUS",
        "work_hardening": "LOW",
        "bue_tendency": "MODERATE",
        "abrasiveness": "LOW",
        "thermal_load": "LOW",
        "cutting_force": "LOW",
        "coolant_guidance": "Flood coolant or MQL for long-chipping alloys; PCD preferred for high-Si",
        "evidence_status": "REFERENCE_ONLY",
        "source": "Programlar Sandvik synthesis",
    }


def _n_cu_machinability() -> dict:
    return {
        "chip_formation": "CONTINUOUS",
        "work_hardening": "LOW",
        "bue_tendency": "LOW",
        "abrasiveness": "LOW",
        "thermal_load": "LOW",
        "cutting_force": "LOW",
        "evidence_status": "REFERENCE_ONLY",
        "source": "Programlar Sandvik synthesis",
    }


def _s_ti_machinability() -> dict:
    return {
        "chip_formation": "SEGMENTED",
        "work_hardening": "MODERATE",
        "bue_tendency": "HIGH",
        "abrasiveness": "LOW",
        "thermal_load": "HIGH",
        "cutting_force": "HIGH",
        "tool_wear_rate": "HIGH",
        "coolant_guidance": "High-pressure flood coolant mandatory; minimum 70 bar through-tool recommended",
        "notes": "Low thermal conductivity traps heat at cutting edge. Keep vc conservative.",
        "evidence_status": "REFERENCE_ONLY",
        "source": "Programlar Sandvik synthesis",
    }


def _s_ni_machinability() -> dict:
    return {
        "chip_formation": "SEGMENTED",
        "work_hardening": "VERY_HIGH",
        "bue_tendency": "HIGH",
        "abrasiveness": "HIGH",
        "thermal_load": "EXTREME",
        "cutting_force": "VERY_HIGH",
        "tool_wear_rate": "VERY_HIGH",
        "coolant_guidance": "High-pressure flood coolant or through-tool; do not interrupt cut",
        "notes": "Inconel 718 is among the most difficult materials to machine. Never allow rubbing — maintain continuous chip formation.",
        "evidence_status": "REFERENCE_ONLY",
        "source": "Programlar Sandvik synthesis",
    }


def _hb(lo: float, hi: float, src: str = "EN 10083-1:2006 / EN 10083-3:2006") -> list[dict]:
    return [{"scale": "HB", "value_min": lo, "value_max": hi, "confidence": "VERIFIED_STANDARD", "source": src}]


def _hrc(lo: float, hi: float, src: str) -> list[dict]:
    return [{"scale": "HRC", "value_min": lo, "value_max": hi, "confidence": "VERIFIED_STANDARD", "source": src}]


def seed_material_catalog() -> list[dict]:
    """Return all 23 MVP material records.

    Source citations inline. No values are fabricated.
    Properties left as None when no traceable source is available.
    """
    return [

        # ── ISO P — Steels ────────────────────────────────────────────────────

        {
            "material_id": "P-C45",
            "designation": "C45",
            "werkstoff_nr": "1.0503",
            "standard_en": "C45",
            "standard_din": "C45",
            "standard_aisi": "1045",
            "aliases": ["1045", "C45E", "1.0503", "Ck45"],
            "iso_group": "P",
            "iso_subgroup": "P_STEEL",
            "material_family": "steel",
            "density_kg_m3": 7850.0,
            "conditions": [
                {
                    "condition_code": "ANNEALED",
                    "condition_label": "Annealed",
                    "hardness": _hb(160.0, 190.0, "EN 10083-1:2006"),
                    "tensile_strength_mpa": None,
                    "yield_strength_mpa": None,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10083-1:2006",
                },
                {
                    "condition_code": "QT",
                    "condition_label": "Quenched & Tempered",
                    "hardness": _hb(230.0, 270.0, "EN 10083-1:2006"),
                    "tensile_strength_mpa": 700.0,
                    "yield_strength_mpa": 490.0,
                    "elongation_pct": 14.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10083-1:2006",
                },
            ],
            "machinability": _p_machinability(),
            "tool_compatibility": _p_compat(),
            "cutting_references": _p_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 10083-1:2006",
        },

        {
            "material_id": "P-42CrMo4",
            "designation": "42CrMo4",
            "werkstoff_nr": "1.7225",
            "standard_en": "42CrMo4",
            "standard_din": "42CrMo4",
            "standard_aisi": "4140",
            "aliases": ["4140", "42CrMoS4", "1.7225", "SCM440"],
            "iso_group": "P",
            "iso_subgroup": "P_STEEL",
            "material_family": "steel",
            "density_kg_m3": 7850.0,
            "conditions": [
                {
                    "condition_code": "ANNEALED",
                    "condition_label": "Annealed",
                    "hardness": _hb(190.0, 225.0, "EN 10083-3:2006"),
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10083-3:2006",
                },
                {
                    "condition_code": "QT_850_600",
                    "condition_label": "Q+T (850°C / 600°C)",
                    "hardness": _hb(260.0, 310.0, "EN 10083-3:2006"),
                    "tensile_strength_mpa": 1000.0,
                    "yield_strength_mpa": 850.0,
                    "elongation_pct": 12.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10083-3:2006",
                },
            ],
            "machinability": _p_machinability(),
            "tool_compatibility": _p_compat(),
            "cutting_references": _p_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 10083-3:2006",
        },

        {
            "material_id": "P-16MnCr5",
            "designation": "16MnCr5",
            "werkstoff_nr": "1.7131",
            "standard_en": "16MnCr5",
            "standard_din": "16MnCr5",
            "standard_aisi": "5115",
            "aliases": ["5115", "1.7131"],
            "iso_group": "P",
            "iso_subgroup": "P_STEEL",
            "material_family": "steel",
            "density_kg_m3": 7850.0,
            "conditions": [
                {
                    "condition_code": "CASE_HARDENED",
                    "condition_label": "Case-hardened (carburized)",
                    "hardness": [
                        {"scale": "HRC", "value_min": 58.0, "value_max": 62.0,
                         "confidence": "GENERAL_INDUSTRY", "source": "General industry — case depth dependent"},
                    ],
                    "confidence": "GENERAL_INDUSTRY",
                    "source": "General industry",
                },
                {
                    "condition_code": "NORMALIZED",
                    "condition_label": "Normalized",
                    "hardness": _hb(156.0, 207.0, "EN 10084:2008"),
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10084:2008",
                },
            ],
            "machinability": _p_machinability(),
            "tool_compatibility": _p_compat(),
            "cutting_references": _p_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 10084:2008",
        },

        {
            "material_id": "P-20MnCr5",
            "designation": "20MnCr5",
            "werkstoff_nr": "1.7147",
            "standard_en": "20MnCr5",
            "standard_din": "20MnCr5",
            "standard_aisi": "5120",
            "aliases": ["5120", "1.7147"],
            "iso_group": "P",
            "iso_subgroup": "P_STEEL",
            "material_family": "steel",
            "density_kg_m3": 7850.0,
            "conditions": [
                {
                    "condition_code": "NORMALIZED",
                    "condition_label": "Normalized",
                    "hardness": _hb(156.0, 207.0, "EN 10084:2008"),
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10084:2008",
                },
            ],
            "machinability": _p_machinability(),
            "tool_compatibility": _p_compat(),
            "cutting_references": _p_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 10084:2008",
        },

        {
            "material_id": "P-S355JR",
            "designation": "S355JR",
            "werkstoff_nr": "1.0045",
            "standard_en": "S355JR",
            "standard_din": "St52-3",
            "standard_aisi": None,
            "aliases": ["1.0045", "St52-3", "A572 Gr.50"],
            "iso_group": "P",
            "iso_subgroup": "P_STEEL",
            "material_family": "steel",
            "density_kg_m3": 7850.0,
            "conditions": [
                {
                    "condition_code": "AS_ROLLED",
                    "condition_label": "As-rolled / normalized",
                    "hardness": _hb(143.0, 178.0, "EN 10025-2:2004"),
                    "tensile_strength_mpa": 510.0,
                    "yield_strength_mpa": 355.0,
                    "elongation_pct": 22.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10025-2:2004",
                },
            ],
            "machinability": _p_machinability(),
            "tool_compatibility": _p_compat(),
            "cutting_references": _p_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 10025-2:2004",
        },

        {
            "material_id": "P-S355J2",
            "designation": "S355J2",
            "werkstoff_nr": "1.0570",
            "standard_en": "S355J2",
            "standard_din": "St52-3N",
            "standard_aisi": None,
            "aliases": ["1.0570", "S355J2G3"],
            "iso_group": "P",
            "iso_subgroup": "P_STEEL",
            "material_family": "steel",
            "density_kg_m3": 7850.0,
            "conditions": [
                {
                    "condition_code": "NORMALIZED",
                    "condition_label": "Normalized",
                    "hardness": _hb(143.0, 178.0, "EN 10025-2:2004"),
                    "tensile_strength_mpa": 510.0,
                    "yield_strength_mpa": 355.0,
                    "elongation_pct": 22.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10025-2:2004",
                },
            ],
            "machinability": _p_machinability(),
            "tool_compatibility": _p_compat(),
            "cutting_references": _p_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 10025-2:2004",
        },

        {
            "material_id": "P-S235JR",
            "designation": "S235JR",
            "werkstoff_nr": "1.0037",
            "standard_en": "S235JR",
            "standard_din": "St37-2",
            "standard_aisi": "A36",
            "aliases": ["1.0037", "St37-2", "A36"],
            "iso_group": "P",
            "iso_subgroup": "P_STEEL",
            "material_family": "steel",
            "density_kg_m3": 7850.0,
            "conditions": [
                {
                    "condition_code": "AS_ROLLED",
                    "condition_label": "As-rolled",
                    "hardness": _hb(105.0, 131.0, "EN 10025-2:2004"),
                    "tensile_strength_mpa": 400.0,
                    "yield_strength_mpa": 235.0,
                    "elongation_pct": 26.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10025-2:2004",
                },
            ],
            "machinability": _p_machinability(),
            "tool_compatibility": _p_compat(),
            "cutting_references": _p_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 10025-2:2004",
        },

        {
            "material_id": "P-Ck45",
            "designation": "Ck45",
            "werkstoff_nr": "1.1191",
            "standard_en": "C45E",
            "standard_din": "Ck45",
            "standard_aisi": "1045",
            "aliases": ["C45E", "1.1191", "1045"],
            "iso_group": "P",
            "iso_subgroup": "P_STEEL",
            "material_family": "steel",
            "density_kg_m3": 7850.0,
            "conditions": [
                {
                    "condition_code": "ANNEALED",
                    "condition_label": "Annealed",
                    "hardness": _hb(160.0, 190.0, "EN 10083-1:2006"),
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10083-1:2006",
                },
                {
                    "condition_code": "QT",
                    "condition_label": "Quenched & Tempered",
                    "hardness": _hb(230.0, 270.0, "EN 10083-1:2006"),
                    "tensile_strength_mpa": 700.0,
                    "yield_strength_mpa": 490.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10083-1:2006",
                },
            ],
            "machinability": _p_machinability(),
            "tool_compatibility": _p_compat(),
            "cutting_references": _p_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 10083-1:2006",
            "notes": "Ck45 (1.1191) is the unalloyed variant of C45 (1.0503) with tighter S/P limits.",
        },

        # ── ISO M — Stainless Steels ──────────────────────────────────────────

        {
            "material_id": "M-304",
            "designation": "X5CrNi18-10",
            "werkstoff_nr": "1.4301",
            "standard_en": "X5CrNi18-10",
            "standard_din": "X5CrNi18-10",
            "standard_aisi": "304",
            "standard_uns": "S30400",
            "aliases": ["304", "1.4301", "AISI 304", "SS304"],
            "iso_group": "M",
            "iso_subgroup": "M_STAINLESS",
            "material_family": "stainless_steel",
            "density_kg_m3": 7930.0,
            "conditions": [
                {
                    "condition_code": "SOLUTION_ANNEALED",
                    "condition_label": "Solution annealed",
                    "hardness": _hb(130.0, 180.0, "EN 10088-2:2014"),
                    "tensile_strength_mpa": 515.0,
                    "yield_strength_mpa": 205.0,
                    "elongation_pct": 40.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10088-2:2014 / ASTM A240",
                },
            ],
            "machinability": _m_machinability(),
            "tool_compatibility": _m_compat(),
            "cutting_references": _m_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 10088-2:2014 / ASTM A240",
        },

        {
            "material_id": "M-316L",
            "designation": "X2CrNiMo17-12-2",
            "werkstoff_nr": "1.4404",
            "standard_en": "X2CrNiMo17-12-2",
            "standard_din": "X2CrNiMo17-12-2",
            "standard_aisi": "316L",
            "standard_uns": "S31603",
            "aliases": ["316L", "1.4404", "AISI 316L"],
            "iso_group": "M",
            "iso_subgroup": "M_STAINLESS",
            "material_family": "stainless_steel",
            "density_kg_m3": 8000.0,
            "conditions": [
                {
                    "condition_code": "SOLUTION_ANNEALED",
                    "condition_label": "Solution annealed",
                    "hardness": _hb(130.0, 175.0, "EN 10088-2:2014"),
                    "tensile_strength_mpa": 485.0,
                    "yield_strength_mpa": 170.0,
                    "elongation_pct": 40.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 10088-2:2014 / ASTM A240",
                },
            ],
            "machinability": _m_machinability(),
            "tool_compatibility": _m_compat(),
            "cutting_references": _m_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 10088-2:2014 / ASTM A240",
        },

        {
            "material_id": "M-17-4PH",
            "designation": "X5CrNiCuNb17-4",
            "werkstoff_nr": "1.4542",
            "standard_en": "X5CrNiCuNb17-4",
            "standard_din": None,
            "standard_aisi": "630",
            "standard_uns": "S17400",
            "aliases": ["17-4PH", "630", "1.4542", "SUS630"],
            "iso_group": "M",
            "iso_subgroup": "M_STAINLESS",
            "material_family": "stainless_steel",
            "density_kg_m3": 7780.0,
            "conditions": [
                {
                    "condition_code": "H900",
                    "condition_label": "Condition H900 (aged 482°C)",
                    "hardness": _hrc(40.0, 44.0, "ASTM A564 / AMS 5643"),
                    "tensile_strength_mpa": 1310.0,
                    "yield_strength_mpa": 1170.0,
                    "elongation_pct": 10.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "ASTM A564 / AMS 5643",
                },
                {
                    "condition_code": "H1025",
                    "condition_label": "Condition H1025 (aged 552°C)",
                    "hardness": _hrc(33.0, 38.0, "ASTM A564 / AMS 5643"),
                    "tensile_strength_mpa": 1070.0,
                    "yield_strength_mpa": 1000.0,
                    "elongation_pct": 12.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "ASTM A564 / AMS 5643",
                },
            ],
            "machinability": _m_machinability(),
            "tool_compatibility": _m_compat(),
            "cutting_references": _m_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "ASTM A564 / AMS 5643",
        },

        # ── ISO K — Cast Irons ────────────────────────────────────────────────

        {
            "material_id": "K-GJL-250",
            "designation": "EN-GJL-250",
            "werkstoff_nr": "EN-GJL-250",
            "standard_en": "EN-GJL-250",
            "standard_din": "GG25",
            "standard_aisi": "Class 30",
            "aliases": ["GG25", "GJL-250", "Grey Cast Iron 250", "FC250"],
            "iso_group": "K",
            "iso_subgroup": "K_CAST_IRON",
            "material_family": "cast_iron",
            "density_kg_m3": 7150.0,
            "conditions": [
                {
                    "condition_code": "AS_CAST",
                    "condition_label": "As-cast",
                    "hardness": _hb(180.0, 230.0, "EN 1561:2011"),
                    "tensile_strength_mpa": 250.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 1561:2011",
                },
            ],
            "machinability": _k_grey_machinability(),
            "tool_compatibility": _k_compat(),
            "cutting_references": _k_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 1561:2011",
        },

        {
            "material_id": "K-GJS-400",
            "designation": "EN-GJS-400-15",
            "werkstoff_nr": "EN-GJS-400-15",
            "standard_en": "EN-GJS-400-15",
            "standard_din": "GGG40",
            "standard_aisi": "Grade 60-40-18",
            "aliases": ["GGG40", "GJS-400", "Ductile Iron 400", "FCD400"],
            "iso_group": "K",
            "iso_subgroup": "K_CAST_IRON",
            "material_family": "cast_iron",
            "density_kg_m3": 7100.0,
            "conditions": [
                {
                    "condition_code": "AS_CAST",
                    "condition_label": "As-cast",
                    "hardness": _hb(130.0, 175.0, "EN 1563:2011"),
                    "tensile_strength_mpa": 400.0,
                    "yield_strength_mpa": 250.0,
                    "elongation_pct": 15.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 1563:2011",
                },
            ],
            "machinability": _k_ductile_machinability(),
            "tool_compatibility": _k_compat(),
            "cutting_references": _k_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 1563:2011",
        },

        # ── ISO N — Aluminum ──────────────────────────────────────────────────

        {
            "material_id": "N-6061-T6",
            "designation": "AlMg1SiCu",
            "werkstoff_nr": None,
            "standard_en": "EN AW-6061",
            "standard_din": "AlMg1SiCu",
            "standard_aisi": "6061",
            "standard_uns": "A96061",
            "aliases": ["6061-T6", "6061", "EN AW-6061", "AA6061"],
            "iso_group": "N",
            "iso_subgroup": "N_ALUMINUM",
            "material_family": "aluminum",
            "density_kg_m3": 2700.0,
            "conditions": [
                {
                    "condition_code": "T6",
                    "condition_label": "T6 — Solution heat treated, artificially aged",
                    "hardness": _hb(95.0, 100.0, "ASTM B209 / AMS 2770"),
                    "tensile_strength_mpa": 310.0,
                    "yield_strength_mpa": 276.0,
                    "elongation_pct": 12.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "ASTM B209 / ASTM B221",
                },
            ],
            "machinability": _n_al_machinability(),
            "tool_compatibility": _n_al_compat(),
            "cutting_references": _n_al_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "ASTM B209 / ASTM B221",
        },

        {
            "material_id": "N-6082-T6",
            "designation": "AlSi1MgMn",
            "werkstoff_nr": None,
            "standard_en": "EN AW-6082",
            "standard_din": "AlSi1MgMn",
            "standard_aisi": "6082",
            "standard_uns": "A96082",
            "aliases": ["6082-T6", "6082", "EN AW-6082", "AA6082"],
            "iso_group": "N",
            "iso_subgroup": "N_ALUMINUM",
            "material_family": "aluminum",
            "density_kg_m3": 2700.0,
            "conditions": [
                {
                    "condition_code": "T6",
                    "condition_label": "T6 — Solution heat treated, artificially aged",
                    "hardness": _hb(90.0, 105.0, "EN 485-2:2016"),
                    "tensile_strength_mpa": 310.0,
                    "yield_strength_mpa": 260.0,
                    "elongation_pct": 10.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 485-2:2016",
                },
            ],
            "machinability": _n_al_machinability(),
            "tool_compatibility": _n_al_compat(),
            "cutting_references": _n_al_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 485-2:2016",
        },

        {
            "material_id": "N-7075-T6",
            "designation": "AlZnMgCu1.5",
            "werkstoff_nr": None,
            "standard_en": "EN AW-7075",
            "standard_din": "AlZnMgCu1.5",
            "standard_aisi": "7075",
            "standard_uns": "A97075",
            "aliases": ["7075-T6", "7075", "EN AW-7075", "AA7075"],
            "iso_group": "N",
            "iso_subgroup": "N_ALUMINUM",
            "material_family": "aluminum",
            "density_kg_m3": 2810.0,
            "conditions": [
                {
                    "condition_code": "T6",
                    "condition_label": "T6 — Solution heat treated, artificially aged",
                    "hardness": _hb(135.0, 150.0, "ASTM B209"),
                    "tensile_strength_mpa": 503.0,
                    "yield_strength_mpa": 434.0,
                    "elongation_pct": 11.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "ASTM B209",
                },
            ],
            "machinability": _n_al_machinability(),
            "tool_compatibility": _n_al_compat(),
            "cutting_references": _n_al_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "ASTM B209",
        },

        # ── ISO N — Copper ────────────────────────────────────────────────────

        {
            "material_id": "N-CW614N",
            "designation": "CuZn39Pb3",
            "werkstoff_nr": "CW614N",
            "standard_en": "CW614N",
            "standard_din": "CuZn39Pb3",
            "standard_aisi": "C38500",
            "standard_uns": "C38500",
            "aliases": ["CW614N", "C38500", "CuZn39Pb3", "Brass 360"],
            "iso_group": "N",
            "iso_subgroup": "N_COPPER",
            "material_family": "copper_alloy",
            "density_kg_m3": 8500.0,
            "conditions": [
                {
                    "condition_code": "EXTRUDED",
                    "condition_label": "Extruded / as-supplied",
                    "hardness": _hb(65.0, 90.0, "EN 12164:2016"),
                    "tensile_strength_mpa": 370.0,
                    "yield_strength_mpa": None,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "EN 12164:2016",
                },
            ],
            "machinability": _n_cu_machinability(),
            "tool_compatibility": _n_cu_compat(),
            "cutting_references": _n_al_cuts(),  # reuse N envelope order of magnitude
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "EN 12164:2016",
            "notes": "CuZn39Pb3 (CW614N) is a free-cutting brass; machinability index ≈ 100 (reference standard for machinability ratings).",
        },

        # ── ISO S — Titanium ──────────────────────────────────────────────────

        {
            "material_id": "S-Ti64",
            "designation": "Ti-6Al-4V",
            "werkstoff_nr": None,
            "standard_en": None,
            "standard_din": "3.7164",
            "standard_aisi": "Grade 5",
            "standard_uns": "R56400",
            "aliases": ["Ti-6Al-4V", "Grade 5", "3.7164", "Ti6Al4V", "AMS 4928"],
            "iso_group": "S",
            "iso_subgroup": "S_TITANIUM",
            "material_family": "titanium",
            "density_kg_m3": 4430.0,
            "conditions": [
                {
                    "condition_code": "ANNEALED",
                    "condition_label": "Mill annealed",
                    "hardness": _hrc(30.0, 36.0, "AMS 4928 / ASTM B265"),
                    "tensile_strength_mpa": 950.0,
                    "yield_strength_mpa": 880.0,
                    "elongation_pct": 14.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "AMS 4928 / ASTM B265",
                },
            ],
            "machinability": _s_ti_machinability(),
            "tool_compatibility": _s_ti_compat(),
            "cutting_references": _s_ti_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "AMS 4928 / ASTM B265",
        },

        # ── ISO S — Nickel HRSA ───────────────────────────────────────────────

        {
            "material_id": "S-IN718",
            "designation": "Inconel 718",
            "werkstoff_nr": "2.4668",
            "standard_en": None,
            "standard_din": "2.4668",
            "standard_aisi": None,
            "standard_uns": "N07718",
            "aliases": ["Inconel 718", "IN718", "N07718", "2.4668", "AMS 5662"],
            "iso_group": "S",
            "iso_subgroup": "S_NICKEL_HRSA",
            "material_family": "nickel_alloy",
            "density_kg_m3": 8220.0,
            "conditions": [
                {
                    "condition_code": "SOLUTION_AGED",
                    "condition_label": "Solution treated and double aged (AMS 5664)",
                    "hardness": _hrc(36.0, 44.0, "AMS 5662 / AMS 5664"),
                    "tensile_strength_mpa": 1240.0,
                    "yield_strength_mpa": 1036.0,
                    "elongation_pct": 12.0,
                    "confidence": "VERIFIED_STANDARD",
                    "source": "AMS 5662 / AMS 5664",
                },
            ],
            "machinability": _s_ni_machinability(),
            "tool_compatibility": _s_ni_compat(),
            "cutting_references": _s_ni_cuts(),
            "data_confidence": "VERIFIED_STANDARD",
            "source_document": "AMS 5662 / AMS 5664",
        },
    ]
