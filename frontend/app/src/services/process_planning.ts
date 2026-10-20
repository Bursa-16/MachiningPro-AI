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
  // Cycle-time foundation explicit job inputs
  cutting_path_length_mm?: number | null
  cutting_path_source?: string | null
  rapid_distance_mm?: number | null
  dwell_sec?: number | null
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

export type MetricStatus = 'AVAILABLE' | 'NOT_AVAILABLE' | 'INSUFFICIENT_DATA' | 'NOT_APPLICABLE'

// ── Cycle-time types (PROCESS_PLAN_CYCLE_TIME_FOUNDATION_01) ──────────────────

export type CycleTimeStatus = 'COMPLETE' | 'PARTIAL' | 'INSUFFICIENT_DATA' | 'NOT_APPLICABLE'
export type CycleTimeScope = 'CUTTING_ONLY' | 'CUTTING_PLUS_EXPLICIT_NONCUTTING' | 'COMPLETE_EXPLICIT_CYCLE'
export type TimeComponentStatus = 'AVAILABLE' | 'NOT_AVAILABLE' | 'INSUFFICIENT_DATA' | 'NOT_APPLICABLE'

export interface TimeComponent {
  component_id: string
  component_type: string
  status: TimeComponentStatus
  time_sec_min: number | null
  time_sec_max: number | null
  distance_mm: number | null
  rate_mm_min: number | null
  formula_reference: string | null
  input_provenance: string | null
  missing_inputs: string[]
  limitations: string[]
}

export interface StepCycleTime {
  status: CycleTimeStatus
  scope: CycleTimeScope
  cutting_time: TimeComponent | null
  rapid_time: TimeComponent | null
  dwell_time: TimeComponent | null
  tool_change_time: null
  known_subtotal_sec_min: number | null
  known_subtotal_sec_max: number | null
  total_cycle_time: null
  components: TimeComponent[]
  missing_inputs: string[]
  limitations: string[]
}

export interface EngineeringMetric {
  metric_id: string
  metric_name: string
  status: MetricStatus
  value: number | null
  min_value: number | null
  max_value: number | null
  unit: string | null
  formula_reference: string | null
  inputs_used: string[]
  missing_inputs: string[]
  explanation: string | null
}

export interface StepEngineeringMetrics {
  metrics: EngineeringMetric[]
  metrics_available_count: number
  metrics_not_available_count: number
  metrics_insufficient_data_count: number
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
  engineering_metrics: StepEngineeringMetrics | null
  cycle_time: StepCycleTime | null
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
  metrics_available_count: number
  metrics_not_available_count: number
  metrics_insufficient_data_count: number
  cycle_time_complete_count: number
  cycle_time_partial_count: number
  cycle_time_insufficient_count: number
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
