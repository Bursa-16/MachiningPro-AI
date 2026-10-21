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
  // Safety flags — always false
  nc_feed_move_equals_confirmed_cutting: false
  arc_chord_approximation_used: false
}

export interface NcAnalyzeResponse {
  feed_evidence: PathEvidence
  rapid_evidence: PathEvidence
  motion_result: NcMotionResult
  // Immutable safety flags — always false
  nc_feed_move_equals_confirmed_cutting: false
  arc_chord_approximation_used: false
  nc_file_executed: false
  nc_feed_automatically_promoted_to_cutting_path: false
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
