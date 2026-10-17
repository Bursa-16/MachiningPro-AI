import api from './apiClient'

export interface ToolHolderCatalogRecord {
  stable_id: string
  manufacturer: string
  product_family: string | null
  product_name: string
  catalog_code: string | null
  holder_category: string
  holder_subcategory: string | null
  machine_interface: string
  machine_interface_key: string
  taper: string | null
  tool_interface: string
  tool_interface_key: string
  collet_system: string | null
  clamping_range_min_mm: number | null
  clamping_range_max_mm: number | null
  compatible_shank_types: string[]
  gauge_length_mm: number | null
  projection_mm: number | null
  overall_length_mm: number | null
  body_diameter_mm: number | null
  nose_diameter_mm: number | null
  weight_kg: number | null
  max_rpm: number | null
  balance_grade: string | null
  runout_um: number | null
  clamping_force_n: number | null
  max_torque_nm: number | null
  through_coolant: boolean | null
  coolant_pressure_bar: number | null
  supported_processes: string[]
  holder_notes: string | null
  compatible_collet_family: string | null
  compatible_tool_shank_family: string | null
  source_title: string
  source_authority: string
  evidence_status: string
  source_note: string | null
  missing_fields: string[]
}

export interface ToolHolderCatalogSummary {
  holder_count: number
  manufacturer_count: number
  category_count: number
  machine_interface_count: number
  tool_interface_count: number
  manufacturers: string[]
  categories: string[]
  machine_interfaces: string[]
  tool_interfaces: string[]
  source_title: string
  evidence_status: string
}

export interface ToolHolderSchema {
  manufacturers: string[]
  categories: string[]
  machine_interfaces: string[]
  tool_interfaces: string[]
  collet_families: string[]
  holder_count: number
  evidence_status: string
}

export interface ToolHolderListParams {
  manufacturer?: string
  category?: string
  machine_interface?: string
  tool_interface?: string
  collet_family?: string
}

export async function fetchToolHolderSchema(): Promise<ToolHolderSchema> {
  return api<ToolHolderSchema>('/tool-holders/schema')
}

export async function fetchToolHolders(params: ToolHolderListParams = {}): Promise<ToolHolderCatalogRecord[]> {
  const query = new URLSearchParams()
  if (params.manufacturer) query.set('manufacturer', params.manufacturer)
  if (params.category) query.set('category', params.category)
  if (params.machine_interface) query.set('machine_interface', params.machine_interface)
  if (params.tool_interface) query.set('tool_interface', params.tool_interface)
  if (params.collet_family) query.set('collet_family', params.collet_family)
  const qs = query.toString()
  return api<ToolHolderCatalogRecord[]>(`/tool-holders${qs ? '?' + qs : ''}`)
}

export async function fetchToolHolderDetail(id: string): Promise<ToolHolderCatalogRecord> {
  return api<ToolHolderCatalogRecord>(`/tool-holders/${id}`)
}
