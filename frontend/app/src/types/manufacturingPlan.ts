export type ManufacturingPlanStatus =
  | 'DRAFT'
  | 'ENGINEER_REVIEWED'
  | 'APPROVED'
  | 'REJECTED'
  | 'SUPERSEDED';

export type ReleaseGateStatus =
  | 'READY_FOR_ENGINEERING_REVIEW'
  | 'REVIEW_REQUIRED'
  | 'INCOMPLETE'
  | 'BLOCKED';

export type CompletenessStatus =
  | 'COMPLETE'
  | 'SUBSTANTIALLY_COMPLETE'
  | 'PARTIALLY_COMPLETE'
  | 'INCOMPLETE';

export type OpenItemSeverity = 'BLOCKING' | 'REVIEW_REQUIRED' | 'ADVISORY';
export type OpenItemStatus = 'OPEN' | 'RESOLVED' | 'WAIVED';

export interface ManufacturingPlanSummary {
  plan_id: string;
  source_id: string;
  drawing_number: string | null;
  revision: string | null;
  status: ManufacturingPlanStatus;
  release_gate: ReleaseGateStatus;
  overall_completeness: number;
  completeness_status: CompletenessStatus;
  open_items_count: number;
  operations_count: number;
  characteristics_count: number;
  traceability_fingerprint: string | null;
  created_at: string | null;
  updated_at: string | null;
  disclaimer: string;
  AUTO_GENERATED_PLAN_MARKED_APPROVED: boolean;
  generation_warnings: string[];
}

export interface ManufacturingOperation {
  op_id: string;
  op_number: number;
  setup_id: string;
  feature_id: string | null;
  operation_type: string;
  machine_id: string | null;
  machine_label: string | null;
  tool_id: string | null;
  holder_id: string | null;
  cutting_speed_m_min: number | null;
  feed_rate_mm_min: number | null;
  rpm: number | null;
  ap_mm: number | null;
  ae_mm: number | null;
  parameter_source: string;
  notes: string;
  REFERENCE_ONLY: boolean;
}

export interface ManufacturingSetup {
  setup_id: string;
  setup_number: number;
  label: string;
  machine_id: string | null;
  machine_label: string | null;
  orientation_note: string;
  fixturing_note: string;
  tool_ids: string[];
  operation_ids: string[];
  notes: string;
  REFERENCE_ONLY: boolean;
}

export interface InspectionPlanRow {
  row_id: string;
  char_id: string;
  char_label: string;
  char_type: string;
  criticality: string;
  stage: string;
  method: string;
  gage_suggestion: string | null;
  frequency: { frequency: string; sample_size: number | null };
  acceptance_criterion: string | null;
  status: string;
}

export interface FinalInspectionPlan {
  plan_id: string;
  rows: InspectionPlanRow[];
  coverage_rate: number;
  uninspected_chars: string[];
  disclaimer: string;
}

export interface ControlPlanRow {
  row_id: string;
  operation_no: string;
  char_label: string;
  char_type: string;
  criticality: string;
  specification: string | null;
  method: string;
  gage_suggestion: string | null;
  stage: string;
  frequency: { frequency: string };
  reaction_plan: string;
  responsibility: string | null;
}

export interface ControlPlan {
  plan_id: string;
  rows: ControlPlanRow[];
  status: string;
  disclaimer: string;
  AUTONOMOUS_NONCONFORMANCE_DISPOSITION: boolean;
}

export interface PlanCompleteness {
  requirements_coverage: number;
  feature_coverage: number;
  operation_coverage: number;
  machine_assignment_coverage: number;
  tool_assignment_coverage: number;
  holder_assignment_coverage: number;
  parameter_coverage: number;
  inspection_coverage: number;
  cycle_time_coverage: number;
  overall_completeness: number;
  completeness_status: CompletenessStatus;
}

export interface OpenItem {
  item_id: string;
  category: string;
  severity: OpenItemSeverity;
  description: string;
  related_step_id: string | null;
  related_char_id: string | null;
  resolution_hint: string;
  status: OpenItemStatus;
  notes: string;
}

export interface ProcessFlowNode {
  node_id: string;
  node_type: string;
  label: string;
  setup_id: string | null;
  op_id: string | null;
}

export interface ProcessFlow {
  flow_id: string;
  nodes: ProcessFlowNode[];
  edges: [string, string][];
  start_node_id: string | null;
  end_node_id: string | null;
}

export interface ManufacturingPlanDetail extends ManufacturingPlanSummary {
  characteristics: unknown[];
  setups: ManufacturingSetup[];
  operations: ManufacturingOperation[];
  tool_list: unknown[];
  machine_list: unknown[];
  parameter_table: unknown[];
  inspection_plan: FinalInspectionPlan | null;
  control_plan: ControlPlan | null;
  process_flow: ProcessFlow | null;
  completeness: PlanCompleteness;
  open_items: OpenItem[];
  pfmea_hooks: unknown[];
  generation_warnings: string[];
}

export interface ValidationFinding {
  code: string;
  severity: OpenItemSeverity;
  message: string;
  field: string | null;
  related_id: string | null;
}

export interface ValidationResult {
  plan_id: string;
  passed: boolean;
  blocking_count: number;
  review_required_count: number;
  advisory_count: number;
  findings: ValidationFinding[];
}

export interface GeneratePlanRequest {
  source_id: string;
  optimized_plan?: unknown;
  req_set?: unknown;
  drawing_number?: string;
  revision?: string;
  calibration_profile_ids?: string[];
}
