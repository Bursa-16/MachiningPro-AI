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

export interface NcMotionResult {
  parser_profile: string
  parser_version: string
  analysis_status:
    | 'COMPLETE'
    | 'PARTIAL'
    | 'UNSUPPORTED_SEMANTICS'
    | 'INVALID_PROGRAM'
    | 'INSUFFICIENT_DATA'
  feed_distance_mm: number
  rapid_distance_mm: number
  block_count_total: number
  supported_motion_count: number
  unsupported_construct_count: number
  unknown_start_count: number
  tool_change_count: number
  units_declared: string | null
  nc_commanded_feed_mm_min: number | null
  unsupported_features: string[]
  limitations: string[]
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
