import api from './apiClient'

export interface MachineCatalogRecord {
  stable_id: string
  manufacturer: string
  model: string
  family: string | null
  machine_type: string
  machine_type_code: string
  supported_processes: string[]
  axis_count: number
  simultaneous_axis_count: number | null
  turning_capable: boolean
  milling_capable: boolean
  drilling_capable: boolean
  spindle_max_rpm: number | null
  spindle_power_kw: number | null
  spindle_torque_nm: number | null
  spindle_interface: string | null
  travel_x_mm: number | null
  travel_y_mm: number | null
  travel_z_mm: number | null
  table_length_mm: number | null
  table_width_mm: number | null
  table_load_kg: number | null
  max_turning_diameter_mm: number | null
  max_turning_length_mm: number | null
  bar_capacity_mm: number | null
  tool_magazine_capacity: number | null
  tool_interface: string | null
  max_tool_diameter_mm: number | null
  max_tool_length_mm: number | null
  rapid_traverse_mpm: number | null
  machine_weight_kg: number | null
  controller_family: string | null
  source_title: string
  evidence_status: string
  source_note: string | null
  missing_fields: string[]
}

export interface MachineCatalogSummary {
  machine_count: number
  manufacturer_count: number
  machine_type_count: number
  manufacturers: string[]
  machine_types: string[]
  source_title: string
  evidence_status: string
}

export interface MachineSchema {
  manufacturers: string[]
  machine_types: string[]
  processes: string[]
  axis_count_options: number[]
  machine_count: number
  evidence_status: string
}

export interface MachineListParams {
  manufacturer?: string
  machine_type?: string
  process?: string
  axis_count?: number
}

export async function fetchMachineSchema(): Promise<MachineSchema> {
  return api<MachineSchema>('/machines/schema')
}

export async function fetchMachineSummary(): Promise<MachineCatalogSummary> {
  return api<MachineCatalogSummary>('/machines/summary')
}

export async function fetchMachines(params: MachineListParams = {}): Promise<MachineCatalogRecord[]> {
  const query = new URLSearchParams()
  if (params.manufacturer) query.set('manufacturer', params.manufacturer)
  if (params.machine_type) query.set('machine_type', params.machine_type)
  if (params.process) query.set('process', params.process)
  if (params.axis_count !== undefined) query.set('axis_count', String(params.axis_count))
  const qs = query.toString()
  return api<MachineCatalogRecord[]>(`/machines${qs ? '?' + qs : ''}`)
}

export async function fetchMachineDetail(id: string): Promise<MachineCatalogRecord> {
  return api<MachineCatalogRecord>(`/machines/${id}`)
}
