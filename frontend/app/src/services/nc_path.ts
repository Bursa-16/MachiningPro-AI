import api from './apiClient'

// ---------------------------------------------------------------------------
// Request / Response types
// ---------------------------------------------------------------------------

export interface NcAnalyzeRequest {
  nc_text: string
  source_name?: string | null
  // Supply (0, 0, 0) to declare program starts at origin.
  // UNKNOWN_INITIAL_POSITION_GUESSED=NO — omit to let parser skip unknowns.
  initial_x?: number | null
  initial_y?: number | null
  initial_z?: number | null
  // Optional feed/spindle validation context (NC_FEED_SPINDLE_PROGRAM_VALIDATION_01)
  // NC_PROGRAM_AUTOMATIC_OPERATION_CLASSIFICATION=NO — caller must supply explicitly
  machine_id?: string | null
  cutting_tool_id?: string | null
  tool_holder_id?: string | null
  operation?: string | null
  material_iso_group?: string | null
  // NC_PROGRAM_TRACEABILITY_AND_AUDIT_01 — optional pass-through
  review_id?: string | null
  process_step_id?: string | null
}

// ---------------------------------------------------------------------------
// NC Program Validation types
// ---------------------------------------------------------------------------

export type NCValidationSeverityValue =
  | 'BLOCKING'
  | 'WARNING'
  | 'ADVISORY'
  | 'INFO'
  | 'INSUFFICIENT_DATA'
  | 'NOT_APPLICABLE'

export type NCValidationStatusValue =
  | 'WITHIN_LIMIT'
  | 'EXCEEDS_LIMIT'
  | 'WITHIN_REFERENCE_RANGE'
  | 'BELOW_REFERENCE_RANGE'
  | 'ABOVE_REFERENCE_RANGE'
  | 'NOT_COMPARABLE'
  | 'INSUFFICIENT_DATA'
  | 'NOT_APPLICABLE'

export interface NCValidationFinding {
  check_id: string
  severity: NCValidationSeverityValue
  status: NCValidationStatusValue
  observed_value: number | null
  observed_unit: string | null
  limit_or_reference: number | null
  limit_unit: string | null
  limit_source: string | null
  message_key: string
  limitations: string[]
  // Immutable safety flags — always false
  nc_commanded_spindle_speed_equals_actual_rpm: false
  nc_commanded_feed_equals_actual_feed: false
}

export interface NCProgramValidationSummary {
  // Feed/spindle evidence from NC
  nc_commanded_feed_mm_min: number | null
  nc_commanded_feed_mm_rev: number | null
  nc_feed_mode: string | null
  nc_commanded_spindle_rpm: number | null
  nc_spindle_state: string | null
  // Calculated engineering values
  calculated_cutting_speed_m_min: number | null
  calculated_feed_per_tooth_mm: number | null
  calculated_feed_per_rev_mm: number | null
  // RPM limit findings
  machine_rpm_limit_check: NCValidationFinding | null
  tool_rpm_limit_check: NCValidationFinding | null
  holder_rpm_limit_check: NCValidationFinding | null
  effective_rpm_limit_check: NCValidationFinding | null
  // Engineering reference findings (ADVISORY)
  cutting_speed_check: NCValidationFinding | null
  feed_per_tooth_check: NCValidationFinding | null
  feed_per_rev_check: NCValidationFinding | null
  // Counters
  blocking_count: number
  warning_count: number
  advisory_count: number
  insufficient_data_count: number
  // Diagnostics
  limitations: string[]
  evidence_sources: string[]
  // Immutable safety flags — always false
  nc_commanded_spindle_speed_equals_actual_rpm: false
  nc_commanded_feed_equals_actual_feed: false
  nc_commanded_feed_equals_recommended_feed: false
  reference_range_validation_is_optimization: false
  nc_program_automatic_operation_classification: false
  machine_feed_limit_validation_implemented: false
  g84_pitch_validation_implemented: false
  generic_feed_without_spindle_warning_implemented: false
  spindle_direction_compatibility_check_implemented: false
}

export type NcAnalysisStatusValue =
  | 'COMPLETE'
  | 'PARTIAL'
  | 'UNSUPPORTED_SEMANTICS'
  | 'INVALID_PROGRAM'
  | 'INSUFFICIENT_DATA'

// NC Motion Segment — bounded by T+M6 tool-change events.
// NC_TOOL_ID_AUTOMATICALLY_MAPPED_TO_CATALOG=NO — tool_id_raw is the raw NC T-word.
export interface NcMotionSegment {
  segment_id: string
  start_line: number
  end_line: number
  tool_id_raw: string | null          // NC T-word; NOT a catalog tool ID
  feed_motion_distance_mm: number
  rapid_motion_distance_mm: number
  linear_motion_count: number
  arc_motion_count: number
  commanded_feed_min: number | null
  commanded_feed_max: number | null
  feed_change_count: number
  analysis_status: NcAnalysisStatusValue
  unsupported_features: string[]
  // Feed/spindle Phase 2 fields (NC_FEED_SPINDLE_PROGRAM_VALIDATION_01)
  feed_mode: string | null                // "G94" | "G95" | "G93"
  commanded_feed_mm_rev: number | null    // F value when G95 active (mm/rev)
  commanded_spindle_rpm: number | null    // S value when G97 active (RPM)
  spindle_state: string | null           // "M3_CW" | "M4_CCW" | "M5_STOP"
  spindle_direction: string | null       // "CW" | "CCW"
  // Immutable safety flags
  nc_feed_move_equals_confirmed_cutting: false
  arc_chord_approximation_used: false
}

export interface NcMotionResult {
  parser_profile: string
  parser_version: string
  analysis_status: NcAnalysisStatusValue
  feed_distance_mm: number
  rapid_distance_mm: number
  block_count_total: number
  supported_motion_count: number
  unsupported_construct_count: number
  unknown_start_count: number
  tool_change_count: number
  arc_motion_count: number
  units_declared: string | null
  nc_commanded_feed_mm_min: number | null
  // Feed/spindle Phase 2 fields (NC_FEED_SPINDLE_PROGRAM_VALIDATION_01)
  nc_feed_mode: string | null               // "G94" | "G95" | "G93"
  nc_commanded_spindle_rpm: number | null   // S word (G97 only, NC_COMMANDED_SPINDLE_SPEED_EQUALS_ACTUAL_RPM=NO)
  nc_spindle_state: string | null          // "M3_CW" | "M4_CCW" | "M5_STOP"
  unsupported_features: string[]
  limitations: string[]
  segments: NcMotionSegment[]
  // Safety flags — always false
  nc_feed_move_equals_confirmed_cutting: false
  arc_chord_approximation_used: false
  nc_file_executed: false
}

export interface PathEvidence {
  evidence_id: string
  source_type: string
  semantic_type: string
  distance_mm: number
  validation_status: string
  source_name_safe: string | null
  source_reference_safe: string | null
  units_original: string | null
  units_canonical: string
  parser_profile: string | null
  parser_version: string | null
  analysis_status: string | null
  supported_motion_count: number
  unsupported_construct_count: number
  unknown_start_count: number
  tool_change_count: number
  nc_commanded_feed_mm_min: number | null
  unsupported_features: string[]
  limitations: string[]
  operation_association: string | null
  // Segment provenance (optional — present when evidence comes from a specific segment)
  // NC_TOOL_ID_AUTOMATICALLY_MAPPED_TO_CATALOG=NO
  segment_id?: string | null
  segment_start_line?: number | null
  segment_end_line?: number | null
  tool_id_raw?: string | null
  linear_motion_count?: number
  arc_motion_count?: number
  feed_change_count?: number
  // Canned cycle provenance (optional — present when evidence includes canned cycle data)
  // CANNED_CYCLE_MOTION_AUTOMATICALLY_PROMOTED_TO_CUTTING=NO
  // CANNED_CYCLE_AUTOMATIC_OPERATION_MAPPING=NO
  canned_cycle_code?: number | null         // G-code number (81..85)
  hole_count?: number | null                // number of cycle invocations
  cycle_repeat_count?: number | null        // L-word count (future)
  programmed_feed_distance_mm?: number | null  // canned feed strokes only
  programmed_rapid_distance_mm?: number | null // canned rapid paths only
  dwell_command_raw?: number | null         // G82 P-word; units controller-specific
  // Safety flags — always false
  nc_feed_move_equals_confirmed_cutting: false
  arc_chord_approximation_used: false
}

// ---------------------------------------------------------------------------
// NC Engineering Review types (NC_PROGRAM_ENGINEERING_REVIEW_01)
// ---------------------------------------------------------------------------

export type ParserFeatureStateValue =
  | 'SUPPORTED'
  | 'BOUNDED'
  | 'DEFERRED'
  | 'UNSUPPORTED'
  | 'INSUFFICIENT_SEMANTICS'

export type EngReviewStatusValue =
  | 'PASS_WITH_EVIDENCE'
  | 'PASS_WITH_ADVISORIES'
  | 'REVIEW_REQUIRED'
  | 'BLOCKED_BY_KNOWN_LIMIT'
  | 'INSUFFICIENT_DATA'
  | 'UNSUPPORTED_FEATURES_PRESENT'

// NC_PROGRAM_TRACEABILITY_AND_AUDIT_01
// ENGINEERING_STATUS_EQUALS_TRACEABILITY_STATUS=NO — separate model
export type TraceabilityStatusValue =
  | 'TRACEABLE'
  | 'PARTIALLY_TRACEABLE'
  | 'INSUFFICIENT_TRACEABILITY_DATA'

export interface NCAnalysisTraceability {
  review_id: string | null
  program_fingerprint: string | null
  configuration_fingerprint: string | null
  analysis_fingerprint: string | null
  traceability_status: TraceabilityStatusValue
  generated_at: string
  review_schema_version: string
  parser_profile: string
  parser_version: string
  machine_id: string | null
  cutting_tool_id: string | null
  tool_holder_id: string | null
  operation: string | null
  process_step_id: string | null
  material_iso_group: string | null
  provenance_summary: string[]
  source_counts: Record<string, number>
  limitations_count: number
  // Immutable safety flags — always false
  hash_equals_digital_signature: false
  hash_equals_approval: false
  hash_equals_certification: false
  false_immutable_audit_claim: false
}

export interface ParserFeatureCoverage {
  feature: string
  state: ParserFeatureStateValue
  detected: boolean
  note: string | null
}

export interface CannedCycleNote {
  cycle_code_str: string
  state: ParserFeatureStateValue
  bounded_reason: string | null
  detected_limitations: string[]
  // Safety flag — always false
  bounded_canned_cycle_mislabeled_complete: false
}

export interface EquipmentSummary {
  machine_id: string | null
  machine_display: string | null
  cutting_tool_id: string | null
  cutting_tool_display: string | null
  tool_holder_id: string | null
  tool_holder_display: string | null
  machine_spindle_max_rpm: number | null
  tool_max_rpm: number | null
  holder_max_rpm: number | null
  effective_rpm_limit: number | null
  effective_rpm_limit_source: string | null
  missing_fields: string[]
}

export interface EngReviewFinding {
  finding_code: string
  category: string
  severity: NCValidationSeverityValue
  title_key: string
  message_key: string
  observed_value: number | null
  limit_value: number | null
  unit: string | null
  source: string | null
  evidence_type: string | null
  segment_id: string | null
  limitation: string | null
}

export interface NCProgramEngineeringReview {
  // A. Program Identity
  source_name_safe: string | null
  parser_profile: string
  parser_version: string
  review_schema_version: string
  units_declared: string | null
  analysis_status: string
  segment_count: number
  tool_change_count: number
  supported_motion_count: number
  unsupported_construct_count: number
  arc_motion_count: number
  // B. Parser Coverage
  feature_coverage: ParserFeatureCoverage[]
  deferred_features_detected: string[]
  unsupported_features_detected: string[]
  // C. Motion Summary (programmed only — PROGRAMMED_MOTION_EQUALS_EXECUTED_MOTION=NO)
  total_feed_distance_mm: number
  total_rapid_distance_mm: number
  // D. Segments
  segments: NcMotionSegment[]
  // E. Equipment
  equipment: EquipmentSummary
  // F. Compatibility
  compatibility_status: string | null
  // G. Validation (reused — NC_PROGRAM_VALIDATION_REUSED=YES)
  validation_summary: NCProgramValidationSummary
  // H. Operation mapping
  operation_association: string | null
  // I. Cycle Time (CYCLE_TIME_FOUNDATION_REUSED=YES)
  cycle_time_known_subtotal_sec: number | null
  cycle_time_status: string | null
  cycle_time_limitations: string[]
  // K. Canned Cycles
  canned_cycle_notes: CannedCycleNote[]
  // L. Findings
  findings: EngReviewFinding[]
  // M. Counts
  blocking_count: number
  warning_count: number
  advisory_count: number
  info_count: number
  insufficient_data_count: number
  unsupported_count: number
  // M. Limitations
  limitations: string[]
  // N. Overall Status
  review_status: EngReviewStatusValue
  // O. Traceability (NC_PROGRAM_TRACEABILITY_AND_AUDIT_01)
  // ENGINEERING_STATUS_EQUALS_TRACEABILITY_STATUS=NO
  traceability?: NCAnalysisTraceability | null
  // Safety flags — all always false
  nc_file_executed: false
  machine_behavior_simulated: false
  collision_check_performed: false
  machine_kinematics_simulated: false
  gouge_check_performed: false
  false_controller_compatibility_claim: false
  false_production_approval_claim: false
  false_safe_to_run_claim: false
  false_collision_free_claim: false
  arbitrary_numeric_engineering_score_implemented: false
  programmed_motion_equals_executed_motion: false
  programmed_feed_distance_equals_confirmed_cutting: false
  t_word_equals_confirmed_tool_identity: false
  partial_time_mislabeled_total: false
  bounded_canned_cycle_mislabeled_complete: false
  private_local_path_visible: false
  private_path_in_api_response: false
}

export interface NcAnalyzeResponse {
  feed_evidence: PathEvidence
  rapid_evidence: PathEvidence
  motion_result: NcMotionResult
  // Feed/spindle validation (NC_FEED_SPINDLE_PROGRAM_VALIDATION_01)
  // PATH_EVIDENCE_SHOULD_CARRY_VALIDATION_RESULTS=NO — separate model
  validation_summary: NCProgramValidationSummary
  // Engineering review (NC_PROGRAM_ENGINEERING_REVIEW_01)
  // VALIDATION_SUMMARY_REMAINS_SEPARATE=YES
  // API_BACKWARD_COMPATIBILITY_PRESERVED=YES — optional field
  engineering_review: NCProgramEngineeringReview | null
  // Immutable safety flags — always false
  nc_feed_move_equals_confirmed_cutting: false
  arc_chord_approximation_used: false
  nc_file_executed: false
  nc_feed_automatically_promoted_to_cutting_path: false
  nc_commanded_spindle_speed_equals_actual_rpm: false
  nc_commanded_feed_equals_actual_feed: false
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

export async function analyzeNcPath(
  req: NcAnalyzeRequest
): Promise<NcAnalyzeResponse> {
  return api<NcAnalyzeResponse>('/nc-path/analyze', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}
