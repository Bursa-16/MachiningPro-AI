import api from './apiClient'
import type { RuleResult } from './compatibility'

export interface SelectionSchemaResponse {
  machines: Array<{ id: string; display: string }>
  cutting_tools: Array<{ id: string; display: string }>
  valid_operations: string[]
  valid_iso_groups: string[]
}

export interface SelectionCriterionResult {
  criterion_id: string
  applicable: boolean
  value: string | null
  note: string
}

export interface CandidateEntry {
  candidate_status: 'RANKED' | 'REJECTED' | 'NOT_RANKABLE'
  rank: number | null
  engineering_tie: boolean
  engineering_tie_reason: string | null
  ahead_reason: string | null
  machine_id: string
  holder_id: string
  cutting_tool_id: string
  compatibility_status: 'COMPATIBLE' | 'INCOMPATIBLE' | 'INSUFFICIENT_DATA'
  compatibility_trace: RuleResult[]
  selection_criteria_trace: SelectionCriterionResult[]
  rejection_reason: string | null
  not_rankable_reason: string | null
  rpm_margin_pct: number | null
  reference_guidance_available: boolean
  calculated_rpm: number | null
}

export interface SelectionRequest {
  operation: string
  iso_material_group: string
  machine_id?: string | null
  cutting_tool_id?: string | null
  cutting_speed_m_min?: number | null
  tool_diameter_mm?: number | null
  max_eligible_returned?: number
}

export interface SelectionResponse {
  overall_state:
    | 'SELECTION_AVAILABLE'
    | 'NO_COMPATIBLE_CONFIGURATION'
    | 'COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE'
    | 'INSUFFICIENT_DATA_FOR_SELECTION'
  operation: string
  iso_material_group: string
  candidates_evaluated: number
  compatible_count: number
  incompatible_count: number
  not_rankable_count: number
  ranked_candidates: CandidateEntry[]
  rejected_sample: CandidateEntry[]
  not_rankable_sample: CandidateEntry[]
  disclaimer: string
}

export async function fetchSelectionSchema(): Promise<SelectionSchemaResponse> {
  return api<SelectionSchemaResponse>('/selection/schema')
}

export async function evaluateSelection(
  req: SelectionRequest
): Promise<SelectionResponse> {
  return api<SelectionResponse>('/selection/evaluate', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}
