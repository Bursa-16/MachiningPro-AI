import api from './apiClient'

export interface CuttingToolCatalogRecord {
  stable_id: string
  manufacturer: string
  product_family: string | null
  product_name: string
  catalog_code: string | null
  tool_category: string
  tool_category_code: string
  tool_subcategory: string | null
  tool_type_code: string | null
  supported_operations: string[]
  iso_material_groups: string[]
  tool_material: string | null
  substrate_grade: string | null
  substrate_material_code: string | null
  coating: string | null
  coating_type: string | null
  coating_brand: string | null
  iso_insert_designation: string | null
  insert_shape: string | null
  insert_shape_code: string | null
  insert_ic_mm: number | null
  insert_thickness_mm: number | null
  nose_radius_mm: number | null
  clearance_angle_deg: number | null
  insert_tolerance_class: string | null
  insert_hand: string | null
  cutting_diameter_mm: number | null
  shank_diameter_mm: number | null
  overall_length_mm: number | null
  cutting_length_mm: number | null
  flute_length_mm: number | null
  number_of_flutes: number | null
  helix_angle_deg: number | null
  corner_radius_mm: number | null
  point_angle_deg: number | null
  shank_interface: string | null
  through_coolant: boolean | null
  max_rpm: number | null
  compatible_holder_interface: string | null
  arbor_interface: string | null
  max_ap_mm: number | null
  max_ae_mm: number | null
  vc_min_mpm: number | null
  vc_max_mpm: number | null
  fz_min_mm: number | null
  fz_max_mm: number | null
  fn_min_mm: number | null
  fn_max_mm: number | null
  ap_max_mm: number | null
  source_title: string
  source_authority: string
  evidence_status: string
  source_note: string | null
  missing_fields: string[]
}

export interface CuttingToolCatalogSummary {
  tool_count: number
  manufacturer_count: number
  category_count: number
  tool_material_count: number
  manufacturers: string[]
  categories: string[]
  tool_materials: string[]
  iso_material_groups: string[]
  source_title: string
  evidence_status: string
}

export interface CuttingToolSchema {
  manufacturers: string[]
  categories: string[]
  operations: string[]
  tool_materials: string[]
  iso_material_groups: string[]
  substrate_codes: string[]
  coating_types: string[]
  tool_count: number
  evidence_status: string
}

export interface CuttingToolListParams {
  manufacturer?: string
  category?: string
  operation?: string
  tool_material?: string
  iso_group?: string
  substrate_material_code?: string
  coating_type?: string
}

export async function fetchCuttingToolSchema(): Promise<CuttingToolSchema> {
  return api<CuttingToolSchema>('/cutting-tools/schema')
}

export async function fetchCuttingTools(params: CuttingToolListParams = {}): Promise<CuttingToolCatalogRecord[]> {
  const query = new URLSearchParams()
  if (params.manufacturer) query.set('manufacturer', params.manufacturer)
  if (params.category) query.set('category', params.category)
  if (params.operation) query.set('operation', params.operation)
  if (params.tool_material) query.set('tool_material', params.tool_material)
  if (params.iso_group) query.set('iso_group', params.iso_group)
  if (params.substrate_material_code) query.set('substrate_material_code', params.substrate_material_code)
  if (params.coating_type) query.set('coating_type', params.coating_type)
  const qs = query.toString()
  return api<CuttingToolCatalogRecord[]>(`/cutting-tools${qs ? '?' + qs : ''}`)
}

export async function fetchCuttingToolDetail(id: string): Promise<CuttingToolCatalogRecord> {
  return api<CuttingToolCatalogRecord>(`/cutting-tools/${id}`)
}
