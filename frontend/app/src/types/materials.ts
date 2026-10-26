// Material Intelligence Foundation — EPIC_01

export interface MaterialHardnessEntry {
  scale: 'HB' | 'HRC' | 'HRB' | 'HV'
  value_min: number
  value_max: number
  confidence: string
  source: string
}

export interface MaterialConditionRecord {
  condition_code: string
  condition_label: string
  hardness: MaterialHardnessEntry[]
  tensile_strength_mpa: number | null
  yield_strength_mpa: number | null
  elongation_pct: number | null
  confidence: string
  source: string
}

export interface MaterialMachinabilityRecord {
  machinability_index: number | null
  chip_formation: string | null
  work_hardening: string | null
  bue_tendency: string | null
  abrasiveness: string | null
  thermal_load: string | null
  cutting_force: string | null
  tool_wear_rate: string | null
  coolant_guidance: string | null
  notes: string | null
  evidence_status: string
  source: string
}

export interface MaterialToolCompatEntry {
  tool_material: string
  rating: 'RECOMMENDED' | 'ACCEPTABLE' | 'CONDITIONAL' | 'NOT_RECOMMENDED' | 'INSUFFICIENT_DATA'
  condition_notes: string | null
  evidence_status: string
  source: string
}

export interface MaterialCuttingRef {
  operation: string
  tool_material: string
  vc_min_m_min: number | null
  vc_max_m_min: number | null
  fn_min_mm_rev: number | null
  fn_max_mm_rev: number | null
  fz_min_mm_tooth: number | null
  fz_max_mm_tooth: number | null
  ap_min_mm: number | null
  ap_max_mm: number | null
  evidence_status: string
  source: string
}

export interface MaterialRecord {
  material_id: string
  designation: string
  werkstoff_nr: string | null
  standard_en: string | null
  standard_din: string | null
  standard_aisi: string | null
  standard_uns: string | null
  aliases: string[]
  iso_group: string
  iso_subgroup: string
  material_family: string
  density_kg_m3: number | null
  elastic_modulus_gpa: number | null
  thermal_conductivity_w_mk: number | null
  specific_heat_j_kgk: number | null
  thermal_expansion_um_mk: number | null
  melting_point_deg_c: number | null
  conditions: MaterialConditionRecord[]
  machinability: MaterialMachinabilityRecord | null
  tool_compatibility: MaterialToolCompatEntry[]
  cutting_references: MaterialCuttingRef[]
  data_confidence: string
  source_document: string
  evidence_status: string
  notes: string | null
}

export interface MaterialListItem {
  material_id: string
  designation: string
  werkstoff_nr: string | null
  standard_aisi: string | null
  iso_group: string
  iso_subgroup: string
  material_family: string
  data_confidence: string
  has_conditions: boolean
  has_machinability: boolean
  has_tool_compat: boolean
  has_cutting_refs: boolean
  aliases: string[]
}

export interface MaterialDetail {
  record: MaterialRecord
  iso_group_label: string
  iso_subgroup_label: string
  family_label: string
}

export interface MaterialSummary {
  material_count: number
  iso_group_counts: Record<string, number>
  family_counts: Record<string, number>
  source_title: string
  evidence_note: string
}

export interface IsoGroupInfo {
  code: string
  label: string
  description: string
  color_hint: string
}
