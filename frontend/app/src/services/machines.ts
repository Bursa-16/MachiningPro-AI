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
  // Spindle
  spindle_max_rpm: number | null
  spindle_min_rpm: number | null
  spindle_power_kw: number | null
  spindle_power_continuous_kw: number | null
  spindle_power_peak_kw: number | null
  spindle_torque_nm: number | null
  spindle_torque_continuous_nm: number | null
  spindle_torque_peak_nm: number | null
  spindle_torque_at_rpm: number | null
  spindle_interface: string | null
  spindle_interfaces_supported: string[]
  // Axes & kinematics
  axis_summary: string | null
  kinematics_type: string | null
  // Workspace
  travel_x_mm: number | null
  travel_y_mm: number | null
  travel_z_mm: number | null
  table_length_mm: number | null
  table_width_mm: number | null
  table_load_kg: number | null
  max_turning_diameter_mm: number | null
  max_turning_length_mm: number | null
  bar_capacity_mm: number | null
  // Tool system
  tool_magazine_capacity: number | null
  tool_magazine_type: string | null
  tool_interface: string | null
  max_tool_diameter_mm: number | null
  max_tool_diameter_adj_mm: number | null
  max_tool_length_mm: number | null
  atc_chip_to_chip_sec: number | null
  atc_tool_to_tool_sec: number | null
  // Dynamics
  rapid_traverse_mpm: number | null
  rapid_x_mpm: number | null
  rapid_y_mpm: number | null
  rapid_z_mpm: number | null
  max_cutting_feed_mm_min: number | null
  // Coolant
  through_spindle_coolant: boolean | null
  coolant_pressure_bar: number | null
  mql_support: boolean | null
  flood_coolant: boolean
  chip_conveyor: boolean | null
  // Features
  has_subspindle: boolean
  has_y_axis: boolean
  has_live_tooling: boolean
  has_b_axis: boolean
  has_pallet_changer: boolean
  // Process capabilities
  capable_tapping: boolean | null
  capable_boring: boolean | null
  capable_threading: boolean | null
  capable_reaming: boolean | null
  capable_5axis_simultaneous: boolean | null
  capable_3plus2: boolean | null
  // Control
  controller_family: string | null
  controller_model: string | null
  controller_generation: string | null
  nc_dialect: string | null
  // Accuracy
  positioning_accuracy_um: number | null
  repeatability_um: number | null
  // Envelope
  machine_weight_kg: number | null
  // Lineage
  year_introduced: number | null
  year_discontinued: number | null
  country_of_origin: string | null
  // Evidence
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
  spindle_interface?: string
  min_spindle_rpm?: number
  min_power_kw?: number
  has_5axis?: boolean
  controller_family?: string
}

export interface MachineSearchParams extends MachineListParams {
  q: string
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
  if (params.spindle_interface) query.set('spindle_interface', params.spindle_interface)
  if (params.min_spindle_rpm !== undefined) query.set('min_spindle_rpm', String(params.min_spindle_rpm))
  if (params.min_power_kw !== undefined) query.set('min_power_kw', String(params.min_power_kw))
  if (params.has_5axis !== undefined) query.set('has_5axis', String(params.has_5axis))
  if (params.controller_family) query.set('controller_family', params.controller_family)
  const qs = query.toString()
  return api<MachineCatalogRecord[]>(`/machines${qs ? '?' + qs : ''}`)
}

export async function searchMachines(params: MachineSearchParams): Promise<MachineCatalogRecord[]> {
  const query = new URLSearchParams()
  query.set('q', params.q)
  if (params.manufacturer) query.set('manufacturer', params.manufacturer)
  if (params.machine_type) query.set('machine_type', params.machine_type)
  if (params.spindle_interface) query.set('spindle_interface', params.spindle_interface)
  if (params.min_spindle_rpm !== undefined) query.set('min_spindle_rpm', String(params.min_spindle_rpm))
  if (params.min_power_kw !== undefined) query.set('min_power_kw', String(params.min_power_kw))
  if (params.has_5axis !== undefined) query.set('has_5axis', String(params.has_5axis))
  return api<MachineCatalogRecord[]>(`/machines/search?${query.toString()}`)
}

export async function fetchMachineDetail(id: string): Promise<MachineCatalogRecord> {
  return api<MachineCatalogRecord>(`/machines/${id}`)
}

export async function fetchMachineCapabilities(id: string): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>(`/machines/${id}/capabilities`)
}

export async function fetchMachineSpindle(id: string): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>(`/machines/${id}/spindle`)
}

export async function fetchMachineCompatibility(
  id: string,
  spindleInterface?: string
): Promise<Record<string, unknown>> {
  const qs = spindleInterface ? `?spindle_interface=${encodeURIComponent(spindleInterface)}` : ''
  return api<Record<string, unknown>>(`/machines/${id}/compatibility${qs}`)
}
