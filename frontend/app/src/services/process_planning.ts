import api from './apiClient'

export interface OperationStepRequest {
  step_id: string
  sequence_number: number
  operation: string
  feature_id?: string | null
  machine_id?: string | null
  cutting_tool_id?: string | null
  cutting_speed_m_min?: number | null
  tool_diameter_mm?: number | null
  predecessor_step_ids?: string[]
}

export interface ProcessPlanRequest {
  part_name: string
  material_iso_group: string
  operations: OperationStepRequest[]
}

export interface SequenceRuleWarning {
  rule_id: string
  reason_code: string
  explanation: string
  affected_step_ids: string[]
}

export interface CuttingParameterRef {
  record_id: string
  parameter_type: string
  min_value: number
  max_value: number
  unit: string
  evidence_status: string
  source_reference: string | null
}

export interface CandidateConfigSummary {
  machine_id: string
  holder_id: string
  cutting_tool_id: string
  rank: number | null
  engineering_tie: boolean
  compatibility_status: string
}

export interface PlanStep {
  step_id: string
  sequence_number: number
  operation: string
  feature_id: string | null
  planning_status: 'PLANNED' | 'BLOCKED' | 'INSUFFICIENT_DATA' | 'NOT_SUPPORTED'
  setup_group: string
  selection_state: string | null
  candidates_evaluated: number
  compatible_count: number
  incompatible_count: number
  not_rankable_count: number
  candidate_configurations: CandidateConfigSummary[]
  engineering_tie: boolean
  engineering_tie_count: number
  cutting_parameter_references: CuttingParameterRef[]
  cutting_parameter_reference_available: boolean
  compatibility_trace: Record<string, unknown>[]
  selection_criteria_trace: Record<string, unknown>[]
  predecessor_step_ids: string[]
  sequence_warnings: SequenceRuleWarning[]
  rejected_sample: Record<string, unknown>[]
  not_rankable_sample: Record<string, unknown>[]
  missing_data: string[]
  planning_notes: string | null
}

export interface ProcessPlanSummary {
  step_count: number
  planned_count: number
  blocked_count: number
  insufficient_data_count: number
  not_supported_count: number
  machine_ids_used: string[]
  holder_ids_used: string[]
  tool_ids_used: string[]
  engineering_tie_count: number
  missing_data_summary: string[]
  sequence_rule_warning_count: number
}

export interface ProcessPlanResponse {
  part_name: string
  material_iso_group: string
  plan_status: 'PLAN_COMPLETE' | 'PLAN_PARTIAL' | 'PLAN_BLOCKED' | 'PLAN_INSUFFICIENT_DATA'
  steps: PlanStep[]
  dependency_graph_valid: boolean
  dependency_violations: string[]
  sequence_rules_applied: Record<string, unknown>[]
  alternative_valid_sequence_supported: boolean
  sequence_not_uniquely_determined: boolean
  summary: ProcessPlanSummary
  limitations: string[]
  provenance: string
  disclaimer: string
}

export interface ProcessPlanningSchema {
  machines: { id: string; display: string }[]
  cutting_tools: { id: string; display: string }[]
  valid_operations: string[]
  valid_iso_groups: string[]
}

export async function fetchProcessPlanningSchema(): Promise<ProcessPlanningSchema> {
  return api<ProcessPlanningSchema>('/process-planning/schema')
}

export async function generateProcessPlan(
  req: ProcessPlanRequest,
): Promise<ProcessPlanResponse> {
  return api<ProcessPlanResponse>('/process-planning/plan', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}
