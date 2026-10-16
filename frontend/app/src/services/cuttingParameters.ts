import { api } from './apiClient'

export interface ParameterRange {
  parameter_type: string
  unit: string
  min_value: number
  max_value: number
  notes: string | null
}

export interface Provenance {
  source_reference: string | null
  page_section: string | null
  source_type: string
}

export interface MatchedScope {
  operation: string | null
  iso_material_group: string | null
  tool_material: string | null
}

export interface QueryResponse {
  matched: boolean
  match_level: string
  match_reason: string
  evidence_status: string
  authority_label: string
  limitation_note: string
  parameters: ParameterRange[]
  provenance: Provenance | null
  scope: MatchedScope
}

export interface SchemaResponse {
  operations: string[]
  iso_material_groups: string[]
  iso_material_labels: Record<string, string>
  tool_materials: string[]
}

export interface CalculateRequest {
  vc_m_min: number
  diameter_mm: number
  operation: string
  feed_per_tooth_mm?: number
  tooth_count?: number
  feed_per_rev_mm?: number
}

export interface CalculateResponse {
  rpm: number
  rpm_formula: string
  feed_rate_mm_min: number | null
  feed_rate_formula: string | null
  machine_limit_note: string
}

export function queryCuttingParameters(
  operation: string,
  isoMaterialGroup: string,
  toolMaterial?: string,
): Promise<QueryResponse> {
  const params = new URLSearchParams({ operation, iso_material_group: isoMaterialGroup })
  if (toolMaterial) params.set('tool_material', toolMaterial)
  return api<QueryResponse>(`/cutting-parameters/query?${params}`)
}

export function getCuttingParameterSchema(): Promise<SchemaResponse> {
  return api<SchemaResponse>('/cutting-parameters/schema')
}

export function calculateMachiningParameters(req: CalculateRequest): Promise<CalculateResponse> {
  return api<CalculateResponse>('/cutting-parameters/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
}
