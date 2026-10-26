"""Pydantic API models for the Material Catalog (EPIC_01_MATERIAL_INTELLIGENCE_FOUNDATION).

Separate from backend.domain.material.Material (constraint validation).
Provides richer, discovery-oriented records for browse UI and API consumers.

FABRICATED_MATERIAL_PROPERTY=NO
MISSING_VALUE_AS_ZERO=NO  — all optional numeric fields are None when unknown
"""

from __future__ import annotations

from pydantic import BaseModel

__all__ = [
    "MaterialHardnessEntry",
    "MaterialConditionRecord",
    "MaterialMachinabilityRecord",
    "MaterialToolCompatEntry",
    "MaterialCuttingRef",
    "MaterialRecord",
    "MaterialSummary",
    "MaterialListItem",
    "MaterialDetail",
    "IsoGroupInfo",
]


class MaterialHardnessEntry(BaseModel):
    """A hardness measurement in one explicit scale — no silent conversion."""
    scale: str          # "HB" / "HRC" / "HRB" / "HV"
    value_min: float
    value_max: float
    confidence: str     # DataConfidence member
    source: str


class MaterialConditionRecord(BaseModel):
    """Heat-treatment or delivery condition with condition-specific properties."""
    condition_code: str     # e.g. "ANNEALED", "QT_850_600", "T6", "SOLUTION_AGED"
    condition_label: str    # human-readable label
    hardness: list[MaterialHardnessEntry] = []
    tensile_strength_mpa: float | None = None
    yield_strength_mpa: float | None = None
    elongation_pct: float | None = None
    confidence: str = "VERIFIED_STANDARD"
    source: str = ""


class MaterialMachinabilityRecord(BaseModel):
    """Qualitative machinability metadata (REFERENCE_ONLY from Programlar synthesis)."""
    machinability_index: float | None = None     # 0–100, AISI 1112 = 100; None when not available
    chip_formation: str | None = None            # ChipFormationClass member
    work_hardening: str | None = None            # MachinabilityLevel member
    bue_tendency: str | None = None              # MachinabilityLevel member (Built-Up Edge)
    abrasiveness: str | None = None              # MachinabilityLevel member
    thermal_load: str | None = None              # MachinabilityLevel member
    cutting_force: str | None = None             # MachinabilityLevel member
    tool_wear_rate: str | None = None            # MachinabilityLevel member
    coolant_guidance: str | None = None          # free text
    notes: str | None = None
    evidence_status: str = "REFERENCE_ONLY"
    source: str = "Programlar Sandvik synthesis"


class MaterialToolCompatEntry(BaseModel):
    """Single tool-material compatibility rating (REFERENCE_ONLY from Programlar matrix)."""
    tool_material: str          # ToolMaterial member: HSS, carbide, cermet, ceramic, CBN, PCD
    rating: str                 # ToolCompatRating member
    condition_notes: str | None = None
    evidence_status: str = "REFERENCE_ONLY"
    source: str = "Programlar Sandvik synthesis"


class MaterialCuttingRef(BaseModel):
    """General-industry cutting parameter reference envelope (REFERENCE_ONLY).

    These are NOT OEM catalog values. Never present as production parameters.
    """
    operation: str              # "turning", "milling", "drilling"
    tool_material: str          # ToolMaterial member
    vc_min_m_min: float | None = None
    vc_max_m_min: float | None = None
    fn_min_mm_rev: float | None = None
    fn_max_mm_rev: float | None = None
    fz_min_mm_tooth: float | None = None
    fz_max_mm_tooth: float | None = None
    ap_min_mm: float | None = None
    ap_max_mm: float | None = None
    evidence_status: str = "REFERENCE_ONLY"
    source: str = "Programlar general industry envelope"


class MaterialRecord(BaseModel):
    """Full material catalog record for API responses."""

    # --- Identity ---
    material_id: str
    designation: str            # primary name (e.g. "42CrMo4")
    werkstoff_nr: str | None = None     # DIN Werkstoff number (e.g. "1.7225")
    standard_en: str | None = None     # EN designation
    standard_din: str | None = None    # DIN designation
    standard_aisi: str | None = None   # AISI/SAE designation
    standard_uns: str | None = None    # UNS designation
    aliases: list[str] = []

    # --- ISO Classification ---
    iso_group: str              # IsoMaterialGroup: P/M/K/N/S/H
    iso_subgroup: str           # IsoMaterialSubGroup: S_TITANIUM, S_NICKEL_HRSA, etc.
    material_family: str        # MaterialFamily member

    # --- Bulk physical properties (condition-independent) ---
    density_kg_m3: float | None = None
    elastic_modulus_gpa: float | None = None
    thermal_conductivity_w_mk: float | None = None
    specific_heat_j_kgk: float | None = None
    thermal_expansion_um_mk: float | None = None
    melting_point_deg_c: float | None = None

    # --- Conditions (condition-dependent mechanical properties) ---
    conditions: list[MaterialConditionRecord] = []

    # --- Machinability ---
    machinability: MaterialMachinabilityRecord | None = None

    # --- Tool compatibility ---
    tool_compatibility: list[MaterialToolCompatEntry] = []

    # --- Cutting references ---
    cutting_references: list[MaterialCuttingRef] = []

    # --- Evidence / provenance ---
    data_confidence: str = "VERIFIED_STANDARD"      # DataConfidence member
    source_document: str = ""
    evidence_status: str = "REFERENCE_ONLY"         # for cutting data
    notes: str | None = None


class MaterialSummary(BaseModel):
    """Aggregate catalog statistics."""
    material_count: int
    iso_group_counts: dict[str, int]
    family_counts: dict[str, int]
    source_title: str
    evidence_note: str


class MaterialListItem(BaseModel):
    """Compact list row for browse UI."""
    material_id: str
    designation: str
    werkstoff_nr: str | None
    standard_aisi: str | None
    iso_group: str
    iso_subgroup: str
    material_family: str
    data_confidence: str
    has_conditions: bool
    has_machinability: bool
    has_tool_compat: bool
    has_cutting_refs: bool
    aliases: list[str]


class MaterialDetail(BaseModel):
    """Full detail response for a single material."""
    record: MaterialRecord
    iso_group_label: str
    iso_subgroup_label: str
    family_label: str


class IsoGroupInfo(BaseModel):
    """Metadata for one ISO group."""
    code: str
    label: str
    description: str
    color_hint: str
