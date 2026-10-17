import api from './apiClient'

export interface SchemaEntry {
  id: string
  display: string
}

export interface CompatibilitySchemaResponse {
  machines: SchemaEntry[]
  holders: SchemaEntry[]
  cutting_tools: SchemaEntry[]
  valid_operations: string[]
  valid_iso_groups: string[]
}

export interface CompatibilityRequest {
  machine_id: string
  holder_id: string
  cutting_tool_id: string
  operation: string
  iso_material_group: string
  cutting_speed_m_min?: number | null
  tool_diameter_mm?: number | null
}

export interface RuleResult {
  rule_id: string
  status: 'PASS' | 'FAIL' | 'UNKNOWN' | 'NOT_APPLICABLE'
  reason_code: string
  detail: string | null
}

export interface CompatibilityResponse {
  overall_status: 'COMPATIBLE' | 'INCOMPATIBLE' | 'INSUFFICIENT_DATA'
  machine_id: string
  holder_id: string
  cutting_tool_id: string
  operation: string
  iso_material_group: string
  rule_results: RuleResult[]
  hard_failures: string[]
  unknown_rules: string[]
  missing_fields: string[]
  calculated_rpm: number | null
  reference_guidance_available: boolean
  disclaimer: string
}

export async function fetchCompatibilitySchema(): Promise<CompatibilitySchemaResponse> {
  return api<CompatibilitySchemaResponse>('/compatibility/schema')
}

export async function evaluateCompatibility(
  req: CompatibilityRequest
): Promise<CompatibilityResponse> {
  return api<CompatibilityResponse>('/compatibility/evaluate', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}
